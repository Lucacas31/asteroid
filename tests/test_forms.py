import pytest

from asteroid.core import comm, forms, pyvalue
from asteroid.core.model import Block, Project
from conftest import CUBE_COMM_BLOCKS


@pytest.mark.parametrize("source", CUBE_COMM_BLOCKS[:9])
def test_cube_blocks_fit_forms(source):
    """Tous les blocs du cas test (sauf TEST_RESU) passent en formulaire, sans perte."""
    command, concept, params = forms.text_to_form(source)
    rendered = forms.render_form(command, concept, params)
    original = pyvalue.parse_statement(source)
    again = pyvalue.parse_statement(rendered)
    assert again.command == original.command and again.concept == original.concept

    def norm(v):  # _F seul ≡ tuple d'un _F, "X" ≡ ("X",)
        if isinstance(v, list) and len(v) == 1:
            return norm(v[0])
        if isinstance(v, list):
            return [norm(x) for x in v]
        if isinstance(v, dict) and not pyvalue.is_ref(v):
            return {k: norm(x) for k, x in v.items()}
        return v

    assert norm(again.params) == norm(original.params)


@pytest.mark.parametrize(
    "source, reason",
    [
        ("x = TEST_RESU()", "pas de formulaire"),
        ('m = AFFE_MODELE(MAILLAGE=mail, AFFE=_F(TOUT="OUI", PHENOMENE="THERMIQUE"))', "THERMIQUE"),
        ("mat = DEFI_MATERIAU(ELAS=_F(E=E, NU=0.3))", "variable Python « E »"),
        ("mat = DEFI_MATERIAU(ELAS=_F(E=2*1e5, NU=0.3))", "expression Python"),
        ("mat = DEFI_MATERIAU(ELAS=_F(E=1.0, NU=0.3), ELAS_ORTH=_F(E_L=1.0))", "ELAS et ELAS_ORTH"),
        ("mat = DEFI_MATERIAU(ELAS=_F(E=1.0, NU=0.3, FOO=1))", "ELAS/FOO non géré"),
        ("mail = LIRE_MAILLAGE(UNITE=21)", "UNITE=21"),
        ("x = AFFE_MODELE(", "syntaxe"),
    ],
)
def test_text_to_form_reasons(source, reason):
    with pytest.raises(forms.FormError, match=reason):
        forms.text_to_form(source)


def test_auto_unit_dropped():
    _, _, params = forms.text_to_form("mail = LIRE_MAILLAGE(FORMAT='MED', UNITE=20)")
    assert params == {"FORMAT": "MED"}


def test_render_order_and_reuse():
    params = {"CRITERES": ["SIEQ_NOEU"], "RESULTAT": {"$ref": "resu"}, "CONTRAINTE": [], "DEFORMATION": None}
    text = forms.render_form("CALC_CHAMP", "resu", params)
    assert text == 'resu = CALC_CHAMP(reuse=resu, RESULTAT=resu, CRITERES=("SIEQ_NOEU",))'


def test_empty_values_are_dropped():
    params = {"MODELE": {"$ref": "model"}, "DDL_IMPO": [{"GROUP_MA": ["X0"], "DX": 0.0, "DY": None}], "FORCE_FACE": []}
    text = forms.render_form("AFFE_CHAR_MECA", "cl", params)
    assert text == 'cl = AFFE_CHAR_MECA(MODELE=model, DDL_IMPO=(_F(GROUP_MA=("X0",), DX=0.0),))'


def test_impr_resu_units_allocated():
    blocks = [
        Block(mode="form", command="IMPR_RESU", params={"FORMAT": "MED", "RESU": [{"RESULTAT": {"$ref": "r1"}}]}),
        Block(mode="text", text='IMPR_RESU(FORMAT="MED", UNITE=81, RESU=_F(RESULTAT=r2))'),
        Block(mode="form", command="IMPR_RESU", params={"FORMAT": "MED", "RESU": [{"RESULTAT": {"$ref": "r3"}}]}),
    ]
    res = comm.generate(Project(blocks=blocks))
    assert 'IMPR_RESU(FORMAT="MED", RESU=(_F(RESULTAT=r1),))' in res.comm
    assert "UNITE=82" in res.comm
    assert {f.unit for f in res.files} == {80, 81, 82}


def test_new_block_form_defaults():
    b = comm.new_block("AFFE_MODELE", set())
    assert b.mode == "form" and b.concept == "model"
    assert b.params["AFFE"][0]["MODELISATION"] == "3D"
    assert comm.new_block("POST_RELEVE_T", set()).mode == "text"


def test_floats_written_as_floats():
    params = {"ELAS": {"E": 210000, "NU": 0.3}}
    assert forms.render_form("DEFI_MATERIAU", "mat", params) == "mat = DEFI_MATERIAU(ELAS=_F(E=210000.0, NU=0.3))"
