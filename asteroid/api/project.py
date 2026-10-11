"""Routes projet, blocs, aperçu du .comm et réglages."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import comm as commgen
from ..core import forms, i18n, pyvalue
from ..core.comm_import import split_comm
from ..core.i18n import t
from ..core.model import DEFAULT_NAME, Block, Project
from ..core.settings import Settings, save_settings
from ..state import state

router = APIRouter(prefix="/api")


class DirBody(BaseModel):
    dir: str | None = None


class PathBody(BaseModel):
    path: str


class ImportBody(BaseModel):
    text: str | None = None
    path: str | None = None


class TextBody(BaseModel):
    text: str


class NewBlockBody(BaseModel):
    command: str
    taken: list[str] = []


@router.get("/state")
def get_state() -> dict:
    return state.snapshot()


@router.post("/project/new")
def new_project(body: DirBody) -> dict:
    state.new(Path(body.dir).expanduser() if body.dir else None)
    return state.snapshot()


@router.post("/project/open")
def open_project(body: DirBody) -> dict:
    if not body.dir:
        raise HTTPException(400, t("Dossier manquant"))
    state.open(Path(body.dir).expanduser())
    return state.snapshot()


@router.put("/project")
def put_project(project: Project) -> dict:
    state.project = project
    state.save()
    return {"saved": state.project_dir is not None}


@router.post("/project/save_as")
def save_as(body: DirBody) -> dict:
    if not body.dir:
        raise HTTPException(400, t("Dossier manquant"))
    directory = Path(body.dir).expanduser()
    old_dir = state.project_dir
    if old_dir and state.project.mesh:
        mesh_abs = (old_dir / state.project.mesh).resolve()
        state.project.mesh = os.path.relpath(mesh_abs, directory)
    state.project_dir = directory
    if state.project.name in (DEFAULT_NAME, t(DEFAULT_NAME)):
        state.project.name = directory.name
    state.save()
    return state.snapshot()


@router.post("/project/mesh")
def set_mesh(body: PathBody) -> dict:
    mesh = Path(body.path).expanduser().resolve()
    if not mesh.is_file():
        raise HTTPException(404, t("Fichier introuvable : {path}", path=mesh))
    if state.project_dir is None:
        # Projet vierge : le dossier du maillage devient le dossier du projet.
        state.project_dir = mesh.parent
        if state.project.name in (DEFAULT_NAME, t(DEFAULT_NAME)):
            state.project.name = mesh.parent.name
    state.project.mesh = os.path.relpath(mesh, state.project_dir)
    state.save()
    return state.snapshot()


def _mesh_groups() -> dict[str, set[str]] | None:
    """Groupes du maillage courant, pour vérifier les noms de groupes."""
    from .mesh import current_mesh

    try:
        _, mesh = current_mesh()
    except HTTPException:
        return None
    groups: dict[str, set[str]] = {"GROUP_MA": set(), "GROUP_NO": set()}
    for g in mesh.groups:
        groups[g.entity].add(g.name)
    return groups


@router.post("/comm")
def preview(project: Project) -> dict:
    return commgen.generate(project, _mesh_groups()).to_dict()


@router.post("/comm/import")
def import_comm(body: ImportBody) -> dict:
    if body.path:
        path = Path(body.path).expanduser()
        if not path.is_file():
            raise HTTPException(404, t("Fichier introuvable : {path}", path=path))
        text = path.read_text(encoding="utf-8", errors="replace")
    else:
        text = body.text or ""
    try:
        res = split_comm(text)
    except pyvalue.ParseError as exc:
        raise HTTPException(422, str(exc)) from None
    return {
        "blocks": res.blocks,
        "warnings": res.warnings,
        "units": res.units,
        "unattached": res.unattached,
        "text": text,
    }


@router.post("/blocks/new")
def new_block(body: NewBlockBody) -> Block:
    return commgen.new_block(body.command.strip().upper(), set(body.taken))


@router.get("/forms")
def form_schemas() -> dict:
    return forms.public_schemas(translate=True)


@router.post("/blocks/to_form")
def to_form(body: TextBody) -> dict:
    """Texte → formulaire. Renvoie la raison si le texte ne tient pas dans le formulaire."""
    try:
        command, concept, params = forms.text_to_form(body.text)
    except forms.FormError as exc:
        return {"ok": False, "reason": str(exc)}
    return {"ok": True, "command": command, "concept": concept, "params": params}


@router.post("/blocks/to_text")
def to_text(block: Block) -> dict:
    return {"text": commgen.block_source(block.model_copy(update={"mode": "form"}))}


@router.get("/settings")
def get_settings() -> Settings:
    return state.settings


@router.put("/settings")
def put_settings(settings: Settings) -> Settings:
    settings.recent_projects = state.settings.recent_projects
    state.settings = settings
    i18n.set_language(settings.language)
    save_settings(settings)
    return settings


@router.get("/i18n")
def translations() -> dict:
    """Langue courante, langues disponibles et traductions pour l'interface."""
    code = i18n.current()
    return {"language": code, "languages": i18n.languages(), "messages": i18n.messages(code)}
