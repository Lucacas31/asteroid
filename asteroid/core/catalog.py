"""Catalogue des commandes Code_Aster : chargement, squelettes, validation.

Le catalogue est exporté depuis l'image Docker par tools/export_catalog.py.
Une copie (17.4.0) est livrée avec l'app ; « Mettre à jour le catalogue »
en écrit une nouvelle dans ~/.config/asteroid/.
"""

from __future__ import annotations

import ast
import gzip
import json
import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import i18n, pyvalue
from .i18n import N_
from .settings import config_dir

BUNDLED = Path(__file__).resolve().parent.parent / "data"

# Références U4 vérifiées sur code-aster.org (nom de la commande en page 1).
DOC_REFS = {
    "LIRE_MAILLAGE": "U4.21.01", "DEFI_GROUP": "U4.22.01", "CREA_MAILLAGE": "U4.23.02",
    "MODI_MAILLAGE": "U4.23.04", "DEFI_CONSTANTE": "U4.31.01", "DEFI_FONCTION": "U4.31.02",
    "FORMULE": "U4.31.05", "CALC_TABLE": "U4.33.03", "DEFI_LIST_REEL": "U4.34.01",
    "DEFI_LIST_INST": "U4.34.03", "AFFE_MODELE": "U4.41.01", "AFFE_CARA_ELEM": "U4.42.01",
    "DEFI_MATERIAU": "U4.43.01", "AFFE_MATERIAU": "U4.43.03", "AFFE_CHAR_MECA": "U4.44.01",
    "AFFE_CHAR_MECA_F": "U4.44.01", "AFFE_CHAR_CINE": "U4.44.03", "MECA_STATIQUE": "U4.51.01",
    "MACRO_ELAS_MULT": "U4.51.02", "STAT_NON_LINE": "U4.51.03", "CALC_MODES": "U4.52.02",
    "CREA_CHAMP": "U4.72.04", "CALC_CHAMP": "U4.81.04", "POST_RELEVE_T": "U4.81.21",
    "POST_ELEM": "U4.81.22", "IMPR_RESU": "U4.91.01", "IMPR_TABLE": "U4.91.03",
    "TEST_RESU": "U4.92.01", "TEST_TABLE": "U4.92.03", "DEFI_FICHIER": "U4.12.03",
}  # fmt: skip

# Type produit des commandes dont le sd_prod est calculé à l'exécution.
DYNAMIC_TYPES = {
    "LIRE_MAILLAGE": "maillage_sdaster",
    "CREA_MAILLAGE": "maillage_sdaster",
    "AFFE_CARA_ELEM": "cara_elem",
    "FORMULE": "formule",
    "CALC_TABLE": "table_sdaster",
}

# Commandes dont le type annoncé par le catalogue ne correspond pas toujours au
# résultat réel (relevé sur les cas tests officiels) : écart = avertissement.
UNSURE_TYPES = {"EXTR_COUPE", "CALC_THER_MULT"}

GROUP_TYPES = {"grma": "GROUP_MA", "grno": "GROUP_NO"}
# Types simples (tout le reste désigne un type de concept).
INT_TYPES = {"I", "UnitDefault", "UnitMed"}
TEXT_TYPES = {"TXM", "grma", "grno", "no", "ma"}
SIMPLE_TYPES = INT_TYPES | TEXT_TYPES | {"R", "C"}


class Catalog:
    def __init__(self, data: dict, source: str):
        self.version: str = data.get("version", "inconnue")
        self.commands: dict[str, dict] = data["commands"]
        self.datastructures: dict[str, list[str]] = data.get("datastructures", {})
        self.source = source

    def command(self, name: str) -> dict | None:
        return self.commands.get(name)

    def summary(self) -> list[dict]:
        return [
            {
                "name": name,
                "fr": cmd.get("fr", ""),
                "produces": cmd.get("sd_prod") is not None or name in DYNAMIC_TYPES,
                "doc": DOC_REFS.get(name),
            }
            for name, cmd in sorted(self.commands.items())
        ]

    def is_subtype(self, actual: str, expected: str) -> bool:
        return expected in self.datastructures.get(actual, [actual])

    def produced_type(self, command: str, params: dict[str, Any], concepts: dict[str, str | None]) -> str | None:
        cmd = self.commands.get(command)
        if cmd is None:
            return None
        sd = cmd.get("sd_prod")
        if isinstance(sd, str) and sd != "<dynamique>":
            return sd
        if command in DYNAMIC_TYPES:
            return DYNAMIC_TYPES[command]
        # Commande réentrante utilisée avec reuse : même type que le concept modifié.
        reuse = params.get("reuse")
        if pyvalue.is_ref(reuse):
            return concepts.get(reuse["$ref"])
        return None

    # ------------------------------------------------------------------ squelette

    def skeleton(self, command: str, concept: str | None) -> str:
        """Texte d'une commande avec ses mots-clés obligatoires à compléter (`...`)."""
        cmd = self.commands.get(command)
        head = f"{concept} = {command}(" if concept else f"{command}("
        if cmd is None:
            return head + ")"
        lines = _skeleton_lines(cmd, "    ")
        if not lines:
            return head + ")"
        return head + "\n" + "\n".join(lines) + "\n)"


def _skeleton_lines(entity: dict, indent: str) -> list[str]:
    lines = []
    for kw, sub in entity.get("keywords", {}).items():
        if sub.get("kind") == "bloc" or sub.get("statut") != "o" or "defaut" in sub:
            continue
        if sub.get("kind") == "fact":
            inner = _skeleton_lines(sub, indent + "    ")
            if inner:
                lines.append(f"{indent}{kw}=_F(")
                lines.extend(inner)
                lines.append(f"{indent}),")
            else:
                lines.append(f"{indent}{kw}=_F(),")
        else:
            into = sub.get("into")
            value = json.dumps(into[0]) if isinstance(into, list) and len(into) == 1 else "..."
            lines.append(f"{indent}{kw}={value},")
    return lines


def _read(path: Path) -> dict:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def _version_key(path: Path) -> tuple:
    m = re.search(r"catalog_([\d.]+)\.json", path.name)
    return tuple(int(x) for x in m.group(1).split(".")) if m else (0,)


def catalog_files() -> list[Path]:
    user = sorted(config_dir().glob("catalog_*.json"), key=_version_key)
    bundled = sorted(BUNDLED.glob("catalog_*.json*"), key=_version_key)
    return user + bundled if user else bundled


@lru_cache(maxsize=1)
def load_catalog() -> Catalog | None:
    """Catalogue le plus récent : celui de l'utilisateur s'il existe, sinon celui livré."""
    files = catalog_files()
    user = [f for f in files if f.parent == config_dir()]
    path = user[-1] if user else (files[-1] if files else None)
    if path is None:
        return None
    return Catalog(_read(path), str(path))


def reload_catalog() -> Catalog | None:
    load_catalog.cache_clear()
    return load_catalog()


# --------------------------------------------------------------------------- validation


@dataclass
class Issue:
    """Message de validation : phrase française (clé de traduction) et ses variables.

    `message` reste en français pour la logique interne ; `to_dict` traduit."""

    level: str  # "error" ou "warning"
    template: str
    vars: dict[str, Any] = field(default_factory=dict)
    fix: dict[str, str] | None = None  # correction proposée, ex. {"kind": "group_case", "from": …, "to": …}

    def _render(self, tr) -> str:
        out = tr(self.template)
        for name, value in self.vars.items():
            if isinstance(value, list):  # alternatives : « réel ou entier »
                value = tr(N_(" ou ")).join(tr(v) for v in value)
            out = out.replace("{" + name + "}", str(value))
        return out

    @property
    def message(self) -> str:
        return self._render(lambda x: x)

    def to_dict(self) -> dict:
        out = {"level": self.level, "message": self._render(i18n.t)}
        if self.fix:
            out["fix"] = self.fix
        return out


UNKNOWN_KEYWORD = N_("{path}/{kw} : mot-clé inconnu")
MISSING_KEYWORD = N_("{path}/{kw} : mot-clé obligatoire manquant")
NOT_ALLOWED = N_("{path}/{kw} : non permis ici (condition : {cond})")


class _Unknown(Exception):
    """Condition de bloc impossible à évaluer (expression, concept au type inconnu…)."""


class Validator:
    """Valide les commandes d'un projet, bloc par bloc, dans l'ordre.

    `mesh_groups` : {"GROUP_MA": {...}, "GROUP_NO": {...}} ou None si pas de maillage.
    Les règles du catalogue (UN_PARMI…) donnent des avertissements : Code_Aster
    complète certains mots-clés avant de les vérifier, ce qu'on ne reproduit pas.
    """

    def __init__(self, catalog: Catalog, mesh_groups: dict[str, set[str]] | None = None):
        self.catalog = catalog
        self.mesh_groups = mesh_groups
        self.concepts: dict[str, str | None] = {}  # nom → type Code_Aster (None si inconnu)
        self.producer: dict[str, str] = {}  # concept → commande qui l'a produit
        # Un .comm voit les fonctions du module math sans import (pi, sqrt…).
        self.pyvars: set[str] = {n for n in dir(math) if not n.startswith("_")}
        # Noms introduits par « from x import * », INCLUDE ou POURSUITE : impossibles à lister.
        self.open_namespace = False
        self.created_groups: dict[str, set[str]] = {"GROUP_MA": set(), "GROUP_NO": set()}

    # ------------------------------------------------------------------ blocs

    def validate_source(self, source: str) -> list[Issue]:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []  # déjà signalé par l'analyse du bloc
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and any(a.name == "*" for a in node.names):
                self.open_namespace = True
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in ("INCLUDE", "POURSUITE"):
                    self.open_namespace = True
                elif node.func.id == "CO" and node.args and isinstance(node.args[0], ast.Constant):
                    # Concept produit par une macro : CO("nom").
                    if isinstance(node.args[0].value, str):
                        self.concepts.setdefault(node.args[0].value, None)
        issues: list[Issue] = []
        for node in tree.body:
            try:
                st = pyvalue.statement_from_node(node, source)
            except pyvalue.ParseError:
                self._record_python(node)
                continue
            if st.command not in self.catalog.commands:
                if st.command.isupper() and st.command not in ("_F", "CO"):
                    issues.append(Issue("warning", N_("{command} : commande absente du catalogue {version}"),
                                         {"command": st.command, "version": self.catalog.version}))
                if st.concept:
                    self.concepts.setdefault(st.concept, None)
                continue
            issues.extend(self.validate_call(st.command, st.concept, st.params))
        return issues

    def _record_python(self, node: ast.stmt) -> None:
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Store):
                self.pyvars.add(sub.id)
            elif isinstance(sub, (ast.FunctionDef, ast.Import, ast.ImportFrom)):
                names = [sub.name] if isinstance(sub, ast.FunctionDef) else [a.asname or a.name for a in sub.names]
                self.pyvars.update(n.split(".")[0] for n in names)

    def validate_call(self, command: str, concept: str | None, params: dict[str, Any]) -> list[Issue]:
        cmd = self.catalog.commands[command]
        issues: list[Issue] = []
        params = dict(params)
        reuse = params.pop("reuse", None)
        if reuse is not None:
            if not cmd.get("reentrant") or cmd.get("reentrant") == "n":
                issues.append(Issue("error", N_("{command} n'accepte pas reuse"), {"command": command}))
            elif concept and pyvalue.is_ref(reuse) and reuse["$ref"] != concept:
                issues.append(Issue("warning", N_("reuse={reuse} mais le résultat s'appelle {concept}"),
                                     {"reuse": reuse["$ref"], "concept": concept}))
        if cmd.get("kind") != "formule":  # les mots-clés de FORMULE sont ses paramètres
            self._check_level(cmd, params, command, issues, [])
        legacy = set(cmd.get("compat_keywords", []))
        unknown = [
            i for i in issues
            if i.template == UNKNOWN_KEYWORD and i.vars["kw"] in legacy
        ]
        if unknown:
            # Code_Aster réécrit d'anciens mots-clés avant de vérifier : un mot-clé inconnu
            # peut être converti, et satisfaire ainsi un obligatoire ou une condition.
            for issue in issues:
                if issue in unknown or issue.template in (MISSING_KEYWORD, NOT_ALLOWED):
                    issue.level = "warning"
        if concept:
            known = self.concepts.get(reuse["$ref"]) if pyvalue.is_ref(reuse) else None
            produced = known or self.catalog.produced_type(command, {**params, "reuse": reuse}, self.concepts)
            self.concepts[concept] = produced
            self.producer[concept] = command
        self._record_created_groups(command, params)
        return issues

    def _record_created_groups(self, command: str, params: dict[str, Any]) -> None:
        if command not in ("DEFI_GROUP", "CREA_MAILLAGE"):
            return
        for kw, entity in (("CREA_GROUP_MA", "GROUP_MA"), ("CREA_GROUP_NO", "GROUP_NO")):
            items = params.get(kw)
            for item in items if isinstance(items, list) else [items] if items else []:
                if isinstance(item, dict):
                    for key in ("NOM", "GROUP_MA", "GROUP_NO"):
                        names = item.get(key)
                        for n in names if isinstance(names, list) else [names]:
                            if isinstance(n, str):
                                self.created_groups[entity].add(n)

    # ------------------------------------------------------------------ niveaux

    def _scope(self, entity: dict, values: dict, ctx: list[dict]) -> tuple[dict, dict, dict]:
        """(mots-clés certains, mots-clés possibles, mots-clés des blocs inactifs).

        Un même mot-clé peut être défini dans plusieurs blocs : on garde toutes ses définitions.
        """
        certain: dict[str, list[dict]] = {}
        possible: dict[str, list[dict]] = {}
        inactive: dict[str, tuple[str, bool]] = {}

        def visit(ent: dict, sure: bool) -> None:
            for kw, sub in ent.get("keywords", {}).items():
                if sub.get("kind") != "bloc":
                    possible.setdefault(kw, []).append(sub)
                    if sure:
                        certain.setdefault(kw, []).append(sub)
                    continue
                active, by_default = self._condition(sub.get("condition", "True"), [values, *ctx], entity)
                if active is False:
                    for inner in _keywords_deep(sub):
                        inactive.setdefault(inner, (sub.get("condition", ""), by_default))
                else:
                    # Une condition vraie grâce à une valeur par défaut reste incertaine.
                    visit(sub, sure and active is True and not by_default)

        visit(entity, True)
        return certain, possible, inactive

    def _check_level(self, entity: dict, values: dict, path: str, issues: list[Issue], ctx: list[dict]) -> None:
        certain, possible, inactive = self._scope(entity, values, ctx)
        for kw, value in values.items():
            candidates = possible.get(kw)
            if not candidates:
                if kw in inactive:
                    cond, by_default = inactive[kw]
                    cond = " ".join(cond.split())
                    level = "warning" if by_default else "error"
                    issues.append(Issue(level, NOT_ALLOWED, {"path": path, "kw": kw, "cond": cond}))
                else:
                    issues.append(Issue("error", UNKNOWN_KEYWORD, {"path": path, "kw": kw}))
                continue
            # La définition qui convient le mieux (moins d'erreurs) l'emporte.
            best: list[Issue] | None = None
            for sub in candidates:
                found: list[Issue] = []
                if sub.get("kind") == "fact":
                    self._check_fact(sub, value, f"{path}/{kw}", found, [values, *ctx])
                else:
                    self._check_simp(sub, value, f"{path}/{kw}", found)
                errors = sum(i.level == "error" for i in found)
                if best is None or errors < sum(i.level == "error" for i in best):
                    best = found
                if not errors:
                    break
            issues.extend(best or [])
        for kw, subs in certain.items():
            if kw not in values and all(s.get("statut") == "o" and "defaut" not in s for s in subs):
                issues.append(Issue("error", MISSING_KEYWORD, {"path": path, "kw": kw}))
        for rule in entity.get("regles", []):
            found = _check_rule(rule, set(values))
            if found:
                issues.append(Issue("warning", found[0], {"path": path, **found[1]}))

    def _check_fact(self, sub: dict, value: Any, path: str, issues: list[Issue], ctx: list[dict]) -> None:
        items = value if isinstance(value, list) else [value]
        if any(pyvalue.is_ref(i) or pyvalue.is_expr(i) for i in items):
            return  # liste construite en Python : contenu inconnu avant l'exécution
        if not all(isinstance(i, dict) for i in items):
            issues.append(Issue("error", N_("{path} : _F(...) attendu"), {"path": path}))
            return
        maxi = sub.get("max", 1)
        if isinstance(maxi, int) and len(items) > maxi:
            issues.append(Issue("error", N_("{path} : au plus {max} occurrence(s), {count} données"),
                                {"path": path, "max": maxi, "count": len(items)}))
        for i, item in enumerate(items):
            label = f"{path}[{i + 1}]" if len(items) > 1 else path
            self._check_level(sub, item, label, issues, ctx)

    def _check_simp(self, sub: dict, value: Any, path: str, issues: list[Issue]) -> None:
        values = value if isinstance(value, list) else [value]
        types = sub.get("typ", [])
        if "not_checked" in types:
            return
        maxi, mini = sub.get("max", 1), sub.get("min", 1)
        # Taille inconnue si une valeur vient de Python ; un complexe ('RI', a, b) compte pour 3.
        countable = "C" not in types and not any(pyvalue.is_ref(v) or pyvalue.is_expr(v) for v in values)
        if countable and isinstance(maxi, int) and len(values) > maxi:
            issues.append(Issue("error", N_("{path} : au plus {max} valeur(s), {count} données"),
                                {"path": path, "max": maxi, "count": len(values)}))
        if countable and isinstance(mini, int) and 0 < len(values) < mini:
            issues.append(Issue("error", N_("{path} : au moins {min} valeur(s)"), {"path": path, "min": mini}))
        into = sub.get("into")
        for v in values:
            if v is Ellipsis:
                issues.append(Issue("warning", N_("{path} : valeur à compléter"), {"path": path}))
                continue
            if pyvalue.is_expr(v) or (isinstance(v, list) and "C" in types):
                continue
            if pyvalue.is_ref(v):
                self._check_ref(v["$ref"], types, path, issues)
                continue
            found = _check_plain(v, types)
            if found:
                issues.append(Issue("error", found[0], {"path": path, **found[1]}))
                continue
            if isinstance(into, list) and v not in into and not (isinstance(v, (int, float)) and float(v) in into):
                shown = ", ".join(map(str, into[:8])) + ("…" if len(into) > 8 else "")
                issues.append(Issue("error", N_("{path}={value} : valeur non permise ({allowed})"),
                                    {"path": path, "value": repr(v), "allowed": shown}))
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                lo, hi = sub.get("val_min"), sub.get("val_max")
                if isinstance(lo, (int, float)) and v < lo:
                    issues.append(Issue("error", N_("{path}={value} : inférieur au minimum {min}"),
                                        {"path": path, "value": v, "min": lo}))
                if isinstance(hi, (int, float)) and v > hi:
                    issues.append(Issue("error", N_("{path}={value} : supérieur au maximum {max}"),
                                        {"path": path, "value": v, "max": hi}))
            for t in types:
                if t in GROUP_TYPES and isinstance(v, str):
                    self._check_group(v, GROUP_TYPES[t], path, issues)

    def _check_ref(self, name: str, types: list, path: str, issues: list[Issue]) -> None:
        if name in self.pyvars:
            return  # variable Python : valeur inconnue avant l'exécution
        if name not in self.concepts:
            level = "warning" if self.open_namespace else "error"
            issues.append(Issue(level, N_("{path} : « {name} » n'est pas défini plus haut"), {"path": path, "name": name}))
            return
        actual = self.concepts[name]
        expected = [t for t in types if isinstance(t, str) and t not in SIMPLE_TYPES and t != "CO"]
        if actual is None or not expected or "CO" in types:
            return
        if not any(self.catalog.is_subtype(actual, t) for t in expected):
            level = "warning" if self.producer.get(name) in UNSURE_TYPES else "error"
            issues.append(Issue(level, N_("{path} : « {name} » est un {actual}, attendu : {expected}"),
                                {"path": path, "name": name, "actual": actual, "expected": ", ".join(expected)}))

    def _check_group(self, name: str, entity: str, path: str, issues: list[Issue]) -> None:
        if self.mesh_groups is None or name in self.created_groups[entity]:
            return
        if name in self.mesh_groups.get(entity, set()):
            return
        if entity == "GROUP_NO" and (name in self.mesh_groups.get("GROUP_MA", set()) or name in self.created_groups["GROUP_MA"]):
            return  # Code_Aster accepte un groupe de mailles là où il attend des nœuds
        # Même nom à la casse près (Code_Aster distingue « Charge » et « charge ») : correction proposée.
        known = self.mesh_groups.get(entity, set()) | self.created_groups[entity]
        if entity == "GROUP_NO":
            known = known | self.mesh_groups.get("GROUP_MA", set()) | self.created_groups["GROUP_MA"]
        same = sorted({g for g in known if g.casefold() == name.casefold()})
        if len(same) == 1:
            template = (
                N_("{path} : groupe de mailles « {name} » absent du maillage, « {suggestion} » existe")
                if entity == "GROUP_MA"
                else N_("{path} : groupe de nœuds « {name} » absent du maillage, « {suggestion} » existe")
            )
            issues.append(Issue("error", template, {"path": path, "name": name, "suggestion": same[0]},
                                fix={"kind": "group_case", "from": name, "to": same[0]}))
            return
        template = (
            N_("{path} : groupe de mailles « {name} » absent du maillage") if entity == "GROUP_MA"
            else N_("{path} : groupe de nœuds « {name} » absent du maillage")
        )
        issues.append(Issue("error", template, {"path": path, "name": name}))

    # ------------------------------------------------------------------ conditions

    def _condition(self, condition: str, scopes: list[dict], entity: dict) -> tuple[bool | None, bool]:
        """(résultat, une valeur par défaut a servi). Résultat None : impossible à évaluer."""
        used_default = False

        def get_all(kw: str) -> list:
            value = get(kw, raw=True)
            return value if isinstance(value, list) else [] if value is None else [value]

        def equal_to(kw: str, ref) -> bool:
            refs = ref if isinstance(ref, (tuple, list)) else (ref,)
            return any(v in refs for v in get_all(kw))

        def is_in(kw: str, seq) -> bool:
            return any(v in seq for v in get_all(kw))

        def get(kw: str, raw: bool = False):
            for scope in scopes:
                if kw in scope:
                    value = scope[kw]
                    break
            else:
                default = _find_default(entity, kw)
                if default is None:
                    return None
                nonlocal used_default
                used_default = True
                value = default
            items = value if isinstance(value, list) else [value]
            if any(pyvalue.is_expr(v) or (pyvalue.is_ref(v) and v["$ref"] in self.pyvars) for v in items):
                raise _Unknown
            items = [v["$ref"] if pyvalue.is_ref(v) else v for v in items]
            if raw:
                return items if isinstance(value, list) else items[0]
            return items[0] if len(items) == 1 else items

        def concept_type(kw: str):
            value = get(kw)
            if value is None:
                return None
            ctype = self.concepts.get(value)
            if ctype is None:
                raise _Unknown
            return ctype

        def compare(op):
            def f(kw, ref):
                v = get(kw)
                return v is not None and op(v, ref)

            return f

        env = {
            "equal_to": equal_to,
            "exists": lambda kw: get(kw) is not None,
            "is_in": is_in,
            "value": get,
            "is_type": concept_type,
            "AsType": lambda x: x,
            "greater_than": compare(lambda a, b: a > b),
            "less_than": compare(lambda a, b: a < b),
            "len": len,
            "abs": abs,
            "type": type,
            "size": len,
            "True": True,
            "False": False,
            "None": None,
        }
        try:
            result = eval(condition, {"__builtins__": {}}, env)  # noqa: S307 — catalogue de confiance
        except _Unknown:
            return None, used_default
        except Exception:  # noqa: BLE001 — condition hors de notre portée : bloc considéré possible
            return None, used_default
        return bool(result), used_default


def _keywords_deep(entity: dict) -> list[str]:
    out = []
    for kw, sub in entity.get("keywords", {}).items():
        if sub.get("kind") == "bloc":
            out.extend(_keywords_deep(sub))
        else:
            out.append(kw)
    return out


def _find_default(entity: dict, kw: str):
    for name, sub in entity.get("keywords", {}).items():
        if sub.get("kind") == "bloc":
            found = _find_default(sub, kw)
            if found is not None:
                return found
        elif name == kw and "defaut" in sub:
            return sub["defaut"]
    return None


def _check_rule(rule: dict, given: set[str]) -> tuple[str, dict] | None:
    """Règle du catalogue, sur les seuls mots-clés écrits.

    Code_Aster complète des mots-clés (défauts, compat_syntax) avant d'appliquer
    les règles : une absence n'est donc jamais signalée, seuls les excès le sont.
    """
    name, args = rule.get("rule"), [a for a in rule.get("args", []) if isinstance(a, str)]
    written = [a for a in args if a in given]
    if name in ("ExactlyOne", "AtMostOne") and len(written) > 1:
        return N_("{path} : au plus un mot-clé parmi {args} ({given} donnés)"), {"args": ", ".join(args), "given": ", ".join(written)}
    if name == "OnlyFirstPresent" and args and args[0] in given:
        extra = [a for a in args[1:] if a in given]
        if extra:
            return N_("{path} : {first} exclut {others}"), {"first": args[0], "others": ", ".join(extra)}
    return None


def _check_plain(value: Any, types: list) -> tuple[str, dict] | None:
    """(message, variables) si `value` (constante Python) ne correspond à aucun des types simples."""
    simple = [t for t in types if t in SIMPLE_TYPES]
    if not simple:
        if any(isinstance(t, str) for t in types):
            return N_("{path} : nom de concept attendu, reçu {value}"), {"value": repr(value)}
        return None
    if isinstance(value, bool):
        return N_("{path} : valeur {value} invalide"), {"value": repr(value)}
    if isinstance(value, str) and any(t in TEXT_TYPES for t in simple):
        return None
    if isinstance(value, int) and (any(t in INT_TYPES for t in simple) or "R" in simple):
        return None
    if isinstance(value, float) and "R" in simple:
        return None
    if "C" in simple and (isinstance(value, (int, float)) or value in ("RI", "MP")):
        return None
    if isinstance(value, float) and any(t in INT_TYPES for t in simple) and value.is_integer():
        return None  # 2.0 pour un entier : accepté par Code_Aster
    labels = {"R": N_("réel"), "C": N_("complexe")} | {t: N_("entier") for t in INT_TYPES} | {t: N_("texte") for t in TEXT_TYPES}
    return N_("{path} : {wanted} attendu, reçu {value}"), {"wanted": sorted({labels[t] for t in simple}), "value": repr(value)}
