"""Routes des runs : lancement, log en direct (SSE), arrêt, historique, gestion des dossiers, ParaView."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from ..core import runner
from ..core.i18n import t
from ..core.runner import open_paraview
from ..state import state

router = APIRouter(prefix="/api/runs")

TEXT_LIMIT = 2_000_000  # au-delà, un fichier du run ne s'affiche pas dans l'app


class StartBody(BaseModel):
    profile: str | None = None  # profil des réglages globaux ; None : valeurs du projet


class NoteBody(BaseModel):
    note: str


def _root() -> Path:
    """Dossier des runs, après reprise des runs restés en cours (app relancée)."""
    root = state.runs_root()
    state.runs.recover(root)
    return root


def _dir(run_id: str, idle: bool = False) -> Path:
    try:
        path = runner.run_path(_root(), run_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    if not path.is_dir():
        raise HTTPException(404, t("Run inconnu"))
    if idle and run_id in state.runs.active and not state.runs.active[run_id].finished:
        raise HTTPException(409, t("Run en cours : impossible pour l'instant"))
    return path


@router.get("")
async def history() -> list[dict]:
    if state.project_dir is None:
        return []
    return state.runs.history(_root())


@router.post("")
async def start(body: StartBody | None = None) -> dict:
    project_dir = state.require_dir()
    if state.project.mesh and not (project_dir / state.project.mesh).is_file():
        raise HTTPException(400, t("Maillage introuvable : {path}", path=state.project.mesh))
    for extra in state.project.files:
        if extra.mode == "D" and not (project_dir / extra.path).is_file():
            raise HTTPException(400, t("Fichier rattaché à l'unité {unit} introuvable : {path}", unit=extra.unit, path=extra.path))
    if body is not None:
        state.project.run_profile = body.profile
    state.save()
    run = await state.runs.start(project_dir, state.project, state.settings)
    return runner.public_info(run.info)


@router.get("/compare")
async def compare(a: str, b: str) -> dict:
    _dir(a), _dir(b)
    return {"diff": runner.compare_comm(_root(), a, b)}


@router.get("/{run_id}")
async def info(run_id: str) -> dict:
    _dir(run_id)
    return state.runs.info(run_id, _root()) or {}


@router.patch("/{run_id}")
async def set_note(run_id: str, body: NoteBody) -> dict:
    path = _dir(run_id)
    active = state.runs.active.get(run_id)
    if active is not None:
        active.info["note"] = body.note  # le run suivi réécrit run.json à la fin
    runner.set_note(path, body.note)
    return {"note": body.note}


@router.delete("/{run_id}")
async def delete(run_id: str) -> dict:
    path = _dir(run_id, idle=True)
    shutil.rmtree(path)
    state.runs.active.pop(run_id, None)
    return {"deleted": run_id}


@router.post("/{run_id}/lighten")
async def lighten(run_id: str) -> dict:
    return {"freed": runner.lighten(_dir(run_id, idle=True))}


@router.get("/{run_id}/files")
async def files(run_id: str) -> list[dict]:
    return runner.run_files(_dir(run_id))


@router.get("/{run_id}/files/{name}", response_class=PlainTextResponse)
async def file_text(run_id: str, name: str) -> str:
    path = _dir(run_id) / name
    if "/" in name or not path.is_file():
        raise HTTPException(404, t("Fichier introuvable : {path}", path=name))
    if path.stat().st_size > TEXT_LIMIT:
        raise HTTPException(413, t("Fichier trop gros pour être affiché : ouvrir le dossier du run"))
    return path.read_text(errors="replace")


@router.post("/{run_id}/open_dir")
async def open_dir(run_id: str) -> dict:
    path = _dir(run_id)
    try:
        subprocess.Popen(["xdg-open", str(path)], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        raise HTTPException(500, t("xdg-open introuvable : dossier {path}", path=path)) from None
    return {"path": str(path)}


@router.get("/{run_id}/log")
async def log(run_id: str) -> StreamingResponse:
    _dir(run_id)
    runs_root = _root()

    async def events():
        async for line in state.runs.follow(run_id, runs_root):
            yield f"data: {json.dumps(line)}\n\n"
        final = state.runs.info(run_id, runs_root) or {}
        yield f"event: end\ndata: {json.dumps(final)}\n\n"

    return StreamingResponse(
        events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


@router.post("/{run_id}/stop")
async def stop(run_id: str) -> dict:
    return {"stopped": await state.runs.stop(run_id)}


@router.post("/{run_id}/paraview")
async def paraview(run_id: str) -> dict:
    try:
        return {"command": open_paraview(_dir(run_id), state.settings)}
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from None
