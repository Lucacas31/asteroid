import asyncio
import json
import shutil

import numpy as np
import pytest

from asteroid.core import captures, results
from asteroid.core.med import read_med
from asteroid.core.model import Block, Project
from asteroid.core.runner import RunManager
from asteroid.core.settings import Settings
from conftest import CUBE_COMM_BLOCKS, docker_image_available

BASE = "\n".join(CUBE_COMM_BLOCKS[:4])  # mail, model, mat (ELAS sans RHO), chmat


def load(cube_med, charge: str, excit: str = "_F(CHARGE=cl)", rho: bool = False) -> tuple:
    base = BASE.replace("NU=0.3))", "NU=0.3, RHO=7.85e-09))") if rho else BASE
    comm = results.Comm(f"{base}\ncl = {charge}\nresu = MECA_STATIQUE(MODELE=model, CHAM_MATER=chmat, EXCIT={excit})")
    solver, cases = comm.cases("resu")
    return results.applied_load(comm, read_med(cube_med), cases[1], comm.zones(solver))


def test_applied_force_face_and_nodal(cube_med):
    force, why = load(cube_med, 'AFFE_CHAR_MECA(MODELE=model, FORCE_FACE=_F(GROUP_MA="X1", FX=10.0))')
    assert why is None and np.allclose(force, [1000.0, 0, 0])  # 10 MPa × 100 mm²
    force, _ = load(cube_med, 'AFFE_CHAR_MECA(MODELE=model, DDL_IMPO=_F(GROUP_MA="X0", DX=0.0), '
                              'FORCE_ARETE=(), FORCE_NODALE=_F(GROUP_MA="X1", FZ=-1.0))')
    nodes = {int(n) for b in read_med(cube_med).group_cells(read_med(cube_med).group("GROUP_MA", "X1")) for n in b.corners.ravel()}
    assert np.allclose(force, [0, 0, -len(nodes)])


def test_applied_pressure_is_normal_resultant(cube_med):
    force, why = load(cube_med, 'AFFE_CHAR_MECA(MODELE=model, PRES_REP=_F(GROUP_MA="X1", PRES=2.0))')
    assert why is None
    assert np.allclose(np.abs(force), [200.0, 0, 0])  # 2 MPa × 100 mm², selon la normale des faces


def test_applied_gravity_uses_density(cube_med):
    force, why = load(cube_med, 'AFFE_CHAR_MECA(MODELE=model, PESANTEUR=_F(GRAVITE=9810.0, DIRECTION=(0.0, 0.0, -2.0)))', rho=True)
    assert why is None and np.allclose(force, [0, 0, -9810.0 * 7.85e-9 * 1000.0])


@pytest.mark.parametrize("charge, excit, expected", [
    ('AFFE_CHAR_MECA(MODELE=model, FORCE_FACE=_F(GROUP_MA="X1", FX=f))', "_F(CHARGE=cl)", "valeur non numérique"),
    ('AFFE_CHAR_MECA(MODELE=model, FORCE_FACE=_F(GROUP_MA="X1", FX=1.0))', "_F(CHARGE=cl, FONC_MULT=fm)", "FONC_MULT"),
    ('AFFE_CHAR_MECA(MODELE=model, FORCE_FACE=_F(GROUP_MA="NOPE", FX=1.0))', "_F(CHARGE=cl)", "absent du maillage"),
    ('AFFE_CHAR_MECA(MODELE=model, FORCE_COQUE=_F(TOUT="OUI", PRES=1.0))', "_F(CHARGE=cl)", "non pris en compte"),
])
def test_applied_load_says_why_not(cube_med, charge, excit, expected):
    force, why = load(cube_med, charge, excit)
    assert force is None and expected in why["template"]


def test_nice_factor_and_shared_params(tmp_path):
    assert [captures._nice(x) for x in (0.7, 1.3, 3, 7, 430)] == [1.0, 2.0, 5.0, 10.0, 500.0]
    base = {"units": results.UNITS["mm-N-MPa"], "file": "r.rmed"}
    a = base | {"bounds": [[0, 0, 0], [10, 10, 10]], "results": [{"concept": "res", "depl": {"max": 0.01}, "vmis": {"max": 8.0}}]}
    b = base | {"bounds": [[0, 0, 0], [20, 10, 10]], "results": [{"concept": "r2", "depl": {"max": 0.05}, "vmis": {"max": 3.0}}]}
    shared = captures.params_for([(tmp_path / "a", a), (tmp_path / "b", b)])
    # Mêmes cadrage, échelle et amplification pour les deux runs.
    assert shared["bounds"] == [[0, 0, 0], [20, 10, 10]] and shared["range"] == [0.0, 8.0]
    assert shared["factor"] == 50.0  # 5 % de la diagonale (24,5 mm) / 0,05 mm, arrondi
    p = captures.script_params(tmp_path / "b", b, shared)
    assert p["color"] == "r2______SIEQ_NOEU" and p["depl"] == "r2______DEPL"
    assert "None" in captures.SCRIPT.format(params=repr(p | {"depl": None}))  # littéral Python
    # Même ensemble de runs (quel que soit l'ordre), mêmes paramètres : même dossier de captures.
    key = captures.compare_key(["b", "a"], shared)
    assert key == captures.compare_key(["a", "b"], shared) and captures.COMPARE_KEY.fullmatch(key)
    assert key != captures.compare_key(["a", "b", "c"], shared)


def test_suggest_capture_command():
    cmd = captures.suggest_command("'/opt/ParaView 6/bin/paraview' --script={script}")
    assert cmd == "'/opt/ParaView 6/bin/pvbatch' --force-offscreen-rendering {script}"
    assert captures.suggest_command("paraview").startswith("pvbatch ")


@pytest.mark.skipif(not docker_image_available(), reason="image Code_Aster absente")
def test_summary_of_cube_traction_docker(tmp_path, cube_med):
    shutil.copy(cube_med, tmp_path / "cube.med")
    texts = CUBE_COMM_BLOCKS[:7] + [
        'resu = CALC_CHAMP(reuse=resu, RESULTAT=resu, CONTRAINTE=("SIGM_NOEU",), CRITERES=("SIEQ_NOEU",), FORCE=("REAC_NODA",))',
        "IMPR_RESU(RESU=_F(RESULTAT=resu))",
    ]
    project = Project(mesh="cube.med", blocks=[Block(text=t) for t in texts])
    project.blocks[2].meta = {"material": "acier"}
    (tmp_path / "materials.json").write_text(json.dumps({"materials": {"acier": {
        "material": {"name": "Acier", "model": "ELAS"}, "units": "mm-N-MPa",
        "converted": {"constants": {}, "strengths": [{"name": "fy", "value": 235.0}]},
    }}}))

    async def go():
        mgr = RunManager()
        run = await mgr.start(tmp_path, project, Settings())
        [_ async for _ in mgr.follow(run.id, tmp_path / "runs")]
        return run

    run = asyncio.run(go())
    assert run.info["status"] == "ok"
    [r] = json.loads((run.dir / "resume.json").read_text())["results"]
    assert r["vmis"]["max"] == pytest.approx(10.0, rel=1e-6)  # traction simple : σVM = F/S
    assert np.allclose(r["applied"], [1000.0, 0, 0])
    assert np.allclose(r["reactions"], [-1000.0, 0, 0], rtol=1e-6)
    assert r["equilibrium"] < 1e-6
    [m] = r["margins"]
    assert m["material"] == "Acier" and m["strengths"][0]["rf"] == pytest.approx(23.5, rel=1e-6)
    assert run.info["headline"]["rf_min"] == pytest.approx(23.5, rel=1e-6)
