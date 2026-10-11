"""Export du catalogue des commandes Code_Aster en JSON.

S'exécute DANS l'image Docker de Code_Aster (Python de l'image, après
`source /opt/activate.sh`) :

    python3 export_catalog.py /out/catalog.json

Le chemin d'installation de code_aster est retrouvé par glob : il contient un
hash spack qui change avec l'image.
"""

import glob
import inspect
import json
import re
import sys

PATTERNS = [
    "/opt/spack/opt/spack/*/code-aster-*/lib64/aster",
    "/opt/spack/var/spack/environments/*/.spack-env/view/lib64/aster",
    "/opt/*/lib/aster",
]


def find_code_aster() -> str:
    for pattern in PATTERNS:
        for path in sorted(glob.glob(pattern)):
            if glob.glob(path + "/code_aster/Cata"):
                return path
    raise SystemExit("code_aster introuvable dans l'image")


sys.path.insert(0, find_code_aster())

from code_aster.Cata import Commands  # noqa: E402
from code_aster.Cata.Language import DataStructure as DS  # noqa: E402

KINDS = {"SimpleKeyword": "simp", "FactorKeyword": "fact", "Bloc": "bloc"}
SKIPPED_KEYS = {"translation", "op", "op_init", "validators"}


def type_name(value):
    if inspect.isclass(value):
        return value.__name__
    return None


def plain(value):
    """Valeur JSON pour un attribut de définition."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    name = type_name(value)
    if name:
        return name
    if callable(value):
        return "<dynamique>"
    return str(value)


def rule(r):
    return {"rule": type(r).__name__, "args": [plain(a) for a in getattr(r, "ruleArgs", ())]}


def entity(obj):
    kind = KINDS.get(type(obj).__name__)
    out = {"kind": kind} if kind else {}
    keywords = {}
    for key, value in obj.definition.items():
        if key in SKIPPED_KEYS:
            continue
        if type(value).__name__ in KINDS:
            keywords[key] = entity(value)
        elif key == "compat_syntax":
            # Fonction qui convertit d'anciens mots-clés avant la vérification :
            # on relève les noms de mots-clés cités dans son code.
            out["compat_syntax"] = value is not None
            try:
                source = inspect.getsource(value)
            except (OSError, TypeError):
                source = ""
            out["compat_keywords"] = sorted(set(re.findall(r"[\"']([A-Z][A-Z0-9_]+)[\"']", source)))
        elif key == "regles":
            rules = value if isinstance(value, (list, tuple)) else (value,)
            out["regles"] = [rule(r) for r in rules]
        elif key == "typ":
            types = value if isinstance(value, (list, tuple)) else (value,)
            out["typ"] = [type_name(t) or plain(t) for t in types]
        else:
            out[key] = plain(value)
    if keywords:
        out["keywords"] = keywords
    return out


def datastructures():
    """Hiérarchie des types de concepts : nom → noms des classes parentes."""
    out = {}
    for name, cls in vars(DS).items():
        if inspect.isclass(cls) and issubclass(cls, DS.DataStructure):
            out[name] = [c.__name__ for c in cls.__mro__ if issubclass(c, DS.DataStructure)]
    return out


def version():
    try:
        from code_aster.Utilities.version import get_version  # type: ignore

        return get_version()
    except Exception:  # noqa: BLE001
        pass
    try:
        from code_aster import pkginfo  # type: ignore

        info = getattr(pkginfo, "pkginfo", None) or getattr(pkginfo, "version_info", None)
        if info:
            return ".".join(str(x) for x in info[0][:3]) if isinstance(info[0], (tuple, list)) else str(info[0])
    except Exception:  # noqa: BLE001
        pass
    return "inconnue"


def main():
    commands = {}
    for name in sorted(dir(Commands)):
        obj = getattr(Commands, name)
        if name.isupper() and type(obj).__name__ in ("Operator", "Macro", "Procedure", "Formule", "Command"):
            data = entity(obj)
            data["kind"] = type(obj).__name__.lower()
            commands[name] = data
    catalog = {"version": version(), "commands": commands, "datastructures": datastructures()}
    out = sys.argv[1] if len(sys.argv) > 1 else "catalog.json"
    with open(out, "w") as f:
        json.dump(catalog, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(commands)} commandes, version {catalog['version']} -> {out}")


if __name__ == "__main__":
    main()
