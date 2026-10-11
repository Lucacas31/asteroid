"""Codec générique entre le texte d'une commande Code_Aster et un arbre de valeurs JSON.

Représentation des valeurs :
- int, float, str, bool, None : tels quels ;
- référence à un concept (`model`) : {"$ref": "model"} ;
- `_F(A=1, B=2)` : {"A": 1, "B": 2} ;
- tuple ou liste : liste JSON ;
- toute autre expression Python : {"$expr": "<source>"}.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from typing import Any

from .i18n import t

LINE_WIDTH = 88
INDENT = "    "


class ParseError(ValueError):
    pass


@dataclass
class Statement:
    command: str
    concept: str | None
    params: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------------- lecture


def parse_statement(source: str) -> Statement:
    """Lit `concept = COMMANDE(MOT=valeur, ...)` ou `COMMANDE(...)`."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ParseError(t("erreur de syntaxe ligne {line} : {error}", line=exc.lineno, error=exc.msg)) from exc
    if len(tree.body) != 1:
        raise ParseError(t("le bloc contient plusieurs instructions"))
    return statement_from_node(tree.body[0], source)


def statement_from_node(node: ast.stmt, source: str) -> Statement:
    concept = None
    if isinstance(node, ast.Assign):
        if len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
            raise ParseError(t("affectation non reconnue"))
        concept = node.targets[0].id
        call = node.value
    elif isinstance(node, ast.Expr):
        call = node.value
    else:
        raise ParseError(t("instruction Python qui n'est pas un appel de commande"))
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
        raise ParseError(t("instruction Python qui n'est pas un appel de commande"))
    if call.args:
        raise ParseError(t("arguments positionnels non gérés"))
    params: dict[str, Any] = {}
    for kw in call.keywords:
        if kw.arg is None:
            raise ParseError(t("argument **kwargs non géré"))
        params[kw.arg] = value_from_node(kw.value, source)
    return Statement(call.func.id, concept, params)


def value_from_node(node: ast.expr, source: str) -> Any:
    if isinstance(node, ast.Constant) and not isinstance(node.value, (bytes, complex)):
        return node.value
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.USub, ast.UAdd))
        and isinstance(node.operand, ast.Constant)
        and isinstance(node.operand.value, (int, float))
        and not isinstance(node.operand.value, bool)
    ):
        value = node.operand.value
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.Name):
        if node.id in ("True", "False", "None"):
            return {"True": True, "False": False, "None": None}[node.id]
        return {"$ref": node.id}
    if isinstance(node, (ast.Tuple, ast.List)):
        return [value_from_node(elt, source) for elt in node.elts]
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_F"
        and not node.args
        and all(kw.arg for kw in node.keywords)
    ):
        return {kw.arg: value_from_node(kw.value, source) for kw in node.keywords}
    segment = ast.get_source_segment(source, node) if source else None
    return {"$expr": segment or ast.unparse(node)}


def literal(node: ast.expr) -> Any:
    """Valeur d'un nœud si c'est une constante simple, sinon None."""
    if not isinstance(node, (ast.Constant, ast.UnaryOp, ast.Name)):
        return None
    value = value_from_node(node, "")
    if isinstance(value, dict) or isinstance(value, list):
        return None
    return value


# --------------------------------------------------------------------------- écriture


def is_ref(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == {"$ref"}


def is_expr(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == {"$expr"}


def render_value(value: Any) -> str:
    """Rendu sur une seule ligne."""
    if value is None or isinstance(value, bool):
        return repr(value)
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if is_ref(value):
        return value["$ref"]
    if is_expr(value):
        return value["$expr"]
    if isinstance(value, dict):
        return "_F(" + ", ".join(f"{k}={render_value(v)}" for k, v in value.items()) + ")"
    if isinstance(value, list):
        items = [render_value(v) for v in value]
        if len(items) == 1:
            return f"({items[0]},)"
        return "(" + ", ".join(items) + ")"
    raise TypeError(f"valeur non gérée : {value!r}")


def _render_block(value: Any, indent: str, prefix: int = 0) -> str:
    """Rendu sur plusieurs lignes si la version sur une ligne est trop longue.

    `prefix` : nombre de caractères déjà écrits sur la ligne après l'indentation.
    """
    inline = render_value(value)
    if len(indent) + prefix + len(inline) + 1 <= LINE_WIDTH:
        return inline
    inner = indent + INDENT
    if isinstance(value, dict) and not is_ref(value) and not is_expr(value):
        lines = [f"{inner}{k}={_render_block(v, inner, len(k) + 1)}," for k, v in value.items()]
        return "_F(\n" + "\n".join(lines) + f"\n{indent})"
    if isinstance(value, list):
        lines = [f"{inner}{_render_block(v, inner)}," for v in value]
        return "(\n" + "\n".join(lines) + f"\n{indent})"
    return inline


def render_statement(command: str, concept: str | None, params: dict[str, Any]) -> str:
    head = f"{concept} = {command}(" if concept else f"{command}("
    inline = head + ", ".join(f"{k}={render_value(v)}" for k, v in params.items()) + ")"
    if len(inline) <= LINE_WIDTH or not params:
        return inline
    lines = [f"{INDENT}{k}={_render_block(v, INDENT, len(k) + 1)}," for k, v in params.items()]
    return head + "\n" + "\n".join(lines) + "\n)"
