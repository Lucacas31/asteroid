"""Modèle du projet : un dossier contenant asteroid.json, le maillage et les runs."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROJECT_FILE = "asteroid.json"
FORMAT_VERSION = 1

UnitSystem = Literal["mm-N-MPa", "m-N-Pa"]


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Persisted(BaseModel):
    """Modèle enregistré sur disque. Les champs inconnus (écrits par une version plus
    récente d'Asteroid) sont conservés et réécrits tels quels, jamais supprimés."""

    model_config = ConfigDict(extra="allow")


DEFAULT_TIME = 300  # s, si ni profil ni limites du projet
DEFAULT_MEMORY = 2048  # Mo
DEFAULT_NAME = "nouveau projet"  # traduit à la création ; remplacé par le nom du dossier


class Block(Persisted):
    """Une commande Code_Aster (`concept = COMMANDE(...)`).

    En mode `form`, la source de vérité est `params` (arbre de valeurs, voir
    pyvalue.py). En mode `text`, c'est `text`, qui contient l'instruction complète.
    """

    id: str = Field(default_factory=new_id)
    command: str = ""
    concept: str | None = None
    mode: Literal["form", "text"] = "text"
    params: dict[str, Any] = Field(default_factory=dict)
    text: str = ""
    fallback_reason: str | None = None
    meta: dict[str, Any] = Field(default_factory=dict)  # ex. {"material": "acier_s235"}


class ExtraFile(Persisted):
    """Fichier rattaché à une unité logique (ex. LIRE_FONCTION(UNITE=40))."""

    unit: int
    path: str  # D : chemin du fichier (relatif au projet ou absolu) ; R : nom écrit dans le run
    mode: Literal["D", "R"] = "D"
    kind: str = "libr"  # type de fichier pour le .export


class Project(Persisted):
    version: int = FORMAT_VERSION
    name: str = DEFAULT_NAME
    mesh: str | None = None  # chemin relatif au dossier du projet
    units: UnitSystem = "mm-N-MPa"
    runs_dir: str = "runs"
    # Limites propres au projet : vides par défaut (le profil de run choisi s'applique) ;
    # définies, elles deviennent le choix par défaut au lancement (profil « Projet »).
    time_limit: int | None = None
    memory_limit: int | None = None
    run_profile: str | None = None  # profil des réglages globaux choisi au dernier lancement

    @model_validator(mode="before")
    @classmethod
    def _old_defaults(cls, data):
        # Projets de la 0.1 : 300 s et 2048 Mo y étaient écrits d'office, pas choisis.
        if isinstance(data, dict) and data.get("time_limit") == 300 and data.get("memory_limit") == 2048:
            data = {**data, "time_limit": None, "memory_limit": None}
        return data
    files: list[ExtraFile] = Field(default_factory=list)
    blocks: list[Block] = Field(default_factory=list)


def load_project(project_dir: Path) -> Project:
    return Project.model_validate_json((project_dir / PROJECT_FILE).read_text())


def save_project(project_dir: Path, project: Project) -> None:
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / PROJECT_FILE
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(project.model_dump(), indent=2, ensure_ascii=False))
    tmp.replace(path)
