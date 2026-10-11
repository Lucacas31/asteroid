import pytest

from asteroid.core import pyvalue
from conftest import CUBE_COMM_BLOCKS


@pytest.mark.parametrize("source", CUBE_COMM_BLOCKS)
def test_roundtrip_is_stable(source):
    st = pyvalue.parse_statement(source)
    rendered = pyvalue.render_statement(st.command, st.concept, st.params)
    again = pyvalue.parse_statement(rendered)
    assert again == st


def test_value_tree():
    st = pyvalue.parse_statement(
        'cl = AFFE_CHAR_MECA(MODELE=model, DDL_IMPO=(_F(GROUP_MA=("X0", "X1"), DX=-1.5),), '
        "PRES_REP=_F(GROUP_MA='P', PRES=2*pi), INFO=1)"
    )
    assert st.command == "AFFE_CHAR_MECA"
    assert st.concept == "cl"
    assert st.params["MODELE"] == {"$ref": "model"}
    assert st.params["DDL_IMPO"] == [{"GROUP_MA": ["X0", "X1"], "DX": -1.5}]
    assert st.params["PRES_REP"]["PRES"] == {"$expr": "2*pi"}
    assert st.params["INFO"] == 1


def test_command_without_concept():
    st = pyvalue.parse_statement("IMPR_RESU(RESU=_F(RESULTAT=resu))")
    assert st.concept is None
    assert pyvalue.render_statement(st.command, None, st.params) == "IMPR_RESU(RESU=_F(RESULTAT=resu))"


def test_single_element_tuple():
    assert pyvalue.render_value(["SIGM_NOEU"]) == '("SIGM_NOEU",)'


@pytest.mark.parametrize(
    "source, reason",
    [
        ("a = 1\nb = 2", "plusieurs instructions"),
        ("x = FOO(1)", "positionnels"),
        ("for i in range(3): pass", "pas un appel"),
        ("x = FOO(", "syntaxe"),
    ],
)
def test_parse_errors(source, reason):
    with pytest.raises(pyvalue.ParseError, match=reason):
        pyvalue.parse_statement(source)


def test_long_statement_is_wrapped():
    st = pyvalue.parse_statement(CUBE_COMM_BLOCKS[4])
    text = pyvalue.render_statement(st.command, st.concept, st.params)
    assert all(len(line) <= pyvalue.LINE_WIDTH for line in text.splitlines())
    assert text.count("\n") > 1
