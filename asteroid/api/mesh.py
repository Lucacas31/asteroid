"""Routes du maillage : résumé JSON et buffers binaires pour le viewer."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from ..core.i18n import t
from ..core.med import Mesh, MedError, read_med
from ..state import state

router = APIRouter(prefix="/api/mesh")

_cache: dict[str, tuple[float, Mesh]] = {}


def current_mesh() -> tuple[Path, Mesh]:
    if state.project_dir is None or not state.project.mesh:
        raise HTTPException(404, t("Aucun maillage sélectionné"))
    path = (state.project_dir / state.project.mesh).resolve()
    if not path.is_file():
        raise HTTPException(404, t("Maillage introuvable : {path}", path=path))
    mtime = path.stat().st_mtime
    cached = _cache.get(str(path))
    if cached and cached[0] == mtime:
        return path, cached[1]
    try:
        mesh = read_med(path)
    except MedError as exc:
        raise HTTPException(422, str(exc)) from None
    _cache.clear()  # un seul maillage à la fois
    _cache[str(path)] = (mtime, mesh)
    return path, mesh


def binary(array: np.ndarray, **headers: str) -> Response:
    return Response(array.tobytes(), media_type="application/octet-stream", headers=headers)


@router.get("")
def summary() -> dict:
    path, mesh = current_mesh()
    return mesh.summary() | {"path": str(path), "version": f"{path}:{path.stat().st_mtime}"}


@router.get("/positions")
def positions() -> Response:
    _, mesh = current_mesh()
    return binary(mesh.coords.astype(np.float32))


@router.get("/skin")
def skin() -> Response:
    _, mesh = current_mesh()
    return binary(mesh.skin()[0])


@router.get("/edges")
def edges() -> Response:
    _, mesh = current_mesh()
    return binary(mesh.skin()[1])


@router.get("/group")
def group(entity: str, name: str) -> Response:
    _, mesh = current_mesh()
    try:
        g = mesh.group(entity, name)
    except KeyError as exc:
        raise HTTPException(404, exc.args[0]) from None
    primitive, indices = mesh.group_geometry(g)
    return binary(indices.astype(np.uint32), **{"X-Primitive": primitive})
