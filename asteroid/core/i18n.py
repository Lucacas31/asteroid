"""Traductions de l'interface et des messages.

La phrase française sert de clé : `t("Fichier introuvable : {path}", path=p)`. Une langue
est un fichier `langues/<code>.json` ({"_langue": "English", "<français>": "<traduction>"}),
livré dans asteroid/data/langues ou ajouté par l'utilisateur dans son dossier `langues/`,
qui complète ou remplace le fichier livré. Une phrase absente reste en français.

Les mots-clés Code_Aster et le .comm généré ne sont jamais traduits.
"""

from __future__ import annotations

import json
from pathlib import Path

from .settings import user_dir

BUILTIN_DIR = Path(__file__).parent.parent / "data" / "langues"
NAME_KEY = "_langue"

_messages: dict[str, str] = {}
_language = "fr"


def _files(code: str) -> list[Path]:
    return [d / f"{code}.json" for d in (BUILTIN_DIR, user_dir("langues")) if (d / f"{code}.json").is_file()]


def _read(path: Path) -> dict[str, str]:
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str)} if isinstance(data, dict) else {}


def messages(code: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in _files(code):
        out.update(_read(path))
    return out


def languages() -> list[dict]:
    """Langues disponibles : le français (langue source) et chaque fichier trouvé."""
    codes = {"fr"}
    for d in (BUILTIN_DIR, user_dir("langues")):
        if d.is_dir():
            codes.update(p.stem for p in d.glob("*.json"))
    names = {"fr": "Français"}
    return [{"code": c, "name": messages(c).get(NAME_KEY) or names.get(c, c)} for c in sorted(codes)]


def set_language(code: str) -> None:
    global _messages, _language
    _language = code
    _messages = messages(code)


def current() -> str:
    return _language


def N_(text: str) -> str:
    """Marque une phrase traduite plus tard, à l'affichage (convention gettext)."""
    return text


def t(text: str, **variables: object) -> str:
    out = _messages.get(text) or text
    for name, value in variables.items():
        out = out.replace("{" + name + "}", str(value))
    return out
