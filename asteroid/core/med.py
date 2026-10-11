"""Lecture d'un maillage MED (HDF5) : nœuds, mailles, groupes, peau, aires et volumes.

Seuls les nœuds sommets des éléments quadratiques servent à l'affichage et aux
mesures. Sur des éléments courbes, aires et volumes sont donc approchés.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import h5py
import numpy as np

from .i18n import t

# Type MED → (dimension, nombre de nœuds sommets, famille de forme)
CELL_TYPES = {
    "PO1": (0, 1, "point"),
    "SE2": (1, 2, "seg"), "SE3": (1, 2, "seg"), "SE4": (1, 2, "seg"),
    "TR3": (2, 3, "tri"), "TR6": (2, 3, "tri"), "TR7": (2, 3, "tri"),
    "QU4": (2, 4, "quad"), "QU8": (2, 4, "quad"), "QU9": (2, 4, "quad"),
    "TE4": (3, 4, "tet"), "T10": (3, 4, "tet"),
    "PY5": (3, 5, "pyra"), "P13": (3, 5, "pyra"),
    "PE6": (3, 6, "prism"), "P15": (3, 6, "prism"), "P18": (3, 6, "prism"),
    "HE8": (3, 8, "hex"), "H20": (3, 8, "hex"), "H27": (3, 8, "hex"),
}  # fmt: skip

# Faces des volumes, en indices locaux de sommets (numérotation MED / Code_Aster).
FACES = {
    "tet": ([(0, 1, 2), (0, 1, 3), (1, 2, 3), (0, 2, 3)], []),
    "pyra": ([(0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)], [(0, 1, 2, 3)]),
    "prism": ([(0, 1, 2), (3, 4, 5)], [(0, 1, 4, 3), (1, 2, 5, 4), (2, 0, 3, 5)]),
    "hex": ([], [(0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]),
}

# Découpage des volumes en tétraèdres, pour le calcul du volume.
TETS = {
    "tet": [(0, 1, 2, 3)],
    "pyra": [(0, 1, 2, 4), (0, 2, 3, 4)],
    "prism": [(0, 1, 2, 3), (1, 2, 3, 4), (2, 3, 4, 5)],
    "hex": [(0, 1, 2, 6), (0, 2, 3, 6), (0, 3, 7, 6), (0, 7, 4, 6), (0, 4, 5, 6), (0, 5, 1, 6)],
}

DIM_LABELS = {3: "volume", 2: "face", 1: "arête", 0: "point"}


class MedError(ValueError):
    pass


@dataclass
class CellBlock:
    type: str
    corners: np.ndarray  # (n, k) indices 0-based des nœuds sommets
    families: np.ndarray  # (n,)

    @property
    def dim(self) -> int:
        return CELL_TYPES[self.type][0]

    @property
    def shape(self) -> str:
        return CELL_TYPES[self.type][2]


@dataclass
class Group:
    name: str
    entity: str  # "GROUP_MA" (mailles) ou "GROUP_NO" (nœuds)
    families: set[int]
    dim: int = 0
    count: int = 0
    measure: float | None = None  # volume, aire ou longueur selon dim

    def summary(self) -> dict:
        return {
            "name": self.name,
            "entity": self.entity,
            "dim": self.dim if self.entity == "GROUP_MA" else None,
            "count": self.count,
            "measure": self.measure,
        }


@dataclass
class Mesh:
    name: str
    coords: np.ndarray  # (N, 3)
    node_families: np.ndarray  # (N,)
    cells: list[CellBlock]
    groups: list[Group] = field(default_factory=list)
    _skin: tuple[np.ndarray, np.ndarray] | None = None

    # ------------------------------------------------------------------ groupes

    def group(self, entity: str, name: str) -> Group:
        for g in self.groups:
            if g.entity == entity and g.name == name:
                return g
        raise KeyError(t("{entity} {name} absent du maillage", entity=entity, name=name))

    def group_cells(self, group: Group) -> list[CellBlock]:
        fams = np.fromiter(group.families, dtype=np.int64)
        out = []
        for block in self.cells:
            mask = np.isin(block.families, fams)
            if mask.any():
                out.append(CellBlock(block.type, block.corners[mask], block.families[mask]))
        return out

    def group_nodes(self, group: Group) -> np.ndarray:
        fams = np.fromiter(group.families, dtype=np.int64)
        return np.nonzero(np.isin(self.node_families, fams))[0]

    # ------------------------------------------------------------------ géométrie

    def skin(self) -> tuple[np.ndarray, np.ndarray]:
        """(triangles (m, 3), arêtes (e, 2)) de la peau du maillage."""
        if self._skin is None:
            volumes = [b for b in self.cells if b.dim == 3]
            if volumes:
                tris, quads = boundary_faces(volumes)
            else:
                tris, quads = surface_polygons([b for b in self.cells if b.dim == 2])
            self._skin = (triangulate(tris, quads), polygon_edges(tris, quads))
        return self._skin

    def group_geometry(self, group: Group) -> tuple[str, np.ndarray]:
        """(primitive, indices) pour mettre un groupe en surbrillance."""
        if group.entity == "GROUP_NO":
            return "points", self.group_nodes(group).astype(np.uint32)
        blocks = self.group_cells(group)
        if group.dim == 3:
            tris, quads = boundary_faces([b for b in blocks if b.dim == 3])
            return "triangles", triangulate(tris, quads)
        if group.dim == 2:
            tris, quads = surface_polygons([b for b in blocks if b.dim == 2])
            return "triangles", triangulate(tris, quads)
        if group.dim == 1:
            segs = [b.corners for b in blocks if b.dim == 1]
            return "lines", np.concatenate(segs).astype(np.uint32)
        points = [b.corners.ravel() for b in blocks]
        return "points", np.unique(np.concatenate(points)).astype(np.uint32)

    def measure(self, blocks: list[CellBlock], dim: int) -> float | None:
        if dim == 3:
            return float(sum(volume(self.coords, b) for b in blocks if b.dim == 3))
        if dim == 2:
            tris, quads = surface_polygons([b for b in blocks if b.dim == 2])
            return area(self.coords, triangulate(tris, quads))
        if dim == 1:
            segs = np.concatenate([b.corners for b in blocks if b.dim == 1])
            return float(np.linalg.norm(self.coords[segs[:, 1]] - self.coords[segs[:, 0]], axis=1).sum())
        return None

    def bbox(self) -> tuple[list[float], list[float]]:
        return self.coords.min(axis=0).tolist(), self.coords.max(axis=0).tolist()

    def summary(self) -> dict:
        lo, hi = self.bbox()
        counts: dict[str, int] = {}
        for b in self.cells:
            counts[b.type] = counts.get(b.type, 0) + len(b.corners)
        return {
            "name": self.name,
            "nodes": len(self.coords),
            "cells": counts,
            "bbox": [lo, hi],
            "groups": [g.summary() for g in sorted(self.groups, key=_group_order)],
        }


def _group_order(g: Group) -> tuple:
    rank = -g.dim if g.entity == "GROUP_MA" else 1
    return (rank, g.name.lower())


# ---------------------------------------------------------------------- lecture


def _decode_names(dataset) -> list[str]:
    raw = np.asarray(dataset[()])
    return [bytes(row.astype(np.uint8)).split(b"\0")[0].decode("latin-1").strip() for row in raw]


def _step_group(mesh_group: h5py.Group) -> h5py.Group:
    if "NOE" in mesh_group:
        return mesh_group
    for key in sorted(mesh_group):
        sub = mesh_group[key]
        if isinstance(sub, h5py.Group) and "NOE" in sub:
            return sub
    raise MedError(t("aucun nœud trouvé dans le maillage"))


def read_med(path: str | Path) -> Mesh:
    try:
        f = h5py.File(path, "r")
    except OSError as exc:
        raise MedError(t("fichier MED illisible : {error}", error=exc)) from exc
    with f:
        if "ENS_MAA" not in f or not len(f["ENS_MAA"]):
            raise MedError(t("aucun maillage dans ce fichier MED"))
        name = sorted(f["ENS_MAA"])[0]
        step = _step_group(f["ENS_MAA"][name])

        coo = step["NOE/COO"]
        n_nodes = int(coo.attrs["NBR"])
        flat = np.asarray(coo[()], dtype=np.float64)
        dim = len(flat) // n_nodes
        coords = np.zeros((n_nodes, 3))
        coords[:, :dim] = flat.reshape(dim, n_nodes).T  # stockage « no interlace »
        node_fam = np.asarray(step["NOE/FAM"][()]) if "FAM" in step["NOE"] else np.zeros(n_nodes, int)

        cells = []
        for type_name in sorted(step["MAI"]) if "MAI" in step else []:
            if type_name not in CELL_TYPES:
                continue
            grp = step["MAI"][type_name]
            n = int(grp["NOD"].attrs["NBR"])
            conn = np.asarray(grp["NOD"][()], dtype=np.int64).reshape(-1, n).T - 1
            k = CELL_TYPES[type_name][1]
            fam = np.asarray(grp["FAM"][()]) if "FAM" in grp else np.zeros(n, int)
            cells.append(CellBlock(type_name, np.ascontiguousarray(conn[:, :k]), fam))

        groups: dict[tuple[str, str], Group] = {}
        fas = f["FAS"][name] if "FAS" in f and name in f["FAS"] else None
        for section, entity in (("ELEME", "GROUP_MA"), ("NOEUD", "GROUP_NO")):
            if fas is None or section not in fas:
                continue
            for fam in fas[section].values():
                if "GRO" not in fam:
                    continue
                num = int(fam.attrs["NUM"])
                for gname in _decode_names(fam["GRO/NOM"]):
                    groups.setdefault((entity, gname), Group(gname, entity, set())).families.add(num)

    mesh = Mesh(name, coords, node_fam, cells, list(groups.values()))
    for g in mesh.groups:
        if g.entity == "GROUP_NO":
            g.count = int(len(mesh.group_nodes(g)))
            continue
        blocks = mesh.group_cells(g)
        g.count = int(sum(len(b.corners) for b in blocks))
        g.dim = max((b.dim for b in blocks), default=0)
        g.measure = mesh.measure(blocks, g.dim) if blocks else None
    return mesh


# ---------------------------------------------------------------------- géométrie


def _faces(blocks: list[CellBlock], kind: int) -> np.ndarray:
    """Toutes les faces triangulaires (kind=0) ou quadrangulaires (kind=1) des volumes."""
    parts = []
    for b in blocks:
        local = FACES[b.shape][kind]
        if local:
            parts.append(b.corners[:, np.array(local)].reshape(-1, 3 + kind))
    return np.concatenate(parts) if parts else np.empty((0, 3 + kind), dtype=np.int64)


def _unique_faces(faces: np.ndarray) -> np.ndarray:
    if not len(faces):
        return faces
    keys = np.sort(faces, axis=1)
    bits = 64 // keys.shape[1]
    if keys.max() < (1 << bits):
        # Une face = un entier : bien plus rapide que np.unique(axis=0).
        packed = np.zeros(len(keys), dtype=np.int64)
        for col in range(keys.shape[1]):
            packed = (packed << bits) | keys[:, col]
        _, first, counts = np.unique(packed, return_index=True, return_counts=True)
    else:
        _, first, counts = np.unique(keys, axis=0, return_index=True, return_counts=True)
    return faces[first[counts == 1]]


def boundary_faces(volumes: list[CellBlock]) -> tuple[np.ndarray, np.ndarray]:
    """Faces qui n'appartiennent qu'à un seul volume : la peau de l'ensemble."""
    return _unique_faces(_faces(volumes, 0)), _unique_faces(_faces(volumes, 1))


def surface_polygons(surfaces: list[CellBlock]) -> tuple[np.ndarray, np.ndarray]:
    tris = [b.corners for b in surfaces if b.shape == "tri"]
    quads = [b.corners for b in surfaces if b.shape == "quad"]
    return (
        np.concatenate(tris) if tris else np.empty((0, 3), dtype=np.int64),
        np.concatenate(quads) if quads else np.empty((0, 4), dtype=np.int64),
    )


def triangulate(tris: np.ndarray, quads: np.ndarray) -> np.ndarray:
    split = np.concatenate([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]]) if len(quads) else quads[:, :3]
    return np.concatenate([tris, split]).astype(np.uint32)


def polygon_edges(tris: np.ndarray, quads: np.ndarray) -> np.ndarray:
    edges = [tris[:, [i, (i + 1) % 3]] for i in range(3)] + [quads[:, [i, (i + 1) % 4]] for i in range(4)]
    all_edges = np.sort(np.concatenate(edges), axis=1)
    return np.unique(all_edges, axis=0).astype(np.uint32) if len(all_edges) else all_edges.astype(np.uint32)


def area(coords: np.ndarray, tris: np.ndarray) -> float:
    if not len(tris):
        return 0.0
    a, b, c = (coords[tris[:, i]] for i in range(3))
    return float(0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1).sum())


def volume(coords: np.ndarray, block: CellBlock) -> float:
    total = 0.0
    for t in TETS[block.shape]:
        a, b, c, d = (coords[block.corners[:, i]] for i in t)
        total += float(np.abs(np.einsum("ij,ij->i", b - a, np.cross(c - a, d - a))).sum() / 6.0)
    return total
