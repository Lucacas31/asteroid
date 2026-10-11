"""Réglages globaux et emplacement des données de l'utilisateur.

Installation classique : ~/.config/asteroid/. Dossier portable : le lanceur définit
ASTEROID_HOME et tout vit à côté de l'app (config/, materiaux/, langues/), à la vue
de l'utilisateur.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import Field

from .model import Persisted

DEFAULT_IMAGE = "simvia/code_aster:stable"

DEFAULT_RUN_COMMAND = (
    "docker run --rm --name asteroid_{run_id} "
    "--user $(id -u):$(id -g) "
    "-v {run_dir}:/work -w /work "
    "{image} "
    'bash -c "source /opt/activate.sh && run_aster {export}"'
)
DEFAULT_CATALOG_COMMAND = (
    "docker run --rm --user $(id -u):$(id -g) "
    "-v {out_dir}:/out -v {script}:/export_catalog.py:ro "
    "{image} "
    'bash -c "source /opt/activate.sh >/dev/null 2>&1 && python3 /export_catalog.py /out/catalog.json"'
)
DEFAULT_STOP_COMMAND = "docker kill asteroid_{run_id}"
# {script} : script généré par l'app qui charge le plugin MEDReader (non chargé
# par défaut dans les binaires officiels) puis ouvre les .rmed du run.
DEFAULT_PARAVIEW_COMMAND = "paraview --script={script}"

MAX_RECENTS = 10


def _default_language() -> str:
    lang = os.environ.get("LANGUAGE") or os.environ.get("LC_ALL") or os.environ.get("LANG") or ""
    return "fr" if lang.startswith("fr") or not lang or lang in ("C", "C.UTF-8", "POSIX") else "en"


def home_dir() -> Path | None:
    """Dossier portable de l'app (variable ASTEROID_HOME du lanceur), sinon None."""
    base = os.environ.get("ASTEROID_HOME")
    return Path(base) if base else None


def config_dir() -> Path:
    base = os.environ.get("ASTEROID_CONFIG_DIR")
    if base:
        return Path(base)
    if home := home_dir():
        return home / "config"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    return Path(xdg or Path.home() / ".config") / "asteroid"


def user_dir(name: str) -> Path:
    """Dossier de données ouvert à l'utilisateur (materiaux, langues)."""
    home = home_dir()
    return (home if home else config_dir()) / name


def N_(text: str) -> str:
    """Phrase traduite à l'affichage (i18n importe ce module : pas d'import en retour)."""
    return text


# Profil « illimité » : run_aster impose 86 400 s sans P time_limit, on écrit donc 100 jours.
UNLIMITED_TIME = 8_640_000


class RunProfile(Persisted):
    """Limites d'un run, choisies au lancement (P time_limit, P memory_limit du .export)."""

    name: str
    time_limit: int | None = 300  # s ; None : illimité
    memory_limit: int = 2048  # Mo


def default_profiles() -> list[RunProfile]:
    return [
        # Noms traduits à l'affichage ; un nom choisi par l'utilisateur s'affiche tel quel.
        RunProfile(name=N_("Court"), time_limit=300, memory_limit=2048),
        RunProfile(name=N_("Long"), time_limit=3600, memory_limit=8192),
        RunProfile(name=N_("Illimité"), time_limit=None, memory_limit=8192),
    ]


class Settings(Persisted):
    docker_image: str = DEFAULT_IMAGE  # variable {image} des commandes
    run_command: str = DEFAULT_RUN_COMMAND
    stop_command: str = DEFAULT_STOP_COMMAND
    paraview_command: str = DEFAULT_PARAVIEW_COMMAND
    catalog_command: str = DEFAULT_CATALOG_COMMAND
    aster_version: str = "17.4.0"
    language: str = Field(default_factory=_default_language)
    # Faux tant que l'utilisateur n'a pas validé l'écran de premier lancement.
    configured: bool = False
    recent_projects: list[str] = Field(default_factory=list)
    run_profiles: list[RunProfile] = Field(default_factory=default_profiles)
    # Captures des résultats par pvbatch ({script}) ; vide : pas de captures.
    capture_command: str = ""


def run_limits(settings: Settings, profile: str | None, time_limit: int | None, memory_limit: int | None) -> dict:
    """Limites du run, par ordre de priorité : le profil choisi au lancement ; les limites du
    projet si elles sont définies (profil None, affiché « Projet ») ; le premier profil."""
    chosen = next((p for p in settings.run_profiles if p.name == profile), None)
    first = settings.run_profiles[0] if settings.run_profiles else None
    if chosen is None and (time_limit is not None or memory_limit is not None):
        base = _limits(first) if first else (300, 2048)
        return {"profile": None, "time_limit": time_limit or base[0], "memory_limit": memory_limit or base[1]}
    chosen = chosen or first
    if chosen is None:
        return {"profile": None, "time_limit": 300, "memory_limit": 2048}
    time, memory = _limits(chosen)
    return {"profile": chosen.name, "time_limit": time, "memory_limit": memory}


def _limits(p: RunProfile) -> tuple[int, int]:
    return (UNLIMITED_TIME if p.time_limit is None else p.time_limit), p.memory_limit


def settings_path() -> Path:
    return config_dir() / "settings.json"


def load_settings() -> Settings:
    path = settings_path()
    if path.exists():
        try:
            data = json.loads(path.read_text())
            # Réglages antérieurs à l'écran de premier lancement : déjà choisis, en français.
            data.setdefault("configured", True)
            data.setdefault("language", "fr")
            return Settings.model_validate(data)
        except ValueError:
            pass
    return Settings()


def save_settings(settings: Settings) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings.model_dump(), indent=2, ensure_ascii=False))


def add_recent(settings: Settings, project_dir: str) -> None:
    recents = [p for p in settings.recent_projects if p != project_dir]
    settings.recent_projects = [project_dir, *recents][:MAX_RECENTS]
    save_settings(settings)
