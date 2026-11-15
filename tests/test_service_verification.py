"""L'écran de vérification enchaîné, côté Atelya (moteur/service_verification.py) : le plan, puis les photos.
Le calage des photos est remplacé par un faux : ces tests ne chargent aucun réseau."""
import json
import threading
import urllib.error
import urllib.request

import numpy as np
import pytest

from moteur import service_verification as sv
from moteur.images import ecrire_image

LOGEMENT = {"schema": "logement/0.1", "projet_id": "essai", "murs": [{"id": "m1", "debut": [0, 0], "fin": [4, 0], "epaisseur": 0.2}],
            "pieces": [{"id": "chambre_1", "nom": "Chambre 2"}, {"id": "chambre_2", "nom": "Chambre 3"}, {"id": "sejour_1", "nom": "Séjour"}]}


def _dossiers(tmp_path, n=3):
    lecture, photos = tmp_path / "lecture", tmp_path / "photos"
    lecture.mkdir(); photos.mkdir()
    (lecture / "verification.json").write_text(json.dumps({"schema": "verification/0.1", "calage": {"px_par_m": 100, "origine_px": [0, 0]},
                                                           "logement": LOGEMENT, "doutes": [{"element": "m1", "raison": "mur douteux"}]}), encoding="utf-8")
    ecrire_image(lecture / "plan.png", np.full((50, 80, 3), 255, np.uint8))
    for i in range(1, n + 1):
        ecrire_image(photos / f"photo-0{i}.jpg", np.full((60, 90, 3), 60 * i, np.uint8))
    return lecture, photos


def _faux_calage(photos, journal_des_appels):
    """Comme le vrai : sûr de la photo 1 ; hésite pour les autres tant qu'aucun endroit n'est pointé pour elles."""
    def ranger(logement, journal):
        fichier = photos / sv.PIECES_DES_PHOTOS
        endroits = json.loads(fichier.read_text(encoding="utf-8")).get("endroits", {}) if fichier.is_file() else {}
        journal_des_appels.append({"logement": logement, "endroits": dict(endroits)})
        noms = sorted(p.stem for p in photos.glob("*.jpg"))
        cam = {"x": 1.0, "y": 2.0, "cap": 90.0}
        sures = [n for n in noms if n == "photo-01" or n in endroits]
        for n in noms:
            journal(f"  {n} : mesurée (meubles : lit)")
        journal("  groupes : " + "+".join(noms))
        return {"fichier": "{nom}.jpg", "cameras": {n: {"camera": cam, "piece": "chambre_1"} for n in sures},
                "incertaines": {n: {"camera": cam, "piece": "chambre_1", "hesite_avec": ["chambre_2"]} for n in noms if n not in sures},
                "a_verifier": {}, "non_calees": {},
                "a_pointer": {n: "Atelya hésite entre chambre_1 et chambre_2. Pointez d'où la photo est prise." for n in noms if n not in sures}}
    return ranger


def test_avancement_en_phrases_simples():
    assert sv.avancement([], 3) == (0, "Atelya se prépare…")
    assert sv.avancement(["Photos calées seules (3 photos…) :", "  photo-01 : mesurée (meubles : lit)"], 3) == (1, "Il regarde la photo 2 sur 3…")
    lignes = ["  photo-01 : mesurée (meubles : lit)", "  photo-02 : trop peu de murs visibles, photo laissée de côté", "  photo-03 : mesurée (meubles : rien de net)"]
    assert sv.avancement(lignes, 3) == (3, "Il compare les photos entre elles…")
    assert sv.avancement(lignes + ["  groupes : photo-01+photo-03"], 3) == (3, "Il pose chaque pièce sur le plan…")


def test_le_plan_puis_les_questions_puis_la_fin(tmp_path):
    lecture, photos = _dossiers(tmp_path)
    appels = []
    e = sv.Enchainement(lecture, photos, _faux_calage(photos, appels), journal=lambda *a: None)
    v = e.verification()
    assert v["photos"] == {"a_suivre": True, "nombre": 3} and v["doutes"] and e.etat()["etape"] == "plan"
    with pytest.raises(sv.Refus):  # pas de réponses sur les photos avant le plan
        e.photos_repondues({"photos": {"endroits": {}}})
    with pytest.raises(sv.Refus):  # un plan sans logement lisible
        e.plan_valide({"logement": {"schema": "logement/0.1", "murs": []}})

    corrige = {**LOGEMENT, "murs": LOGEMENT["murs"] + [{"id": "m2", "debut": [4, 0], "fin": [4, 3], "epaisseur": 0.2}]}
    e.plan_valide({"schema": "resultat-verification/0.1", "projet_id": "essai", "statut": "valide", "logement": corrige})
    e.attendre(10)
    assert appels[0]["logement"] == corrige                         # les photos sont rangées sur le plan VÉRIFIÉ
    assert json.loads((lecture / "logement-verifie.json").read_text(encoding="utf-8")) == corrige
    s = e.etat()
    assert s["etape"] == "questions" and s["rangees"] == 1 and s["total"] == 3 and s["tour"] == 1
    assert [q["nom"] for q in s["photos"]["questions"]] == ["photo-02", "photo-03"]
    assert "« Chambre 2 »" in s["photos"]["questions"][0]["question"]  # les noms affichés à l'écran, pas les identifiants
    assert e.verification()["logement"] == corrige and e.verification()["doutes"] == []  # page rouverte : le plan vérifié
    assert not e.fin_vue.is_set()
    with pytest.raises(sv.Refus):  # le plan est déjà terminé
        e.plan_valide({"logement": corrige})

    # une photo pointée, une « je ne sais pas », et une photo qui n'était pas demandée (ignorée)
    e.photos_repondues({"photos": {"endroits": {"photo-02": [1.5, 2.25, 45.0], "photo-01": [9, 9, 0]}, "passees": ["photo-03"]}})
    e.attendre(10)
    rangement = json.loads((photos / sv.PIECES_DES_PHOTOS).read_text(encoding="utf-8"))
    assert rangement["endroits"] == {"photo-02": [1.5, 2.25, 45.0]} and appels[1]["endroits"] == rangement["endroits"]
    s = e.etat()
    assert s["etape"] == "fini" and s["rangees"] == 2 and s["laissees"] == 1 and s["tour"] == 2  # la photo passée n'est pas redemandée
    assert s["places"] == [{"nom": n, "x": 1.0, "y": 2.0, "cap": 90.0, "piece": "chambre_1"} for n in ("photo-01", "photo-02")]  # dessinées sur le plan
    assert e.fin_vue.is_set()


def test_aucune_question(tmp_path):
    lecture, photos = _dossiers(tmp_path, n=1)
    e = sv.Enchainement(lecture, photos, _faux_calage(photos, []), journal=lambda *a: None)
    e.plan_valide({"logement": LOGEMENT})
    e.attendre(10)
    s = e.etat()
    assert s["etape"] == "fini" and s["rangees"] == 1 and s["total"] == 1 and s["laissees"] == 0 and "photos" not in s


def test_le_calcul_plante_on_peut_recommencer(tmp_path):
    lecture, photos = _dossiers(tmp_path)
    bon, essais = _faux_calage(photos, []), []

    def ranger(logement, journal):
        essais.append(1)
        if len(essais) == 1:
            raise RuntimeError("carte graphique occupée")
        return bon(logement, journal)
    e = sv.Enchainement(lecture, photos, ranger, journal=lambda *a: None)
    e.plan_valide({"logement": LOGEMENT})
    e.attendre(10)
    s = e.etat()
    assert s["etape"] == "erreur" and "carte graphique occupée" in s["erreur"] and s["retour"] == "plan" and not e.fin_vue.is_set()
    e.plan_valide({"logement": LOGEMENT})  # « Terminer le plan » une seconde fois
    e.attendre(10)
    assert e.etat()["etape"] == "questions"


def test_dossiers_incomplets(tmp_path):
    lecture, photos = _dossiers(tmp_path)
    vide = tmp_path / "vide"; vide.mkdir()
    with pytest.raises(FileNotFoundError):
        sv.Enchainement(lecture, vide, lambda *a: {})
    with pytest.raises(FileNotFoundError):
        sv.Enchainement(vide, photos, lambda *a: {})


def test_le_service_par_le_navigateur(tmp_path):
    """Les mêmes échanges par le petit serveur local, comme les fait la page de l'écran."""
    lecture, photos = _dossiers(tmp_path)
    e = sv.Enchainement(lecture, photos, _faux_calage(photos, []), journal=lambda *a: None)
    serveur, adresse = sv.servir(e, port=0)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    try:
        def lire(chemin, corps=None, entetes=None):
            r = urllib.request.Request(adresse.rstrip("/") + chemin, data=None if corps is None else json.dumps(corps).encode("utf-8"),
                                       headers={"Content-Type": "application/json", **(entetes or {})})
            try:
                with urllib.request.urlopen(r, timeout=10) as f:
                    return f.status, f.read()
            except urllib.error.HTTPError as x:
                return x.code, x.read()

        code, page = lire("/index.html")
        assert code == 200 and b"fond-attente" in page
        assert lire("/verification.js")[0] == 200 and lire("/calculs-verif.js")[0] == 200
        assert lire("/atelya/plan.png")[1][:4] == b"\x89PNG"
        assert json.loads(lire("/atelya/verification.json")[1])["photos"] == {"a_suivre": True, "nombre": 3}
        assert json.loads(lire("/atelya/etat")[1])["etape"] == "plan"
        assert lire("/../CLAUDE.md")[0] == 404 and lire("/tests/verif.test.js")[0] == 404  # rien d'autre que l'écran n'est donné

        assert lire("/atelya/plan", {"logement": LOGEMENT}, {"Origin": "https://ailleurs.example"})[0] == 403  # un autre site : refusé
        assert lire("/atelya/etat", entetes={"Host": "ailleurs.example"})[0] == 403
        assert lire("/atelya/plan", {"logement": {}})[0] == 409
        assert json.loads(lire("/atelya/etat")[1])["etape"] == "plan"
        assert lire("/atelya/plan", {"logement": LOGEMENT}, {"Origin": adresse.rstrip("/")})[0] == 202
        e.attendre(10)
        s = json.loads(lire("/atelya/etat")[1])
        assert s["etape"] == "questions" and len(s["photos"]["questions"]) == 2 and s["photos"]["questions"][0]["image"].startswith("data:image/jpeg")
        assert lire("/atelya/photos", {"photos": {"endroits": {"photo-02": [1, 2, 3], "photo-03": [2, 2]}}})[0] == 202
        e.attendre(10)
        s = json.loads(lire("/atelya/etat")[1])
        assert s["etape"] == "fini" and s["rangees"] == 3 and e.fin_vue.is_set()
    finally:
        serveur.shutdown()
        serveur.server_close()
