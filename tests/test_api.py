import shutil

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from asteroid import state as state_module
    from asteroid.server import app

    state_module.state.__init__()  # état neuf, réglages dans le dossier isolé
    return TestClient(app, base_url="http://127.0.0.1")


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


def test_foreign_host_or_origin_refused(client):
    assert client.get("/api/state").status_code == 200
    assert client.get("/api/state", headers={"Origin": "http://127.0.0.1:8765"}).status_code == 200
    # DNS rebinding : nom étranger qui pointe vers 127.0.0.1.
    assert client.get("/api/settings", headers={"Host": "evil.test:8765"}).status_code == 403
    # Requête d'une autre page ouverte dans le navigateur.
    assert client.post("/api/runs", headers={"Origin": "https://evil.test"}).status_code == 403
    assert client.post("/api/runs", headers={"Origin": "null"}).status_code == 403


def test_rename_and_group_fix_routes(client):
    blocks = [
        {"command": "DEFI_MATERIAU", "concept": "pla", "mode": "form", "params": {}},
        {"mode": "text", "text": "chmat = AFFE_MATERIAU(MAILLAGE=mail, AFFE=_F(GROUP_MA='vol', MATER=mat))"},
    ]
    res = client.post("/api/blocks/rename_concept", json={"blocks": blocks, "index": 0, "old": "mat", "new": "pla"}).json()
    assert res["count"] == 1 and "MATER=pla" in res["blocks"][1]["text"]
    res = client.post("/api/blocks/replace_group", json={"block": res["blocks"][1], "old": "vol", "new": "VOL"}).json()
    assert res["count"] == 1 and "GROUP_MA='VOL'" in res["block"]["text"]


def test_run_management_routes(client, tmp_path):
    from asteroid import state as state_module
    from asteroid.core.runner import run_path
    from asteroid.core.settings import Settings

    # Une seule boucle asyncio pour toutes les requêtes : le suivi du run y tourne.
    with client:
        client.post("/api/project/new", json={"dir": str(tmp_path / "p")})
        state_module.state.settings = Settings(run_command="echo {run_id} > mesh.med; echo ok", stop_command="")
        ids = []
        for text in ("a = 1", "a = 2"):
            project = client.get("/api/state").json()["project"]
            project["blocks"] = [{"mode": "text", "text": text}]
            client.put("/api/project", json=project)
            ids.append(client.post("/api/runs", json={"profile": "Long"}).json()["id"])
            client.get(f"/api/runs/{ids[-1]}/log")  # flux SSE lu jusqu'à la fin du run
        history = client.get("/api/runs").json()
        assert [r["id"] for r in history] == ids[::-1]
        assert history[0]["profile"] == "Long" and history[0]["size"] > 0

        assert client.patch(f"/api/runs/{ids[0]}", json={"note": "E = 2300"}).status_code == 200
        assert client.get(f"/api/runs/{ids[0]}").json()["note"] == "E = 2300"
        names = {f["name"] for f in client.get(f"/api/runs/{ids[0]}/files").json()}
        assert {"run.comm", "run.export", "run.log", "run.sh", "run.json"} <= names
        assert "a = 1" in client.get(f"/api/runs/{ids[0]}/files/run.comm").text

        res = client.get("/api/runs/compare", params={"ids": f"{ids[0]},{ids[1]}"}).json()
        assert res["reference"] == ids[0]
        assert "-a = 1" in res["diffs"][ids[1]] and "+a = 2" in res["diffs"][ids[1]]
        assert client.get("/api/runs/compare", params={"ids": ids[0]}).status_code == 400
        # Captures : seuls « run » et un dossier de comparaison cmp-<10 hex> sont servis.
        assert client.get(f"/api/runs/{ids[0]}/captures/../iso.png").status_code == 404
        assert client.get(f"/api/runs/{ids[0]}/captures/cmp-zz/iso.png").status_code == 404

        assert client.delete(f"/api/runs/{ids[1]}").status_code == 200
        assert [r["id"] for r in client.get("/api/runs").json()] == [ids[0]]
        # Aucun identifiant ne sort du dossier des runs.
        for bad in ("..", "../x", "a/b", ".cache"):
            with pytest.raises(ValueError):
                run_path(tmp_path, bad)
        assert client.delete("/api/runs/.hidden").status_code == 400
