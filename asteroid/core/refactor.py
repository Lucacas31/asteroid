"""Modifications de blocs à travers le projet : renommage d'un concept, correction d'un nom de groupe.

Les blocs texte sont modifiés par position dans l'arbre Python (ast) : seuls les
noms et chaînes visés changent, le reste du texte (commentaires, mise en forme)
est conservé. Un bloc texte invalide n'est pas touché.
"""

from __future__ import annotations

import ast
from typing import Any

from . import forms, pyvalue
from .model import Block


def _offsets(text: str):
    """(ligne, colonne en octets UTF-8) de ast → position dans la chaîne."""
    starts, pos = [], 0
    for line in text.splitlines(keepends=True):
        starts.append(pos)
        pos += len(line)
    lines = text.splitlines(keepends=True)

    def at(lineno: int, col: int) -> int:
        return starts[lineno - 1] + len(lines[lineno - 1].encode()[:col].decode())

    return at


def _replace_spans(text: str, spans: list[tuple[int, int, str]]) -> str:
    for start, end, new in sorted(spans, reverse=True):
        text = text[:start] + new + text[end:]
    return text


# --------------------------------------------------------------------------- concepts


def _rename_refs(value: Any, old: str, new: str) -> tuple[Any, int]:
    if pyvalue.is_ref(value):
        return ({"$ref": new}, 1) if value["$ref"] == old else (value, 0)
    if isinstance(value, dict):
        count, out = 0, {}
        for k, v in value.items():
            out[k], n = _rename_refs(v, old, new)
            count += n
        return out, count
    if isinstance(value, list):
        items = [_rename_refs(v, old, new) for v in value]
        return [v for v, _ in items], sum(n for _, n in items)
    return value, 0


def _rename_text(text: str, old: str, new: str) -> tuple[str, int, bool]:
    """(texte, références renommées, le bloc redéfinit `old` sans le réutiliser)."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text, 0, False
    names = [n for n in ast.walk(tree) if isinstance(n, ast.Name) and n.id == old]
    loads = [n for n in names if not isinstance(n.ctx, ast.Store)]
    stores = [n for n in names if isinstance(n.ctx, ast.Store)]
    # `old = CMD(...)` sans lire `old` : nouveau concept du même nom, la suite ne parle plus du renommé.
    redefined = bool(stores) and not loads
    targets = loads if redefined else names
    at = _offsets(text)
    spans = [(at(n.lineno, n.col_offset), at(n.end_lineno, n.end_col_offset), new) for n in targets]
    return _replace_spans(text, spans), len(loads), redefined


def rename_concept(blocks: list[Block], index: int, old: str, new: str) -> tuple[list[Block], int]:
    """Renomme les références à `old` dans les blocs qui suivent `index`.

    Une commande réentrante (reuse) qui modifie `old` est renommée elle aussi ; une
    redéfinition de `old` arrête la propagation. Renvoie (blocs, références renommées).
    """
    out = list(blocks)
    total = 0
    for i in range(index + 1, len(blocks)):
        block = blocks[i]
        if block.mode == "form":
            params, count = _rename_refs(block.params, old, new)
            update: dict[str, Any] = {"params": params}
            redefined = False
            if block.concept == old:
                reuse = forms.SCHEMAS.get(block.command, {}).get("reuse")
                if reuse and block.params.get(reuse) == {"$ref": old}:
                    update["concept"] = new
                else:
                    redefined = True
        else:
            text, count, redefined = _rename_text(block.text, old, new)
            update = {"text": text}
        if count or "concept" in update:
            out[i] = block.model_copy(update=update)
            total += count
        if redefined:
            break
    return out, total


# --------------------------------------------------------------------------- groupes


def _is_group_kw(kw: str | None) -> bool:
    return bool(kw) and kw.startswith(("GROUP_MA", "GROUP_NO"))


def _replace_group_params(value: Any, old: str, new: str, kw: str | None = None) -> tuple[Any, int]:
    if isinstance(value, dict) and not pyvalue.is_ref(value) and not pyvalue.is_expr(value):
        count, out = 0, {}
        for k, v in value.items():
            out[k], n = _replace_group_params(v, old, new, k)
            count += n
        return out, count
    if isinstance(value, list):
        items = [_replace_group_params(v, old, new, kw) for v in value]
        return [v for v, _ in items], sum(n for _, n in items)
    if _is_group_kw(kw) and value == old:
        return new, 1
    return value, 0


def _replace_group_text(text: str, old: str, new: str) -> tuple[str, int]:
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text, 0
    at = _offsets(text)
    spans = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.keyword) and _is_group_kw(node.arg)):
            continue
        values = node.value.elts if isinstance(node.value, (ast.Tuple, ast.List)) else [node.value]
        for v in values:
            if not (isinstance(v, ast.Constant) and v.value == old):
                continue
            start, end = at(v.lineno, v.col_offset), at(v.end_lineno, v.end_col_offset)
            quote = text[start]
            if quote in "'\"" and text[end - 1] == quote:  # ni préfixe (r'', f'') ni chaîne implicite
                spans.append((start, end, quote + new + quote))
    return _replace_spans(text, spans), len(spans)


def replace_group(block: Block, old: str, new: str) -> tuple[Block, int]:
    """Remplace le nom de groupe `old` par `new` dans les mots-clés GROUP_MA*/GROUP_NO* du bloc."""
    if block.mode == "form":
        params, count = _replace_group_params(block.params, old, new)
        return block.model_copy(update={"params": params}), count
    text, count = _replace_group_text(block.text, old, new)
    return block.model_copy(update={"text": text}), count
