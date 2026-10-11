import shutil

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from asteroid import state as state_module
    from asteroid.server import app

    state_module.state.__init__()  # état neuf, réglages dans le dossier isolé
    return TestClient(app)


def test_project_flow(client, tmp_path, cube_med):
    mesh = tmp_path / "proj" / "cube.med"
    mesh.parent.mkdir()
    shutil.copy(cube_med, mesh)

    snap = client.get("/api/state").json()
    assert snap["project_dir"] is None

    # Projet vierge : le choix du maillage fixe le dossier du projet.
    snap = client.post("/api/project/mesh", json={"path": str(mesh)}).json()
    assert snap["project_dir"] == str(mesh.parent)
    assert snap["project"]["mesh"] == "cube.med"
    assert (mesh.parent / "asteroid.json").exists()

    block = client.post("/api/blocks/new", json={"command": "lire_maillage"}).json()
    assert block["mode"] == "form" and block["params"] == {"FORMAT": "MED"}

    project = snap["project"] | {"blocks": [block]}
    assert client.put("/api/project", json=project).json() == {"saved": True}
    preview = client.post("/api/comm", json=project).json()
    assert "F mmed mesh.med D 20" in preview["export"]
    assert preview["blocks"][0]["concept"] == "mail"

    client.post("/api/project/new", json={})
    snap = client.post("/api/project/open", json={"dir": str(mesh.parent)}).json()
    assert snap["project"]["blocks"][0]["params"] == block["params"]
    assert snap["settings"]["recent_projects"][0] == str(mesh.parent)

    assert client.get("/api/runs").json() == []


def test_open_missing(client, tmp_path):
    r = client.post("/api/project/open", json={"dir": str(tmp_path)})
    assert r.status_code == 404


def test_fs_list(client, tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b.med").write_text("")
    data = client.get("/api/fs/list", params={"path": str(tmp_path)}).json()
    assert data["entries"] == [{"name": "a", "dir": True}, {"name": "b.med", "dir": False}]


def test_mesh_endpoints(client, tmp_path, cube_med):
    import numpy as np

    mesh = tmp_path / "cube.med"
    shutil.copy(cube_med, mesh)
    assert client.get("/api/mesh").status_code == 404
    client.post("/api/project/mesh", json={"path": str(mesh)})
    summary = client.get("/api/mesh").json()
    assert summary["groups"][0]["name"] == "VOL"
    pos = np.frombuffer(client.get("/api/mesh/positions").content, dtype=np.float32)
    assert len(pos) == 3 * summary["nodes"]
    skin = np.frombuffer(client.get("/api/mesh/skin").content, dtype=np.uint32)
    assert len(skin) % 3 == 0 and skin.max() < summary["nodes"]
    r = client.get("/api/mesh/group", params={"entity": "GROUP_MA", "name": "X1"})
    assert r.headers["X-Primitive"] == "triangles"
    assert client.get("/api/mesh/group", params={"entity": "GROUP_MA", "name": "NOPE"}).status_code == 404


def test_import_comm(client, tmp_path):
    f = tmp_path / "x.comm"
    f.write_text('DEBUT()\nmail = LIRE_MAILLAGE()\nIMPR_RESU(RESU=_F(MAILLAGE=mail))\nFIN()\n')
    data = client.post("/api/comm/import", json={"path": str(f)}).json()
    assert [b["command"] for b in data["blocks"]] == ["LIRE_MAILLAGE", "IMPR_RESU"]
    r = client.post("/api/comm/import", json={"text": "x = ("})
    assert r.status_code == 422 and "ligne 1" in r.json()["detail"]
