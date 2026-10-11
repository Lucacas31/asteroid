"""Lancement et suivi des runs Code_Aster."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import AsyncIterator

from . import comm as commgen
from .i18n import t
from .message import parse_message, status_from
from .model import Project
from .settings import Settings

RUN_INFO = "run.json"
RUN_LOG = "run.log"
STOP_GRACE = 5.0


def substitute(template: str, variables: dict[str, str]) -> str:
    """Remplace uniquement les variables connues, pour laisser intacts ${VAR} ou $(cmd)."""
    for key, value in variables.items():
        template = template.replace("{" + key + "}", value)
    return template


@dataclass
class Run:
    id: str
    dir: Path
    command: str
    blocks: list[commgen.BlockInfo]
    stop_command: str = ""
    started: float = field(default_factory=time.time)
    lines: list[str] = field(default_factory=list)
    proc: asyncio.subprocess.Process | None = None
    finished: bool = False
    stopped: bool = False
    info: dict = field(default_factory=dict)
    cond: asyncio.Condition = field(default_factory=asyncio.Condition)


class RunManager:
    def __init__(self) -> None:
        self.active: dict[str, Run] = {}

    # ------------------------------------------------------------------ lancement

    async def start(self, project_dir: Path, project: Project, settings: Settings) -> Run:
        result = commgen.generate(project)
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
        run = Run(
            run_id,
            run_dir,
            command,
            result.blocks,
            stop_command=substitute(settings.stop_command, variables),
        )
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
            "warnings": result.warnings,
        }
        self._write_info(run)
        self.active[run_id] = run

        run.proc = await asyncio.create_subprocess_shell(
            command,
            cwd=run_dir,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
            executable="/bin/bash",
            limit=1 << 20,
        )
        asyncio.create_task(self._pump(run))
        return run

    async def _pump(self, run: Run) -> None:
        assert run.proc and run.proc.stdout
        with open(run.dir / RUN_LOG, "w", encoding="utf-8") as log:
            await self._append(run, log, f"$ {run.command}")
            while True:
                try:
                    raw = await run.proc.stdout.readline()
                except ValueError:  # ligne plus longue que la limite
                    raw = await run.proc.stdout.read(1 << 20)
                if not raw:
                    break
                await self._append(run, log, raw.decode("utf-8", "replace").rstrip("\n"))
            returncode = await run.proc.wait()
        await self._finish(run, returncode)

    async def _append(self, run: Run, log, line: str) -> None:
        log.write(line + "\n")
        log.flush()
        async with run.cond:
            run.lines.append(line)
            run.cond.notify_all()

    async def _finish(self, run: Run, returncode: int) -> None:
        message_file = run.dir / commgen.MESSAGE_NAME
        diagnostic, messages = None, []
        if message_file.exists():
            report = parse_message(message_file.read_text(errors="replace"))
            report.align([(b.start_line, b.command, b.concept) for b in run.blocks if b.command])
            diagnostic = report.diagnostic
            for msg in report.messages:
                item = msg.to_dict()
                item["block_id"] = commgen.block_for_line(run.blocks, msg.comm_line)
                messages.append(item)
        status = "stopped" if run.stopped else status_from(diagnostic, returncode)
        ended = time.time()
        run.info.update(
            status=status,
            ended=datetime.fromtimestamp(ended).isoformat(timespec="seconds"),
            duration=round(ended - run.started, 1),
            returncode=returncode,
            diagnostic=diagnostic,
            messages=messages,
        )
        self._write_info(run)
        async with run.cond:
            run.finished = True
            run.cond.notify_all()

    def _write_info(self, run: Run) -> None:
        (run.dir / RUN_INFO).write_text(json.dumps(run.info, indent=2, ensure_ascii=False))

    # ------------------------------------------------------------------ arrêt

    async def stop(self, run_id: str) -> bool:
        run = self.active.get(run_id)
        if not run or run.finished or not run.proc:
            return False
        run.stopped = True
        if run.stop_command:
            proc = await asyncio.create_subprocess_shell(
                run.stop_command, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
            )
            await proc.wait()
        try:
            await asyncio.wait_for(run.proc.wait(), STOP_GRACE)
        except asyncio.TimeoutError:
            try:
                os.killpg(run.proc.pid, signal.SIGTERM)
            except ProcessLookupError:
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
            return run.info
        path = runs_root / run_id / RUN_INFO
        if not path.exists():
            return None
        info = json.loads(path.read_text())
        if info.get("status") == "running":
            info["status"] = "interrupted"  # l'app a été fermée pendant le run
        return info

    def history(self, runs_root: Path) -> list[dict]:
        if not runs_root.is_dir():
            return []
        items = []
        for d in sorted(runs_root.iterdir(), reverse=True):
            if d.is_dir() and (d / RUN_INFO).exists():
                info = self.info(d.name, runs_root)
                if info:
                    items.append({k: info.get(k) for k in ("id", "status", "started", "duration")})
        return items


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
