"""Modèle du projet : un dossier contenant asteroid.json, le maillage et les runs."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PROJECT_FILE = "asteroid.json"
FORMAT_VERSION = 1

UnitSystem = Literal["mm-N-MPa", "m-N-Pa"]


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Persisted(BaseModel):
    """Modèle enregistré sur disque. Les champs inconnus (écrits par une version plus
    récente d'Asteroid) sont conservés et réécrits tels quels, jamais supprimés."""

    model_config = ConfigDict(extra="allow")


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
    time_limit: int = 300
    memory_limit: int = 2048
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
