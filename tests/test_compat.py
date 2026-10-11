"""Fichiers écrits par une version plus récente : les champs inconnus survivent à la réécriture."""

import json

from fastapi.testclient import TestClient

from asteroid.core import materials as mat
from asteroid.core.model import PROJECT_FILE, load_project, save_project
from asteroid.core.settings import load_settings, save_settings, settings_path


def test_project_unknown_fields_kept(tmp_path):
    data = {
        "name": "p",
        "profil_run": {"time_limit": 3600},
        "blocks": [{"command": "LIRE_MAILLAGE", "mode": "form", "params": {}, "nouveau": [1, 2]}],
        "files": [{"unit": 40, "path": "f.txt", "option": True}],
    }
    (tmp_path / PROJECT_FILE).write_text(json.dumps(data))
    project = load_project(tmp_path)
    project.name = "modifié"
    project.blocks[0] = project.blocks[0].model_copy(update={"concept": "mail"})
    save_project(tmp_path, project)
    saved = json.loads((tmp_path / PROJECT_FILE).read_text())
    assert saved["name"] == "modifié" and saved["profil_run"] == {"time_limit": 3600}
    assert saved["blocks"][0]["nouveau"] == [1, 2] and saved["blocks"][0]["concept"] == "mail"
    assert saved["files"][0]["option"] is True


def test_project_unknown_fields_through_api(tmp_path):
    from asteroid import state as state_module
    from asteroid.server import app

    (tmp_path / PROJECT_FILE).write_text(json.dumps({"name": "p", "futur": "x"}))
    state_module.state.__init__()
    client = TestClient(app, base_url="http://127.0.0.1")
    snap = client.post("/api/project/open", json={"dir": str(tmp_path)}).json()
    assert snap["project"]["futur"] == "x"
    # Le frontend renvoie le projet tel qu'il l'a reçu, modifié.
    assert client.put("/api/project", json=snap["project"] | {"name": "q"}).json() == {"saved": True}
    assert json.loads((tmp_path / PROJECT_FILE).read_text())["futur"] == "x"


def test_settings_unknown_fields_kept():
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"configured": True, "language": "fr", "profils": [{"nom": "long"}]}))
    settings = load_settings()
    settings.language = "en"
    save_settings(settings)
    assert json.loads(path.read_text())["profils"] == [{"nom": "long"}]


def test_material_unknown_fields_kept():
    root = mat.ensure_library()
    (root / "futur.json").write_text(json.dumps({
        "units": "SI (Pa, kg/m³, 1/K)", "name": "Futur", "constants": {"E": 1e9, "NU": 0.3},
        "fournisseur": "X", "strengths": [{"name": "Rt", "value": 5e7, "direction": "Z"}],
    }))
    [m] = [m for m in mat.load_library() if m.id == "futur"]
    assert "units" not in m.model_dump()  # note de fichier, pas un champ
    mat.save_material(m.model_copy(update={"name": "Futur 2"}))
    saved = json.loads((root / "futur.json").read_text())
    assert saved["fournisseur"] == "X" and saved["strengths"][0]["direction"] == "Z"
    assert saved["name"] == "Futur 2" and saved["units"].startswith("SI")
