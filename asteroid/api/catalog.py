"""Routes du catalogue : liste des commandes, définition d'une commande, mise à jour."""

from __future__ import annotations

import asyncio
import json
import shlex
import tempfile
from pathlib import Path

from fastapi import APIRouter, HTTPException

from ..core.catalog import load_catalog, reload_catalog
from ..core.forms import SCHEMAS
from ..core.i18n import t
from ..core.runner import substitute
from ..core.settings import config_dir, save_settings
from ..state import state

router = APIRouter(prefix="/api/catalog")

SCRIPT = Path(__file__).resolve().parent.parent / "tools" / "export_catalog.py"


def _catalog():
    cat = load_catalog()
    if cat is None:
        raise HTTPException(404, t("Aucun catalogue disponible"))
    return cat


@router.get("")
def summary() -> dict:
    cat = _catalog()
    commands = [c | {"form": c["name"] in SCHEMAS} for c in cat.summary()]
    return {"version": cat.version, "source": cat.source, "commands": commands}


@router.get("/command/{name}")
def command(name: str) -> dict:
    cmd = _catalog().command(name)
    if cmd is None:
        raise HTTPException(404, t("{name} absent du catalogue", name=name))
    return cmd


@router.post("/update")
async def update() -> dict:
    """Exporte le catalogue depuis l'image Docker et l'installe dans ~/.config/asteroid."""
    with tempfile.TemporaryDirectory(prefix="asteroid-cata-") as tmp:
        command = substitute(
            state.settings.catalog_command,
            {
                "out_dir": shlex.quote(tmp),
                "script": shlex.quote(str(SCRIPT)),
                "image": state.settings.docker_image,
            },
        )
        proc = await asyncio.create_subprocess_shell(
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, executable="/bin/bash"
        )
        out, _ = await proc.communicate()
        result = Path(tmp) / "catalog.json"
        if proc.returncode != 0 or not result.exists():
            raise HTTPException(500, t("Échec de l'export du catalogue :") + "\n" + out.decode(errors="replace")[-2000:])
        version = json.loads(result.read_text()).get("version", "inconnue")
        target = config_dir() / f"catalog_{version}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result.read_text())
    cat = reload_catalog()
    state.settings.aster_version = version
    save_settings(state.settings)
    return {"version": version, "commands": len(cat.commands) if cat else 0, "path": str(target)}
