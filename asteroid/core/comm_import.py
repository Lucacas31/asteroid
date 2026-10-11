"""Import d'un .comm existant : découpage en blocs, texte d'origine conservé."""

from __future__ import annotations

import ast
import io
import tokenize
from dataclasses import dataclass, field

from . import forms, pyvalue
from .comm import block_source, collect_files
from .i18n import t
from .model import Block

SKIPPED = {"DEBUT", "FIN", "POURSUITE"}


@dataclass
class ImportResult:
    blocks: list[Block]
    warnings: list[str] = field(default_factory=list)
    units: list[str] = field(default_factory=list)  # unités rattachées automatiquement
    unattached: list[dict] = field(default_factory=list)  # unités sans fichier : à rattacher


def _command(node: ast.stmt, source: str) -> tuple[str, str | None] | None:
    try:
        st = pyvalue.statement_from_node(node, source)
    except pyvalue.ParseError:
        return None
    return st.command, st.concept


def has_comments(text: str) -> bool:
    try:
        return any(t.type == tokenize.COMMENT for t in tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, SyntaxError):
        return False


def as_form_if_possible(block: Block) -> Block:
    """Passe en mode graphique une commande reconnue par un formulaire.

    Un bloc commenté reste en texte : le formulaire perdrait ses commentaires.
    """
    if block.command not in forms.SCHEMAS:
        return block
    if has_comments(block.text):
        block.fallback_reason = t("bloc commenté, laissé en texte pour garder les commentaires")
        return block
    try:
        command, concept, params = forms.text_to_form(block.text)
    except forms.FormError as exc:
        block.fallback_reason = str(exc)
        return block
    # Le texte d'origine reste dans `text` (non utilisé en mode graphique).
    return Block(id=block.id, command=command, concept=concept, mode="form", params=params, text=block.text)


def split_comm(source: str) -> ImportResult:
    """Un bloc par commande de premier niveau.

    Les commentaires qui précèdent une commande restent avec elle. Les instructions
    Python consécutives qui ne sont pas des commandes (paramètres, imports, boucles…)
    forment un seul bloc texte. DEBUT, POURSUITE et FIN sont retirés.
    """
    source = source.replace("\r\n", "\n").expandtabs(4)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise pyvalue.ParseError(t("erreur de syntaxe ligne {line} : {error}", line=exc.lineno, error=exc.msg)) from exc

    lines = source.splitlines()
    result = ImportResult([])
    pending: list[str] = []  # lignes de code Python libre en attente
    carry: list[str] = []  # commentaires d'une commande retirée (DEBUT…), pour le bloc suivant
    cursor = 0  # première ligne (0-indexée) pas encore attribuée

    def flush_pending() -> None:
        text = "\n".join(pending).strip("\n")
        if text.strip():
            result.blocks.append(Block(mode="text", text=text))
        pending.clear()

    for node in tree.body:
        start, end = node.lineno - 1, node.end_lineno or node.lineno
        if start < cursor:
            # Instruction sur une ligne déjà attribuée (« a = 1 ; b = 2 ») : même bloc.
            extra = lines[cursor:end]
            if extra and pending:
                pending.extend(extra)
            elif extra and result.blocks:
                last = result.blocks[-1]
                last.text = last.text + "\n" + "\n".join(extra)
                last.mode, last.params = "text", {}  # le bloc contient maintenant plusieurs instructions
                if last.command in forms.SCHEMAS:
                    last.fallback_reason = t("plusieurs instructions dans le bloc")
            cursor = max(cursor, end)
            continue
        # Commentaires et lignes vides juste au-dessus : rattachés à cette instruction.
        lead = start
        while lead > cursor and (not lines[lead - 1].strip() or lines[lead - 1].lstrip().startswith("#")):
            lead -= 1
        before = carry + lines[cursor:lead]  # commentaires reportés + code orphelin éventuel
        text_lines = lines[lead:end]
        while carry and len(before) == len(carry) and text_lines and not text_lines[0].strip():
            text_lines = text_lines[1:]  # pas de ligne vide entre l'en-tête reporté et le code
        cursor = end
        carry = []

        info = _command(node, source)
        if info and info[0] in SKIPPED:
            carry = [l for l in before + lines[lead:start] if l.strip()]  # en-tête du fichier…
            call = node.value if isinstance(node, (ast.Expr, ast.Assign)) else None
            if isinstance(call, ast.Call) and call.keywords:
                args = ", ".join(kw.arg or "**" for kw in call.keywords)
                result.warnings.append(t("{command} retiré : l'app écrit DEBUT() et FIN()", command=f"{info[0]}({args})"))
            continue
        if info is None:
            pending.extend(before + text_lines)
            continue
        flush_pending()
        command, concept = info
        text = "\n".join(before + text_lines).strip("\n")
        result.blocks.append(as_form_if_possible(Block(command=command, concept=concept, mode="text", text=text)))

    tail = lines[cursor:]
    if result.blocks and not pending and all(not l.strip() or l.lstrip().startswith("#") for l in tail):
        # Commentaires de fin de fichier : rattachés au dernier bloc.
        extra = "\n".join(tail).rstrip()
        if extra.strip():
            result.blocks[-1].text += "\n" + extra
    else:
        pending.extend(tail)
        flush_pending()

    files, warnings, unattached = collect_files([block_source(b) for b in result.blocks], has_mesh=True)
    result.warnings.extend(warnings)
    result.unattached = unattached
    result.units = [f"UNITE={f.unit} → {f.name}" for f in files]
    return result
