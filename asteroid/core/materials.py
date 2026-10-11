"""Bibliothèque de matériaux (SI) et copie convertie dans le projet.

La bibliothèque, commune à tous les projets, est un dossier `materiaux/` : un fichier
JSON par matériau, en SI. On partage un matériau en copiant son fichier, une
bibliothèque en déposant un dossier (les sous-dossiers sont lus). Quand un projet
utilise un matériau, l'app en
copie une version convertie dans les unités du projet (materials.json du projet) :
un ancien calcul reste reproductible même si la bibliothèque évolue.

C'est la seule conversion d'unités que fait l'app.
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .i18n import t
from .settings import config_dir, user_dir

Model = Literal["ELAS", "ELAS_ISTR", "ELAS_ORTH"]

# Constantes de chaque modèle (noms Code_Aster) et leur grandeur.
CONSTANTS: dict[str, dict[str, str]] = {
    "ELAS": {"E": "stress", "NU": "ratio", "ALPHA": "expansion"},
    "ELAS_ISTR": {"E_L": "stress", "E_N": "stress", "NU_LT": "ratio", "NU_LN": "ratio", "G_LN": "stress"},
    "ELAS_ORTH": {
        "E_L": "stress", "E_T": "stress", "E_N": "stress",
        "NU_LT": "ratio", "NU_LN": "ratio", "NU_TN": "ratio",
        "G_LT": "stress", "G_LN": "stress", "G_TN": "stress",
    },
}  # fmt: skip

# Facteurs SI → système du projet.
FACTORS: dict[str, dict[str, float]] = {
    "mm-N-MPa": {"stress": 1e-6, "density": 1e-12, "ratio": 1.0, "expansion": 1.0},
    "m-N-Pa": {"stress": 1.0, "density": 1.0, "ratio": 1.0, "expansion": 1.0},
}


class Strength(BaseModel):
    name: str  # ex. « Traction XY »
    value: float  # Pa


class Material(BaseModel):
    """Matériau de la bibliothèque, en SI."""

    id: str = ""
    name: str
    description: str = ""
    source: str = ""  # fiche technique, article, essai perso…
    model: Model = "ELAS"
    constants: dict[str, float] = Field(default_factory=dict)  # SI, noms Code_Aster
    rho: float | None = None  # kg/m³
    strengths: list[Strength] = Field(default_factory=list)  # Pa, pour un futur calcul de marges

    def cleaned(self) -> "Material":
        """Copie aux valeurs arrondies à 12 chiffres significatifs (bruit des conversions d'affichage)."""
        return self.model_copy(
            update={
                "constants": {k: _clean(v) for k, v in self.constants.items()},
                "rho": None if self.rho is None else _clean(self.rho),
                "strengths": [Strength(name=s.name, value=_clean(s.value)) for s in self.strengths],
            }
        )


def slug(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text or "materiau"


# Valeurs de départ : matériaux métalliques courants, sources citées.
SEED = [
    Material(
        id="acier_s235",
        name="Acier S235",
        description="Acier de construction non allié",
        source="EN 1993-1-1 : § 3.2.6 (E, ν, α), tableau 3.1 (fy, fu, t ≤ 40 mm) ; EN 1991-1-1 (ρ)",
        constants={"E": 210e9, "NU": 0.3, "ALPHA": 12e-6},
        rho=7850,
        strengths=[Strength(name="Limite élastique fy", value=235e6), Strength(name="Rupture fu", value=360e6)],
    ),
    Material(
        id="aluminium_6061_t6",
        name="Aluminium 6061-T6",
        description="Alliage d'aluminium corroyé, état T6",
        source="ASM Aerospace Specification Metals, fiche 6061-T6",
        constants={"E": 68.9e9, "NU": 0.33, "ALPHA": 23.6e-6},
        rho=2700,
        strengths=[Strength(name="Limite élastique Rp0,2", value=276e6), Strength(name="Rupture Rm", value=310e6)],
    ),
]


SI_NOTE = "SI (Pa, kg/m³, 1/K)"


def library_dir() -> Path:
    return user_dir("materiaux")


def material_file(material_id: str) -> Path:
    root = library_dir().resolve()
    path = (root / f"{material_id}.json").resolve()
    if root not in path.parents:
        raise ValueError(t("Identifiant de matériau invalide : {id}", id=material_id))
    return path


def ensure_library() -> Path:
    """Crée le dossier au premier usage : matériaux de départ, ou reprise de l'ancien
    materials.json unique. Un dossier existant n'est jamais complété (un matériau
    supprimé ne revient pas)."""
    root = library_dir()
    if root.is_dir():
        return root
    items = [_translated_seed(m) for m in SEED]
    old = config_dir() / "materials.json"
    if old.exists():
        try:
            items = [Material.model_validate(m) for m in json.loads(old.read_text()).get("materials", [])]
        except ValueError:
            pass
    root.mkdir(parents=True, exist_ok=True)
    for m in items:
        save_material(m)
    return root


def _translated_seed(material: Material) -> Material:
    m = material.model_copy(deep=True)
    m.name, m.description = t(m.name), t(m.description)
    for s in m.strengths:
        s.name = t(s.name)
    return m


def load_library(errors: list[str] | None = None) -> list[Material]:
    """Matériaux du dossier ; un fichier illisible est signalé dans `errors`, pas bloquant."""
    root = ensure_library()
    items = []
    for path in sorted(root.rglob("*.json")):
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts):
            continue
        try:
            m = Material.model_validate_json(path.read_text())
        except ValueError as exc:
            if errors is not None:
                errors.append(f"{rel} : {str(exc).splitlines()[0]}")
            continue
        m.id = rel.with_suffix("").as_posix()
        items.append(m)
    return items


def save_material(material: Material) -> Material:
    material = material.cleaned()
    path = material_file(material.id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"units": SI_NOTE, **material.model_dump(exclude={"id"})}
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return material


def delete_material(material_id: str) -> None:
    material_file(material_id).unlink()


def read_materials_file(path: Path) -> list[Material]:
    """Matériaux d'un fichier à importer : un matériau, une liste, {"materials": [...]}
    (ancienne bibliothèque) ou le materials.json d'un projet (copies figées)."""
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "materials" in data:
        data = data["materials"]
        if isinstance(data, dict):
            data = [entry.get("material", entry) for entry in data.values()]
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError(t("format non reconnu"))
    return [Material.model_validate(m) for m in data]


def import_file(path: Path) -> list[Material]:
    """Copie les matériaux du fichier dans la bibliothèque, sous des identifiants libres."""
    taken = {m.id for m in load_library()}
    added = []
    for m in read_materials_file(path):
        m.id = unique_id(m.name, taken)
        taken.add(m.id)
        added.append(save_material(m))
    return added


def unique_id(name: str, taken: set[str]) -> str:
    base = slug(name)
    candidate, n = base, 2
    while candidate in taken:
        candidate, n = f"{base}_{n}", n + 1
    return candidate


# --------------------------------------------------------------------------- conversion


def _clean(x: float) -> float:
    """1240 × 1e-12 = 1.2400000000000001e-09 : arrondi à 12 chiffres significatifs."""
    return float(f"{x:.12g}")


def convert(material: Material, units: str) -> dict:
    """Valeurs du matériau dans le système du projet, prêtes pour DEFI_MATERIAU."""
    f = FACTORS[units]
    kinds = CONSTANTS[material.model]
    values = {k: _clean(v * f[kinds[k]]) for k, v in material.constants.items() if k in kinds}
    if material.rho is not None:
        values["RHO"] = _clean(material.rho * f["density"])
    return {
        "constants": values,
        "strengths": [{"name": s.name, "value": _clean(s.value * f["stress"])} for s in material.strengths],
    }


# Gardées dans la bibliothèque mais pas écrites dans DEFI_MATERIAU (inutiles en statique pure).
NOT_WRITTEN = {"ALPHA"}


def defi_materiau_params(material: Material, units: str) -> dict:
    """Paramètres du formulaire DEFI_MATERIAU (mot-clé facteur du modèle)."""
    values = convert(material, units)["constants"]
    return {material.model: {k: v for k, v in values.items() if k not in NOT_WRITTEN}}


# --------------------------------------------------------------------------- copie dans le projet

PROJECT_FILE = "materials.json"


def load_project_materials(project_dir: Path) -> dict:
    path = project_dir / PROJECT_FILE
    if not path.exists():
        return {}
    return json.loads(path.read_text()).get("materials", {})


def copy_to_project(project_dir: Path, material: Material, units: str) -> dict:
    """Copie figée et convertie du matériau dans materials.json du projet."""
    entries = load_project_materials(project_dir)
    entry = {
        "material": material.model_dump(),
        "units": units,
        "converted": convert(material, units),
        "copied": datetime.now().isoformat(timespec="seconds"),
    }
    entries[material.id] = entry
    path = project_dir / PROJECT_FILE
    path.write_text(json.dumps({"materials": entries}, indent=2, ensure_ascii=False))
    return entry
