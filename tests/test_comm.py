from asteroid.core import comm
from asteroid.core.model import Block, ExtraFile, Project
from conftest import CUBE_COMM_BLOCKS


def project(blocks, mesh="cube.med") -> Project:
    return Project(mesh=mesh, blocks=[Block(mode="text", text=t) for t in blocks])


def test_generate_cube():
    res = comm.generate(project(CUBE_COMM_BLOCKS))
    lines = res.comm.splitlines()
    assert lines[0] == "DEBUT()"
    assert lines[-1] == "FIN()"
    assert [b.command for b in res.blocks][:3] == ["LIRE_MAILLAGE", "AFFE_MODELE", "DEFI_MATERIAU"]
    assert res.blocks[0].concept == "mail"
    assert res.blocks[8].concept is None
    # Les plages de lignes pointent bien sur le texte de chaque bloc.
    for info, text in zip(res.blocks, CUBE_COMM_BLOCKS):
        assert "\n".join(lines[info.start_line - 1 : info.end_line]) == text
    assert res.export.splitlines() == [
        "P time_limit 300",
        "P memory_limit 2048",
        "F comm run.comm D 1",
        "F mmed mesh.med D 20",
        "F rmed resultat.rmed R 80",
        "F mess message R 6",
    ]
    assert res.warnings == []


def test_units_from_text_blocks():
    res = comm.generate(project([
        'mail = LIRE_MAILLAGE(UNITE=21)',
        'IMPR_RESU(FORMAT="MED", UNITE=81, RESU=_F(RESULTAT=resu))',
        'IMPR_RESU(FORMAT="MED", RESU=_F(RESULTAT=resu2))',
        'IMPR_TABLE(TABLE=tab)',
        'DEFI_FICHIER(UNITE=50, FICHIER="x.txt")',
        'x = LIRE_FONCTION(UNITE=40)',
    ]))
    names = {(f.kind, f.name, f.mode, f.unit) for f in res.files}
    assert names == {
        ("mmed", "mesh.med", "D", 21),
        ("rmed", "resultat.rmed", "R", 81),
        ("rmed", "resultat_80.rmed", "R", 80),
        ("resu", "resultat.resu", "R", 8),
    }
    assert res.warnings == ["LIRE_FONCTION : UNITE=40 non rattachée à un fichier"]


def test_missing_mesh_warning_and_syntax_error():
    res = comm.generate(project(['mail = LIRE_MAILLAGE()', "x = FOO("], mesh=None))
    assert "aucun maillage" in res.warnings[0]
    assert res.blocks[1].error.startswith("erreur de syntaxe")


def test_form_block_rendering():
    block = Block(command="DEFI_MATERIAU", concept="mat", mode="form",
                  params={"ELAS": {"E": 210000.0, "NU": 0.3}})
    res = comm.generate(Project(blocks=[block]))
    assert "mat = DEFI_MATERIAU(ELAS=_F(E=210000.0, NU=0.3))" in res.comm


def test_new_text_block_names():
    b = comm.new_text_block("DEFI_MATERIAU", {"mat"})
    assert b.concept == "mat2" and b.text.startswith("mat2 = DEFI_MATERIAU(")
    assert comm.new_text_block("CALC_CHAMP", {"resu"}).concept == "resu"
    assert comm.new_text_block("IMPR_RESU", set()).concept is None
    skeleton = comm.new_text_block("POST_RELEVE_T", set()).text
    assert skeleton.startswith("post = POST_RELEVE_T(\n") and "ACTION=_F(" in skeleton
    compile(skeleton, "x", "exec")


def test_block_for_line():
    res = comm.generate(project(CUBE_COMM_BLOCKS))
    third = res.blocks[2]
    assert comm.block_for_line(res.blocks, third.start_line) == third.id
    assert comm.block_for_line(res.blocks, 1) is None


def test_mesh_scale():
    res = comm.generate(project([
        'mail = LIRE_MAILLAGE(FORMAT="MED")',
        "mail = MODI_MAILLAGE(reuse=mail, MAILLAGE=mail, ECHELLE=1000.0)",
    ]))
    assert res.mesh_scale == 1000.0
    assert comm.generate(project(CUBE_COMM_BLOCKS)).mesh_scale == 1.0


def test_preview_contains_validation():
    blocks = list(CUBE_COMM_BLOCKS)
    blocks[4] = blocks[4].replace('"X0"', '"NOPE"')
    res = comm.generate(project(blocks), mesh_groups={"GROUP_MA": {"X0", "Y0", "Z0", "X1"}, "GROUP_NO": set()})
    errors = [(b.command, i["message"]) for b in res.blocks for i in b.issues if i["level"] == "error"]
    assert len(errors) == 1
    assert errors[0][0] == "AFFE_CHAR_MECA" and "« NOPE » absent du maillage" in errors[0][1]


def test_expressions_in_keywords_do_not_break_preview():
    """Régression : une expression (2*F) dans un mot-clé faisait planter l'analyse des unités."""
    res = comm.generate(project([
        "F = 10.0",
        'cl = AFFE_CHAR_MECA(MODELE=model, FORCE_FACE=_F(GROUP_MA="X1", FX=2*F))',
        "IMPR_RESU(UNITE=2*40, RESU=_F(RESULTAT=resu))",
    ]))
    assert "FX=2*F" in res.comm


def test_extra_files_attached_to_units():
    p = project(['f = LIRE_FONCTION(UNITE=40, FORMAT="LIBRE")', 'IMPR_TABLE(TABLE=t, UNITE=41)'])
    assert comm.generate(p).unattached == [{"command": "LIRE_FONCTION", "unit": 40}]
    p.files = [ExtraFile(unit=40, path="data/courbe.txt"), ExtraFile(unit=41, path="table.txt", mode="R")]
    res = comm.generate(p)
    assert res.unattached == [] and res.warnings == []
    assert "F libr courbe.txt D 40" in res.export
    assert "F libr table.txt R 41" in res.export
