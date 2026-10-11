import shutil
import subprocess
import sys
from pathlib import Path

import pytest

DATA = Path(__file__).parent / "data"
sys.path.insert(0, str(DATA))

CUBE_COMM_BLOCKS = [
    'mail = LIRE_MAILLAGE(FORMAT="MED")',
    'model = AFFE_MODELE(MAILLAGE=mail, AFFE=_F(TOUT="OUI", PHENOMENE="MECANIQUE", MODELISATION="3D"))',
    "mat = DEFI_MATERIAU(ELAS=_F(E=210000.0, NU=0.3))",
    'chmat = AFFE_MATERIAU(MAILLAGE=mail, AFFE=_F(TOUT="OUI", MATER=mat))',
    'cl = AFFE_CHAR_MECA(MODELE=model, DDL_IMPO=(_F(GROUP_MA="X0", DX=0.0), '
    '_F(GROUP_MA="Y0", DY=0.0), _F(GROUP_MA="Z0", DZ=0.0)))',
    # F = 1000 N sur S = 100 mm², soit 10 MPa.
    'force = AFFE_CHAR_MECA(MODELE=model, FORCE_FACE=_F(GROUP_MA="X1", FX=10.0))',
    "resu = MECA_STATIQUE(MODELE=model, CHAM_MATER=chmat, EXCIT=(_F(CHARGE=cl), _F(CHARGE=force)))",
    'resu = CALC_CHAMP(reuse=resu, RESULTAT=resu, CONTRAINTE=("SIGM_NOEU",))',
    "IMPR_RESU(RESU=_F(RESULTAT=resu))",
    'TEST_RESU(RESU=(\n'
    '    _F(RESULTAT=resu, NUME_ORDRE=1, NOM_CHAM="SIGM_NOEU", NOM_CMP="SIXX", TYPE_TEST="MIN",\n'
    '       VALE_CALC=10.0, VALE_REFE=10.0, REFERENCE="ANALYTIQUE"),\n'
    '    _F(RESULTAT=resu, NUME_ORDRE=1, NOM_CHAM="SIGM_NOEU", NOM_CMP="SIXX", TYPE_TEST="MAX",\n'
    '       VALE_CALC=10.0, VALE_REFE=10.0, REFERENCE="ANALYTIQUE"),\n'
    "))",
]


@pytest.fixture(scope="session")
def cube_med(tmp_path_factory) -> Path:
    from make_cube import make_cube

    return make_cube(tmp_path_factory.mktemp("mesh") / "cube.med")


def docker_image_available(image: str = "simvia/code_aster:stable") -> bool:
    if shutil.which("docker") is None:
        return False
    res = subprocess.run(["docker", "image", "inspect", image], capture_output=True)
    return res.returncode == 0


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTEROID_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.delenv("ASTEROID_HOME", raising=False)
    # Messages attendus en français, quelle que soit la locale de la machine.
    monkeypatch.setenv("LANGUAGE", "fr_FR")
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
