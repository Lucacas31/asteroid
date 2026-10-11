from asteroid.core.message import parse_message, status_from

SAMPLE = """\
# Commande #0002 de run.comm.changed.py, ligne 15
mail = LIRE_MAILLAGE(FORMAT='MED',
                     INFO=1)

# Commande #0006 de run.comm.changed.py, ligne 18
cl = AFFE_CHAR_MECA(MODELE=model)

 ╔════════════════════════════════════════════════════════════════════════╗
 ║ <A> <MODELISA4_9>                                                      ║
 ║                                                                        ║
 ║ Une alarme sur deux                                                    ║
 ║ lignes.                                                                ║
 ╚════════════════════════════════════════════════════════════════════════╝

 ╔════════════════════════════════════════════════════════════════════════╗
 ║ <EXCEPTION> <MODELISA7_77>                                             ║
 ║                                                                        ║
 ║ le GROUP_MA  INEXISTANT  ne fait pas partie du maillage :  00000001    ║
 ╚════════════════════════════════════════════════════════════════════════╝

 ╔════════════════════════════════════════════════════════════════════════╗
 ║ <I> <CATAMESS_89>                                                      ║
 ║ Liste des alarmes émises lors de l'exécution du calcul.                ║
 ╚════════════════════════════════════════════════════════════════════════╝

   !----------------------------------------------------------------!
   ! <F> <DVP_1>                                                    !
   ! ancien format                                                  !
   !----------------------------------------------------------------!

--- DIAGNOSTIC JOB : <S>_ERROR
"""


def test_parse_message():
    report = parse_message(SAMPLE)
    assert report.diagnostic == "<S>_ERROR"
    levels = [(m.level, m.id) for m in report.messages]
    assert levels == [("A", "MODELISA4_9"), ("F", "MODELISA7_77"), ("F", "DVP_1")]
    alarm = report.messages[0]
    assert alarm.text == "Une alarme sur deux\nlignes."
    assert alarm.exec_line == 18
    assert [(c.number, c.command, c.concept) for c in report.commands] == [
        (2, "LIRE_MAILLAGE", "mail"),
        (6, "AFFE_CHAR_MECA", "cl"),
    ]
    # mail est en ligne 3 du .comm, cl en ligne 9 : décalage de 12.
    offset = report.align([(3, "LIRE_MAILLAGE", "mail"), (9, "AFFE_CHAR_MECA", "cl"), (20, "X", "y")])
    assert offset == 12
    assert alarm.comm_line == 6


def test_align_with_debut_only():
    report = parse_message("# Commande #0001 de f.py, ligne 13\nDEBUT()\n")
    assert report.align([]) == 12


def test_status():
    assert status_from("OK", 0) == "ok"
    assert status_from("<A>_ALARM", 0) == "alarm"
    assert status_from("<S>_ERROR", 1) == "fail"
    assert status_from("NOOK_TEST_RESU", 0) == "fail"
    assert status_from(None, 0) == "ok"
    assert status_from(None, 137) == "fail"
