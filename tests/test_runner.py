import asyncio
import json
import shutil
import subprocess

import pytest

from asteroid.core.model import Block, ExtraFile, Project
from asteroid.core.runner import RunManager
from asteroid.core.settings import Settings
from conftest import CUBE_COMM_BLOCKS, docker_image_available


def run_project(tmp_path, project, settings, stop_after=None):
    async def go():
        mgr = RunManager()
        run = await mgr.start(tmp_path, project, settings)
        if stop_after is not None:
            await asyncio.sleep(stop_after)
            assert await mgr.stop(run.id)
        lines = [line async for line in mgr.follow(run.id, tmp_path / project.runs_dir)]
        return mgr, run, lines

    return asyncio.run(go())


def test_fake_run(tmp_path):
    (tmp_path / "m.med").write_bytes(b"fake")
    project = Project(mesh="m.med", blocks=[Block(text='mail = LIRE_MAILLAGE(FORMAT="MED")')])
    settings = Settings(
        run_command="echo id={run_id}; ls {comm} {export} {mesh}; "
        "printf '# Commande #0001 de x, ligne 1\\n--- DIAGNOSTIC JOB : <A>_ALARM\\n' > message",
        stop_command="",
    )
    mgr, run, lines = run_project(tmp_path, project, settings)
    assert lines[0].startswith("$ echo id=")
    assert f"id={run.id}" in lines
    assert {"run.comm", "run.export", "mesh.med"} <= set(lines)
    info = json.loads((run.dir / "run.json").read_text())
    assert info["status"] == "alarm"
    assert info["diagnostic"] == "<A>_ALARM"
    assert mgr.history(tmp_path / "runs")[0]["id"] == run.id
    # Relecture d'un run terminé, comme après un redémarrage de l'app.
    replay = asyncio.run(_collect(RunManager(), run.id, tmp_path / "runs"))
    assert replay == lines


async def _collect(mgr, run_id, root):
    return [line async for line in mgr.follow(run_id, root)]


def test_stop(tmp_path):
    settings = Settings(run_command="echo start; sleep 30", stop_command="true")
    _, run, lines = run_project(tmp_path, Project(), settings, stop_after=0.5)
    assert run.info["status"] == "stopped"
    assert run.info["duration"] < 15


@pytest.mark.skipif(not docker_image_available(), reason="image Code_Aster absente")
def test_cube_traction_docker(tmp_path, cube_med):
    shutil.copy(cube_med, tmp_path / "cube.med")
    project = Project(mesh="cube.med", blocks=[Block(text=t) for t in CUBE_COMM_BLOCKS])
    _, run, lines = run_project(tmp_path, project, Settings())
    info = run.info
    assert info["status"] == "ok", "\n".join(lines[-40:])
    assert (run.dir / "resultat.rmed").stat().st_size > 0
    message = (run.dir / "message").read_text()
    assert "NOOK" not in message
    assert message.count(" OK ") >= 2  # les deux TEST_RESU sur SIXX = F/S


@pytest.mark.skipif(not docker_image_available(), reason="image Code_Aster absente")
def test_error_is_attached_to_block_docker(tmp_path, cube_med):
    shutil.copy(cube_med, tmp_path / "cube.med")
    blocks = [Block(text=t) for t in CUBE_COMM_BLOCKS[:7]]
    blocks[4].text = blocks[4].text.replace('"X0"', '"INEXISTANT"')
    _, run, _ = run_project(tmp_path, Project(mesh="cube.med", blocks=blocks), Settings())
    assert run.info["status"] == "fail"
    fatal = [m for m in run.info["messages"] if m["level"] == "F"]
    assert fatal and fatal[0]["id"] == "MODELISA7_77"
    assert fatal[0]["block_id"] == blocks[4].id
    assert fatal[0]["count"] == 1


@pytest.mark.skipif(not docker_image_available(), reason="image Code_Aster absente")
def test_stop_kills_container_docker(tmp_path):
    blocks = [Block(text="import time\ntime.sleep(120)")]
    _, run, _ = run_project(tmp_path, Project(blocks=blocks), Settings(), stop_after=4)
    assert run.info["status"] == "stopped"
    assert run.info["duration"] < 15
    ps = subprocess.run(
        ["docker", "ps", "-q", "-f", f"name=asteroid_{run.id}"], capture_output=True, text=True
    )
    assert ps.stdout.strip() == ""


FORM_CUBE = [
    ("LIRE_MAILLAGE", "mail", {"FORMAT": "MED"}),
    ("AFFE_MODELE", "model", {"MAILLAGE": {"$ref": "mail"},
     "AFFE": [{"TOUT": "OUI", "PHENOMENE": "MECANIQUE", "MODELISATION": "3D"}]}),
    ("DEFI_MATERIAU", "mat", {"ELAS": {"E": 210000, "NU": 0.3}}),
    ("AFFE_MATERIAU", "chmat", {"MAILLAGE": {"$ref": "mail"}, "AFFE": [{"TOUT": "OUI", "MATER": {"$ref": "mat"}}]}),
    ("AFFE_CHAR_MECA", "cl", {"MODELE": {"$ref": "model"},
     "DDL_IMPO": [{"GROUP_MA": ["X0"], "DX": 0}, {"GROUP_MA": ["Y0"], "DY": 0}, {"GROUP_MA": ["Z0"], "DZ": 0}],
     "FORCE_FACE": [{"GROUP_MA": ["X1"], "FX": 10}]}),
    ("MECA_STATIQUE", "resu", {"MODELE": {"$ref": "model"}, "CHAM_MATER": {"$ref": "chmat"},
     "EXCIT": [{"CHARGE": {"$ref": "cl"}}]}),
    ("CALC_CHAMP", "resu", {"RESULTAT": {"$ref": "resu"}, "CONTRAINTE": ["SIGM_NOEU"]}),
    ("IMPR_RESU", None, {"FORMAT": "MED", "RESU": [{"RESULTAT": {"$ref": "resu"}}]}),
]  # fmt: skip


@pytest.mark.skipif(not docker_image_available(), reason="image Code_Aster absente")
def test_cube_traction_forms_docker(tmp_path, cube_med):
    """Même cas que test_cube_traction_docker, construit avec les formulaires."""
    shutil.copy(cube_med, tmp_path / "cube.med")
    blocks = [Block(mode="form", command=c, concept=n, params=p) for c, n, p in FORM_CUBE]
    blocks.append(Block(text=CUBE_COMM_BLOCKS[-1]))  # TEST_RESU, sans formulaire
    _, run, lines = run_project(tmp_path, Project(mesh="cube.med", blocks=blocks), Settings())
    assert run.info["status"] == "ok", "\n".join(lines[-40:])
    assert "NOOK" not in (run.dir / "message").read_text()


def test_extra_data_file_copied(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "courbe.txt").write_text("0 0\n1 1\n")
    project = Project(blocks=[Block(text="f = LIRE_FONCTION(UNITE=40)")], files=[ExtraFile(unit=40, path="data/courbe.txt")])
    settings = Settings(run_command="cat courbe.txt; grep courbe {export}", stop_command="")
    _, run, lines = run_project(tmp_path, project, settings)
    assert "1 1" in lines and "F libr courbe.txt D 40" in lines


@pytest.mark.skipif(not docker_image_available(), reason="image Code_Aster absente")
def test_attached_data_file_docker(tmp_path):
    """Un fichier rattaché à UNITE=40 est copié dans le run et lu par Code_Aster."""
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "courbe.txt").write_text("0.0 0.0\n1.0 1.0\n")
    blocks = [
        Block(text='f = LIRE_FONCTION(UNITE=40, NOM_PARA="INST", INDIC_PARA=(1, 1), INDIC_RESU=(1, 2))'),
        Block(text="TEST_FONCTION(VALEUR=_F(FONCTION=f, VALE_PARA=0.5, VALE_CALC=0.5))"),
    ]
    project = Project(blocks=blocks, files=[ExtraFile(unit=40, path="data/courbe.txt")])
    _, run, lines = run_project(tmp_path, project, Settings())
    assert run.info["status"] == "ok", "\n".join(lines[-30:])
    assert (run.dir / "courbe.txt").exists()
