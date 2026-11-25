"""Le dessin des fenêtres lu sur les photos (F2, 20/11/2026, moteur/vitrages.py) : la vue par les fenêtres n'est peinte que par
les VITRES NUES de chaque photo (ni montants, ni rideau), là où elles sont vraiment sur la photo."""
import numpy as np

from moteur import vitrages as vt
from moteur import vue_dehors as vd
from tests.test_vue_dehors import _camera_piece_a, _logement

TAILLE = (1000, 700)


def fenetre(**plus) -> dict:
    """Un battant de 200 × 300 pixels, une traverse à mi-hauteur."""
    return {"baie": "F1", "coins": [[400, 200], [600, 200], [600, 500], [400, 500]], "traverses": [[345, 355, 345, 355]], **plus}


def test_les_vitres_nues_sont_le_vitrage_sans_ses_barres_ni_ses_caches():
    f = fenetre(montants=[[495, 505, 495, 505]], caches=[[560, 150, 700, 600]])
    nues, entier = vt.vitres_nues(f, TAILLE), vt.masque_du_vitrage(f, TAILLE)
    assert entier[350, 500] == 1 and entier[350, 380] == 0
    assert nues[250, 450] == 1 and nues[450, 530] == 1  # deux vitres
    assert nues[350, 450] == 0 and nues[250, 500] == 0  # la traverse et le montant
    assert nues[250, 580] == 0 and nues[250, 557] == 0 and nues[250, 550] == 1  # le cache (un rideau), et sa marge
    assert nues[202, 450] == 0 and nues[250, 402] == 0  # rétréci de la précision de la lecture
    assert nues[250, 495 - 7] == 1 and nues[250, 495 - 2] == 0  # la barre est élargie de la marge, pas plus
    assert vt.vitres_nues(fenetre(vue="lueur"), TAILLE).sum() == 0 and vt.vitres_nues({"baie": "F1", "vue": "non"}, TAILLE).sum() == 0


def test_un_cache_peut_etre_un_polygone():
    f = fenetre(caches=[[[560, 150], [700, 150], [700, 600], [460, 600]]])  # un rideau en biais
    nues = vt.vitres_nues(f, TAILLE)
    assert nues[220, 520] == 1 and nues[480, 520] == 0


def test_plusieurs_battants_font_une_seule_fenetre():
    lecture = {"format": vt.FORMAT, "photos": {"photo-01": [
        fenetre(), {"baie": "F1", "coins": [[620, 205], [800, 215], [800, 495], [620, 498]]}, {"baie": "F2", "vue": "non"}]}}
    assert vt.controler(lecture, {"photo-01": TAILLE}, {"F1", "F2"}) == []
    lu = vt.d_une_photo(lecture, "photo-01", TAILLE)
    assert set(lu) == {"F1", "F2"} and lu["F2"]["vue"] == "non" and lu["F2"]["vitres"].sum() == 0
    assert lu["F1"]["vitres"][250, 450] == 1 and lu["F1"]["vitres"][300, 700] == 1
    # le battement entre les deux battants (20 pixels) et la traverse sont des barres minces, à combler
    assert lu["F1"]["debout"][300, 610] == 1 and lu["F1"]["couchees"][350, 450] == 1 and lu["F1"]["debout"][300, 450] == 0
    assert lu["F1"]["vitrage"][300, 610] == 1  # le battement fait partie de la fenêtre
    assert vt.d_une_photo(lecture, "photo-02", TAILLE) == {} and vt.d_une_photo(None, "photo-01", TAILLE) == {}


def test_un_mur_entre_deux_vitrages_n_est_pas_comble():
    deux = [fenetre(), {"baie": "F1", "coins": [[700, 200], [900, 200], [900, 500], [700, 500]]}]  # 100 pixels entre les deux
    debout, _ = vt.barres_a_combler(deux, TAILLE)
    assert debout[300, 650] == 0


def test_le_controle_dit_les_defauts_d_une_lecture():
    bon = {"format": vt.FORMAT, "photos": {"photo-01": [fenetre()]}}
    assert vt.controler(bon) == []
    assert vt.controler({"format": "autre", "photos": {}})
    for faute in ({"coins": [[600, 200], [400, 200], [400, 500], [600, 500]]},  # coins dans le désordre
                  {"coins": [[400, 200], [600, 200], [600, 500]]},  # trois coins
                  {"traverses": [[355, 345, 345, 355]]},  # bords d'une barre dans le désordre
                  {"montants": [[100, 110, 100, 110]]},  # barre hors du vitrage
                  {"caches": [[10, 10, 5, 20]]}, {"vue": "peut-être"}):
        assert vt.controler({"format": vt.FORMAT, "photos": {"photo-01": [fenetre(**faute)]}}), faute
    deux_avis = {"format": vt.FORMAT, "photos": {"photo-01": [fenetre(), {"baie": "F1", "vue": "non"}]}}
    assert any("à la fois" in d for d in vt.controler(deux_avis))
    assert any("inconnue" in d for d in vt.controler(bon, baies={"F9"}))


def test_une_barre_est_comblee_d_apres_les_vitres_qui_la_bordent():
    """Derrière une barre mince le dehors continue : une ligne d'immeuble (ici une bande sombre horizontale) passe droit derrière
    le montant, et la barre elle-même (grise) disparaît."""
    image = np.full((700, 1000, 3), 240, np.uint8)
    image[290:300] = 60  # une corniche de l'immeuble d'en face, sur toute la largeur
    image[:, 495:505] = 150  # le montant de la fenêtre, gris, devant
    image[345:355] = 150  # et sa traverse
    f = fenetre(montants=[[495, 505, 495, 505]])
    lu = vt.d_une_photo({"format": vt.FORMAT, "photos": {"p": [f]}}, "p", TAILLE)["F1"]
    comble, fait = vt.combler(image, lu["debout"], lu["couchees"], lu["vitres"])
    assert fait[295, 500] == 1 and fait[350, 450] == 1
    assert abs(int(comble[295, 500, 0]) - 60) <= 2  # la corniche continue derrière le montant
    assert abs(int(comble[250, 500, 0]) - 240) <= 2 and abs(int(comble[350, 450, 0]) - 240) <= 2  # plus de gris de barre
    assert (comble[lu["vitres"] > 0] == image[lu["vitres"] > 0]).all()  # les vitres ne sont pas touchées
    assert image[250, 500, 0] == 150  # la photo donnée non plus
    rien, fait = vt.combler(image, lu["debout"], lu["couchees"], np.zeros_like(lu["vitres"]))
    assert fait.sum() == 0 and (rien == image).all()  # aucune vitre au bord : rien n'est inventé


def test_la_photo_ne_peint_la_vue_que_par_ses_vitres_lues():
    """Le trou de la fenêtre d'après le plan tombe à côté de la vraie fenêtre de la photo (place de l'appareil à 30-50 cm) :
    avec le dessin lu, la photo voit dehors par ses vitres, là où elles sont vraiment, et pas par le rideau."""
    log = _logement()
    ouv, murs, cam = vd.ouvertures_vitrees(log), vd.murs_et_trous(log), _camera_piece_a()
    image = np.full((700, 1000, 3), 200, np.uint8)
    trou = vd.masque_fenetres(cam, TAILLE, [o for o in ouv if o["id"] == "F1"], murs)[1] > 0
    vs, us = np.nonzero(trou)
    x0, x1, y0, y1 = int(us.min()), int(us.max()), int(vs.min()), int(vs.max())
    decale = 60  # la vraie fenêtre de la photo est 60 pixels plus à droite que le trou du plan
    f = {"baie": "F1", "coins": [[x0 + decale, y0], [x1 + decale, y0], [x1 + decale, y1], [x0 + decale, y1]],
         "montants": [[(x0 + x1) / 2 + decale - 6, (x0 + x1) / 2 + decale + 6] * 2],
         "caches": [[x1 + decale - 50, y0 - 20, x1 + decale + 40, y1 + 20]]}  # un rideau sur le bord droit
    lecture = {"format": vt.FORMAT, "photos": {"a": [f]}}
    sans = vd.preparer_photo(image, cam, ouv, "bonne", murs, ecart_px=1.0)
    avec = vd.preparer_photo(image, cam, ouv, "bonne", murs, ecart_px=1.0, vitrages=vt.d_une_photo(lecture, "a", TAILLE))
    ym = (y0 + y1) // 2
    assert sans["masque"][ym, x0 + 20] == 1 and avec["masque"][ym, x0 + 20] == 0  # le bord gauche du trou du plan : un mur, en vrai
    assert avec["masque"][ym, x1 + decale - 70] == 1 and avec["masque"][ym, x1 + decale - 30] == 0  # la vitre, pas le rideau
    assert avec["masque"][ym, (x0 + x1) // 2 + decale] == 1  # le montant, comblé d'après les vitres
    assert avec["lues"] == ["F1"] and avec["fenetres"]["F1"][ym, x1 + decale - 70] == 1
    non = {"format": vt.FORMAT, "photos": {"a": [{"baie": "F1", "vue": "non"}, {"baie": "F2", "vue": "non"}]}}
    assert vd.preparer_photo(image, cam, ouv, "bonne", murs, ecart_px=1.0, vitrages=vt.d_une_photo(non, "a", TAILLE)) is None


def test_un_vitrage_depoli_ne_montre_qu_une_lueur():
    lecture = {"format": vt.FORMAT, "photos": {"p1": [{"baie": "O5", "vue": "lueur"}, fenetre(baie="O7")],
                                                "p2": [{"baie": "O5", "vue": "non"}, {"baie": "O9", "vue": "lueur"}, fenetre(baie="O9")]}}
    assert vt.controler({"format": vt.FORMAT, "photos": {"p1": lecture["photos"]["p1"]}}) == []
    assert vt.depolies(lecture) == {"O5"}  # O9 : une photo y voit le dehors, ce n'est pas un vitrage dépoli
    assert vt.depolies(None) == set()


def test_le_partage_de_la_fenetre_redresse_de_la_perspective():
    f = fenetre(montants=[[495, 505, 495, 505]])
    p = vt.partage(f)
    assert p["montants"] == [(0.475, 0.525)] and abs(p["traverses"][0][0] - 0.483) < 0.002
    assert vt.partage({"baie": "F1", "vue": "non"}) is None
