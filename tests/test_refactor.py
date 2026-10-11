from asteroid.core.model import Block
from asteroid.core.refactor import rename_concept, replace_group


def form(command, concept, params):
    return Block(command=command, concept=concept, mode="form", params=params)


def text(source):
    return Block(mode="text", text=source)


def test_rename_concept_forms_and_text():
    blocks = [
        form("DEFI_MATERIAU", "pla", {"ELAS": {"E": 2300.0, "NU": 0.35}}),
        form("AFFE_MATERIAU", "chmat", {"MAILLAGE": {"$ref": "mail"}, "AFFE": [{"TOUT": "OUI", "MATER": {"$ref": "mat"}}]}),
        text("# matériau\nchmat2 = AFFE_MATERIAU(MAILLAGE=mail, AFFE=_F(TOUT='OUI', MATER=mat))  # mat ici reste"),
    ]
    out, count = rename_concept(blocks, 0, "mat", "pla")
    assert count == 2
    assert out[1].params["AFFE"][0]["MATER"] == {"$ref": "pla"}
    # Commentaires et chaînes conservés, seul le nom Python change.
    assert out[2].text == "# matériau\nchmat2 = AFFE_MATERIAU(MAILLAGE=mail, AFFE=_F(TOUT='OUI', MATER=pla))  # mat ici reste"
    assert out[1].id == blocks[1].id


def test_rename_follows_reuse_and_stops_on_redefinition():
    blocks = [
        form("LIRE_MAILLAGE", "mesh", {"FORMAT": "MED"}),
        form("MODI_MAILLAGE", "mail", {"MAILLAGE": {"$ref": "mail"}, "ECHELLE": 1000.0}),
        text("mail = DEFI_GROUP(reuse=mail, MAILLAGE=mail, CREA_GROUP_NO=_F(GROUP_MA='Charge'))"),
        form("AFFE_MODELE", "model", {"MAILLAGE": {"$ref": "mail"}}),
        text("mail = LIRE_MAILLAGE(UNITE=21)"),
        form("AFFE_MODELE", "model2", {"MAILLAGE": {"$ref": "mail"}}),
    ]
    out, count = rename_concept(blocks, 0, "mail", "mesh")
    assert out[1].concept == "mesh" and out[1].params["MAILLAGE"] == {"$ref": "mesh"}
    assert out[2].text == "mesh = DEFI_GROUP(reuse=mesh, MAILLAGE=mesh, CREA_GROUP_NO=_F(GROUP_MA='Charge'))"
    assert out[3].params["MAILLAGE"] == {"$ref": "mesh"}
    # Nouveau maillage du même nom : il n'est pas renommé, la suite le désigne toujours.
    assert out[4].text == "mail = LIRE_MAILLAGE(UNITE=21)"
    assert out[5].params["MAILLAGE"] == {"$ref": "mail"}
    assert count == 4


def test_rename_skips_invalid_text():
    blocks = [form("DEFI_MATERIAU", "mat", {}), text("chmat = AFFE_MATERIAU(MATER=mat")]
    out, count = rename_concept(blocks, 0, "mat", "pla")
    assert count == 0 and out[1].text == blocks[1].text


def test_replace_group_text_keeps_quotes_and_other_strings():
    block = text(
        "cl = AFFE_CHAR_MECA(MODELE=model,\n"
        "    DDL_IMPO=_F(GROUP_MA=('encastre', \"charge\"), DX=0.),\n"
        "    FORCE_FACE=_F(GROUP_MA='charge', FZ=-2.0))  # é 'charge'\n"
        "TITRE = 'charge'"
    )
    out, count = replace_group(block, "charge", "Charge")
    assert count == 2
    assert out.text == (
        "cl = AFFE_CHAR_MECA(MODELE=model,\n"
        "    DDL_IMPO=_F(GROUP_MA=('encastre', \"Charge\"), DX=0.),\n"
        "    FORCE_FACE=_F(GROUP_MA='Charge', FZ=-2.0))  # é 'charge'\n"
        "TITRE = 'charge'"
    )


def test_replace_group_form():
    block = form("AFFE_CHAR_MECA", "cl", {
        "DDL_IMPO": [{"GROUP_MA": ["encastre", "X0"], "DX": 0.0}],
        "FORCE_NODALE": [{"GROUP_NO": ["encastre"], "FX": 1.0}],
        "MODELE": {"$ref": "encastre"},
    })
    out, count = replace_group(block, "encastre", "Encastre")
    assert count == 2
    assert out.params["DDL_IMPO"][0]["GROUP_MA"] == ["Encastre", "X0"]
    assert out.params["FORCE_NODALE"][0]["GROUP_NO"] == ["Encastre"]
    assert out.params["MODELE"] == {"$ref": "encastre"}
