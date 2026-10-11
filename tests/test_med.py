from pathlib import Path

import numpy as np
import pytest

from asteroid.core.med import MedError, area, read_med

DATA = Path(__file__).parent / "data"


def groups(mesh):
    return {(g.entity, g.name): g for g in mesh.groups}


def test_gmsh_tetra_cube(cube_med):
    mesh = read_med(cube_med)
    g = groups(mesh)
    assert set(g) == {("GROUP_MA", n) for n in ["VOL", "X0", "X1", "Y0", "Y1", "Z0", "Z1"]}
    assert g["GROUP_MA", "VOL"].dim == 3
    assert g["GROUP_MA", "VOL"].measure == pytest.approx(1000.0)
    for name in ["X0", "X1", "Y0", "Y1", "Z0", "Z1"]:
        assert g["GROUP_MA", name].dim == 2
        assert g["GROUP_MA", name].measure == pytest.approx(100.0)
    tris, edges = mesh.skin()
    # Tous les nœuds de peau sont sur les faces du cube.
    on_face = np.isclose(mesh.coords[np.unique(tris)], 0).any(axis=1) | np.isclose(
        mesh.coords[np.unique(tris)], 10
    ).any(axis=1)
    assert on_face.all()
    assert edges.shape[1] == 2 and len(edges) > 0


@pytest.fixture(
    scope="module",
    params=["tet4", "tet10", "hex8", "h20_aster"],
)
def any_cube(request, tmp_path_factory):
    if request.param == "h20_aster":
        return DATA / "cube_h20_aster.med", {"H20", "QU8"}
    from make_cube import make_cube

    path = tmp_path_factory.mktemp(request.param) / "cube.med"
    options = {"tet4": {}, "tet10": {"order": 2}, "hex8": {"hexa": True}}[request.param]
    types = {"tet4": {"TE4", "TR3"}, "tet10": {"T10", "TR6"}, "hex8": {"HE8", "QU4"}}[request.param]
    return make_cube(path, **options), types


def test_skin_and_measures_all_types(any_cube):
    """Une face interne non éliminée gonflerait l'aire de peau au-delà de 600 mm²."""
    path, types = any_cube
    mesh = read_med(path)
    assert {b.type for b in mesh.cells} == types
    tris, _ = mesh.skin()
    assert area(mesh.coords, tris) == pytest.approx(600.0)
    g = groups(mesh)
    assert g["GROUP_MA", "VOL"].measure == pytest.approx(1000.0)
    for name in ["X0", "X1", "Y0", "Y1", "Z0", "Z1"]:
        assert g["GROUP_MA", name].measure == pytest.approx(100.0)
    prim, idx = mesh.group_geometry(g["GROUP_MA", "VOL"])
    assert area(mesh.coords, idx) == pytest.approx(600.0)


def test_aster_quadratic_hexa():
    mesh = read_med(DATA / "cube_h20_aster.med")
    g = groups(mesh)
    assert {b.type for b in mesh.cells} == {"H20", "QU8"}
    assert g["GROUP_MA", "VOL"].measure == pytest.approx(1000.0)
    # Famille portant deux groupes : X0 et X_ALL.
    assert g["GROUP_MA", "X_ALL"].measure == pytest.approx(200.0)
    assert g["GROUP_MA", "X_ALL"].count == g["GROUP_MA", "X0"].count * 2
    nodes = g["GROUP_NO", "N_X1"]
    assert nodes.count > 0
    assert np.allclose(mesh.coords[mesh.group_nodes(nodes), 0], 10.0)
    prim, idx = mesh.group_geometry(nodes)
    assert prim == "points" and len(idx) == nodes.count
    prim, idx = mesh.group_geometry(g["GROUP_MA", "VOL"])
    assert prim == "triangles" and idx.shape[1] == 3


def test_summary_order(cube_med):
    summary = read_med(cube_med).summary()
    assert summary["groups"][0]["name"] == "VOL"
    assert summary["nodes"] > 0 and "TE4" in summary["cells"]
    assert summary["bbox"] == [[0, 0, 0], [10, 10, 10]]


def test_not_med(tmp_path):
    bad = tmp_path / "x.med"
    bad.write_text("pas du hdf5")
    with pytest.raises(MedError):
        read_med(bad)
