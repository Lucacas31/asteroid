"""Génération du .comm et du .export à partir des blocs du projet."""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from pathlib import PurePath

from . import forms, pyvalue
from .i18n import t
from .model import Block, ExtraFile, Project

COMM_NAME = "run.comm"
EXPORT_NAME = "run.export"
MESH_NAME = "mesh.med"
MESSAGE_NAME = "message"

# Concepts par défaut pour les commandes courantes. Les autres prennent le nom de
# la commande en minuscules, tronqué au premier mot.
DEFAULT_CONCEPTS = {
    "LIRE_MAILLAGE": "mail",
    "MODI_MAILLAGE": "mail",
    "CREA_MAILLAGE": "mail",
    "AFFE_MODELE": "model",
    "DEFI_MATERIAU": "mat",
    "AFFE_MATERIAU": "chmat",
    "AFFE_CARA_ELEM": "cara",
    "AFFE_CHAR_MECA": "cl",
    "MECA_STATIQUE": "resu",
    "MACRO_ELAS_MULT": "resu",
    "STAT_NON_LINE": "resu",
    "CALC_CHAMP": "resu",
    "DEFI_FONCTION": "fonc",
    "DEFI_LIST_REEL": "linst",
}

# Commandes qui modifient un concept existant (reuse) : même nom de concept.
REUSE_COMMANDS = {"MODI_MAILLAGE", "CALC_CHAMP"}

# Commandes sans concept produit.
NO_RESULT = {
    "DEBUT", "FIN", "POURSUITE", "IMPR_RESU", "IMPR_TABLE", "IMPR_FONCTION",
    "TEST_RESU", "TEST_TABLE", "TEST_FONCTION", "DETRUIRE", "DEFI_FICHIER", "IMPR_CO",
}

TEMPLATES = {
    "LIRE_MAILLAGE": 'mail = LIRE_MAILLAGE(FORMAT="MED")',
    "MODI_MAILLAGE": 'mail = MODI_MAILLAGE(reuse=mail, MAILLAGE=mail, ORIE_PEAU=_F(GROUP_MA_PEAU=("",)))',
    "AFFE_MODELE": (
        "model = AFFE_MODELE(\n    MAILLAGE=mail,\n"
        '    AFFE=_F(TOUT="OUI", PHENOMENE="MECANIQUE", MODELISATION="3D"),\n)'
    ),
    "DEFI_MATERIAU": "mat = DEFI_MATERIAU(ELAS=_F(E=210000.0, NU=0.3, RHO=7.85e-09))",
    "AFFE_MATERIAU": 'chmat = AFFE_MATERIAU(MAILLAGE=mail, AFFE=_F(TOUT="OUI", MATER=mat))',
    "AFFE_CHAR_MECA": 'cl = AFFE_CHAR_MECA(\n    MODELE=model,\n    DDL_IMPO=_F(GROUP_MA=("",), DX=0.0, DY=0.0, DZ=0.0),\n)',
    "MECA_STATIQUE": "resu = MECA_STATIQUE(MODELE=model, CHAM_MATER=chmat, EXCIT=_F(CHARGE=cl))",
    "CALC_CHAMP": (
        "resu = CALC_CHAMP(\n    reuse=resu,\n    RESULTAT=resu,\n"
        '    CONTRAINTE=("SIGM_NOEU",),\n    CRITERES=("SIEQ_NOEU",),\n    FORCE=("REAC_NODA",),\n)'
    ),
    "IMPR_RESU": 'IMPR_RESU(FORMAT="MED", RESU=_F(RESULTAT=resu))',
}


def default_concept(command: str, taken: set[str]) -> str | None:
    if command in NO_RESULT:
        return None
    base = DEFAULT_CONCEPTS.get(command) or command.split("_")[0].lower()[:8]
    if command in REUSE_COMMANDS:
        return base
    name, n = base, 2
    while name in taken:
        name, n = f"{base}{n}", n + 1
    return name


def new_block(command: str, taken: set[str]) -> Block:
    """Bloc graphique pré-rempli si la commande a un formulaire, sinon bloc texte."""
    schema = forms.SCHEMAS.get(command)
    if schema is None:
        return new_text_block(command, taken)
    concept = default_concept(command, taken)
    return Block(command=command, concept=concept, mode="form", params=json_copy(schema["defaults"]))


def json_copy(value):
    import copy

    return copy.deepcopy(value)


def new_text_block(command: str, taken: set[str]) -> Block:
    concept = default_concept(command, taken)
    template = TEMPLATES.get(command)
    if template is None:
        from .catalog import load_catalog

        cat = load_catalog()
        if cat and cat.command(command):
            return Block(command=command, concept=concept, mode="text", text=cat.skeleton(command, concept))
    default = DEFAULT_CONCEPTS.get(command)
    if template is None:
        text = f"{concept} = {command}()" if concept else f"{command}()"
    elif concept and default and template.startswith(default + " ="):
        text = concept + template[len(default):]
    else:
        text = template
    return Block(command=command, concept=concept, mode="text", text=text)


# --------------------------------------------------------------------------- analyse


@dataclass
class BlockInfo:
    id: str
    command: str
    concept: str | None
    error: str | None = None
    start_line: int = 0  # dans le .comm généré, 1-indexé
    end_line: int = 0
    issues: list[dict] = field(default_factory=list)  # validation par le catalogue


def block_source(block: Block, unit: int | None = None) -> str:
    if block.mode == "form":
        return forms.render_form(block.command, block.concept, block.params, unit)
    return block.text.strip()


def _form_units(blocks: list[Block]) -> dict[str, int]:
    """Unités des IMPR_RESU graphiques : 80 pour le premier, puis la suivante libre."""
    used = set()
    for b in blocks:
        if b.mode == "text":
            for name, kws in _calls(b.text):
                if isinstance(kws.get("UNITE"), int):
                    used.add(kws["UNITE"])
    units, unit = {}, 80
    for b in blocks:
        if b.mode == "form" and b.command == "IMPR_RESU":
            while unit in used:
                unit += 1
            units[b.id] = unit
            used.add(unit)
    return units


def analyze_text(text: str) -> tuple[str, str | None, str | None]:
    """(commande, concept, erreur) d'un bloc texte, sans exiger une seule instruction."""
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return "", None, t("erreur de syntaxe ligne {line} : {error}", line=exc.lineno, error=exc.msg)
    for node in tree.body:
        try:
            st = pyvalue.statement_from_node(node, text)
            return st.command, st.concept, None
        except pyvalue.ParseError:
            continue
    return "", None, None


# --------------------------------------------------------------------------- unités


@dataclass
class FileEntry:
    kind: str  # type de fichier pour le .export (mmed, rmed, resu…)
    name: str  # nom relatif au dossier du run
    mode: str  # D (donnée) ou R (résultat)
    unit: int


@dataclass
class CommResult:
    comm: str
    export: str
    blocks: list[BlockInfo]
    files: list[FileEntry]
    warnings: list[str] = field(default_factory=list)
    mesh_scale: float = 1.0
    unattached: list[dict] = field(default_factory=list)  # [{"command", "unit"}] sans fichier  # produit des MODI_MAILLAGE(ECHELLE=...) du .comm

    def to_dict(self) -> dict:
        return asdict(self)


IMPR_RESU_UNITS = {"MED": 80, "RESULTAT": 8, "ASTER": 26, "GMSH": 37, "IDEAS": 30}
RESULT_KINDS = {
    "MED": ("rmed", "resultat{}.rmed"),
    "RESULTAT": ("resu", "resultat{}.resu"),
    "ASTER": ("resu", "resultat{}.aster"),
    "GMSH": ("msh", "resultat{}.msh"),
    "IDEAS": ("resu", "resultat{}.unv"),
}


def _keywords(call: ast.Call) -> dict[str, object]:
    return {kw.arg: pyvalue.literal(kw.value) for kw in call.keywords if kw.arg}


def _calls(source: str):
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            yield node.func.id, _keywords(node)


def run_name(extra: ExtraFile) -> str:
    """Nom du fichier dans le dossier du run."""
    return PurePath(extra.path).name if extra.mode == "D" else extra.path


def collect_files(
    sources: list[str], has_mesh: bool, extra: list[ExtraFile] | tuple = ()
) -> tuple[list[FileEntry], list[str], list[dict]]:
    """Associe les unités logiques utilisées dans le .comm à des fichiers du run.

    Renvoie (fichiers, avertissements, unités sans fichier). Les fichiers rattachés
    par l'utilisateur (`extra`) sont prioritaires.
    """
    files: dict[int, FileEntry] = {f.unit: FileEntry(f.kind, run_name(f), f.mode, f.unit) for f in extra}
    warnings: list[str] = []
    unattached: list[dict] = []
    result_count: dict[str, int] = {}

    def missing(name: str, unit: int, message: str) -> None:
        if unit in files:
            return
        warnings.append(message)
        if not any(u["unit"] == unit for u in unattached):
            unattached.append({"command": name, "unit": unit})

    def add(entry: FileEntry) -> None:
        if entry.unit not in files:
            files[entry.unit] = entry

    for source in sources:
        for name, kws in _calls(source):
            unit = kws.get("UNITE")
            if name == "LIRE_MAILLAGE":
                fmt = kws.get("FORMAT") or "MED"
                unit = unit if isinstance(unit, int) else 20
                if fmt != "MED":
                    missing(name, unit, t("LIRE_MAILLAGE FORMAT={format} : unité {unit} non rattachée à un fichier", format=fmt, unit=unit))
                elif not has_mesh:
                    warnings.append(t("LIRE_MAILLAGE présent mais aucun maillage sélectionné"))
                elif any(f.kind == "mmed" for f in files.values()) and unit not in files:
                    warnings.append(t("LIRE_MAILLAGE : unité {unit} non rattachée (un seul maillage par projet)", unit=unit))
                else:
                    add(FileEntry("mmed", MESH_NAME, "D", unit))
            elif name in ("IMPR_RESU", "IMPR_TABLE"):
                if name == "IMPR_TABLE":
                    fmt = "RESULTAT"
                    default = 8
                else:
                    fmt = kws.get("FORMAT") or "MED"
                    default = IMPR_RESU_UNITS.get(str(fmt), 8)
                unit = unit if isinstance(unit, int) else default
                if unit in files:
                    continue
                kind, pattern = RESULT_KINDS.get(str(fmt), ("resu", "resultat{}.txt"))
                n = result_count.get(kind, 0)
                result_count[kind] = n + 1
                add(FileEntry(kind, pattern.format("" if n == 0 else f"_{unit}"), "R", unit))
            elif isinstance(unit, int) and name not in ("DEFI_FICHIER",):
                missing(name, unit, t("{command} : UNITE={unit} non rattachée à un fichier", command=name, unit=unit))
    return sorted(files.values(), key=lambda f: (f.mode != "D", f.unit)), warnings, unattached


# --------------------------------------------------------------------------- génération


def generate(project: Project, mesh_groups: dict[str, set[str]] | None = None, validate: bool = True) -> CommResult:
    lines = ["DEBUT()", ""]
    infos: list[BlockInfo] = []
    sources: list[str] = []
    units = _form_units(project.blocks)
    for block in project.blocks:
        unit = units.get(block.id)
        source = block_source(block, None if unit == 80 else unit)
        if block.mode == "text":
            command, concept, error = analyze_text(source)
        else:
            command, concept, error = block.command, block.concept, None
        start = len(lines) + 1
        body = source.splitlines() or [""]
        lines.extend(body)
        infos.append(BlockInfo(block.id, command, concept, error, start, start + len(body) - 1))
        lines.append("")
        sources.append(source)
    lines.append("FIN()")
    comm = "\n".join(lines) + "\n"

    if validate:
        from .catalog import Validator, load_catalog

        cat = load_catalog()
        if cat is not None:
            validator = Validator(cat, mesh_groups)
            for info, source in zip(infos, sources):
                info.issues = [i.to_dict() for i in validator.validate_source(source)]

    files, warnings, unattached = collect_files(sources, project.mesh is not None, project.files)
    return CommResult(
        comm, generate_export(project, files), infos, files, warnings, mesh_scale(sources), unattached
    )


def mesh_scale(sources: list[str]) -> float:
    """Facteur d'échelle appliqué au maillage par MODI_MAILLAGE(ECHELLE=...)."""
    scale = 1.0
    for source in sources:
        for name, kws in _calls(source):
            factor = kws.get("ECHELLE")
            if name == "MODI_MAILLAGE" and isinstance(factor, (int, float)) and factor > 0:
                scale *= factor
    return scale


def generate_export(project: Project, files: list[FileEntry]) -> str:
    lines = [
        f"P time_limit {project.time_limit}",
        f"P memory_limit {project.memory_limit}",
        f"F comm {COMM_NAME} D 1",
    ]
    lines += [f"F {f.kind} {f.name} {f.mode} {f.unit}" for f in files]
    lines.append(f"F mess {MESSAGE_NAME} R 6")
    return "\n".join(lines) + "\n"


def block_for_line(infos: list[BlockInfo], line: int | None) -> str | None:
    if line is None:
        return None
    for info in infos:
        if info.start_line <= line <= info.end_line:
            return info.id
    return None

