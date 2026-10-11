"""État de l'application : un seul projet ouvert à la fois (outil mono-utilisateur)."""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException

from .core.i18n import set_language, t
from .core.materials import library_dir
from .core.model import DEFAULT_NAME, Project, load_project, save_project
from .core.runner import RunManager
from .core.settings import Settings, add_recent, config_dir, load_settings, user_dir


class AppState:
    def __init__(self) -> None:
        self.settings: Settings = load_settings()
        set_language(self.settings.language)
        self.project: Project = Project()
        self.project_dir: Path | None = None
        self.runs = RunManager()

    def snapshot(self) -> dict:
        return {
            "project": self.project.model_dump(),
            "project_dir": str(self.project_dir) if self.project_dir else None,
            "settings": self.settings.model_dump(),
            "paths": {
                "config": str(config_dir()),
                "materials": str(library_dir()),
                "languages": str(user_dir("langues")),
            },
        }

    def require_dir(self) -> Path:
        if self.project_dir is None:
            raise HTTPException(400, t("Le projet n'a pas encore de dossier."))
        return self.project_dir

    def runs_root(self) -> Path:
        return self.require_dir() / self.project.runs_dir

    def new(self, directory: Path | None) -> None:
        self.project = Project(name=directory.name if directory else t(DEFAULT_NAME))
        self.project_dir = directory
        if directory is not None:
            self.save()

    def open(self, directory: Path) -> None:
        if directory.is_file():
            directory = directory.parent
        try:
            self.project = load_project(directory)
        except FileNotFoundError:
            raise HTTPException(404, t("Aucun asteroid.json dans {path}", path=directory)) from None
        except ValueError as exc:
            raise HTTPException(400, t("asteroid.json illisible : {error}", error=exc)) from None
        self.project_dir = directory
        add_recent(self.settings, str(directory))

    def save(self) -> None:
        if self.project_dir is not None:
            save_project(self.project_dir, self.project)
            add_recent(self.settings, str(self.project_dir))


state = AppState()
