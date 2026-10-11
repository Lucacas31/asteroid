import pytest

from asteroid.core import comm, pyvalue
from asteroid.core.comm_import import split_comm
from asteroid.core.model import Project

SOURCE = '''\
# Cube en traction
DEBUT(LANG="FR")

E = 210000.0
NU = 0.3

# Maillage
mesh = LIRE_MAILLAGE(UNITE=20)
model = AFFE_MODELE(MAILLAGE=mesh,
                    AFFE=_F(TOUT='OUI', PHENOMENE='MECANIQUE', MODELISATION='3D'))
mat = DEFI_MATERIAU(ELAS=_F(E=E, NU=NU))  # acier
for i in range(2):
    print(i)
IMPR_RESU(FORMAT="MED", UNITE=80, RESU=_F(RESULTAT=resu))
x = LIRE_FONCTION(UNITE=40)

FIN()
# fin du fichier
'''


def test_split_comm():
    res = split_comm(SOURCE)
    texts = [b.text for b in res.blocks]
    assert [b.command for b in res.blocks] == ["", "LIRE_MAILLAGE", "AFFE_MODELE", "DEFI_MATERIAU", "", "IMPR_RESU", "LIRE_FONCTION"]
    assert [b.mode for b in res.blocks] == ["text", "text", "form", "text", "text", "form", "text"]
    # L'en-tête placé avant DEBUT() est conservé avec le premier bloc.
    assert texts[0] == "# Cube en traction\nE = 210000.0\nNU = 0.3"
    # Bloc commenté : laissé en texte, intact.
    assert texts[1] == "# Maillage\nmesh = LIRE_MAILLAGE(UNITE=20)"
    assert "commentaires" in res.blocks[1].fallback_reason
    # Reconnu par le formulaire : passe en mode graphique.
    assert res.blocks[2].params["AFFE"][0]["MODELISATION"] == "3D"
    assert res.blocks[2].params["MAILLAGE"] == {"$ref": "mesh"}
    assert texts[3].endswith("# acier")
    assert texts[4] == "for i in range(2):\n    print(i)"
    assert "# fin du fichier" in texts[-1]
    assert not any("DEBUT" in t or "FIN()" in t for t in texts)
    assert res.blocks[1].concept == "mesh"
    assert 'DEBUT(LANG) retiré' in res.warnings[0]
    assert "LIRE_FONCTION : UNITE=40 non rattachée à un fichier" in res.warnings
    assert res.unattached == [{"command": "LIRE_FONCTION", "unit": 40}]
    assert res.units == ["UNITE=20 → mesh.med", "UNITE=80 → resultat.rmed"]


def test_import_then_generate_roundtrip():
    res = split_comm(SOURCE)
    generated = comm.generate(Project(mesh="m.med", blocks=res.blocks)).comm
    assert generated.startswith("DEBUT()")
    assert generated.count("FIN()") == 1
    compile(generated, "run.comm", "exec")


def test_syntax_error():
    with pytest.raises(pyvalue.ParseError, match="ligne 2"):
        split_comm("a = 1\nb = (\n")


def test_variable_keeps_text():
    res = split_comm("mat = DEFI_MATERIAU(ELAS=_F(E=E, NU=0.3))")
    assert res.blocks[0].mode == "text"
    assert "variable Python « E »" in res.blocks[0].fallback_reason


def test_several_statements_on_one_line():
    src = "DEBUT()\nmclf = {} ; mclf['RESU'] = []\nmail = LIRE_MAILLAGE(FORMAT='MED'); x = (\n  1)\nFIN()\n"
    res = split_comm(src)
    assert [b.text for b in res.blocks] == [
        "mclf = {} ; mclf['RESU'] = []",
        "mail = LIRE_MAILLAGE(FORMAT='MED'); x = (\n  1)",
    ]
    assert res.blocks[1].mode == "text" and "plusieurs instructions" in res.blocks[1].fallback_reason
    generated = comm.generate(Project(blocks=res.blocks), validate=False).comm
    assert generated.count("mclf = {}") == 1
    compile(generated, "x", "exec")
