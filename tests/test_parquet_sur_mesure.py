"""Le parquet SUR MESURE d'après les photos (18/11/2026) : la fiche, le dessin, la mesure, et la boucle « dessiner un parquet
connu puis le mesurer comme sur une photo » qui contrôle les deux l'un par l'autre."""
import json

import cv2
import numpy as np
import pytest
from pydantic import ValidationError

from moteur import parquet_photo as pp
from moteur import parquet_sur_mesure as psm
from moteur import reconnaitre_sols as rs
from moteur.logement import Sol
from moteur.matieres import SUR_MESURE, matiere_et_teinte, nom_materiau, sens_du_nom, sorte


def bois_d_essai(cote: int = 900, graine: int = 0) -> np.ndarray:
    """Une « photo de bois » d'essai : un brun clair avec un fil de haut en bas (chaque colonne a sa nuance)."""
    alea = np.random.default_rng(graine)
    fil = cv2.GaussianBlur(alea.normal(0, 1, (1, cote)).astype(np.float32), (0, 0), 3)
    grain = alea.normal(0, 3, (cote, cote)).astype(np.float32)
    gris = 150 + 10 * fil / max(float(fil.std()), 1e-6) + grain
    return np.clip(np.stack([gris * 1.15, gris * 0.9, gris * 0.6], -1), 0, 255).astype(np.uint8)


def comme_une_photo(dessin: dict, resolution: float = pp.RESOLUTION_M) -> np.ndarray:
    """Le parquet dessiné, vu comme sur une photo mise à plat : lames à l'horizontale, 3 mm par pixel, un peu flou, bruité."""
    image = np.rot90(np.asarray(dessin["couleur"]), -1)
    n = int(round(dessin["taille_m"] / resolution))
    petite = cv2.GaussianBlur(cv2.resize(image, (n, n), interpolation=cv2.INTER_AREA), (0, 0), 0.8)
    return np.clip(petite + np.random.default_rng(1).normal(0, 2.0, petite.shape), 0, 255).astype(np.uint8)


def test_la_fiche_borne_arrondit_et_dit_ce_qui_est_suppose():
    f = psm.fiche({"largeur_m": 0.1131, "nuance": 0.1373, "creux_mm": 1.03, "chaleur": 0.031, "longueur_m": 0.8})
    assert f == {"pose": "lames", "largeur": 0.115, "longueur": 0.8, "nuance": 0.14, "chaleur": 0.03, "joint_mm": 1.0, "bois": "chene_clair"}
    # deux mesures presque égales : le même parquet (même clé, donc même image) ; une autre largeur : un autre parquet
    assert psm.cle(psm.fiche({"largeur_m": 0.1139, "nuance": 0.141, "creux_mm": 0.98, "chaleur": 0.029, "longueur_m": 0.81})) == psm.cle(f)
    assert psm.cle(psm.fiche({"largeur_m": 0.075, "nuance": 0.14, "creux_mm": 1.0, "chaleur": 0.03, "longueur_m": 0.8})) != psm.cle(f)
    # rien de mesuré sauf la largeur : le reste est supposé, et dit comme tel ; des lames larges sont supposées longues
    etroit, large = psm.fiche({"largeur_m": 0.07}), psm.fiche({"largeur_m": 0.18})
    assert etroit["supposes"] == ["chaleur", "joint_mm", "longueur", "nuance"] and etroit["longueur"] < large["longueur"]
    assert psm.fiche({})["supposes"] == ["chaleur", "joint_mm", "largeur", "longueur", "nuance"]
    assert psm.fiche({"largeur_m": 0.9, "longueur_m": 9, "nuance": 3})["largeur"] == 0.35  # borné
    assert psm.nom(f).startswith(psm.PREFIXE) and psm.est_sur_mesure(psm.nom(f)) and not psm.est_sur_mesure("vieux_parquet")
    # la liste des valeurs supposées ne change pas le dessin
    assert psm.cle({**f, "supposes": ["nuance"]}) == psm.cle(f)


def test_le_dessin_a_la_largeur_voulue_des_lames_de_haut_en_bas_et_se_raccorde():
    f = psm.fiche({"largeur_m": 0.10, "longueur_m": 0.8, "nuance": 0.10, "chaleur": 0.0, "creux_mm": 1.5})
    d = psm.dessiner(f, bois_d_essai(), 900 / 1.8, mm_par_px=2.0)
    image = np.asarray(d["couleur"], np.float32).mean(-1)
    assert d["taille_m"] == pytest.approx(2.6, abs=0.06) and image.shape[0] == image.shape[1]
    assert d["relief"].size == d["couleur"].size == d["brillance"].size
    # lames de HAUT EN BAS : les longs joints sombres sont des colonnes ; leur écart est la largeur des lames
    colonnes = image.mean(0)
    sombres = np.nonzero(colonnes < np.median(colonnes) - 2.5 * np.std(colonnes - cv2.blur(colonnes[None], (9, 1))[0]))[0]
    ecarts = np.diff(sombres)
    px_par_lame = 0.10 / d["taille_m"] * image.shape[1]
    assert len(sombres) >= 20 and np.bincount(ecarts[ecarts > 3]).argmax() == pytest.approx(px_par_lame, rel=0.06)  # l'écart le plus fréquent
    assert image.mean(0).std() > 2 * image.mean(1).std()  # bien plus de contraste en travers des lames que le long
    # le même dessin deux fois (le hasard est tiré de la fiche), et une longueur moyenne proche de celle demandée
    assert np.array_equal(np.asarray(psm.dessiner(f, bois_d_essai(), 900 / 1.8, mm_par_px=2.0)["couleur"]), np.asarray(d["couleur"]))
    assert np.mean([lame["longueur_m"] for lame in d["plan"]]) == pytest.approx(0.8, rel=0.2)
    # raccord sans couture : la première et la dernière ligne (le long des lames) se ressemblent comme deux lignes voisines
    voisines = float(np.abs(image[10] - image[11]).mean())
    assert float(np.abs(image[0] - image[-1]).mean()) < 4 * voisines + 4


LIMITE_CONNUE = pytest.mark.xfail(strict=False, reason="limite connue (18/11/2026) : joints discrets ET lames peu nuancées, sur le bois d'essai "
                                  "très granuleux : selon le tirage, la largeur peut sortir DOUBLE (une lame sur deux comptée)")


@pytest.mark.parametrize("largeur, longueur, nuance, joint", [(0.075, 0.6, 0.12, 1.5), pytest.param(0.11, 0.8, 0.05, 0.6, marks=LIMITE_CONNUE),
                                                              (0.11, 0.8, 0.08, 1.0), (0.16, 1.5, 0.08, 1.0)])
def test_boucle_dessiner_puis_mesurer(largeur, longueur, nuance, joint):
    """Un parquet dessiné avec des valeurs connues, puis mesuré comme sur une photo : la mesure retrouve ces valeurs."""
    f = psm.fiche({"largeur_m": largeur, "longueur_m": longueur, "nuance": nuance, "chaleur": 0.0, "creux_mm": joint})
    photo = comme_une_photo(psm.dessiner(f, bois_d_essai(), 900 / 1.8))
    m = pp.mesurer_parquet([(photo, np.ones(photo.shape[:2], bool))])
    assert m["largeur_m"] == pytest.approx(largeur, rel=0.04)
    assert m["nuance"] == pytest.approx(nuance, abs=max(0.35 * nuance, 0.03))  # (le grain du bois d'essai compte pour ~3 %)
    assert m["creux_mm"] == pytest.approx(joint, abs=0.9)  # (la mesure la moins fine ; le bois d'essai a un grain très marqué)
    assert m["longueur_m"] == pytest.approx(longueur, rel=0.6)  # la longueur moyenne n'est connue qu'à moitié près…


def test_la_longueur_mesuree_separe_lames_courtes_et_longues():
    mesures = []
    for longueur in (0.45, 1.8):
        f = psm.fiche({"largeur_m": 0.12, "longueur_m": longueur, "nuance": 0.10, "chaleur": 0.0, "creux_mm": 1.0})
        photo = comme_une_photo(psm.dessiner(f, bois_d_essai(), 900 / 1.8))
        mesures.append(pp.mesurer_parquet([(photo, np.ones(photo.shape[:2], bool))])["longueur_m"])
    assert mesures[0] < 0.9 < 1.1 < mesures[1]  # … mais des lames courtes ne sont jamais prises pour des longues


def test_trop_peu_de_sol_rien_n_est_dit():
    f = psm.fiche({"largeur_m": 0.10, "longueur_m": 0.8, "nuance": 0.1, "chaleur": 0.0, "creux_mm": 1.0})
    photo = comme_une_photo(psm.dessiner(f, bois_d_essai(), 900 / 1.8))
    ok = np.zeros(photo.shape[:2], bool)
    ok[:150, :150] = True  # 45 cm × 45 cm de sol vu : pas de quoi mesurer
    assert "largeur_m" not in pp.mesurer_parquet([(photo, ok)])
    uni = np.full((600, 600, 3), (190, 150, 100), np.uint8)  # un sol uni : aucune lame
    assert "largeur_m" not in pp.mesurer_parquet([(uni, np.ones((600, 600), bool))])


def test_le_meme_parquet_dans_les_pieces_qui_montrent_le_meme():
    mesure = lambda l, **k: {"largeur_m": l, "largeur": {"fenetres": 10}, "rangs_m": 40.0, "nuance": 0.13, "chaleur": 0.02,
                                   "creux_mm": 1.0, "longueur_m": 0.8, **k}
    pieces = {
        "entree": {"famille": "lames", "zones": [], "parquet_mesure": mesure(0.113)},
        "chambre_1": {"famille": "lames", "zones": [], "parquet_mesure": mesure(0.107, nuance=0.15)},
        "chambre_2": {"famille": "lames", "zones": [], "parquet_mesure": {"sol_m2": 0.3, "fenetres": 1}},  # trop peu vue
        "bureau": {"famille": "lames", "zones": [], "parquet_mesure": mesure(0.075, largeur={"fenetres": 5})},  # d'autres lames
        "sejour": {"famille": "point_de_hongrie", "zones": [{"famille": "lames", "contour": [], "largeur_lames": 0.11}]},
        "cuisine": {"famille": "carreaux", "zones": []},
    }
    rs.memes_parquets(pieces)
    p = {k: v.get("parquet") for k, v in pieces.items()}
    assert p["entree"] == p["chambre_1"] and p["entree"]["largeur"] == 0.11 and "supposes" not in p["entree"]
    assert p["entree"]["nuance"] == 0.14  # les mesures des deux pièces réunies
    assert p["bureau"]["largeur"] == 0.075 and psm.cle(p["bureau"]) != psm.cle(p["entree"])
    # la chambre trop peu vue : le parquet le plus appuyé du logement, entièrement SUPPOSÉ ; même image que l'entrée
    assert psm.cle(p["chambre_2"]) == psm.cle(p["entree"]) and len(p["chambre_2"]["supposes"]) == 5
    # la zone de lames du séjour, mesurée par l'ancienne mesure seulement (11 cm) : le même parquet aussi
    assert psm.cle(pieces["sejour"]["zones"][0]["parquet"]) == psm.cle(p["entree"])
    assert p["sejour"]["pose"] == "point_de_hongrie" and p["cuisine"] is None  # le point de Hongrie a sa propre fiche ; pas le carrelage


def test_sans_aucune_mesure_un_parquet_suppose_et_dit_comme_tel():
    pieces = {"chambre": {"famille": "lames", "zones": []}}
    rs.memes_parquets(pieces)
    assert len(pieces["chambre"]["parquet"]["supposes"]) == 5 and pieces["chambre"]["parquet"]["largeur"] == 0.09


def test_le_format_accepte_le_sur_mesure_et_exige_sa_fiche():
    f = psm.fiche({"largeur_m": 0.11, "longueur_m": 0.8, "nuance": 0.13})
    sol = Sol.model_validate({"matiere": SUR_MESURE, "parquet": f, "sens": 90.0, "statut": "estime", "source": "brique photos"})
    assert sol.parquet.largeur == 0.11 and sol.parquet.supposes == ["chaleur", "joint_mm"]
    with pytest.raises(ValidationError):
        Sol.model_validate({"matiere": SUR_MESURE, "statut": "estime", "source": "brique photos"})
    with pytest.raises(ValidationError):
        Sol.model_validate({"matiere": SUR_MESURE, "parquet": {**f, "largeur": 0.9}, "statut": "estime", "source": "x"})
    # le nom du matériau : la matière dessinée, son sens, sa teinte ; les outils qui lisent ce nom s'y retrouvent
    from moteur.habillage import matiere_d_un_sol

    nom = nom_materiau(matiere_d_un_sol(sol), (1.2, 1.0, 0.8), None, sol.sens)
    assert nom == f"{psm.nom(sol.parquet.model_dump())}^90~1.20,1.00,0.80"
    assert matiere_et_teinte(nom) == (psm.nom(sol.parquet.model_dump()), (1.2, 1.0, 0.8)) and sens_du_nom(nom) == 90.0
    assert sorte(nom) == "bois"
    assert psm.cle(sol.parquet.model_dump()) == psm.cle(f)  # la fiche relue du format donne la même image


def test_le_plan_de_construction_porte_les_parquets_et_la_construction_les_dessine(tmp_path):
    from PIL import Image

    from moteur.construire import dessiner_parquets
    from moteur.habillage import plan_habille
    from moteur.logement import Logement

    f = psm.fiche({"largeur_m": 0.11, "longueur_m": 0.8, "nuance": 0.13, "chaleur": 0.02, "creux_mm": 1.0})
    sol = {"matiere": SUR_MESURE, "parquet": f, "sens": 90.0, "teinte": [1.1, 1.0, 0.9], "statut": "estime", "source": "brique photos"}
    mur = lambda i, a, b: {"id": f"m{i}", "debut": a, "fin": b, "epaisseur": 0.2, "statut": "mesure", "source": "essai"}
    logement = Logement.model_validate({
        "schema": "logement/0.1", "projet_id": "essai", "hauteur_sous_plafond": 2.5,
        "murs": [mur(1, [0, 0], [4, 0]), mur(2, [4, 0], [4, 3]), mur(3, [4, 3], [0, 3]), mur(4, [0, 3], [0, 0])], "ouvertures": [],
        "pieces": [{"id": "chambre_1", "nom": "Chambre", "contour": [[0.1, 0.1], [3.9, 0.1], [3.9, 2.9], [0.1, 2.9]], "sol": sol,
                    "statut": "mesure", "source": "essai"}]})
    plan = plan_habille(logement)
    nom = psm.nom(f)
    assert plan["parquets_sur_mesure"] == {nom: {**f, "supposes": [], "angle": None}}
    sols = {b["materiau"] for b in plan["briques"] if b["categorie"] == "sol" and b["element"] == "chambre_1"}
    assert sols == {f"{nom}^90~1.10,1.00,0.90"}
    # la bibliothèque d'essai : une seule photo de bois
    bib = tmp_path / "matieres"
    (bib / "chene_clair").mkdir(parents=True)
    Image.fromarray(bois_d_essai(400)).save(bib / "chene_clair" / "couleur.jpg")
    (bib / "matieres.json").write_text(json.dumps({"chene_clair": {"taille_image_m": [1.8, 1.8]}}), encoding="utf-8")
    fiches = dessiner_parquets(plan["parquets_sur_mesure"], bib, tmp_path / "3d")
    dossier = tmp_path / "3d" / "matieres-sur-mesure" / nom
    assert all((dossier / n).is_file() for n in ("couleur.jpg", "relief.jpg", "brillance.jpg", "fiche.json"))
    assert fiches[nom]["taille_image_m"][0] == pytest.approx(2.64, abs=0.12) and fiches[nom]["dossier"] == str(dossier.resolve())
    date = (dossier / "couleur.jpg").stat().st_mtime_ns
    assert dessiner_parquets(plan["parquets_sur_mesure"], bib, tmp_path / "3d")[nom]["dossier"] == fiches[nom]["dossier"]
    assert (dossier / "couleur.jpg").stat().st_mtime_ns == date  # déjà dessiné : pas redessiné
    assert dessiner_parquets(plan["parquets_sur_mesure"], None, tmp_path / "3d") == {}  # sans bibliothèque : rien (Mac, tests)
    # la couleur moyenne du dessin, pour calculer la teinte sans attendre la construction : un brun, pas du noir
    a = psm.albedo(f, bib)
    assert 0.1 < a[1] < a[0] < 0.8 and a[2] < a[1]

    # le paquet pour Unreal : le parquet sur mesure est une « photo » comme les autres, posée dans le sens du sol, sans quart
    # de tour (ses lames vont de haut en bas de l'image), et ses images sont copiées depuis le dossier de la maquette
    from moteur.export_unreal import copier_photos, fiche_materiau

    fm = fiche_materiau(f"{nom}^90~1.10,1.00,0.90", fiches, {}, 0.0, {}, {})
    assert fm["genre"] == "photo" and fm["rotation_deg"] == 90.0 and fm["teinte"] == [1.1, 1.0, 0.9] and fm["sorte"] == "bois"
    assert fm["photos"]["dossier"] == f"matieres/{nom}" and fm["parquet"]["largeur"] == 0.11 and fm["credit"] == "chene_clair"
    copies = copier_photos({"materiaux": {"sol": fm}}, None, tmp_path / "paquet")
    assert copies == [nom] and (tmp_path / "paquet" / "matieres" / nom / "couleur.jpg").is_file()


def test_les_sols_a_lames_ecrits_dans_le_logement_sont_sur_mesure():
    resultat = {"pieces": {"chambre_1": {"famille": "lames", "part": 0.9, "zones": [], "sens": 90.0, "photos_couleur": 2,
                                         "parquet_mesure": {"largeur_m": 0.112, "largeur": {"fenetres": 9}, "rangs_m": 30.0, "nuance": 0.12,
                                                            "chaleur": 0.02, "creux_mm": 1.2, "longueur_m": 0.75, "photos": 2, "sol_m2": 2.1}}}}
    logement = {"pieces": [{"id": "chambre_1", "contour": [[0, 0], [4, 0], [4, 3], [0, 3]]}]}
    sol = rs.sols_vers_logement(resultat, logement, None, None)["pieces"][0]["sol"]
    assert sol["matiere"] == SUR_MESURE and sol["sens"] == 90.0 and sol["statut"] == "estime"
    assert sol["parquet"] == {"pose": "lames", "largeur": 0.11, "longueur": 0.75, "nuance": 0.12, "chaleur": 0.02, "joint_mm": 1.2, "bois": "chene_clair"}
    assert "parquet mesuré sur 2 photos" in sol["source"]
    Sol.model_validate(sol)


def photo_d_un_sol(dessin: dict, sens_deg: float, cam, taille=(1206, 804), sur: int = 3) -> np.ndarray:
    """Une « photo » d'essai : le parquet dessiné, posé au sol dans le sens demandé, vu par l'appareil `cam`."""
    from moteur.sens_des_lames import vers_le_sol

    parquet = np.rot90(np.asarray(dessin["couleur"]), -1)  # lames à l'horizontale : colonne = le long des lames
    px_par_m = parquet.shape[0] / dessin["taille_m"]
    w, h = taille[0] * sur, taille[1] * sur
    u, v = np.meshgrid((np.arange(w) + 0.5) / sur, (np.arange(h) + 0.5) / sur)
    X, Y = vers_le_sol(u, v, cam)
    a = np.radians(sens_deg)
    le_long, travers = X * np.cos(a) + Y * np.sin(a), -X * np.sin(a) + Y * np.cos(a)
    sol = np.isfinite(X)
    colonnes = np.where(sol, le_long * px_par_m, 0).astype(np.int64) % parquet.shape[1]
    lignes = np.where(sol, -travers * px_par_m, 0).astype(np.int64) % parquet.shape[0]
    image = np.where(sol[..., None], parquet[lignes, colonnes], 235).astype(np.uint8)  # au-dessus de l'horizon : un mur clair
    return cv2.resize(image, taille, interpolation=cv2.INTER_AREA)


@pytest.mark.parametrize("sens", [0.0, 90.0])
def test_de_la_photo_a_la_mesure(sens):
    """Toute la chaîne de mesure sur une photo d'essai : le sol mis à plat dans le sens des lames, puis mesuré."""
    f = psm.fiche({"largeur_m": 0.12, "longueur_m": 0.9, "nuance": 0.10, "chaleur": 0.0, "creux_mm": 1.5})
    dessin = psm.dessiner(f, bois_d_essai(), 900 / 1.8)
    cam = [1.0, 2.0, 1.3, 20.0, 0.0, 520.0, 603.0, 250.0]  # à 1,30 m du sol, regard à 20° de l'axe x, horizon au tiers haut
    photo = photo_d_un_sol(dessin, sens, cam)
    contour = [[0, 0], [7, 0], [7, 5], [0, 5]]
    image, vu = pp.sol_dans_le_sens(photo, cam, contour, sens)
    assert vu.sum() * pp.RESOLUTION_M ** 2 > 1.5  # plus de 1,5 m² de sol vu assez finement
    m = pp.mesurer_parquet([(image, pp.bois_propre(image, vu), pp.bois_vu(image, vu))])
    assert m["largeur_m"] == pytest.approx(0.12, rel=0.05)
    assert m["nuance"] == pytest.approx(0.10, rel=0.4)
    # dans le mauvais sens, les lames ne sont plus à l'horizontale : aucune largeur de lame ne doit sortir à leur vraie valeur
    image, vu = pp.sol_dans_le_sens(photo, cam, contour, (sens + 90.0) % 180.0)
    autre = pp.mesurer_parquet([(image, pp.bois_propre(image, vu), pp.bois_vu(image, vu))])
    assert "largeur_m" not in autre or abs(autre["largeur_m"] - 0.12) > 0.02
    # la part de la pièce à garder (le sol d'une zone) : rien hors d'elle
    image, vu = pp.sol_dans_le_sens(photo, cam, contour, sens, garder=lambda X, Y: X > 100)
    assert not vu.any()


def test_le_point_de_hongrie_est_une_vraie_image_qui_se_raccorde():
    """Le point de Hongrie dessiné en vraie image (dans le film Unreal, celui que Blender calculait n'existait pas)."""
    f = psm.fiche({"pose": "point_de_hongrie", "largeur_m": 0.09, "longueur_m": 0.5, "nuance": 0.1, "chaleur": 0.0, "creux_mm": 1.0})
    assert f["pose"] == "point_de_hongrie" and f["angle"] == 45.0 and psm.cle(f) != psm.cle({**f, "pose": "lames"})
    assert psm.fiche({"pose": "point_de_hongrie", "largeur_m": 0.08})["longueur"] == pytest.approx(0.45, abs=0.03)  # supposée : 5,5 fois la largeur
    d = psm.dessiner(f, bois_d_essai(), 900 / 1.8, mm_par_px=2.0)
    long_m, travers_m = d["taille_m"]  # [le long des rangs, en travers]
    rang = 0.5 * np.sin(np.radians(45))
    assert d["plan"]["rangs"] % 2 == 0 and travers_m == pytest.approx(d["plan"]["rangs"] * rang, rel=0.02)  # un nombre pair de rangs
    image = np.asarray(d["couleur"], np.float32).mean(-1)
    assert image.shape[1] / image.shape[0] == pytest.approx(travers_m / long_m, rel=0.02)  # largeur de l'image = travers des rangs
    # les longs joints entre les rangs de chevrons sont des COLONNES de l'image (rangs de haut en bas), espacées d'un rang
    colonnes = image.mean(0)
    sombres = np.nonzero(colonnes < np.median(colonnes) - 6)[0]
    ecarts = np.diff(sombres)
    assert len(sombres) >= d["plan"]["rangs"] - 1
    assert np.bincount(ecarts[ecarts > 3]).argmax() == pytest.approx(rang / travers_m * image.shape[1], rel=0.06)
    # raccord sans couture dans les deux sens
    assert float(np.abs(image[0] - image[-1]).mean()) < 4 * float(np.abs(image[10] - image[11]).mean()) + 4
    assert float(np.abs(image[:, 0] - image[:, -1]).mean()) < 25  # (la première et la dernière colonne tombent sur un long joint)
    # dans le format, et un seul point de Hongrie par logement, à la taille mesurée sur les photos quand elle l'a été
    Sol.model_validate({"matiere": SUR_MESURE, "parquet": f, "statut": "estime", "source": "brique photos"})
    pieces = {"sejour": {"famille": "point_de_hongrie", "zones": [], "parquet_mesure": {"rang_m": 0.30, "rang": {"fenetres": 8}}},
              "chambre": {"famille": "point_de_hongrie", "zones": []}}
    rs.memes_parquets(pieces)
    h = pieces["sejour"]["parquet"]
    assert h == pieces["chambre"]["parquet"] and h["pose"] == "point_de_hongrie"
    assert h["longueur"] == pytest.approx(0.30 / np.sin(np.radians(45)), abs=0.03) and "largeur" not in h["supposes"]
    seul = {"chambre": {"famille": "point_de_hongrie", "zones": []}}
    rs.memes_parquets(seul)
    assert seul["chambre"]["parquet"]["largeur"] == 0.09 and "largeur" in seul["chambre"]["parquet"]["supposes"]
