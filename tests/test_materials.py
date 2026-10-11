import json
import shutil

import pytest
from fastapi.testclient import TestClient

from asteroid.core import materials as mat


def test_conversion_mm_n_mpa():
    pla = mat.Material(name="PLA", constants={"E": 2.3e9, "NU": 0.35}, rho=1240)
    params = mat.defi_materiau_params(pla, "mm-N-MPa")
    # Exemple du cahier des charges : 1240 kg/m³ → 1,24e-9 t/mm³.
    assert params == {"ELAS": {"E": 2300.0, "NU": 0.35, "RHO": 1.24e-9}}
    assert mat.defi_materiau_params(pla, "m-N-Pa") == {"ELAS": {"E": 2.3e9, "NU": 0.35, "RHO": 1240.0}}


def test_orthotropic_and_strengths():
    m = mat.Material(
        name="PLA imprimé",
        model="ELAS_ISTR",
        constants={"E_L": 2.3e9, "E_N": 1.9e9, "NU_LT": 0.35, "NU_LN": 0.3, "G_LN": 0.7e9, "E": 1.0},
        strengths=[mat.Strength(name="Traction Z", value=25e6)],
    )
    conv = mat.convert(m, "mm-N-MPa")
    assert conv["constants"] == {"E_L": 2300.0, "E_N": 1900.0, "NU_LT": 0.35, "NU_LN": 0.3, "G_LN": 700.0}
    assert conv["strengths"] == [{"name": "Traction Z", "value": 25.0}]


def test_alpha_kept_in_library_not_written():
    steel = next(m for m in mat.SEED if m.id == "acier_s235")
    assert "ALPHA" in mat.convert(steel, "mm-N-MPa")["constants"]
    assert mat.defi_materiau_params(steel, "mm-N-MPa") == {"ELAS": {"E": 210000.0, "NU": 0.3, "RHO": 7.85e-09}}


@pytest.fixture
def client():
    from asteroid import state as state_module
    from asteroid.server import app

    state_module.state.__init__()
    return TestClient(app)


def test_library_api_and_project_copy(client, tmp_path, cube_med):
    lib = client.get("/api/materials").json()["materials"]
    assert {m["id"] for m in lib} == {"acier_s235", "aluminium_6061_t6"}  # bibliothèque initiale

    pla = client.post("/api/materials", json={"name": "PLA blanc", "source": "fiche fabricant",
                                              "constants": {"E": 2.3e9, "NU": 0.35}, "rho": 1240}).json()
    assert pla["id"] == "pla_blanc"
    copy = client.post("/api/materials/pla_blanc/duplicate").json()
    assert copy["id"] == "pla_blanc_copie" and copy["name"] == "PLA blanc (copie)"
    copy["constants"]["E"] = 2.0e9
    assert client.put("/api/materials/pla_blanc_copie", json=copy).json()["constants"]["E"] == 2.0e9
    assert client.delete("/api/materials/pla_blanc_copie").json() == {"deleted": "pla_blanc_copie"}
    assert len(client.get("/api/materials").json()["materials"]) == 3

    # Utilisation dans un projet : conversion + copie figée.
    shutil.copy(cube_med, tmp_path / "cube.med")
    client.post("/api/project/mesh", json={"path": str(tmp_path / "cube.med")})
    used = client.post("/api/materials/pla_blanc/use").json()
    assert used["params"] == {"ELAS": {"E": 2300.0, "NU": 0.35, "RHO": 1.24e-9}}
    saved = json.loads((tmp_path / "materials.json").read_text())["materials"]["pla_blanc"]
    assert saved["units"] == "mm-N-MPa" and saved["material"]["constants"]["E"] == 2.3e9

    # La bibliothèque évolue : la copie du projet ne bouge pas.
    pla["constants"]["E"] = 3.0e9
    client.put("/api/materials/pla_blanc", json=pla)
    assert client.get("/api/materials/project").json()["pla_blanc"]["converted"]["constants"]["E"] == 2300.0


def test_use_with_explicit_units(client, tmp_path, cube_med):
    shutil.copy(cube_med, tmp_path / "cube.med")
    client.post("/api/project/mesh", json={"path": str(tmp_path / "cube.med")})
    used = client.post("/api/materials/acier_s235/use", json={"units": "m-N-Pa"}).json()
    assert used["units"] == "m-N-Pa" and used["params"]["ELAS"]["E"] == 210e9
    assert client.post("/api/materials/acier_s235/use", json={"units": "km"}).status_code == 400


def test_library_folder(client, tmp_path, monkeypatch):
    """Un fichier par matériau ; sous-dossiers lus ; fichier illisible signalé ; import."""
    monkeypatch.setenv("ASTEROID_HOME", str(tmp_path / "app"))
    root = tmp_path / "app" / "materiaux"
    client.get("/api/materials")
    saved = json.loads((root / "acier_s235.json").read_text())
    assert saved["units"] == mat.SI_NOTE and "id" not in saved and saved["constants"]["E"] == 210e9

    (root / "partage").mkdir()
    (root / "partage" / "petg.json").write_text(json.dumps({"name": "PETG", "constants": {"E": 2.1e9}}))
    (root / "casse.json").write_text("{")
    lib = client.get("/api/materials").json()
    assert "partage/petg" in {m["id"] for m in lib["materials"]}
    assert lib["errors"][0].startswith("casse.json") and lib["dir"] == str(root)
    assert client.post("/api/materials/partage/petg/use", json={"units": "mm-N-MPa"}).json()["params"] == {
        "ELAS": {"E": 2100.0}
    }
    assert client.delete("/api/materials/partage/petg").status_code == 200
    assert not (root / "partage" / "petg.json").exists()
    with pytest.raises(ValueError):
        mat.material_file("../x")

    # Import d'un fichier à plusieurs matériaux, dont un nom déjà pris.
    shared = tmp_path / "lib.json"
    shared.write_text(json.dumps({"materials": [{"name": "Acier S235"}, {"name": "PLA", "rho": 1240}]}))
    added = client.post("/api/materials/import", json={"path": str(shared)}).json()
    assert [m["id"] for m in added] == ["acier_s235_2", "pla"]
    assert (root / "pla.json").exists()
    shared.write_text("[1]")
    assert client.post("/api/materials/import", json={"path": str(shared)}).status_code == 400


def test_library_migrated_from_single_file(client, tmp_path, monkeypatch):
    config = tmp_path / "old"
    monkeypatch.setenv("ASTEROID_CONFIG_DIR", str(config))
    config.mkdir()
    (config / "materials.json").write_text(json.dumps({"materials": [{"id": "abs", "name": "ABS"}]}))
    assert [m["id"] for m in client.get("/api/materials").json()["materials"]] == ["abs"]
    assert (config / "materiaux" / "abs.json").exists() and (config / "materials.json").exists()
