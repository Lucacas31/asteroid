"""Formulaires dédiés : un schéma par commande, avec les vrais mots-clés Code_Aster.

Le schéma sert à trois choses :
- le frontend construit le formulaire à partir de lui ;
- un bloc texte ne passe en mode graphique que si tous ses mots-clés y figurent ;
- l'ordre des mots-clés dans le .comm généré suit celui du schéma.

Types de champs :
- concept : référence à un concept défini plus haut ({"$ref": nom}), filtrée par type ;
- groups : liste de noms de groupes du maillage (GROUP_MA ou GROUP_NO) ;
- flag : mot-clé qui vaut "OUI" (TOUT="OUI") ;
- enum / multienum : une ou plusieurs valeurs parmi `into` ;
- float / int / text : valeurs simples ; `size` > 1 pour un tuple de réels ;
- factor : mot-clé facteur, `max` occurrences de _F(...) avec ses propres champs.
  `fill_all` : à la création, une occurrence par concept disponible pour ce champ.
`unit` indique la grandeur physique, affichée dans l'unité du projet.
"""

from __future__ import annotations

from typing import Any

from . import pyvalue
from .i18n import t

# Type de concept produit par commande (filtre des listes de concepts).
CONCEPT_TYPES = {
    "LIRE_MAILLAGE": "maillage",
    "MODI_MAILLAGE": "maillage",
    "CREA_MAILLAGE": "maillage",
    "DEFI_GROUP": "maillage",
    "AFFE_MODELE": "modele",
    "DEFI_MATERIAU": "mater",
    "AFFE_MATERIAU": "cham_mater",
    "AFFE_CARA_ELEM": "cara_elem",
    "AFFE_CHAR_MECA": "char_meca",
    "AFFE_CHAR_MECA_F": "char_meca",
    "AFFE_CHAR_CINE": "char_cine",
    "MECA_STATIQUE": "evol_elas",
    "STAT_NON_LINE": "evol_noli",
    "MACRO_ELAS_MULT": "mult_elas",
    "DEFI_FONCTION": "fonction",
    "FORMULE": "fonction",
    "DEFI_CONSTANTE": "fonction",
    "DEFI_LIST_REEL": "listr8",
}

RESULT_TYPES = ["evol_elas", "evol_noli", "mult_elas"]

# Mots-clés gérés automatiquement par l'app : acceptés à l'import s'ils valent le défaut.
AUTO_KEYWORDS = {
    "LIRE_MAILLAGE": {"UNITE": 20, "FORMAT": "MED"},
    "IMPR_RESU": {"FORMAT": "MED", "UNITE": 80},
}


def concept(kw: str, ctype: str | list[str], required: bool = False, **extra) -> dict:
    types = [ctype] if isinstance(ctype, str) else ctype
    return {"kw": kw, "type": "concept", "ctypes": types, "required": required, **extra}


def groups(kw: str = "GROUP_MA", dims: list[int] | None = None, **extra) -> dict:
    entity = "GROUP_NO" if kw.startswith("GROUP_NO") else "GROUP_MA"
    return {"kw": kw, "type": "groups", "entity": entity, "dims": dims, **extra}


def real(kw: str, unit: str | None = None, **extra) -> dict:
    return {"kw": kw, "type": "float", "unit": unit, **extra}


def enum(kw: str, into: list[str], **extra) -> dict:
    return {"kw": kw, "type": "enum", "into": into, **extra}


def multienum(kw: str, into: list[str], **extra) -> dict:
    return {"kw": kw, "type": "multienum", "into": into, **extra}


def flag(kw: str = "TOUT") -> dict:
    return {"kw": kw, "type": "flag"}


def factor(kw: str, fields: list[dict], max: int | None = None, **extra) -> dict:
    """max=None : nombre d'occurrences illimité."""
    return {"kw": kw, "type": "factor", "fields": fields, "max": max, **extra}


def forces(*names: str, unit: str) -> list[dict]:
    return [real(n, unit) for n in names]


WHERE_MA = [flag("TOUT"), groups("GROUP_MA")]

SCHEMAS: dict[str, dict] = {
    "LIRE_MAILLAGE": {
        "doc": "U4.21.01",
        "fields": [enum("FORMAT", ["MED"], default="MED", hidden=True)],
        "defaults": {"FORMAT": "MED"},
    },
    "MODI_MAILLAGE": {
        "doc": "U4.23.04",
        "reuse": "MAILLAGE",
        "fields": [
            concept("MAILLAGE", "maillage", required=True),
            factor("ORIE_PEAU", [groups("GROUP_MA_PEAU", [2], label="Faces à orienter")], max=1,
                   help="Réoriente les normales des faces de bord, utile avant PRES_REP."),
            real("ECHELLE", None, help="Facteur appliqué à toutes les coordonnées."),
        ],
        "defaults": {"ORIE_PEAU": {"GROUP_MA_PEAU": []}},
    },
    "AFFE_MODELE": {
        "doc": "U4.41.01",
        "fields": [
            concept("MAILLAGE", "maillage", required=True),
            factor("AFFE", [
                *WHERE_MA,
                enum("PHENOMENE", ["MECANIQUE"], default="MECANIQUE"),
                enum("MODELISATION", ["3D", "3D_SI", "C_PLAN", "D_PLAN", "AXIS", "DKT", "COQUE_3D"], default="3D"),
            ], required=True),
        ],
        "defaults": {"AFFE": [{"TOUT": "OUI", "PHENOMENE": "MECANIQUE", "MODELISATION": "3D"}]},
    },
    "DEFI_MATERIAU": {
        "doc": "U4.43.01",
        "exclusive": ["ELAS", "ELAS_ISTR", "ELAS_ORTH"],
        "fields": [
            factor("ELAS", [
                real("E", "stress", required=True), real("NU", None, required=True),
                real("RHO", "density"), real("ALPHA", "expansion"),
            ], max=1),
            factor("ELAS_ISTR", [
                real("E_L", "stress", required=True), real("E_N", "stress", required=True),
                real("NU_LT", None, required=True), real("NU_LN", None, required=True),
                real("G_LN", "stress", required=True), real("RHO", "density"),
            ], max=1, help="Isotrope transverse : plan L-T isotrope, N normale."),
            factor("ELAS_ORTH", [
                real("E_L", "stress", required=True), real("E_T", "stress", required=True),
                real("E_N", "stress", required=True),
                real("NU_LT", None, required=True), real("NU_LN", None, required=True),
                real("NU_TN", None, required=True),
                real("G_LT", "stress", required=True), real("G_LN", "stress", required=True),
                real("G_TN", "stress", required=True), real("RHO", "density"),
            ], max=1, help="Orthotrope : repère matériau défini par AFFE_CARA_ELEM/MASSIF."),
        ],
        "defaults": {"ELAS": {"E": None, "NU": None}},
    },
    "AFFE_MATERIAU": {
        "doc": "U4.43.03",
        "fields": [
            concept("MAILLAGE", "maillage", required=True),
            factor("AFFE", [*WHERE_MA, concept("MATER", "mater", required=True)], required=True),
        ],
        "defaults": {"AFFE": [{"TOUT": "OUI", "MATER": None}]},
    },
    "AFFE_CARA_ELEM": {
        "doc": "U4.42.01",
        "fields": [
            concept("MODELE", "modele", required=True),
            factor("MASSIF", [
                *WHERE_MA,
                real("ANGL_REP", "angle", size=3, help="Angles nautiques α, β, γ du repère matériau (°)."),
            ], required=True),
        ],
        "defaults": {"MASSIF": [{"TOUT": "OUI", "ANGL_REP": [0.0, 0.0, 0.0]}]},
    },
    "AFFE_CHAR_MECA": {
        "doc": "U4.44.01",
        "fields": [
            concept("MODELE", "modele", required=True),
            factor("DDL_IMPO", [
                *WHERE_MA, groups("GROUP_NO"),
                *forces("DX", "DY", "DZ", unit="length"),
            ], label="Déplacements imposés"),
            factor("LIAISON_SOLIDE", [groups("GROUP_MA"), groups("GROUP_NO")], label="Liaison solide"),
            factor("FORCE_FACE", [groups("GROUP_MA", [2]), *forces("FX", "FY", "FZ", unit="pressure")],
                   label="Force surfacique", area=True),
            factor("PRES_REP", [groups("GROUP_MA", [2]), real("PRES", "pressure")],
                   label="Pression (normale sortante)", area=True),
            factor("FORCE_ARETE", [groups("GROUP_MA", [1]), *forces("FX", "FY", "FZ", unit="lineic")],
                   label="Force linéique"),
            factor("FORCE_NODALE", [groups("GROUP_NO"), *forces("FX", "FY", "FZ", unit="force")],
                   label="Force nodale"),
            factor("PESANTEUR", [
                real("GRAVITE", "accel", required=True),
                real("DIRECTION", None, size=3, required=True),
                groups("GROUP_MA", [3], help="Vide : tout le modèle."),
            ], max=1, label="Pesanteur"),
        ],
        "defaults": {},
    },
    "MECA_STATIQUE": {
        "doc": "U4.51.01",
        "fields": [
            concept("MODELE", "modele", required=True),
            concept("CHAM_MATER", "cham_mater", required=True),
            concept("CARA_ELEM", "cara_elem"),
            factor("EXCIT", [
                concept("CHARGE", ["char_meca", "char_cine"], required=True),
                concept("FONC_MULT", "fonction"),
            ], required=True, fill_all="CHARGE"),
        ],
        "defaults": {"EXCIT": [{"CHARGE": None}]},
    },
    "MACRO_ELAS_MULT": {
        "doc": "U4.51.02",
        "fields": [
            concept("MODELE", "modele", required=True),
            concept("CHAM_MATER", "cham_mater", required=True),
            concept("CARA_ELEM", "cara_elem"),
            concept("CHAR_MECA_GLOBAL", "char_meca", multiple=True, label="Charges communes à tous les cas"),
            factor("CAS_CHARGE", [
                {"kw": "NOM_CAS", "type": "text", "required": True},
                concept("CHAR_MECA", "char_meca", multiple=True),
            ], required=True),
        ],
        "defaults": {"CAS_CHARGE": [{"NOM_CAS": "cas1", "CHAR_MECA": []}]},
    },
    "CALC_CHAMP": {
        "doc": "U4.81.04",
        "reuse": "RESULTAT",
        "fields": [
            concept("RESULTAT", RESULT_TYPES, required=True),
            multienum("CONTRAINTE", ["SIGM_NOEU", "SIGM_ELNO", "SIEF_NOEU", "SIEF_ELNO"]),
            multienum("CRITERES", ["SIEQ_NOEU", "SIEQ_ELNO", "SIEQ_ELGA", "EPEQ_NOEU"]),
            multienum("DEFORMATION", ["EPSI_NOEU", "EPSI_ELNO", "EPSI_ELGA"]),
        ],
        "defaults": {"CONTRAINTE": ["SIGM_NOEU"], "CRITERES": ["SIEQ_NOEU"]},
    },
    "IMPR_RESU": {
        "doc": "U4.91.01",
        "fields": [
            enum("FORMAT", ["MED"], default="MED", hidden=True),
            factor("RESU", [
                concept("RESULTAT", RESULT_TYPES),
                concept("MAILLAGE", "maillage"),
                multienum("NOM_CHAM", ["DEPL", "SIGM_NOEU", "SIEQ_NOEU", "EPSI_NOEU", "SIEF_ELGA", "REAC_NODA"],
                          help="Vide : tous les champs calculés."),
            ], required=True),
        ],
        "defaults": {"FORMAT": "MED", "RESU": [{"RESULTAT": None}]},
    },
}  # fmt: skip


TRANSLATED = ("label", "help")


def _translated(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: t(v) if k in TRANSLATED and isinstance(v, str) else _translated(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_translated(v) for v in value]
    return value


def public_schemas(translate: bool = False) -> dict:
    """Schémas pour le frontend ; libellés et aides dans la langue de l'interface si `translate`."""
    return {"schemas": _translated(SCHEMAS) if translate else SCHEMAS, "concept_types": CONCEPT_TYPES}


# --------------------------------------------------------------------------- texte → formulaire


class FormError(ValueError):
    pass


def _check(fields: list[dict], params: dict[str, Any], path: str) -> dict[str, Any]:
    """Vérifie que `params` tient dans `fields` et renvoie une version normalisée."""
    by_kw = {f["kw"]: f for f in fields}
    out: dict[str, Any] = {}
    for kw, value in params.items():
        field = by_kw.get(kw)
        name = f"{path}{kw}"
        if field is None:
            raise FormError(t("mot-clé {name} non géré par le formulaire", name=name))
        out[kw] = _check_value(field, value, name)
    return out


def _check_value(field: dict, value: Any, name: str) -> Any:
    kind = field["type"]
    if pyvalue.is_expr(value):
        raise FormError(t("{name} : expression Python « {expr} » non gérée par le formulaire", name=name, expr=value["$expr"]))
    if kind == "concept":
        values = value if isinstance(value, list) else [value]
        if not all(pyvalue.is_ref(v) for v in values):
            raise FormError(t("{name} : un nom de concept est attendu", name=name))
        return values if field.get("multiple") else values[0] if len(values) == 1 else _fail(name)
    if pyvalue.is_ref(value):
        raise FormError(t("{name} : variable Python « {ref} » non gérée par le formulaire", name=name, ref=value["$ref"]))
    if kind == "groups":
        values = value if isinstance(value, list) else [value]
        if not all(isinstance(v, str) for v in values):
            raise FormError(t("{name} : noms de groupes attendus", name=name))
        return values
    if kind == "flag":
        if value != "OUI":
            raise FormError(t("{name}='{value}' non géré", name=name, value=value))
        return value
    if kind == "enum":
        if value not in field["into"]:
            raise FormError(t("{name}='{value}' non proposé par le formulaire", name=name, value=value))
        return value
    if kind == "multienum":
        values = value if isinstance(value, list) else [value]
        unknown = [v for v in values if v not in field["into"]]
        if unknown:
            raise FormError(t("{name} : {values} non proposé par le formulaire", name=name, values=", ".join(map(str, unknown))))
        return values
    if kind in ("float", "int"):
        size = field.get("size", 1)
        values = value if isinstance(value, list) else [value]
        if len(values) != size and not (size > 1 and len(values) <= size):
            raise FormError(t("{name} : {size} valeur(s) attendue(s)", name=name, size=size))
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values):
            raise FormError(t("{name} : valeur numérique attendue", name=name))
        return values if size > 1 else values[0]
    if kind == "text":
        if not isinstance(value, str):
            raise FormError(t("{name} : texte attendu", name=name))
        return value
    if kind == "factor":
        items = value if isinstance(value, list) else [value]
        if not all(isinstance(i, dict) and not pyvalue.is_ref(i) for i in items):
            raise FormError(t("{name} : _F(...) attendu", name=name))
        if field.get("max") is not None and len(items) > field["max"]:
            raise FormError(t("{name} : au plus {max} occurrence(s)", name=name, max=field["max"]))
        checked = [_check(field["fields"], item, f"{name}/") for item in items]
        return checked[0] if field.get("max") == 1 else checked
    raise FormError(t("{name} : type de champ inconnu", name=name))


def _fail(name: str):
    raise FormError(t("{name} : un seul concept attendu", name=name))


def text_to_form(text: str) -> tuple[str, str | None, dict[str, Any]]:
    """(commande, concept, params) si le texte tient dans un formulaire, sinon FormError."""
    try:
        st = pyvalue.parse_statement(text.strip())
    except pyvalue.ParseError as exc:
        raise FormError(str(exc)) from exc
    schema = SCHEMAS.get(st.command)
    if schema is None:
        raise FormError(t("pas de formulaire pour {command}", command=st.command))
    params = dict(st.params)
    reuse = params.pop("reuse", None)
    if reuse is not None and not schema.get("reuse"):
        raise FormError(t("reuse non géré par ce formulaire"))
    for kw, default in AUTO_KEYWORDS.get(st.command, {}).items():
        if kw in params and kw != "FORMAT":
            if params[kw] != default:
                raise FormError(t("{kw}={value} : l'app gère ce mot-clé automatiquement ({kw}={default})", kw=kw, value=params[kw], default=default))
            del params[kw]
    checked = _check(schema["fields"], params, "")
    exclusive = [k for k in schema.get("exclusive", []) if k in checked]
    if len(exclusive) > 1:
        raise FormError(t("{keywords} dans le même bloc : non géré par le formulaire", keywords=t(" et ").join(exclusive)))
    return st.command, st.concept, checked


# --------------------------------------------------------------------------- formulaire → texte


def _ordered(fields: list[dict], params: dict[str, Any]) -> dict[str, Any]:
    """Mots-clés dans l'ordre du schéma, valeurs vides retirées."""
    out: dict[str, Any] = {}
    for field in fields:
        kw = field["kw"]
        if kw not in params:
            continue
        value = params[kw]
        if value is None or value == [] or value == "":
            continue
        if field["type"] == "factor":
            items = value if isinstance(value, list) else [value]
            items = [_ordered(field["fields"], i) for i in items]
            items = [i for i in items if i]
            if not items:
                continue
            value = items[0] if field.get("max") == 1 else items
        elif field["type"] in ("float", "int") and isinstance(value, list):
            if any(v is None for v in value):
                continue
            if field["type"] == "float":
                value = [float(v) for v in value]
        elif field["type"] == "float" and isinstance(value, (int, float)):
            value = float(value)  # 210000 → 210000.0 : un réel s'écrit en réel
        out[kw] = value
    return out


def render_form(command: str, concept: str | None, params: dict[str, Any], unit: int | None = None) -> str:
    schema = SCHEMAS.get(command)
    if schema is None:
        return pyvalue.render_statement(command, concept, params)
    ordered = _ordered(schema["fields"], params)
    reuse_kw = schema.get("reuse")
    if reuse_kw and concept and ordered.get(reuse_kw) == {"$ref": concept}:
        ordered = {"reuse": {"$ref": concept}, **ordered}
    if unit is not None:
        ordered["UNITE"] = unit
    return pyvalue.render_statement(command, concept, ordered)
