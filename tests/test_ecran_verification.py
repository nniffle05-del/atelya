"""L'écran de vérification (outils/verification-plan) rend des logement.json que le moteur sait lire.

Ces tests ne lancent pas la page : ils relisent, avec les règles du moteur (moteur/logement.py),
le logement d'exemple AVANT vérification et le logement corrigé enregistré par le bouton « Valider ».
"""

import json
from pathlib import Path

from moteur.logement import charger_logement, verifier_coherence

DOSSIER = Path(__file__).resolve().parent.parent / "outils" / "verification-plan" / "exemples"


def test_la_lecture_a_verifier_est_un_logement_valide():
    v = json.loads((DOSSIER / "exemple-cas-test-00.verification.json").read_text(encoding="utf-8"))
    chemin = DOSSIER / "_lecture.json"
    try:
        chemin.write_text(json.dumps(v["logement"], ensure_ascii=False), encoding="utf-8")
        logement = charger_logement(chemin)
    finally:
        chemin.unlink(missing_ok=True)
    assert verifier_coherence(logement) == []


def test_le_logement_corrige_est_lu_par_le_moteur():
    logement = charger_logement(DOSSIER / "exemple-cas-test-00.logement-corrige.json")
    assert verifier_coherence(logement) == []
    noms = {p.id: p.nom for p in logement.pieces}
    assert noms["chambre"] == "Chambre"  # corrigé (Atelya avait lu « Bureau »)
    portes_sdb = [o for o in logement.ouvertures if o.mur == "C_sdb" and o.type == "porte"]
    assert len(portes_sdb) == 1  # la porte oubliée a été ajoutée
    assert all(e.confiance == 1 for e in [*logement.murs, *logement.ouvertures, *logement.pieces]
               if "verification" in e.source)


def test_calculs_de_l_ecran_dans_edge():
    """Les tests JavaScript de l'écran (outils/verification-plan/tests/verif.test.js) lancés dans Edge (sans Node.js)."""
    import importlib.util
    chemin = Path(__file__).resolve().parent.parent / "outils" / "verification-plan" / "tests" / "lancer_dans_edge.py"
    spec = importlib.util.spec_from_file_location("lancer_dans_edge", chemin)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    res = module.lancer()
    if res is None:
        pytest.skip("Microsoft Edge absent")
    lignes, echecs = res
    assert echecs == 0, "\n".join(l for l in lignes if not l.startswith("OK"))
    assert len(lignes) >= 57
