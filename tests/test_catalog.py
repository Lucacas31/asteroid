import pytest

from asteroid.core.catalog import Validator, load_catalog
from conftest import CUBE_COMM_BLOCKS

GROUPS = {"GROUP_MA": {"VOL", "X0", "X1", "Y0", "Y1", "Z0", "Z1"}, "GROUP_NO": set()}
BASE = "\n".join(CUBE_COMM_BLOCKS[:4])  # mail, model, mat, chmat


@pytest.fixture(scope="module")
def catalog():
    cat = load_catalog()
    assert cat is not None and len(cat.commands) > 200
    return cat


def check(catalog, source: str, groups=GROUPS):
    v = Validator(catalog, groups)
    v.validate_source(BASE)
    return v.validate_source(source)


def messages(issues, level="error"):
    return [i.message for i in issues if i.level == level]


def test_cube_case_is_clean(catalog):
    v = Validator(catalog, GROUPS)
    issues = [i for b in CUBE_COMM_BLOCKS for i in v.validate_source(b)]
    assert messages(issues) == []


@pytest.mark.parametrize(
    "source, expected",
    [
        ("resu = MECA_STATIQUE(CHAM_MATER=chmat)", "MODELE : mot-clé obligatoire manquant"),
        ('m2 = AFFE_MODELE(MAILLAGE=mail, AFFE=_F(TOUT="OUI", PHENOMENE="FOO", MODELISATION="3D"))', "valeur non permise"),
        ('m2 = DEFI_MATERIAU(ELAS=_F(E="abc", NU=0.3))', "réel attendu"),
        ("resu = MECA_STATIQUE(MODELE=nope, CHAM_MATER=chmat)", "« nope » n'est pas défini plus haut"),
        ("resu = MECA_STATIQUE(MODELE=mat, CHAM_MATER=chmat)", "« mat » est un mater_sdaster"),
        ('cl = AFFE_CHAR_MECA(MODELE=model, DDL_IMPO=_F(GROUP_MA="NOPE", DX=0.0))', "groupe de mailles « NOPE » absent"),
        ('m = LIRE_MAILLAGE(FORMAT="GMSH", NOM_MED="x")', "NOM_MED : non permis ici"),
        ("m2 = DEFI_MATERIAU(ELAS=(_F(E=1.0, NU=0.3), _F(E=2.0, NU=0.3)))", "au plus 1 occurrence"),
        ("resu = MECA_STATIQUE(MODELE=model, CHAM_MATER=chmat, FOO=1)", "FOO : mot-clé inconnu"),
    ],
)
def test_detects_errors(catalog, source, expected):
    found = messages(check(catalog, source))
    assert any(expected in m for m in found), found


def test_python_variables_and_created_groups(catalog):
    source = (
        "E = 2.1e5\n"
        "mat2 = DEFI_MATERIAU(ELAS=_F(E=E, NU=0.3))\n"
        'mail = DEFI_GROUP(reuse=mail, MAILLAGE=mail, CREA_GROUP_NO=_F(GROUP_MA="X1", NOM="N_X1"))\n'
        'cl = AFFE_CHAR_MECA(MODELE=model, DDL_IMPO=_F(GROUP_NO="N_X1", DX=0.0))'
    )
    assert messages(check(catalog, source)) == []


def test_no_mesh_no_group_check(catalog):
    source = 'cl = AFFE_CHAR_MECA(MODELE=model, DDL_IMPO=_F(GROUP_MA="NOPE", DX=0.0))'
    assert messages(check(catalog, source, groups=None)) == []


def test_skeleton(catalog):
    text = catalog.skeleton("MECA_STATIQUE", "resu")
    assert text.startswith("resu = MECA_STATIQUE(\n")
    assert "    MODELE=...," in text
    compile(text, "x", "exec")
    issues = check(catalog, text)
    assert any("à compléter" in m for m in messages(issues, "warning"))
