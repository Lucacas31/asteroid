"""Routes des runs : lancement, log en direct (SSE), arrêt, historique, ParaView."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..core.i18n import t
from ..core.runner import open_paraview
from ..state import state

router = APIRouter(prefix="/api/runs")


@router.get("")
def history() -> list[dict]:
    if state.project_dir is None:
        return []
    return state.runs.history(state.runs_root())


@router.post("")
async def start() -> dict:
    project_dir = state.require_dir()
    if state.project.mesh and not (project_dir / state.project.mesh).is_file():
        raise HTTPException(400, t("Maillage introuvable : {path}", path=state.project.mesh))
    for extra in state.project.files:
        if extra.mode == "D" and not (project_dir / extra.path).is_file():
            raise HTTPException(400, t("Fichier rattaché à l'unité {unit} introuvable : {path}", unit=extra.unit, path=extra.path))
    state.save()
    run = await state.runs.start(project_dir, state.project, state.settings)
    return run.info


@router.get("/{run_id}")
def info(run_id: str) -> dict:
    data = state.runs.info(run_id, state.runs_root())
    if data is None:
        raise HTTPException(404, t("Run inconnu"))
    return data


@router.get("/{run_id}/log")
async def log(run_id: str) -> StreamingResponse:
    runs_root = state.runs_root()

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
def paraview(run_id: str) -> dict:
    run_dir = state.runs_root() / run_id
    if not run_dir.is_dir():
        raise HTTPException(404, t("Run inconnu"))
    try:
        return {"command": open_paraview(run_dir, state.settings)}
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from None
