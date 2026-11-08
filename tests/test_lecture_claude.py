"""Le format de la lecture de Claude (moteur.lecture_claude 0.1.0) : fiche acceptée, refusée, doutes, taille de l'image."""
from __future__ import annotations

import copy

import numpy as np

from moteur.lecture_claude import (COTE_MAX_PX, JETONS_MAX, consigne, controler_fiche, image_pour_claude, jetons_image,
                                   taille_pour_claude)


def _fiche() -> dict:
    """Un studio de 4 × 3 m dessiné à 100 px/m, murs de 20 cm, une porte, une fenêtre, une cloison (salle d'eau)."""
    return {
        "schema": "lecture-claude/0.1",
        "image": {"nom": "studio.png", "largeur": 600, "hauteur": 500},
        "murs": [
            {"id": "M1", "axe": [90, 410, 510, 410], "epaisseur_px": 20},
            {"id": "M2", "axe": [500, 100, 500, 420], "epaisseur_px": 20},
            {"id": "M3", "axe": [90, 110, 510, 110], "epaisseur_px": 20},
            {"id": "M4", "axe": [100, 100, 100, 420], "epaisseur_px": 20},
            {"id": "M5", "axe": [350, 110, 350, 410], "epaisseur_px": 8},
        ],
        "ouvertures": [
            {"id": "O1", "type": "porte", "bords": [150, 410, 233, 410], "mur": "M1"},
            {"id": "O2", "type": "fenetre", "bords": [180, 110, 300, 110], "mur": "M3"},
        ],
        "pieces": [
            {"id": "P1", "nom": "Séjour", "type": "sejour", "point": [220, 260],
             "contour": [[110, 120], [346, 120], [346, 400], [110, 400]]},
            {"id": "P2", "nom": None, "type": "salle_d_eau", "point": [420, 260]},
        ],
        "cotes": [
            {"texte": "4,00", "valeur_m": 4.0, "cadre": [280, 440, 320, 455], "bouts": [[100, 450], [500, 450]], "mur": "M1"},
            {"texte": "300", "valeur_m": 3.0, "cadre": [40, 250, 60, 275], "bouts": [[60, 110], [60, 410]], "mur": "M4"},
        ],
        "surfaces": [{"texte": "6,8 m²", "valeur_m2": 6.8, "cadre": [200, 280, 250, 295], "piece": "P1"}],
        "textes": [{"texte": "1/50", "cadre": [500, 470, 540, 485], "genre": "echelle_ecrite"}],
        "echelle_proposee": {"px_par_m": 100.0, "source": "cotes", "explication": "4,00 m = 400 px"},
        "doutes": [{"raison": "la porte de la salle d'eau n'est pas dessinée", "gravite": "fort", "element": "M5"}],
    }


def test_fiche_correcte_acceptee():
    f = controler_fiche(_fiche(), image_envoyee=(600, 500))
    assert not f.refusee
    assert f.problemes == []
    assert len(f.lecture.murs) == 5 and f.lecture.cotes[1].valeur_m == 3.0


def test_forme_invalide_refusee():
    for abimer in (
        lambda d: d["pieces"][0].update(type="garage"),  # type inconnu
        lambda d: d["murs"][1].update(id="M1"),  # id en double
        lambda d: d["ouvertures"][0].update(mur="M9"),  # mur inconnu
        lambda d: d["surfaces"][0].update(piece="P9"),  # pièce inconnue
        lambda d: d.pop("echelle_proposee"),  # champ obligatoire manquant
        lambda d: d.update(couleur="rouge"),  # champ inventé
        lambda d: d["murs"][0].update(epaisseur_px=0),  # épaisseur nulle
        lambda d: d["pieces"][0].update(contour=[[1, 1], [2, 2]]),  # contour de 2 points
    ):
        d = _fiche()
        abimer(d)
        f = controler_fiche(d)
        assert f.refusee and f.lecture is None, d
        assert f.problemes[0].code == "forme"


def test_image_d_une_autre_taille_refusee():
    f = controler_fiche(_fiche(), image_envoyee=(1200, 1000))
    assert f.refusee and f.problemes[0].code == "image_taille"


def test_image_que_l_api_aurait_reduite_refusee():
    d = _fiche()
    d["image"].update(largeur=4000, hauteur=3000)
    f = controler_fiche(d)
    assert f.refusee and any(p.code == "image_reduite" for p in f.problemes)


def test_points_hors_image():
    d = _fiche()
    d["murs"][0]["axe"] = [90, 410, 605, 410]  # 5 px dehors (< 2 %) : ramené au bord
    f = controler_fiche(d)
    assert not f.refusee and f.lecture.murs[0].axe[2] == 600
    d["murs"][0]["axe"] = [90, 410, 700, 410]  # 100 px dehors : refus
    f = controler_fiche(d)
    assert f.refusee and any(p.code == "hors_image" for p in f.problemes)


def test_traits_nuls_refuses():
    d = _fiche()
    d["murs"][0]["axe"] = [90, 410, 90, 410]
    assert any(p.code == "mur_nul" for p in controler_fiche(d).problemes)
    d = _fiche()
    d["cotes"][0]["bouts"] = [[100, 450], [100, 450]]
    assert any(p.code == "cote_nulle" for p in controler_fiche(d).problemes)


def test_nombre_mal_recopie_donne_un_doute():
    d = _fiche()
    d["cotes"][0]["valeur_m"] = 4.35  # écrit « 4,00 »
    d["surfaces"][0]["valeur_m2"] = 8.6  # écrit « 6,8 m² »
    f = controler_fiche(d)
    assert not f.refusee
    assert {p.code for p in f.problemes} == {"cote_mal_recopiee", "surface_mal_recopiee"}
    assert all(p.gravite == "doute" for p in f.problemes)


def test_cote_en_centimetres_bien_comprise():
    d = _fiche()
    d["cotes"][1]["valeur_m"] = 300.0  # « 300 » compté en mètres au lieu de centimètres
    f = controler_fiche(d)
    assert [p.code for p in f.problemes] == ["cote_mal_recopiee"]


def test_point_hors_contour_donne_un_doute():
    d = _fiche()
    d["pieces"][0]["point"] = [420, 260]
    f = controler_fiche(d)
    assert [p.code for p in f.problemes] == ["point_hors_contour"]


def test_taille_pour_claude_comme_la_documentation():
    # Exemples de la documentation de l'API (vision, vision-coordinates), lus le 08/11/2026.
    assert taille_pour_claude(1075, 1520, 1568, 1568) == (924, 1307)  # modèles « standard »
    assert taille_pour_claude(1920, 1080, 1568, 1568) == (1456, 819)
    assert taille_pour_claude(1920, 1080) == (1920, 1080)  # haute résolution : inchangée (2 691 jetons)
    assert taille_pour_claude(3840, 2160) == (2576, 1449)
    assert taille_pour_claude(2000, 1500) == (2000, 1500)  # 3 888 jetons
    for w, h in ((5000, 3500), (3500, 5000), (8000, 1000), (2600, 2600)):
        l2, h2 = taille_pour_claude(w, h)
        assert l2 <= COTE_MAX_PX and h2 <= COTE_MAX_PX and jetons_image(l2, h2) <= JETONS_MAX
        assert taille_pour_claude(l2, h2) == (l2, h2)  # une image déjà réduite n'est plus touchée


def test_image_pour_claude():
    img = np.full((3000, 4000, 3), 255, np.uint8)
    petite, f = image_pour_claude(img)
    assert petite.shape[:2][::-1] == taille_pour_claude(4000, 3000)
    assert abs(f - petite.shape[1] / 4000) < 1e-9
    deja, f1 = image_pour_claude(petite)
    assert deja is petite and f1 == 1.0


def test_fiche_non_modifiee_et_consigne():
    d = _fiche()
    avant = copy.deepcopy(d)
    controler_fiche(d)
    assert d == avant
    texte = consigne()
    assert "lecture-claude/0.1" in texte and "PIXELS" in texte and "salle_d_eau" in texte
