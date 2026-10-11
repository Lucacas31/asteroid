"""Routes de la bibliothèque de matériaux et de leur utilisation dans le projet."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import materials as mat
from ..core.i18n import t
from ..state import state

router = APIRouter(prefix="/api/materials")


def _find(materials: list[mat.Material], material_id: str) -> mat.Material:
    for m in materials:
        if m.id == material_id:
            return m
    raise HTTPException(404, t("Matériau inconnu : {id}", id=material_id))


@router.get("")
def library() -> dict:
    errors: list[str] = []
    items = mat.load_library(errors)
    return {"materials": items, "errors": errors, "dir": str(mat.library_dir())}


@router.post("")
def create(material: mat.Material) -> mat.Material:
    material.id = mat.unique_id(material.name, {m.id for m in mat.load_library()})
    return mat.save_material(material)


class ImportBody(BaseModel):
    path: str


@router.post("/import")
def import_materials(body: ImportBody) -> list[mat.Material]:
    path = Path(body.path).expanduser()
    if not path.is_file():
        raise HTTPException(404, t("Fichier introuvable : {path}", path=path))
    try:
        return mat.import_file(path)
    except ValueError as exc:
        raise HTTPException(400, f"{path.name} : {str(exc).splitlines()[0]}") from exc


@router.post("/open-folder")
def open_folder() -> dict:
    """Ouvre le dossier de la bibliothèque dans le gestionnaire de fichiers."""
    root = mat.ensure_library()
    opener = shutil.which("xdg-open")
    if opener is None:
        raise HTTPException(400, t("xdg-open introuvable. Dossier : {path}", path=root))
    subprocess.Popen([opener, str(root)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"dir": str(root)}


@router.put("/{material_id:path}")
def update(material_id: str, material: mat.Material) -> mat.Material:
    _find(mat.load_library(), material_id)
    material.id = material_id
    return mat.save_material(material)


@router.post("/{material_id:path}/duplicate")
def duplicate(material_id: str) -> mat.Material:
    items = mat.load_library()
    copy = _find(items, material_id).model_copy(deep=True)
    copy.name = t("{name} (copie)", name=copy.name)
    copy.id = mat.unique_id(copy.name, {m.id for m in items})
    return mat.save_material(copy)


@router.delete("/{material_id:path}")
def delete(material_id: str) -> dict:
    _find(mat.load_library(), material_id)
    mat.delete_material(material_id)
    return {"deleted": material_id}


class UseBody(BaseModel):
    units: str | None = None  # unités affichées par l'interface (le projet n'est peut-être pas encore enregistré)


@router.post("/{material_id:path}/use")
def use(material_id: str, body: UseBody | None = None) -> dict:
    """Convertit le matériau dans les unités du projet et en copie une version figée dans le projet."""
    material = _find(mat.load_library(), material_id)
    units = (body.units if body else None) or state.project.units
    if units not in mat.FACTORS:
        raise HTTPException(400, t("Système d'unités inconnu : {units}", units=units))
    params = mat.defi_materiau_params(material, units)
    entry = mat.copy_to_project(state.project_dir, material, units) if state.project_dir else None
    return {"params": params, "units": units, "entry": entry, "material": material}


@router.get("/project")
def project_materials() -> dict:
    if state.project_dir is None:
        return {}
    return mat.load_project_materials(state.project_dir)
