"""Lancement et suivi des runs Code_Aster.

Un run est un script `run.sh` détaché du serveur : il écrit lui-même sa sortie dans
`run.log` et son code de retour dans `run.exit`. Fermer l'app n'arrête donc pas le
calcul ; à la réouverture, un run encore en cours est repris (suivi du log), un run
fini entre-temps reçoit son vrai statut (lecture du fichier `message`).
"""

from __future__ import annotations

import asyncio
import difflib
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from . import captures, results
from . import comm as commgen
from .i18n import t
from .materials import load_project_materials
from .message import parse_message, status_from
from .model import Project
from .settings import Settings, run_limits

RUN_INFO = "run.json"
RUN_LOG = "run.log"
RUN_SCRIPT = "run.sh"
RUN_EXIT = "run.exit"
STOP_GRACE = 5.0
POLL = 0.2
RUN_ID = re.compile(r"[\w][\w.-]*")

SCRIPT = """\
#!/bin/bash
# Généré par Asteroid : commande de lancement des réglages, exécutée depuis ce dossier.
# Sortie dans {log}, code de retour dans {exit}. Relançable à la main : bash {script}
cd "$(dirname "$0")"
bash -c {command} >> {log} 2>&1 < /dev/null
echo $? > {exit}
"""


def substitute(template: str, variables: dict[str, str]) -> str:
    """Remplace uniquement les variables connues, pour laisser intacts ${VAR} ou $(cmd)."""
    for key, value in variables.items():
        template = template.replace("{" + key + "}", value)
    return template


def project_for_run(project: Project, settings: Settings) -> Project:
    """Projet avec les limites du profil choisi (P time_limit, P memory_limit du .export)."""
    limits = run_limits(settings, project.run_profile, project.time_limit, project.memory_limit)
    return project.model_copy(update={"time_limit": limits["time_limit"], "memory_limit": limits["memory_limit"]})


def material_snapshot(project_dir: Path, project: Project, infos: list[commgen.BlockInfo]) -> dict:
    """Matériaux de la bibliothèque utilisés par les DEFI_MATERIAU, par concept : nom, modèle,
    résistances dans les unités de leur copie (pour les marges du résumé)."""
    concepts = {b.id: b.concept for b in infos}
    copies = load_project_materials(project_dir)
    out = {}
    for block in project.blocks:
        entry = copies.get(block.meta.get("material") or "")
        concept = block.concept if block.mode == "form" else concepts.get(block.id)
        if entry is None or not concept:
            continue
        out[concept] = {
            "name": entry["material"]["name"],
            "model": entry["material"].get("model", "ELAS"),
            "units": entry["units"],
            "strengths": entry["converted"].get("strengths", []),
        }
    return out


def _alive(pid: int | None, run_dir: Path) -> bool:
    """Le processus du run tourne encore (et c'est bien lui : même dossier courant)."""
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:
        return Path(os.readlink(f"/proc/{pid}/cwd")) == run_dir.resolve()
    except OSError:
        return True


@dataclass
class Run:
    id: str
    dir: Path
    command: str
    blocks: list[commgen.BlockInfo]
    stop_command: str = ""
    started: float = field(default_factory=time.time)
    lines: list[str] = field(default_factory=list)
    proc: subprocess.Popen | None = None
    pid: int | None = None
    finished: bool = False
    stopped: bool = False
    info: dict = field(default_factory=dict)
    cond: asyncio.Condition = field(default_factory=asyncio.Condition)

    def alive(self) -> bool:
        if self.proc is not None:
            return self.proc.poll() is None
        return _alive(self.pid, self.dir)


class RunManager:
    def __init__(self) -> None:
        self.active: dict[str, Run] = {}
        self.capturing: set[str] = set()  # runs dont les captures pvbatch sont en cours

    # ------------------------------------------------------------------ lancement

    async def start(self, project_dir: Path, project: Project, settings: Settings) -> Run:
        limits = run_limits(settings, project.run_profile, project.time_limit, project.memory_limit)
        result = commgen.generate(project_for_run(project, settings))
        runs_root = project_dir / project.runs_dir
        run_id = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        run_dir = runs_root / run_id
        n = 2
        while run_dir.exists():
            run_dir = runs_root / f"{run_id}-{n}"
            n += 1
        run_id = run_dir.name
        run_dir.mkdir(parents=True)

        (run_dir / commgen.COMM_NAME).write_text(result.comm)
        (run_dir / commgen.EXPORT_NAME).write_text(result.export)
        if project.mesh and any(f.kind == "mmed" for f in result.files):
            shutil.copy2(project_dir / project.mesh, run_dir / commgen.MESH_NAME)
        for extra in project.files:
            if extra.mode == "D":
                shutil.copy2(project_dir / extra.path, run_dir / commgen.run_name(extra))

        variables = {
            "run_dir": shlex.quote(str(run_dir.resolve())),
            "export": commgen.EXPORT_NAME,
            "comm": commgen.COMM_NAME,
            "mesh": commgen.MESH_NAME,
            "run_id": run_id,
            "image": settings.docker_image,
        }
        command = substitute(settings.run_command, variables)
        run = Run(run_id, run_dir, command, result.blocks, stop_command=substitute(settings.stop_command, variables))
        run.info = {
            "id": run_id,
            "status": "running",
            "started": datetime.fromtimestamp(run.started).isoformat(timespec="seconds"),
            "ended": None,
            "duration": None,
            "returncode": None,
            "diagnostic": None,
            "messages": [],
            "command": command,
            "stop_command": run.stop_command,
            "capture_command": settings.capture_command,
            "warnings": result.warnings,
            "note": "",
            "units": project.units,
            "materials": material_snapshot(project_dir, project, result.blocks),
            **limits,
            # Pour rattacher les messages aux blocs si le run est repris après un redémarrage.
            "blocks": [asdict(b) | {"issues": []} for b in result.blocks],
        }
        (run_dir / RUN_LOG).write_text(f"$ {command}\n")
        (run_dir / RUN_SCRIPT).write_text(
            SCRIPT.format(command=shlex.quote(command), log=RUN_LOG, exit=RUN_EXIT, script=RUN_SCRIPT)
        )
        run.proc = subprocess.Popen(
            ["bash", RUN_SCRIPT],
            cwd=run_dir,
            start_new_session=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        run.pid = run.info["pid"] = run.proc.pid
        self._write_info(run)
        self.active[run_id] = run
        asyncio.create_task(self._watch(run))
        return run

    async def _watch(self, run: Run) -> None:
        """Suit run.log jusqu'à la fin du script (run.exit) ou la mort du processus."""
        log = run.dir / RUN_LOG
        pos, partial = 0, b""
        while True:
            done = (run.dir / RUN_EXIT).exists() or not run.alive()
            data = b""
            try:
                with open(log, "rb") as f:
                    f.seek(pos)
                    data = f.read()
            except OSError:
                pass
            pos += len(data)
            chunks = (partial + data).split(b"\n")
            partial = chunks.pop()
            if chunks:
                await self._append(run, [c.decode("utf-8", "replace") for c in chunks])
            if done and not data:
                break
            await asyncio.sleep(POLL)
        if partial:
            await self._append(run, [partial.decode("utf-8", "replace")])
        await self._finish(run, _read_exit(run.dir))

    async def _append(self, run: Run, lines: list[str]) -> None:
        async with run.cond:
            run.lines.extend(lines)
            run.cond.notify_all()

    async def _finish(self, run: Run, returncode: int | None) -> None:
        if run.proc is not None:
            run.proc.wait()  # récupère le processus (pas de zombie)
        diagnostic, messages = None, []
        message_file = run.dir / commgen.MESSAGE_NAME
        if message_file.exists():
            report = parse_message(message_file.read_text(errors="replace"))
            report.align([(b.start_line, b.command, b.concept) for b in run.blocks if b.command])
            diagnostic = report.diagnostic
            for msg in report.messages:
                item = msg.to_dict()
                item["block_id"] = commgen.block_for_line(run.blocks, msg.comm_line)
                messages.append(item)
        if run.stopped:
            status = "stopped"
        elif returncode is None and diagnostic is None:
            status = "interrupted"  # processus disparu sans code de retour ni diagnostic
        else:
            status = status_from(diagnostic, returncode)
        ended = (run.dir / RUN_EXIT).stat().st_mtime if (run.dir / RUN_EXIT).exists() else time.time()
        run.info.update(
            status=status,
            ended=datetime.fromtimestamp(ended).isoformat(timespec="seconds"),
            duration=round(ended - run.started, 1),
            returncode=returncode,
            diagnostic=diagnostic,
            messages=messages,
        )
        summary = None
        if status in ("ok", "alarm"):
            try:
                summary = await asyncio.to_thread(results.load_or_compute, run.dir, run.info)
                run.info["headline"] = summary.get("headline")
            except Exception as exc:  # noqa: BLE001 — un résumé impossible ne doit pas gâcher le run
                with open(run.dir / RUN_LOG, "a") as log:
                    log.write(f"[asteroid] résumé des résultats impossible : {exc}\n")
        self._write_info(run)
        if summary and run.info.get("capture_command"):
            asyncio.create_task(self.capture(run.dir, summary, run.info["capture_command"]))
        async with run.cond:
            run.finished = True
            run.cond.notify_all()

    async def capture(self, run_dir: Path, summary: dict, command: str) -> dict | None:
        """Captures pvbatch d'un run seul (cadrage et échelle propres au run)."""
        shared = captures.params_for([(run_dir, summary)])
        if shared is None:
            return None
        self.capturing.add(run_dir.name)
        try:
            return await captures.capture(run_dir, summary, shared, command)
        finally:
            self.capturing.discard(run_dir.name)

    def _write_info(self, run: Run) -> None:
        (run.dir / RUN_INFO).write_text(json.dumps(run.info, indent=2, ensure_ascii=False))

    # ------------------------------------------------------------------ reprise

    def recover(self, runs_root: Path) -> None:
        """Reprend les runs marqués « en cours » que ce serveur ne suit pas (app relancée)."""
        if not runs_root.is_dir():
            return
        for d in runs_root.iterdir():
            path = d / RUN_INFO
            if d.name in self.active or not path.is_file():
                continue
            try:
                info = json.loads(path.read_text())
            except ValueError:
                continue
            if info.get("status") != "running":
                continue
            started = datetime.fromisoformat(info["started"]).timestamp()
            blocks = [commgen.BlockInfo(**b) for b in info.get("blocks", [])]
            run = Run(d.name, d, info.get("command", ""), blocks, info.get("stop_command", ""), started,
                      pid=info.get("pid"), info=info)
            self.active[d.name] = run
            asyncio.get_running_loop().create_task(self._watch(run))

    # ------------------------------------------------------------------ arrêt

    async def stop(self, run_id: str) -> bool:
        run = self.active.get(run_id)
        if not run or run.finished:
            return False
        run.stopped = True
        if run.stop_command:
            proc = await asyncio.create_subprocess_shell(
                run.stop_command, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()
        end = time.time() + STOP_GRACE
        while run.alive() and time.time() < end:
            await asyncio.sleep(POLL)
        if run.alive() and run.pid:
            try:
                os.killpg(run.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass
        return True

    # ------------------------------------------------------------------ lecture

    async def follow(self, run_id: str, runs_root: Path) -> AsyncIterator[str]:
        run = self.active.get(run_id)
        if run is None:
            log = runs_root / run_id / RUN_LOG
            if log.exists():
                for line in log.read_text(errors="replace").splitlines():
                    yield line
            return
        i = 0
        while True:
            async with run.cond:
                await run.cond.wait_for(lambda: len(run.lines) > i or run.finished)
                new = run.lines[i:]
                finished = run.finished
            i += len(new)
            for line in new:
                yield line
            if finished and i >= len(run.lines):
                return

    def info(self, run_id: str, runs_root: Path) -> dict | None:
        run = self.active.get(run_id)
        if run is not None:
            return public_info(run.info)
        path = runs_root / run_id / RUN_INFO
        if not path.exists():
            return None
        return public_info(json.loads(path.read_text()))

    def history(self, runs_root: Path) -> list[dict]:
        if not runs_root.is_dir():
            return []
        items = []
        for d in sorted(runs_root.iterdir(), reverse=True):
            if d.is_dir() and (d / RUN_INFO).exists():
                info = self.info(d.name, runs_root)
                if info:
                    keys = ("id", "status", "started", "duration", "note", "profile", "time_limit", "memory_limit", "headline", "units")
                    items.append({k: info.get(k) for k in keys} | {"size": dir_size(d), "has_mesh": (d / commgen.MESH_NAME).exists()})
        return items


def public_info(info: dict) -> dict:
    """run.json sans les données internes (blocs, pid, matériaux, commande de captures)."""
    return {k: v for k, v in info.items() if k not in ("blocks", "pid", "materials", "capture_command")}


def _read_exit(run_dir: Path) -> int | None:
    try:
        return int((run_dir / RUN_EXIT).read_text().strip())
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------- dossiers de runs


def run_path(runs_root: Path, run_id: str) -> Path:
    """Dossier d'un run ; refuse tout identifiant qui sortirait du dossier des runs."""
    if not RUN_ID.fullmatch(run_id):
        raise ValueError(t("identifiant de run invalide : {id}", id=run_id))
    return runs_root / run_id


def dir_size(directory: Path) -> int:
    return sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())


def run_files(run_dir: Path) -> list[dict]:
    return [
        {"name": f.relative_to(run_dir).as_posix(), "size": f.stat().st_size}
        for f in sorted(run_dir.rglob("*"))
        if f.is_file()
    ]


def set_note(run_dir: Path, note: str) -> None:
    path = run_dir / RUN_INFO
    info = json.loads(path.read_text())
    info["note"] = note
    path.write_text(json.dumps(info, indent=2, ensure_ascii=False))


def lighten(run_dir: Path) -> int:
    """Retire la copie du maillage d'un run (résultats, .comm et message conservés). Octets libérés."""
    mesh = run_dir / commgen.MESH_NAME
    if not mesh.exists():
        return 0
    size = mesh.stat().st_size
    mesh.unlink()
    return size


def compare_comm(runs_root: Path, a: str, b: str) -> list[str]:
    """Différences entre les .comm de deux runs (diff unifié, sans en-tête)."""
    texts = [(run_path(runs_root, r) / commgen.COMM_NAME).read_text().splitlines() for r in (a, b)]
    return list(difflib.unified_diff(texts[0], texts[1], a, b, n=2, lineterm=""))[2:]



# ---------------------------------------------------------------------- post-traitement


def result_files(run_dir: Path) -> list[Path]:
    return sorted(run_dir.glob("*.rmed"))


PARAVIEW_SCRIPT = """\
from paraview.simple import *
try:
    LoadDistributedPlugin("MEDReader", remote=False, ns=globals())
except Exception as exc:
    print("MEDReader indisponible :", exc)
for path in {files!r}:
    Show(OpenDataFile(path))
ResetCamera()
Render()
"""


def open_paraview(run_dir: Path, settings: Settings) -> str:
    files = result_files(run_dir)
    if not files:
        raise FileNotFoundError(t("aucun fichier .rmed dans ce run"))
    script = run_dir / "paraview_open.py"
    script.write_text(PARAVIEW_SCRIPT.format(files=[str(f.resolve()) for f in files]))
    command = substitute(
        settings.paraview_command,
        {
            "rmed": shlex.quote(str(files[0].resolve())),
            "script": shlex.quote(str(script.resolve())),
            "run_dir": shlex.quote(str(run_dir.resolve())),
        },
    )
    subprocess.Popen(
        command,
        shell=True,
        cwd=run_dir,
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return command
