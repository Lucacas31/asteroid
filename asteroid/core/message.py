"""Lecture du fichier `message` de Code_Aster : diagnostic et messages <F>/<E>/<A>."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field

BOX_TOP = re.compile(r"^\s*[╔┌!]\s*[═─-]{10,}")
BOX_LINE = re.compile(r"^\s*[║│!]\s?(.*?)\s*[║│!]\s*$")
BOX_BOTTOM = re.compile(r"^\s*[╚└!]\s*[═─-]{10,}")
HEADER = re.compile(r"^<(A|F|E|S|EXCEPTION|I)>\s*(?:<([A-Z0-9_]+)>)?\s*(.*)$")
COMMAND = re.compile(r"^# Commande #(\d+) de \S+, ligne (\d+)")
DIAGNOSTIC = re.compile(r"DIAGNOSTIC JOB\s*:\s*(\S+)")
CALL = re.compile(r"^(?:([A-Za-z_]\w*)\s*=\s*)?([A-Z_][A-Z0-9_]*)\(")

# <S> et <EXCEPTION> signalent des erreurs fatales levées en Python.
LEVELS = {"A": "A", "F": "F", "E": "E", "S": "F", "EXCEPTION": "F"}


@dataclass
class AsterMessage:
    level: str  # "F", "E" ou "A"
    id: str
    text: str
    comm_line: int | None = None  # ligne dans le .comm écrit par l'app
    count: int = 1
    exec_line: int | None = None  # ligne dans le fichier exécuté par run_aster

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CommandHeader:
    number: int
    exec_line: int
    command: str | None
    concept: str | None


@dataclass
class MessageReport:
    diagnostic: str | None
    messages: list[AsterMessage]
    commands: list[CommandHeader] = field(default_factory=list)

    def align(self, starts: list[tuple[int, str, str | None]]) -> int | None:
        """Calcule le décalage de lignes entre le fichier exécuté et notre .comm.

        run_aster ajoute quelques lignes en tête du .comm avant de l'exécuter.
        `starts` liste (ligne, commande, concept) des instructions connues du .comm.
        On confronte chaque en-tête « # Commande » à ces instructions, et on
        retient le décalage le plus fréquent. Renseigne ensuite `comm_line`.
        """
        votes: Counter[int] = Counter()
        for header in self.commands:
            if header.number == 1:
                votes[header.exec_line - 1] += 1  # DEBUT, toujours en ligne 1
            for line, command, concept in starts:
                if header.command == command and header.concept == concept:
                    votes[header.exec_line - line] += 1
        if not votes:
            return None
        offset = votes.most_common(1)[0][0]
        for msg in self.messages:
            if msg.exec_line is not None:
                msg.comm_line = msg.exec_line - offset
        return offset


def parse_message(text: str) -> MessageReport:
    lines = text.splitlines()
    diagnostic = None
    current_line: int | None = None
    commands: list[CommandHeader] = []
    messages: dict[tuple, AsterMessage] = {}

    i = 0
    while i < len(lines):
        line = lines[i]
        if m := DIAGNOSTIC.search(line):
            diagnostic = m.group(1)
        elif m := COMMAND.match(line):
            current_line = int(m.group(2))
            call = CALL.match(lines[i + 1]) if i + 1 < len(lines) else None
            commands.append(
                CommandHeader(
                    int(m.group(1)),
                    current_line,
                    call.group(2) if call else None,
                    call.group(1) if call else None,
                )
            )
        elif BOX_TOP.match(line):
            body: list[str] = []
            i += 1
            while i < len(lines) and not BOX_BOTTOM.match(lines[i]):
                if m := BOX_LINE.match(lines[i]):
                    body.append(m.group(1).rstrip())
                i += 1
            _add_box(messages, body, current_line)
        i += 1

    return MessageReport(diagnostic, list(messages.values()), commands)


def _add_box(messages: dict, body: list[str], exec_line: int | None) -> None:
    if not body:
        return
    m = HEADER.match(body[0].strip())
    if not m or m.group(1) == "I":
        return
    level = LEVELS[m.group(1)]
    msg_id = m.group(2) or ""
    rest = [m.group(3)] if m.group(3) else []
    text = "\n".join(rest + body[1:]).strip()
    key = (level, msg_id, text, exec_line)
    if key in messages:
        # Une erreur fatale est réimprimée dans la trace Python : on ne la compte qu'une fois.
        if level == "A":
            messages[key].count += 1
    else:
        messages[key] = AsterMessage(level, msg_id, text, exec_line=exec_line)


def status_from(diagnostic: str | None, returncode: int | None) -> str:
    """Statut final d'un run : ok, alarm ou fail."""
    if diagnostic is None:
        return "ok" if returncode == 0 else "fail"
    if diagnostic == "OK":
        return "ok"
    if diagnostic.startswith("<A>"):
        return "alarm"
    return "fail"
