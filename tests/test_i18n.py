"""Traductions : chaque phrase à traduire du code figure dans le fichier anglais livré."""

import json
import re
from pathlib import Path

from asteroid.core import i18n
from asteroid.core.forms import SCHEMAS
from asteroid.core.materials import SEED

ROOT = Path(__file__).parent.parent
# t("…") et N_("…") avec une chaîne littérale ; un appel non littéral doit marquer ses phrases par N_().
CALL = re.compile(r'\b(?:t|N_)\(\s*"((?:[^"\\]|\\.)*)"')
NOT_LITERAL = re.compile(r"\b(?:t|N_)\(\s*'")


def code_keys() -> set[str]:
    keys = set()
    files = [*(ROOT / "asteroid").rglob("*.py"), *(ROOT / "frontend" / "src").rglob("*.svelte"),
             *(ROOT / "frontend" / "src").rglob("*.ts")]  # fmt: skip
    for path in files:
        if "static" in path.parts:
            continue
        text = path.read_text()
        assert not NOT_LITERAL.search(text), f"{path} : t('…') entre guillemets simples, non vérifiable"
        for raw in CALL.findall(text):
            keys.add(json.loads(f'"{raw}"'))
    return keys


def schema_keys(value) -> set[str]:
    if isinstance(value, dict):
        out = {v for k, v in value.items() if k in ("label", "help") and isinstance(v, str)}
        for v in value.values():
            out |= schema_keys(v)
        return out
    if isinstance(value, list):
        return set().union(*(schema_keys(v) for v in value)) if value else set()
    return set()


def all_keys() -> set[str]:
    seed = {s for m in SEED for s in (m.name, m.description, *(x.name for x in m.strengths))}
    return code_keys() | schema_keys(SCHEMAS) | seed


def test_every_key_translated_in_english():
    english = json.loads((i18n.BUILTIN_DIR / "en.json").read_text())
    missing = sorted(all_keys() - english.keys())
    assert not missing, "Phrases sans traduction anglaise :\n" + "\n".join(missing)


def test_english_placeholders_match():
    english = json.loads((i18n.BUILTIN_DIR / "en.json").read_text())
    placeholder = re.compile(r"\{\w+\}")
    wrong = [k for k, v in english.items() if not k.startswith("_") and set(placeholder.findall(k)) != set(placeholder.findall(v))]
    assert not wrong, wrong


def test_user_language_file_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTEROID_HOME", str(tmp_path))
    (tmp_path / "langues").mkdir()
    (tmp_path / "langues" / "de.json").write_text(json.dumps({"_langue": "Deutsch", "Run inconnu": "Unbekannter Lauf"}))
    assert {"code": "de", "name": "Deutsch"} in i18n.languages()
    try:
        i18n.set_language("de")
        assert i18n.t("Run inconnu") == "Unbekannter Lauf"
        assert i18n.t("Fichier introuvable : {path}", path="x") == "Fichier introuvable : x"  # repli
    finally:
        i18n.set_language("fr")
