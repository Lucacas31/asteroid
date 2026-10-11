"""Sélection de fichiers et dossiers côté hôte.

Un navigateur ne donne jamais le chemin absolu d'un fichier choisi. Le backend
ouvre donc le sélecteur natif (zenity). Sans zenity, le frontend bascule sur
un petit explorateur qui s'appuie sur /api/fs/list.
"""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.i18n import t

router = APIRouter(prefix="/api/fs")


class PickBody(BaseModel):
    mode: Literal["file", "dir"] = "file"
    title: str = "Choisir"
    filters: list[str] = []  # ex. ["Maillage MED | *.med *.mmed"]
    start: str | None = None


@router.post("/pick")
async def pick(body: PickBody) -> dict:
    zenity = shutil.which("zenity")
    if zenity is None:
        return {"path": None, "fallback": True}
    args = [zenity, "--file-selection", f"--title={body.title}"]
    if body.mode == "dir":
        args.append("--directory")
    for f in body.filters:
        args.append(f"--file-filter={f}")
    if body.filters:
        all_files = t("Tous les fichiers")
        args.append(f"--file-filter={all_files} | *")
    if body.start:
        start = Path(body.start).expanduser()
        args.append(f"--filename={start}/" if start.is_dir() else f"--filename={start}")
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL
    )
    out, _ = await proc.communicate()
    path = out.decode().strip()
    return {"path": path if proc.returncode == 0 and path else None, "fallback": False}


@router.get("/list")
def list_dir(path: str = "~") -> dict:
    directory = Path(path).expanduser().resolve()
    if not directory.is_dir():
        raise HTTPException(404, t("Dossier introuvable : {path}", path=directory))
    entries = []
    for child in sorted(directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if child.name.startswith("."):
            continue
        entries.append({"name": child.name, "dir": child.is_dir()})
    return {"path": str(directory), "parent": str(directory.parent), "entries": entries}
