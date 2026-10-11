"""Résumé des résultats d'un run, lu dans le .rmed : chiffres clés, marges, équilibre.

- Déplacement max (norme de DEPL) et Von Mises max (SIEQ_NOEU, ou calculé depuis
  SIGM_NOEU), par concept résultat et numéro d'ordre.
- Marges : résistances des matériaux de la bibliothèque (copiées dans run.json au
  lancement, dans les unités du projet) divisées par le Von Mises max de leur zone
  d'AFFE_MATERIAU. Le critère est affiché tel quel : l'app donne le chiffre.
- Équilibre : la charge appliquée est recalculée par Asteroid à partir du .comm et
  de la géométrie du maillage du .rmed (après MODI_MAILLAGE) ; si REAC_NODA a été
  imprimé, la somme des réactions doit en être l'opposée. Ce qui n'est pas
  calculable (fonction, FONC_MULT, mot-clé non géré) est dit, jamais deviné.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import h5py
import numpy as np

from . import pyvalue
from .i18n import N_
from .med import TETS, CellBlock, Mesh, read_med, surface_polygons, triangulate

SUMMARY_FILE = "resume.json"
SUMMARY_VERSION = 1
UNITS = {
    "mm-N-MPa": {"length": "mm", "stress": "MPa", "force": "N"},
    "m-N-Pa": {"length": "m", "stress": "Pa", "force": "N"},
}
LINEAR = {"PO1", "SE2", "TR3", "QU4", "TE4", "PY5", "PE6", "HE8"}
# Mots-clés d'AFFE_CHAR_MECA sans force appliquée (conditions aux limites, liaisons).
NO_FORCE = {"MODELE", "DDL_IMPO", "FACE_IMPO", "ARETE_IMPO", "INFO", "VERI_NORM", "DOUBLE_LAGRANGE", "VERI_AFFE"}
SOLVERS = {"MECA_STATIQUE", "MACRO_ELAS_MULT"}


class Unsupported(Exception):
    """Charge que le contrôle ne sait pas recalculer ; le message dit pourquoi."""

    def __init__(self, template: str, **values: Any) -> None:
        super().__init__(template)
        self.note = {"template": template, "vars": values}


def note(template: str, **values: Any) -> dict:
    return {"template": template, "vars": values}


# --------------------------------------------------------------------------- champs


@dataclass
class Step:
    order: int
    inst: float
    values: np.ndarray  # (composantes, nœuds du profil)
    nodes: np.ndarray | None  # indices 0-based des nœuds, None : tous


@dataclass
class Field:
    concept: str
    name: str
    components: list[str]
    steps: list[Step] = field(default_factory=list)

    def component(self, step: Step, name: str) -> np.ndarray:
        return step.values[self.components.index(name)]


def read_fields(path: Path) -> list[Field]:
    """Champs aux nœuds du fichier (les champs aux points de Gauss sont ignorés)."""
    out = []
    with h5py.File(path, "r") as f:
        if "CHA" not in f:
            return []
        for name, g in f["CHA"].items():
            if len(name) <= 8:
                continue
            ncomp = int(g.attrs["NCO"])
            raw = g.attrs["NOM"]
            raw = raw.decode() if isinstance(raw, bytes) else str(raw)
            comps = [raw[i:i + 16].strip() for i in range(0, 16 * ncomp, 16)]
            fld = Field(name[:8].rstrip("_"), name[8:], comps)
            for key in sorted(g):
                step = g[key]
                if "NOE" not in step:
                    continue
                for pfl_name, data in step["NOE"].items():
                    values = np.asarray(data["CO"][()], dtype=np.float64).reshape(ncomp, -1)
                    nodes = None
                    if pfl_name != "MED_NO_PROFILE_INTERNAL" and "PROFILS" in f and pfl_name in f["PROFILS"]:
                        nodes = np.asarray(f["PROFILS"][pfl_name]["PFL"][()], dtype=np.int64) - 1
                    fld.steps.append(Step(int(step.attrs["NOR"]), float(step.attrs["PDT"]), values, nodes))
                    break
            if fld.steps:
                out.append(fld)
    return out


def _extreme(values: np.ndarray, nodes: np.ndarray | None, coords: np.ndarray) -> dict:
    i = int(np.argmax(values))
    node = int(nodes[i]) if nodes is not None else i
    return {"max": float(values[i]), "node": node + 1, "xyz": coords[node].tolist()}


def von_mises(sig: Field, step: Step) -> np.ndarray:
    xx, yy, zz, xy, xz, yz = (sig.component(step, c) for c in ("SIXX", "SIYY", "SIZZ", "SIXY", "SIXZ", "SIYZ"))
    return np.sqrt(0.5 * ((xx - yy) ** 2 + (yy - zz) ** 2 + (zz - xx) ** 2) + 3 * (xy**2 + xz**2 + yz**2))


def _vmis(fields: dict[str, Field], order: int) -> tuple[np.ndarray, np.ndarray | None, str] | None:
    """(valeurs, nœuds, source) du Von Mises aux nœuds pour ce numéro d'ordre."""
    sieq = fields.get("SIEQ_NOEU")
    if sieq is not None and "VMIS" in sieq.components:
        for st in sieq.steps:
            if st.order == order:
                return sieq.component(st, "VMIS"), st.nodes, "SIEQ_NOEU"
    sigm = fields.get("SIGM_NOEU")
    if sigm is not None and {"SIXX", "SIYY", "SIZZ", "SIXY", "SIXZ", "SIYZ"} <= set(sigm.components):
        for st in sigm.steps:
            if st.order == order:
                return von_mises(sigm, st), st.nodes, "SIGM_NOEU"
    return None


# --------------------------------------------------------------------------- .comm


def statements(comm: str) -> list[pyvalue.Statement]:
    tree = ast.parse(comm)
    out = []
    for node in tree.body:
        try:
            out.append(pyvalue.statement_from_node(node, comm))
        except pyvalue.ParseError:
            continue
    return out


def as_list(value: Any) -> list:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def ref(value: Any) -> str | None:
    return value["$ref"] if pyvalue.is_ref(value) else None


def num(value: Any, kw: str) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    raise Unsupported(N_("{kw} : valeur non numérique (variable ou fonction)"), kw=kw)


class Comm:
    """Commandes du .comm d'un run, indexées par concept (première définition hors reuse)."""

    def __init__(self, comm: str) -> None:
        self.statements = statements(comm)
        self.defs: dict[str, pyvalue.Statement] = {}
        for st in self.statements:
            if st.concept and "reuse" not in st.params:
                self.defs.setdefault(st.concept, st)

    def cases(self, concept: str) -> tuple[pyvalue.Statement | None, dict[int, list[dict]]]:
        """(commande de calcul, {ordre: [{"CHARGE": nom, "FONC_MULT": …}]})."""
        st = self.defs.get(concept)
        if st is None or st.command not in SOLVERS:
            return st, {}
        if st.command == "MECA_STATIQUE":
            excit = [{"CHARGE": ref(e.get("CHARGE")), "FONC_MULT": e.get("FONC_MULT")} for e in as_list(st.params.get("EXCIT"))]
            return st, {1: excit}
        common = [{"CHARGE": ref(c)} for c in as_list(st.params.get("CHAR_MECA_GLOBAL"))]
        out = {}
        for i, case in enumerate(as_list(st.params.get("CAS_CHARGE")), start=1):
            out[i] = common + [{"CHARGE": ref(c)} for c in as_list(case.get("CHAR_MECA"))]
        return st, out

    def zones(self, solver: pyvalue.Statement | None) -> list[dict]:
        """Occurrences d'AFFE de l'AFFE_MATERIAU du calcul : [{"tout", "groups", "mater"}]."""
        chmat = ref(solver.params.get("CHAM_MATER")) if solver else None
        st = self.defs.get(chmat) if chmat else None
        if st is None or st.command != "AFFE_MATERIAU":
            return []
        return [
            {
                "tout": a.get("TOUT") == "OUI",
                "groups": [g for g in as_list(a.get("GROUP_MA")) if isinstance(g, str)],
                "mater": [m for m in (ref(x) for x in as_list(a.get("MATER"))) if m],
            }
            for a in as_list(st.params.get("AFFE"))
        ]

    def rho(self, mater: str) -> float | None:
        st = self.defs.get(mater)
        if st is None or st.command != "DEFI_MATERIAU":
            return None
        for kw in ("ELAS", "ELAS_ISTR", "ELAS_ORTH"):
            for occ in as_list(st.params.get(kw)):
                value = occ.get("RHO")
                if isinstance(value, (int, float)):
                    return float(value)
        return None


# --------------------------------------------------------------------------- géométrie


def _cells(mesh: Mesh, groups: list[str], tout: bool, dim: int, kw: str) -> list[CellBlock]:
    if tout:
        return [b for b in mesh.cells if b.dim == dim]
    blocks = []
    for name in groups:
        try:
            g = mesh.group("GROUP_MA", name)
        except KeyError:
            raise Unsupported(N_("{kw} : groupe « {name} » absent du maillage du résultat"), kw=kw, name=name) from None
        blocks += [b for b in mesh.group_cells(g) if b.dim == dim]
    return blocks


def _vector_sum_area(mesh: Mesh, blocks: list[CellBlock]) -> np.ndarray:
    """Σ n dA des faces, orientées par leur connectivité (celle qu'utilise Code_Aster)."""
    tris = triangulate(*surface_polygons(blocks))
    if not len(tris):
        return np.zeros(3)
    a, b, c = (mesh.coords[tris[:, i]] for i in range(3))
    return 0.5 * np.cross(b - a, c - a).sum(axis=0)


def _cell_volumes(mesh: Mesh, block: CellBlock) -> np.ndarray:
    total = np.zeros(len(block.corners))
    for t in TETS[block.shape]:
        a, b, c, d = (mesh.coords[block.corners[:, i]] for i in t)
        total += np.abs(np.einsum("ij,ij->i", b - a, np.cross(c - a, d - a))) / 6.0
    return total


def _occurrence_force(kw: str, occ: dict) -> np.ndarray:
    return np.array([num(occ[c], f"{kw}/{c}") if c in occ else 0.0 for c in ("FX", "FY", "FZ")])


def charge_force(st: pyvalue.Statement, mesh: Mesh, comm: Comm, zones: list[dict]) -> np.ndarray:
    """Résultante des forces d'un AFFE_CHAR_MECA (N)."""
    if st.command == "AFFE_CHAR_CINE":
        return np.zeros(3)
    if st.command != "AFFE_CHAR_MECA":
        raise Unsupported(N_("{command} : charge non recalculée"), command=st.command)
    total = np.zeros(3)
    for kw, value in st.params.items():
        if kw in NO_FORCE or kw.startswith("LIAISON"):
            continue
        for occ in as_list(value):
            groups = [g for g in as_list(occ.get("GROUP_MA")) if isinstance(g, str)]
            tout = occ.get("TOUT") == "OUI"
            if any(k in occ for k in ("MAILLE", "NOEUD", "SANS_GROUP_MA")):
                raise Unsupported(N_("{kw} : MAILLE, NOEUD ou SANS_GROUP_MA non pris en compte"), kw=kw)
            if kw == "FORCE_FACE":
                blocks = _cells(mesh, groups, tout, 2, kw)
                total += _occurrence_force(kw, occ) * mesh.measure(blocks, 2) if blocks else 0
            elif kw == "FORCE_ARETE":
                blocks = _cells(mesh, groups, tout, 1, kw)
                total += _occurrence_force(kw, occ) * mesh.measure(blocks, 1) if blocks else 0
            elif kw == "FORCE_INTERNE":
                blocks = _cells(mesh, groups, tout, 3, kw)
                total += _occurrence_force(kw, occ) * sum(_cell_volumes(mesh, b).sum() for b in blocks)
            elif kw == "PRES_REP":
                blocks = _cells(mesh, groups, tout, 2, kw)
                total -= num(occ.get("PRES"), f"{kw}/PRES") * _vector_sum_area(mesh, blocks)
            elif kw == "FORCE_NODALE":
                total += _occurrence_force(kw, occ) * _node_count(mesh, occ, kw)
            elif kw == "PESANTEUR":
                if groups or tout:
                    raise Unsupported(N_("PESANTEUR restreinte à des groupes : non recalculée"))
                g = num(occ.get("GRAVITE"), "PESANTEUR/GRAVITE")
                d = np.array([num(x, "PESANTEUR/DIRECTION") for x in as_list(occ.get("DIRECTION"))])
                if len(d) != 3 or not np.linalg.norm(d):
                    raise Unsupported(N_("PESANTEUR : DIRECTION invalide"))
                total += g * d / np.linalg.norm(d) * _mass(mesh, comm, zones)
            else:
                raise Unsupported(N_("{kw} : non pris en compte par le contrôle"), kw=kw)
    return total


def _node_count(mesh: Mesh, occ: dict, kw: str) -> int:
    nodes: set[int] = set()
    for name in as_list(occ.get("GROUP_NO")):
        try:
            nodes |= set(mesh.group_nodes(mesh.group("GROUP_NO", name)).tolist())
        except KeyError:
            raise Unsupported(N_("{kw} : groupe « {name} » absent du maillage du résultat"), kw=kw, name=name) from None
    for name in as_list(occ.get("GROUP_MA")):
        try:
            blocks = mesh.group_cells(mesh.group("GROUP_MA", name))
        except KeyError:
            raise Unsupported(N_("{kw} : groupe « {name} » absent du maillage du résultat"), kw=kw, name=name) from None
        if any(b.type not in LINEAR for b in blocks):
            # Les nœuds milieux ne sont pas lus : le nombre de nœuds serait faux.
            raise Unsupported(N_("{kw} sur GROUP_MA d'éléments quadratiques : non recalculée"), kw=kw)
        for b in blocks:
            nodes |= set(b.corners.ravel().tolist())
    return len(nodes)


def _mass(mesh: Mesh, comm: Comm, zones: list[dict]) -> float:
    if not zones:
        raise Unsupported(N_("PESANTEUR : AFFE_MATERIAU du calcul introuvable"))
    mass = 0.0
    for block in (b for b in mesh.cells if b.dim == 3):
        rho = np.full(len(block.corners), np.nan)
        for z in zones:  # une occurrence plus loin remplace les précédentes, comme dans Code_Aster
            value = next((r for r in (comm.rho(m) for m in z["mater"]) if r is not None), None)
            if z["tout"]:
                mask = np.ones(len(block.corners), bool)
            else:
                fams = set()
                for name in z["groups"]:
                    try:
                        fams |= mesh.group("GROUP_MA", name).families
                    except KeyError:
                        continue
                mask = np.isin(block.families, list(fams))
            if mask.any() and value is None:
                raise Unsupported(N_("PESANTEUR : RHO absent ou non numérique dans DEFI_MATERIAU"))
            rho[mask] = value if value is not None else np.nan
        mass += float(np.nansum(rho * _cell_volumes(mesh, block)))
    return mass


def applied_load(comm: Comm, mesh: Mesh, excit: list[dict], zones: list[dict]) -> tuple[list[float] | None, dict | None]:
    total = np.zeros(3)
    try:
        for e in excit:
            if e.get("FONC_MULT") is not None:
                raise Unsupported(N_("FONC_MULT dans EXCIT : charge non recalculée"))
            st = comm.defs.get(e.get("CHARGE") or "")
            if st is None:
                raise Unsupported(N_("charge « {name} » introuvable dans le .comm"), name=e.get("CHARGE"))
            total += charge_force(st, mesh, comm, zones)
    except Unsupported as exc:
        return None, exc.note
    return total.tolist(), None


# --------------------------------------------------------------------------- résumé


def _zone_nodes(mesh: Mesh, zone: dict) -> np.ndarray | None:
    """Nœuds d'une zone d'AFFE_MATERIAU ; None : tout le maillage."""
    if zone["tout"]:
        return None
    nodes = []
    for name in zone["groups"]:
        try:
            for b in mesh.group_cells(mesh.group("GROUP_MA", name)):
                nodes.append(b.corners.ravel())
        except KeyError:
            continue
    return np.unique(np.concatenate(nodes)) if nodes else np.empty(0, np.int64)


def _margins(mesh: Mesh, zones: list[dict], materials: dict, vm: tuple, units: str) -> list[dict]:
    values, nodes, _ = vm
    full = np.full(len(mesh.coords), np.nan)
    full[nodes if nodes is not None else slice(None)] = values
    out = []
    for z in zones:
        zn = _zone_nodes(mesh, z)
        zone_vm = full if zn is None else full[zn]
        vmax = float(np.nanmax(zone_vm)) if np.isfinite(zone_vm).any() else None
        for m in z["mater"]:
            mat = materials.get(m)
            row = {"zone": "TOUT" if z["tout"] else ", ".join(z["groups"]), "concept": m, "vmis_max": vmax}
            if mat is None:
                row["note"] = note(N_("matériau hors bibliothèque : pas de résistance connue"))
            elif mat.get("units") != units:
                row["note"] = note(N_("matériau converti en {units}, projet en {project}"), units=mat.get("units"), project=units)
            else:
                row |= {"material": mat["name"], "model": mat["model"]}
                row["strengths"] = [
                    {"name": s["name"], "value": s["value"], "rf": s["value"] / vmax if vmax else None}
                    for s in mat.get("strengths", [])
                ]
                if not row["strengths"]:
                    row["note"] = note(N_("aucune résistance renseignée dans la bibliothèque"))
            out.append(row)
    return out


def summarize(run_dir: Path, info: dict) -> dict:
    rmeds = sorted(run_dir.glob("*.rmed"))
    units = info.get("units", "mm-N-MPa")
    base = {"version": SUMMARY_VERSION, "units": UNITS.get(units, UNITS["mm-N-MPa"]), "results": []}
    if not rmeds:
        return base | {"note": note(N_("pas de fichier .rmed dans ce run"))}
    rmed = rmeds[0]
    mesh = read_med(rmed)
    base["bounds"] = list(mesh.bbox())  # maillage du résultat (après MODI_MAILLAGE)
    fields: dict[str, dict[str, Field]] = {}
    for fld in read_fields(rmed):
        fields.setdefault(fld.concept, {})[fld.name] = fld
    try:
        comm = Comm((run_dir / "run.comm").read_text())
    except (OSError, SyntaxError):
        comm = Comm("")
    materials = info.get("materials", {})
    results = []
    for concept, flds in fields.items():
        solver, cases = comm.cases(concept)
        zones = comm.zones(solver)
        orders = sorted({st.order for f in flds.values() for st in f.steps})
        for order in orders:
            item: dict[str, Any] = {"concept": concept, "order": order, "notes": []}
            depl = flds.get("DEPL")
            st = next((s for s in depl.steps if s.order == order), None) if depl else None
            if st is not None and {"DX", "DY", "DZ"} <= set(depl.components):
                mag = np.sqrt(sum(depl.component(st, c) ** 2 for c in ("DX", "DY", "DZ")))
                item["depl"] = _extreme(mag, st.nodes, mesh.coords)
            vm = _vmis(flds, order)
            if vm is not None:
                item["vmis"] = _extreme(vm[0], vm[1], mesh.coords) | {"source": vm[2]}
                item["margins"] = _margins(mesh, zones, materials, vm, units)
            else:
                item["notes"].append(note(N_("ni SIEQ_NOEU ni SIGM_NOEU dans le .rmed : ajouter CRITERES=('SIEQ_NOEU',) à CALC_CHAMP et l'imprimer")))
            reac = flds.get("REAC_NODA")
            rst = next((s for s in reac.steps if s.order == order), None) if reac else None
            if rst is not None and {"DX", "DY", "DZ"} <= set(reac.components):
                item["reactions"] = [float(reac.component(rst, c).sum()) for c in ("DX", "DY", "DZ")]
            if order in cases:
                item["applied"], item["applied_note"] = applied_load(comm, mesh, cases[order], zones)
            else:
                item["applied"], item["applied_note"] = None, note(N_("calcul de {concept} non reconnu (MECA_STATIQUE ou MACRO_ELAS_MULT attendu)"), concept=concept)
            if item.get("reactions") is None:
                item["notes"].append(note(N_("REAC_NODA absent : ajouter FORCE=('REAC_NODA',) à CALC_CHAMP pour le contrôle d'équilibre")))
            elif item["applied"] is not None:
                f, r = np.array(item["applied"]), np.array(item["reactions"])
                scale = max(np.linalg.norm(f), np.linalg.norm(r))
                item["equilibrium"] = float(np.linalg.norm(f + r) / scale) if scale > 0 else 0.0
            results.append(item)
    return base | {"file": rmed.name, "results": results, "headline": headline(results)}


def headline(results: list[dict]) -> dict:
    """Valeurs du tableau des runs : maxima sur tous les résultats, plus petite marge."""
    depl = [r["depl"]["max"] for r in results if "depl" in r]
    vmis = [r["vmis"]["max"] for r in results if "vmis" in r]
    rfs = [s["rf"] for r in results for m in r.get("margins", []) for s in m.get("strengths", []) if s.get("rf") is not None]
    return {
        "depl_max": max(depl) if depl else None,
        "vmis_max": max(vmis) if vmis else None,
        "rf_min": min(rfs) if rfs else None,
    }


def load_or_compute(run_dir: Path, info: dict) -> dict:
    """Résumé en cache (resume.json), recalculé si le .rmed est plus récent ou le format a changé."""
    path = run_dir / SUMMARY_FILE
    rmeds = sorted(run_dir.glob("*.rmed"))
    if path.exists():
        try:
            cached = json.loads(path.read_text())
            fresh = not rmeds or path.stat().st_mtime >= rmeds[0].stat().st_mtime
            if cached.get("version") == SUMMARY_VERSION and fresh:
                return cached
        except ValueError:
            pass
    summary = summarize(run_dir, info)
    path.write_text(json.dumps(summary, indent=1, ensure_ascii=False))
    return summary
