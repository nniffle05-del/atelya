"""Lot 2 du générateur (--lot2), les trois chantiers : chaque trait est dessiné, et la vérité ne bouge pas.

La référence d'un test est le même plan dessiné SANS le lot 2, à la même échelle et avec les mêmes marges : c'est
l'ancien chemin de code. Si un trait touchait un masque, la comparaison le verrait.
"""
import dataclasses
import json
import math
import random
import re

import cv2
import numpy as np
import pytest

from moteur.generateur import VERSION_GENERATEUR
from moteur.generateur import exportateur as E
from moteur.generateur import lot2 as L
from moteur.generateur import rendu as R
from moteur.generateur.annotations import CLASSES, rect_de_l_ouverture
from moteur.generateur.exportateur import Options, fabriquer_exemple, generer_lot, style_pour
from moteur.generateur.logements import generer, surface_piece
from moteur.generateur.plan_pdf import style_a_plat
from moteur.generateur.reglages import Reglages
from moteur.generateur.rendu import Repere, _cadre_des_murs, rendre
from moteur.generateur.validateur import Regles, valider_dossier
from moteur.generateur.variantes import Style, style_au_hasard

MASQUES = ("masque_semantique", "masque_pieces", "masque_elements", "hauteur", "contours")


def _base(**k) -> Style:
    """Un style à plat, sans salissure ni texte de marge : les pixels regardés sont exactement ceux du trait."""
    reglage = dict(px_par_m=100.0, taille_texte=20, marges=(170, 140, 140, 380), cartouche=False, titre=False, fleche_nord=False)
    reglage.update(k)
    return Style(**reglage)


def _rendus(graine: int, l: L.Lot2, base: Style | None = None, sans_cotes: bool = False, biais: bool = False):
    """(rendu avec le lot 2, rendu de référence sans lui, style, logement)."""
    log = generer(graine, Reglages())
    if biais:
        from moteur.generateur.biais import couper_angles
        couper_angles(log, random.Random(f"biais-{graine}"))
    style = base if base is not None else _base()
    L.appliquer(style, l, sans_cotes=sans_cotes)
    # Avant le rendu : le Repere d'une vraie caméra écrit dans le style (il recule la focale).
    reference = dataclasses.replace(style, lot2=None, marges=L.marges_lot2(style, style.marges, len(log.niveaux[0].pieces)))
    avec = rendre(log, log.niveaux[0], style)
    return avec, rendre(log, log.niveaux[0], reference), style, log


def _verite_inchangee(avec, reference, masques=MASQUES) -> None:
    assert avec.images["plan"].shape == reference.images["plan"].shape
    for nom in masques:
        assert np.array_equal(avec.images[nom], reference.images[nom]), nom


def _masques_du(style) -> tuple:
    """La carte de hauteur dépend du mobilier (exception connue) : un meuble écarté ou retourné la change."""
    return tuple(m for m in MASQUES if m != "hauteur") if style.mobilier else MASQUES


def _couleur_de(rendu, classe: str) -> tuple:
    """La couleur la plus fréquente sur une classe : textes et traits ne pèsent rien face à l'aplat."""
    pixels = rendu.images["plan"][rendu.images["masque_semantique"] == CLASSES[classe]]
    valeurs, comptes = np.unique(pixels, axis=0, return_counts=True)
    return tuple(int(v) for v in valeurs[comptes.argmax()])


def _diff(a, b) -> np.ndarray:
    return np.any(a.images["plan"] != b.images["plan"], axis=2)


def _fabriquer(tmp_path, monkeypatch, l: L.Lot2, graine: int = 60002):
    """Un vrai exemple écrit sur le disque avec ce tirage imposé : la seule preuve de bout en bout."""
    monkeypatch.setattr(E, "lot2_au_hasard", lambda rng: l)
    opt = Options(dossier=tmp_path, lot2=True, reprise=False)
    r = fabriquer_exemple(graine, opt, Reglages(), Regles.charger(None))
    assert r.statut == "accepte", r.erreurs
    dossier = tmp_path / "exemples" / f"{graine:06d}"
    assert valider_dossier(dossier, Regles.charger(None)).accepte
    return dossier


def _espion_textes(monkeypatch) -> list[str]:
    """Tout ce qui s'écrit vraiment sur l'image : _Dessin.texte (donc _ecrire), le stylo, le texte tourné."""
    ecrits = []
    vrai = R._Dessin.texte
    monkeypatch.setattr(R._Dessin, "texte", lambda self, xy, texte, *a, **k: (ecrits.append(texte), vrai(self, xy, texte, *a, **k))[1])
    for nom in ("texte_main", "_texte_tourne"):
        monkeypatch.setattr(L, nom, (lambda f: lambda d, xy, texte, *a, **k: (ecrits.append(texte), f(d, xy, texte, *a, **k))[1])(getattr(L, nom)))
    return ecrits


def _espion_cotes(monkeypatch) -> list[tuple[str, float, bool]]:
    """Chaque cote dessinée : (texte écrit, longueur du trait en mm, horizontale). La longueur vient des pixels du trait, pas du
    calcul qui a produit le texte : une cote fausse se voit, même si le calcul faux donne un nombre bien formé."""
    cotes = []
    vrai = L._cote_fine

    def espion(d, a, b, horizontale, texte, *r, **k):
        cotes.append((texte, math.dist(a, b) / d.rep.s, horizontale))
        return vrai(d, a, b, horizontale, texte, *r, **k)
    monkeypatch.setattr(L, "_cote_fine", espion)
    return cotes


# ---------------------------------------------------------------- l'image contre le masque


_MAGENTA, _VERT = (255, 0, 255), (0, 255, 0)
# Même classe, même couleur : deux sortes de pièces de la même classe ne se contredisent pas.
_PALETTE_TEMOIN = {s: (40 + 12 * CLASSES[s], 200 - 9 * CLASSES[s], 90 + 8 * (CLASSES[s] % 5)) for s in L._SORTES}


def _en_couleurs_temoins(style) -> None:
    """Murs magenta, fenêtres vertes, une couleur par sorte de pièce. Le reste du tirage est gardé, rotation et perspective comprises.

    Retirés, car ils ont le droit d'avoir ces couleurs hors du masque : la flèche du nord, les repères en triangles et le contour
    gris d'un extérieur sont dessinés à la couleur des murs."""
    l = style.lot2
    style.salissure, style.papier, style.contraste, style.realisme = "", 255, 1.0, None
    style.murs_contour, style.murs, style.fond, style.traits = False, _MAGENTA, (255, 255, 255), (60, 60, 60)
    style.variete, style.mobilier, style.pieces_colorees, style.fleche_nord = None, False, True, False
    l.palette, l.sols, l.murs_dessin, l.triangles, l.portes_boites = "_temoin", {}, "", False, False
    l.teinte, l.ecran, l.ecran_bordure = None, False, False
    l.fenetres_pleines, l.couleur_fenetres, l.contour_fenetres = True, _VERT, _VERT
    l.exterieurs = [{**e, "contour": "fin"} for e in l.exterieurs]


def _proche(image: np.ndarray, couleur: tuple, tolerance: int = 30) -> np.ndarray:
    return np.abs(image.astype(int) - np.array(couleur)).sum(axis=2) < tolerance


def _image_contre_masque(rendu) -> None:
    """Ce que le modèle voit et ce qu'on lui dit de voir sont-ils au même endroit ? Comparer des masques entre eux ne le dit pas.
    Un rebord de 2 pixels est toléré : l'image est lissée, pas le masque."""
    img, sem = rendu.images["plan"], rendu.images["masque_semantique"]
    assert img.shape[:2] == sem.shape
    k3, k5 = np.ones((3, 3), np.uint8), np.ones((5, 5), np.uint8)
    bati = ((sem >= 1) & (sem <= 4)).astype(np.uint8)
    fenetres = ((sem == CLASSES["fenetre"]) | (sem == CLASSES["porte_fenetre"])).astype(np.uint8)
    magenta, vert = _proche(img, _MAGENTA), _proche(img, _VERT)
    assert int((magenta & (cv2.dilate(bati, k5) == 0)).sum()) == 0  # aucun mur dessiné là où le masque dit autre chose
    coeur = cv2.erode((sem == CLASSES["mur"]).astype(np.uint8), k5) > 0
    assert coeur.any() and magenta[coeur].mean() > 0.9  # et le masque n'affirme aucun mur qui n'est pas dessiné
    assert int((vert & (cv2.dilate(fenetres, k5) == 0)).sum()) == 0
    coeur_f = cv2.erode(fenetres, k3) > 0
    if coeur_f.sum() > 50:
        assert vert[coeur_f].mean() > 0.5
    for sorte, couleur in _PALETTE_TEMOIN.items():
        zone = (sem == CLASSES[sorte]).astype(np.uint8)
        pixels = _proche(img, couleur, 6)
        # Une tache, pas un pixel seul : sur un plan penché, le lissage entre le séjour et le magenta retombe parfois sur la cuisine.
        fuite = (pixels & (cv2.dilate(zone, k5) == 0)).astype(np.uint8)
        assert not cv2.erode(fuite, k3).any(), sorte
        coeur_p = cv2.erode(zone, k5) > 0
        if coeur_p.sum() >= 200:
            assert pixels[coeur_p].mean() > 0.4, sorte  # le reste : noms, cotes et traits écrits dans la pièce


@pytest.mark.parametrize("graine,options", [
    (60002, {}),  # à plat
    (3021, {}),  # logiciel grand public penché, deux extérieurs
    (3025, {}),  # murs noirs penchés
    (3012, {"biais": True}),  # murs en biais
    (40002, {"photo_realiste": True, "vraie_camera": True, "familles": ["photo"]}),  # une vraie caméra
], ids=["a_plat", "logiciel_penche", "murs_noirs_penches", "biais", "camera"])
def test_image_contre_masque(monkeypatch, graine, options):
    monkeypatch.setitem(L.PALETTES_LOT2, "_temoin", _PALETTE_TEMOIN)
    style = style_pour(graine, 0, Options(dossier=None, lot2=True, **options))
    log = generer(graine, Reglages())
    if options.get("biais"):
        from moteur.generateur.biais import couper_angles
        couper_angles(log, random.Random(f"biais-{graine}"))
        assert log.niveaux[0].murs_libres
    if graine in (3021, 3025):
        assert style.rotation  # sinon ce cas ne prouve plus rien pour un plan penché
    _en_couleurs_temoins(style)
    _image_contre_masque(rendre(log, log.niveaux[0], style))


@pytest.mark.parametrize("graine,compose,disposition,biais,rotation", [
    (62, "niveaux", "empiles", False, 2.5),  # duplex, penché
    (62, "niveaux", "cote_a_cote", False, 0.0),
    (26, "deux_logements", "palier", True, 0.0),  # murs en biais
    (26, "deux_logements", "mitoyen", False, -1.5),  # penché
])
def test_image_contre_masque_ensemble(monkeypatch, graine, compose, disposition, biais, rotation):
    monkeypatch.setitem(L.PALETTES_LOT2, "_temoin", _PALETTE_TEMOIN)
    opt = Options(dossier=None, lot2=True, biais=biais)
    log = generer(graine, Reglages())
    if biais:
        from moteur.generateur.biais import couper_angles
        couper_angles(log, random.Random(f"biais-{graine}"))
    rc = random.Random(f"test-{graine}-{compose}-{disposition}")
    log_b = None if log.duplex else E.second_logement(graine, opt, Reglages(), Regles.charger(None), rc)
    style = style_pour(graine, 0, opt)
    c = L.composer(log, log_b, compose, disposition, style, rc)
    assert c.disposition == disposition and len(style.lot2.blocs) == 0
    L.vers_ensemble(style, c)
    _en_couleurs_temoins(style)
    style.rotation = rotation or style.rotation
    _image_contre_masque(rendre(c.log, c.log.niveaux[0], style, "ensemble"))


def test_le_temoin_voit_une_image_decalee(monkeypatch):
    # Le témoin du témoin : à quoi servirait-il s'il ne voyait pas le défaut qu'il doit attraper ?
    monkeypatch.setitem(L.PALETTES_LOT2, "_temoin", _PALETTE_TEMOIN)
    style = style_pour(60002, 0, Options(dossier=None, lot2=True))
    log = generer(60002, Reglages())
    _en_couleurs_temoins(style)
    rendu = rendre(log, log.niveaux[0], style)
    _image_contre_masque(rendu)
    rendu.images["plan"] = np.roll(rendu.images["plan"], 60, axis=1)
    with pytest.raises(AssertionError):
        _image_contre_masque(rendu)


# ---------------------------------------------------------------- le socle


def test_sans_option_rien_ne_change():
    for g in (1, 60001, 60002, 40002):
        s = style_pour(g, 0, Options(dossier=None))
        assert s.lot2 is None
        assert s == style_au_hasard(random.Random(f"style-{g}-0"), 2, None)
        assert "lot2" not in s.en_dict()  # annotations.json reste identique à l'octet


def test_options_sans_lot2_identiques_dans_reglages(tmp_path):
    assert "lot2" not in E._options_json(Options(dossier=tmp_path))
    assert E._options_json(Options(dossier=tmp_path, lot2=True))["lot2"] is True


def test_la_verite_ne_bouge_pas_sur_des_tirages():
    for graine in (60001, 60002, 60005, 60013):
        style = style_pour(graine, 0, Options(dossier=None, lot2=True))
        assert style.lot2 is not None
        log = generer(graine, Reglages())
        reference = dataclasses.replace(style, lot2=None, marges=L.marges_lot2(style, style.marges, len(log.niveaux[0].pieces)))
        _verite_inchangee(rendre(log, log.niveaux[0], style), rendre(log, log.niveaux[0], reference), _masques_du(style))


def test_le_dessin_change():
    log = generer(60003, Reglages())
    sans = rendre(log, log.niveaux[0], style_pour(60003, 0, Options(dossier=None)))
    avec = rendre(log, log.niveaux[0], style_pour(60003, 0, Options(dossier=None, lot2=True)))
    assert sans.images["plan"].shape != avec.images["plan"].shape or not np.array_equal(sans.images["plan"], avec.images["plan"])


def test_tirages_varies():
    tirages = [L.lot2_au_hasard(random.Random(k)) for k in range(400)]
    assert {l.famille for l in tirages} == set(L.POIDS_FAMILLES)
    for attribut in ("dimensions", "etiquettes", "fenetres_pleines", "hsp", "mention_sol", "recadre", "sortie_jpeg", "triangles", "tableau", "sans_noms",
                     "cotes_interieures", "cotes_par_mur", "cercles_pmr", "sols", "numero_lot", "abreviations", "mentions_menuiseries", "exterieurs",
                     "textes_verticaux", "teinte", "manuscrit", "placards_fleches", "escalier", "pastilles"):
        assert 0 < sum(bool(getattr(l, attribut)) for l in tirages) < 400, attribut


def test_les_familles_ont_les_poids_de_la_conception():
    assert L.POIDS_FAMILLES == {"agence_coloree": 14, "promoteur_gris": 14, "murs_noirs": 13, "carrez_legende": 8,
                                "logiciel_public": 5, "scan_ancien": 6, "cotes_rouges": 2, "neutre": 10}
    assert set(L.POIDS_FAMILLES) == set(L.FAMILLES_LOT2)


def test_tout_est_json():
    json.dumps(dataclasses.asdict(L.lot2_au_hasard(random.Random(1))))
    style = style_pour(60001, 0, Options(dossier=None, lot2=True))
    assert json.loads(json.dumps(style.en_dict()))["lot2"]["famille"] == style.lot2.famille


def test_appliquer_est_deterministe():
    for k in range(30):
        l = L.lot2_au_hasard(random.Random(k))
        a, b = _base(), _base()
        L.appliquer(a, dataclasses.replace(l))
        L.appliquer(b, dataclasses.replace(l))
        assert a == b


def test_cle_du_hasard():
    a = style_pour(60001, 0, Options(dossier=None, lot2=True)).lot2
    assert a == style_pour(60001, 0, Options(dossier=None, lot2=True)).lot2
    assert a == L.lot2_au_hasard(random.Random("lot2-60001-0"))
    autres = [style_pour(60001, 0, Options(dossier=None, lot2=True, graine_styles=k)).lot2 for k in range(1, 6)]
    assert any(a != b for b in autres)


def test_le_recul_de_cote_est_le_meme():
    assert L.RECUL_COTE == R.RECUL_COTE


def test_pdf_sans_lot2():
    assert style_a_plat(style_pour(60001, 0, Options(dossier=None, lot2=True))).lot2 is None


def test_pdf_d_un_jeu_lot2_le_dit_clairement(tmp_path, capsys):
    from moteur.generateur.plan_pdf import fabriquer_jeu
    (tmp_path / "lot2").mkdir()
    (tmp_path / "lot2" / "reglages.json").write_text(json.dumps({"options": {"lot2": True}}), encoding="utf-8")
    bilan = fabriquer_jeu(tmp_path / "lot2", tmp_path / "pdf-lot2", ids=[])
    assert "jeu fabriqué avec --lot2 : non pris en charge" in capsys.readouterr().out and "alerte" in bilan
    # Les autres jeux n'en entendent pas parler : ni ligne, ni clé dans le bilan.
    (tmp_path / "ancien").mkdir()
    (tmp_path / "ancien" / "reglages.json").write_text(json.dumps({"options": {"diversite": 2}}), encoding="utf-8")
    for jeu in ("ancien", "sans-reglages"):
        (tmp_path / jeu).mkdir(exist_ok=True)
        bilan = fabriquer_jeu(tmp_path / jeu, tmp_path / f"pdf-{jeu}", ids=[])
        assert "lot2" not in capsys.readouterr().out and "alerte" not in bilan


def test_version():
    assert VERSION_GENERATEUR == "0.1.6"


def test_sortie_jpeg_et_manifeste(tmp_path, monkeypatch):
    dossier = _fabriquer(tmp_path, monkeypatch, L.Lot2(famille="neutre", sortie_jpeg=True))
    assert (dossier / "niveau_0" / "plan.jpg").exists() and not (dossier / "niveau_0" / "plan.png").exists()
    manifeste = json.loads((dossier / "manifeste.json").read_text(encoding="utf-8"))
    assert manifeste["lot2"]["famille"] == "neutre"


def test_lot_sans_option_sans_cle_lot2(tmp_path):
    generer_lot(Options(dossier=tmp_path, nombre=1, depart=60005, reprise=False), processus=1)
    dossier = tmp_path / "exemples" / "060005"
    assert "lot2" not in json.loads((dossier / "manifeste.json").read_text(encoding="utf-8"))
    annotations = json.loads((dossier / "niveau_0" / "annotations.json").read_text(encoding="utf-8"))
    assert "lot2" not in annotations["style"]


def test_lot_lot2_de_bout_en_bout(tmp_path):
    bilan = generer_lot(Options(dossier=tmp_path, nombre=8, depart=1, lot2=True, variantes=1, diversite=3, reprise=False), processus=1)
    assert bilan["statuts"]["rejete"] == 0 and bilan["statuts"]["accepte"] >= 5
    for d in (tmp_path / "exemples").glob("*/"):
        assert valider_dossier(d, Regles.charger(None)).accepte, d.name


# ---------------------------------------------------------------- trait 1 : agence colorée foncée


def _agence(**traits) -> L.Lot2:
    l = L.lot2_au_hasard(random.Random(3), famille="agence_coloree", transversaux=False)
    l.mobilier_fixes = l.mobilier_couleur = False
    return dataclasses.replace(l, **traits)


def test_trait_1_agence_coloree():
    l = _agence(palette="agence", couleur_murs=(24, 32, 56))
    avec, reference, style, _ = _rendus(60002, l)
    assert _couleur_de(avec, "mur") == (24, 32, 56)
    assert _couleur_de(avec, "chambre") == L.PALETTES_LOT2["agence"]["chambre"]
    _verite_inchangee(avec, reference)


def test_trait_1_rose_niveau_et_surface_totale_dans_les_marges():
    avec, reference, style, log = _rendus(60002, _agence(rose_des_vents=True, legende_niveau=True, surface_totale=True))
    plan = avec.images["plan"]
    h, w = plan.shape[:2]
    fond = np.array(style.fond)
    assert np.any(plan[h - round(6 * style.taille_texte):, :round(5 * style.taille_texte)] != fond)  # la rose, en bas à gauche
    sem = avec.images["masque_semantique"]
    assert sem[h - round(6 * style.taille_texte):, :round(5 * style.taille_texte)].max() == 0  # et jamais sur le logement
    assert np.any(plan[:, np.nonzero(sem.max(axis=0))[0].max() + 5:] != fond)  # la colonne de droite
    _verite_inchangee(avec, reference)


def test_trait_1_palette_lot2_a_part():
    # Une clé ajoutée à variantes.PALETTES changerait les tirages des anciens jeux.
    from moteur.generateur.variantes import PALETTES
    assert set(PALETTES) == {"pastel", "bois", "gris"}


def test_trait_1_equipements_fixes_seulement():
    style = _base()
    avec, _, _, _ = _rendus(60002, _agence(mobilier_fixes=True, mobilier_couleur=True), style)
    types = {m.type for lst in avec.meubles.values() for m in lst}
    assert types and types <= L.MEUBLES_FIXES


# ---------------------------------------------------------------- trait 2 : dimensions de pièce, étiquette


def test_format_dimensions():
    assert L.format_dimensions(3050, 2850, "3,05 m × 2,85 m") == "3,05 m × 2,85 m"
    assert L.format_dimensions(3870, 4650, "3.87 x 4.65 m") == "3.87 x 4.65 m"


@pytest.mark.parametrize("mode", ["ajoute", "remplace"])
def test_trait_2_dimensions(mode, monkeypatch):
    sans, _, _, _ = _rendus(60002, L.Lot2(famille="neutre"))
    ecrits = _espion_textes(monkeypatch)
    avec, reference, _, log = _rendus(60002, L.Lot2(famille="neutre", dimensions=mode))
    # Le texte écrit est la vraie mesure de la pièce : une dimension fausse ne change pas les masques, seul ce contrôle la voit.
    pieces = log.niveaux[0].pieces

    def attendu(p):
        return f"{p.rect.largeur / 1000:.2f} m × {p.rect.hauteur / 1000:.2f} m".replace(".", ",")
    ecrites = {x for x in ecrits if "×" in x}
    assert ecrites and ecrites <= {attendu(p) for p in pieces}
    assert attendu(max(pieces, key=surface_piece)) in ecrites
    diff = _diff(avec, sans)
    assert diff.sum() > 100
    # La différence reste dans le logement : les dimensions s'écrivent dans les pièces, pas dans la marge.
    ys, xs = np.nonzero(avec.images["masque_semantique"])
    dehors = diff.copy()
    dehors[ys.min():ys.max() + 1, xs.min():xs.max() + 1] = False
    assert not dehors.any()
    _verite_inchangee(avec, reference)


def test_trait_2_etiquette_blanche_dans_une_piece_coloree():
    l = _agence(palette="agence", dimensions="remplace", etiquettes="bloc", couleur_murs=(24, 32, 56))
    avec, reference, _, _ = _rendus(60002, l)
    sans, _, _, _ = _rendus(60002, _agence(palette="agence", dimensions="remplace", couleur_murs=(24, 32, 56)))
    def blancs(r):
        zone = r.images["masque_semantique"] == CLASSES["chambre"]
        return int(np.all(r.images["plan"][zone] == 255, axis=1).sum())
    assert blancs(avec) > 200 and blancs(sans) == 0
    _verite_inchangee(avec, reference)


def test_trait_2_etiquette_jamais_sur_une_piece_en_biais():
    # La boîte d'une pièce coupée peut déborder de son contour : un cadre opaque y cacherait un mur.
    l = _agence(palette="agence", dimensions="remplace", etiquettes="bloc")
    avec, _, _, log = _rendus(101, l, biais=True)
    sans, _, _, _ = _rendus(101, _agence(palette="agence", dimensions="remplace"), biais=True)
    coupees = [p for p in log.niveaux[0].pieces if p.contour]
    assert coupees
    ids = {p.id: i + 1 for i, p in enumerate(log.niveaux[0].pieces)}
    droites = [p for p in log.niveaux[0].pieces if not p.contour]
    diff = _diff(avec, sans)
    for p in coupees:  # aucun pixel changé : ni cadre, ni fond blanc
        assert not diff[avec.images["masque_pieces"] == ids[p.id]].any(), p.nom
    assert any(diff[avec.images["masque_pieces"] == ids[p.id]].any() for p in droites)  # le cadre existe ailleurs


def test_trait_2_etiquette_absente_si_elle_ne_tient_pas():
    # Texte énorme : le cadre ne tient dans aucune petite pièce, et rien de blanc n'y apparaît.
    l = _agence(palette="agence", dimensions="remplace", etiquettes="bloc", part_texte=None)
    avec, _, _, _ = _rendus(60002, l, _base(taille_texte=60))
    zone = avec.images["masque_semantique"] == CLASSES["wc"]
    assert not np.all(avec.images["plan"][zone] == 255, axis=1).any()


def test_trait_2_noms_tronques():
    from moteur.dessin_plan import _police
    police = _police("DejaVuSans.ttf", 20)
    court = L.tronquer(police, "Salle de bains", 60)
    assert court.endswith("…") and len(court) < len("Salle de bains") and police.getlength(court) <= 60
    assert L.tronquer(police, "WC", 60) == "WC"


def test_trait_2_releve_dessine_et_verite_inchangee():
    l = L.Lot2(famille="neutre")
    L._tirer_releve(l, random.Random(1))
    avec, reference, style, _ = _rendus(60013, l)
    assert style.mobilier is False and style.cotes is False
    assert _couleur_de(avec, "fenetre") == (255, 255, 255)
    assert _couleur_de(avec, "porte") == (255, 255, 255)
    _verite_inchangee(avec, reference)


# ---------------------------------------------------------------- trait 4 : murs noirs (sans les balcons)


def test_trait_4_murs_noirs():
    l = L.lot2_au_hasard(random.Random(2), famille="murs_noirs", transversaux=False)
    l = dataclasses.replace(l, couleur_murs=(12, 12, 12), parentheses_grises=True, couleur_surface=(135, 135, 135))
    avec, reference, style, _ = _rendus(60002, l, _base(pieces_colorees=True))
    assert _couleur_de(avec, "mur") == (12, 12, 12)
    assert style.pieces_colorees is False  # les pièces restent blanches, comme fr-046
    assert L.format_surface(12.2, dataclasses.replace(l, surface_decimales=1), True) == "(12,2 m²)"
    sans, _, _, _ = _rendus(60002, dataclasses.replace(l, parentheses_grises=False, couleur_surface=(135, 135, 135)), _base())
    assert _diff(avec, sans).any()
    _verite_inchangee(avec, reference)


# ---------------------------------------------------------------- trait 5 : légende / tableau de surfaces


@pytest.mark.parametrize("cote", ["droite", "gauche", "bas"])
def test_trait_5_tableau(cote):
    l = L.Lot2(famille="carrez_legende", tableau=cote, noms_courts=True)
    avec, reference, style, log = _rendus(60002, l)
    sans_marge = Repere(_cadre_des_murs(log.niveaux[0]), dataclasses.replace(_base(), lot2=None), random.Random(0))
    rep = Repere(_cadre_des_murs(log.niveaux[0]), style, random.Random(0), nb_pieces=len(log.niveaux[0].pieces))
    plan, sem = avec.images["plan"], avec.images["masque_semantique"]
    ys, xs = np.nonzero(sem)
    if cote == "bas":
        zone = plan[ys.max() + round(L._debut_tableau(style)):]
        assert rep.hauteur0 >= sans_marge.hauteur0
    elif cote == "droite":
        zone = plan[:, xs.max() + round(L._debut_tableau(style)):]
        assert rep.largeur0 >= sans_marge.largeur0
    else:
        zone = plan[:, :xs.min() - round(L._debut_tableau(style))]
    assert np.any(zone != np.array(style.fond))
    _verite_inchangee(avec, reference)


def test_trait_5_exemple_ecrit_et_valide(tmp_path, monkeypatch):
    l = L.Lot2(famille="carrez_legende", tableau="bas", tableau_bordures=True, noms_courts=True)
    _fabriquer(tmp_path, monkeypatch, l)


def test_trait_5_sans_surface_autorisee_pas_de_tableau():
    # --sans-cotes qui a éteint les surfaces : aucune mesure écrite, ni dans les pièces ni dans la marge.
    l = L.Lot2(famille="carrez_legende", tableau="droite", noms_courts=True)
    sans_tableau = L.Lot2(famille="carrez_legende", noms_courts=True)
    a, _, _, _ = _rendus(60002, l, _base(surfaces=False, cotes=False), sans_cotes=True)
    b, _, _, _ = _rendus(60002, sans_tableau, _base(surfaces=False, cotes=False), sans_cotes=True)
    assert np.array_equal(a.images["plan"], b.images["plan"])


def test_trait_5_les_noms_peuvent_disparaitre():
    a, ref, style, _ = _rendus(60002, L.Lot2(famille="carrez_legende", tableau="droite", noms_courts=True, sans_noms=True))
    b, _, _, _ = _rendus(60002, L.Lot2(famille="carrez_legende", tableau="droite", noms_courts=True))
    assert style.noms is False and style.surfaces is True
    assert _diff(a, b).any()
    _verite_inchangee(a, ref)


# ---------------------------------------------------------------- trait 8 : fenêtres en rectangles de couleur


def test_trait_8_fenetres_pleines():
    bleu = (64, 200, 215)
    l = L.Lot2(famille="neutre", fenetres_pleines=True, couleur_fenetres=bleu)
    avec, reference, style, log = _rendus(60002, l)
    d = rendre.__globals__["Repere"](_cadre_des_murs(log.niveaux[0]), style, random.Random(0), nb_pieces=len(log.niveaux[0].pieces))
    fenetres = [o for o in log.niveaux[0].ouvertures if o.type == "fenetre"]
    portes = [o for o in log.niveaux[0].ouvertures if o.type == "porte"]
    assert fenetres and portes
    for o in fenetres:
        r = rect_de_l_ouverture(o)
        x, y = d.final((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
        assert tuple(int(v) for v in avec.images["plan"][round(y), round(x)]) == bleu
        assert avec.images["masque_semantique"][round(y), round(x)] == CLASSES["fenetre"]
    assert _couleur_de(avec, "porte") == style.fond  # une porte reste un trou
    _verite_inchangee(avec, reference)


def test_trait_8_avec_des_murs_d_un_simple_trait():
    l = L.Lot2(famille="neutre", fenetres_pleines=True, murs_dessin="trait", epaisseur_trait_mur=0.25)
    avec, reference, style, _ = _rendus(60002, l)
    plein, _, _, _ = _rendus(60002, L.Lot2(famille="neutre", fenetres_pleines=True))
    zone = avec.images["masque_semantique"] == CLASSES["mur"]
    # Le masque garde toute l'épaisseur du mur, seul le dessin s'affine : moins d'encre, même vérité.
    foncé = lambda r: int((r.images["plan"][zone].mean(axis=1) < 128).sum())
    assert foncé(avec) < foncé(plein)
    _verite_inchangee(avec, reference)


# ---------------------------------------------------------------- trait 16 : cotes rouges


def _rouge(image: np.ndarray) -> np.ndarray:
    r, g, b = image[..., 0].astype(int), image[..., 1].astype(int), image[..., 2].astype(int)
    return (r > 120) & (r - g > 70) & (r - b > 70)


def _rouges(**traits) -> L.Lot2:
    l = L.lot2_au_hasard(random.Random(4), famille="cotes_rouges", transversaux=False)
    return dataclasses.replace(l, couleur_cotes=(200, 35, 35), **traits)


def test_trait_16_chaines_rouges():
    avec, reference, style, _ = _rendus(60002, _rouges(cotes_interieures_rouges=False, echelle_ecrite=""))
    ys, _ = np.nonzero(avec.images["masque_semantique"])
    assert _rouge(avec.images["plan"][:ys.min()]).sum() > 100  # la chaîne du haut, dans la marge
    _verite_inchangee(avec, reference)


def test_trait_16_cotes_interieures_rouges():
    avec, reference, _, _ = _rendus(60002, _rouges(cotes_interieures_rouges=True, echelle_ecrite=""))
    dans_les_pieces = avec.images["masque_pieces"] > 0
    assert _rouge(avec.images["plan"])[dans_les_pieces].sum() > 200
    _verite_inchangee(avec, reference)


def test_trait_16_echelle_ecrite():
    a, _, _, _ = _rendus(60002, _rouges(cotes_interieures_rouges=False, echelle_ecrite="Échelle : 1/50e"))
    b, _, _, _ = _rendus(60002, _rouges(cotes_interieures_rouges=False, echelle_ecrite=""))
    assert _diff(a, b).any()
    ys, _ = np.nonzero(_diff(a, b))
    assert ys.max() < np.nonzero(a.images["masque_semantique"])[0].min()  # en haut, hors du logement


def test_trait_16_sans_cotes_gagne_toujours():
    l = _rouges(cotes_interieures_rouges=True, echelle_ecrite="Échelle : 1/50e")
    avec, _, style, _ = _rendus(60002, l, _base(cotes=False), sans_cotes=True)
    assert style.cotes is False
    assert not _rouge(avec.images["plan"]).any()
    neutre, _, _, _ = _rendus(60002, _rouges(cotes_interieures_rouges=False, echelle_ecrite=""), _base(cotes=False), sans_cotes=True)
    assert np.array_equal(avec.images["plan"], neutre.images["plan"])


# ---------------------------------------------------------------- trait 19 : HSP et mention de sol


@pytest.mark.parametrize("hsp", ["hsp:", "HsP :", "HSP cercle"])
def test_trait_19_hsp(hsp):
    sans, _, _, _ = _rendus(60002, L.Lot2(famille="neutre"))
    avec, reference, _, _ = _rendus(60002, L.Lot2(famille="neutre", hsp=hsp))
    diff = _diff(avec, sans)
    assert diff.sum() > 50
    assert not diff[avec.images["masque_semantique"] == 0].any()  # dans les pièces seulement
    _verite_inchangee(avec, reference)


def test_trait_19_mention_de_sol_et_hasard_reproductible():
    l = L.Lot2(famille="neutre", mention_sol="(sol)")
    a, reference, _, _ = _rendus(60002, l)
    b, _, _, _ = _rendus(60002, l)
    sans, _, _, _ = _rendus(60002, L.Lot2(famille="neutre"))
    assert _diff(a, sans).any()
    assert np.array_equal(a.images["plan"], b.images["plan"])
    _verite_inchangee(a, reference)


def test_trait_19_rien_dans_une_piece_trop_basse():
    # Une pièce où le nom et la surface ne laissent pas de place : la ligne HSP n'y est pas écrite.
    petit = _base(taille_texte=34)
    sans, _, _, log = _rendus(60002, L.Lot2(famille="neutre"), dataclasses.replace(petit))
    avec, _, _, _ = _rendus(60002, L.Lot2(famille="neutre", hsp="hsp:"), dataclasses.replace(petit))
    s = sans.annotations["image"]["px_par_m"] / 1000
    basses = [p for p in log.niveaux[0].pieces if p.rect.hauteur * s * 0.95 < 34 * 1.25 * 2 + 25 * 1.25]
    assert basses
    ids = {p.id: i + 1 for i, p in enumerate(log.niveaux[0].pieces)}
    diff = _diff(avec, sans)
    for p in basses:
        assert not diff[avec.images["masque_pieces"] == ids[p.id]].any(), p.nom


def test_trait_19_plan_et_plan_sans_mobilier_ecrivent_pareil():
    style = _base(mobilier=True)
    avec, _, _, _ = _rendus(60002, L.Lot2(famille="neutre", hsp="hsp:", mention_sol="sol"), style)
    ecart = np.any(avec.images["plan"] != avec.images["plan_sans_mobilier"], axis=2)
    assert ecart.any()
    # Le texte tiré au hasard (le sol) doit être le même : il ne reste de différences que là où sont les meubles.
    meubles = cv2.dilate((avec.images["hauteur"] > 0).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    assert not ecart[~meubles].any()


# ---------------------------------------------------------------- trait 20 : image recadrée serrée


def test_trait_20_recadre(tmp_path, monkeypatch):
    l = L.Lot2(famille="neutre", recadre=True, marges=(3, 2, 5, 4))
    avec, reference, style, log = _rendus(60002, l)
    assert (style.cotes, style.cartouche, style.titre, style.echelle_graphique) == (False, False, False, False)
    rep = Repere(_cadre_des_murs(log.niveaux[0]), style, random.Random(0), nb_pieces=len(log.niveaux[0].pieces))
    assert rep.largeur0 <= (rep.xmax - rep.xmin) * rep.s + 24
    assert rep.hauteur0 <= (rep.ymax - rep.ymin) * rep.s + 24
    sem = avec.images["masque_semantique"]
    ys, xs = np.nonzero(sem)
    h, w = sem.shape
    assert ys.min() <= 12 and h - 1 - ys.max() <= 12 and xs.min() <= 12 and w - 1 - xs.max() <= 12
    _verite_inchangee(avec, reference)
    _fabriquer(tmp_path, monkeypatch, L.Lot2(famille="neutre", recadre=True, marges=(3, 2, 5, 4)))


def test_trait_20_pas_de_recadrage_d_une_vraie_photo():
    style = _base(focale=1.1, focale_photo=0.77, inclinaison=(10.0, 3.0))
    l = L.Lot2(famille="neutre", recadre=True, marges=(3, 2, 5, 4))
    L.appliquer(style, l)
    assert l.recadre is False


# ---------------------------------------------------------------- combinaisons avec les autres options


@pytest.mark.parametrize("options", [
    {"styles_monde": True}, {"biais": True}, {"sans_cotes": True}, {"photo_realiste": True, "vraie_camera": True, "familles": ["photo"]},
])
def test_combinaisons(options):
    for graine in (60002, 40002):
        style = style_pour(graine, 0, Options(dossier=None, lot2=True, **options))
        log = generer(graine, Reglages())
        if options.get("biais"):
            from moteur.generateur.biais import couper_angles
            couper_angles(log, random.Random(f"biais-{graine}"))
        reference = dataclasses.replace(style, lot2=None, marges=L.marges_lot2(style, style.marges, len(log.niveaux[0].pieces)))
        avec = rendre(log, log.niveaux[0], style)
        _verite_inchangee(avec, rendre(log, log.niveaux[0], reference), _masques_du(style))
        if options.get("sans_cotes"):
            assert style.cotes is False and style.cotes_partielles is False


def test_sans_cotes_gagne_sur_toutes_les_familles():
    for k in range(120):
        graine = 60000 + k
        sans = style_pour(graine, 0, Options(dossier=None, sans_cotes=True))
        avec = style_pour(graine, 0, Options(dossier=None, sans_cotes=True, lot2=True))
        assert avec.cotes is False and avec.cotes_partielles is False
        assert avec.surfaces == sans.surfaces  # ni rallumées, ni éteintes par une famille
        assert not avec.lot2.dimensions
        if not avec.surfaces:
            assert not avec.titre and not avec.cartouche


_DIMENSIONS = re.compile(r"\d[,.]\d{2}.*[x×].*\d[,.]\d{2}")
_FORME_DE_COTE = re.compile(r"^\d{1,2}[,.]\d{2}( m)?$|^\d{2,3}$|^\d+(,\d+)? m$")


def _mesures_ecrites(ecrits: list[str], style, log) -> list[str]:
    """Ce qui a la forme d'une mesure, moins ce que --sans-cotes permet par choix : la barre d'échelle tirée par l'option
    (exportateur.style_pour), les surfaces si elles sont permises, et ce qui n'est pas une longueur (numéro de lot, pastilles,
    HSP : « HSP non » dans la conception)."""
    l = style.lot2
    permis = {"1 m", "2 m"} if style.echelle_graphique else set()
    permis |= {l.numero_lot} | {str(k) for k in range(1, len(log.pieces) + 1)}
    permis |= {f"{n.hsp / 1000:.2f}" for n in log.niveaux} if l.hsp == "HSP cercle" else set()
    if style.surfaces and l.tableau:  # la colonne de valeurs d'un tableau de surfaces (« 4,01 ») : des surfaces, pas des cotes
        permis |= {f"{surface_piece(p) / 1e6:.{l.tableau_decimales}f}".replace(".", ",") for p in log.pieces}
    mesures = [x for x in ecrits if (_DIMENSIONS.search(x) or _FORME_DE_COTE.match(x)) and x not in permis]
    if not style.surfaces:
        mesures += [x for x in ecrits if "m²" in x or " cm" in x or "mètres" in x]
    return mesures


@pytest.mark.parametrize("graine", [43, 67, 65, 46, 80, 16, 21])
def test_sans_cotes_aucune_mesure_sur_de_vrais_tirages(monkeypatch, graine):
    # Par le vrai chemin, sans rien forcer : 43, 67 et 65 écrivaient « 2,00 m × 1,60 m » quand les surfaces sont permises ;
    # 46 et 80 écrivaient « Murs extérieurs : 20 cm » et « T1 de 33 m² », 16 et 21 ce titre, quand elles ne le sont pas.
    ecrits = _espion_textes(monkeypatch)
    style = style_pour(graine, 0, Options(dossier=None, lot2=True, sans_cotes=True))
    log = generer(graine, Reglages())
    rendre(log, log.niveaux[0], style)
    assert ecrits
    assert not _mesures_ecrites(ecrits, style, log)


def test_sans_cotes_dimensions_meme_si_les_surfaces_sont_permises(monkeypatch):
    ecrits = _espion_textes(monkeypatch)
    avec, _, style, log = _rendus(60002, L.Lot2(famille="neutre", dimensions="ajoute"), _base(cotes=False, surfaces=True), sans_cotes=True)
    assert style.surfaces is True and any("m²" in x for x in ecrits)
    assert not any(_DIMENSIONS.search(x) for x in ecrits)


def test_sans_cotes_titre_et_cartouche_eteints_avec_les_surfaces():
    eteint = _appliquee_sans_cotes(_base(surfaces=False, cotes=False, titre=True, cartouche=True))
    assert eteint.titre is False and eteint.cartouche is False
    permis = _appliquee_sans_cotes(_base(surfaces=True, cotes=False, titre=True, cartouche=True))
    assert permis.titre is True and permis.cartouche is True  # le titre écrit alors une surface, permise
    # Sans --lot2, rien ne change : les jeux « sans cotes » déjà fabriqués restent identiques.
    ancien = style_pour(46, 0, Options(dossier=None, sans_cotes=True))
    assert not ancien.surfaces and (ancien.titre or ancien.cartouche)


def _appliquee_sans_cotes(style: Style) -> Style:
    L.appliquer(style, L.Lot2(famille="neutre"), sans_cotes=True)
    return style


def test_style_absurde_garde_ses_couleurs():
    from moteur.generateur.variete import Variete
    style = _base(fond=(10, 200, 30), murs=(90, 0, 90), variete=Variete(absurde=True, murs="gris_clair"))
    l = L.lot2_au_hasard(random.Random(3), famille="agence_coloree", transversaux=False)
    L.appliquer(style, l)
    assert style.fond == (10, 200, 30) and style.murs == (90, 0, 90)
    assert l.palette == "" and style.variete.murs == "gris_clair"


def test_styles_monde_murs_pleins_pour_les_familles_foncees():
    from moteur.generateur.variete import Variete
    style = _base(variete=Variete(murs="trait"))
    L.appliquer(style, L.lot2_au_hasard(random.Random(3), famille="murs_noirs", transversaux=False))
    assert style.variete.murs == "plein"


def test_croquis_penche_les_murs_restent_visibles():
    # Un croquis a un aplat presque blanc et un trait foncé autour. Sur un écran penché, le trait saute (contour décalé) :
    # les murs disparaissaient de l'image alors que le masque les affirme (graine 16820).
    assert style_pour(16820, 0, Options(dossier=None, lot2=True)).murs == (30, 30, 30)
    clair = (230, 230, 230)
    penche = _base(famille="croquis", murs=clair, murs_contour=True)
    l = L.Lot2(famille="neutre", ecran=True, rotation=3.0, papier=240, contraste=0.9)
    avec, _, style, _ = _rendus(60002, l, penche)
    assert style.rotation == 3.0 and style.murs_contour is False and style.murs == style.murs_contour_couleur
    gris = cv2.cvtColor(avec.images["plan"], cv2.COLOR_RGB2GRAY).astype(float)
    mur = (avec.images["masque_semantique"] == CLASSES["mur"]).astype(np.uint8)
    coeur = cv2.erode(mur, np.ones((5, 5), np.uint8)) > 0
    autour = (cv2.dilate(mur, np.ones((15, 15), np.uint8)) > 0) & ~(cv2.dilate(mur, np.ones((5, 5), np.uint8)) > 0)
    assert gris[autour].mean() - gris[coeur].mean() > 80
    # À plat, le croquis garde son trait et son aplat.
    droit = _base(famille="croquis", murs=clair, murs_contour=True)
    L.appliquer(droit, L.Lot2(famille="neutre"))
    assert droit.murs == clair and droit.murs_contour is True
    # Une couleur tirée par la famille et un style absurde gardent leurs couleurs.
    tiree = _base(famille="croquis", murs=clair, murs_contour=True, rotation=2.0, focale=1.1)
    L.appliquer(tiree, L.Lot2(famille="neutre", couleur_murs=(24, 32, 56)))
    assert tiree.murs == (24, 32, 56)
    from moteur.generateur.variete import Variete
    absurde = _base(murs=(90, 0, 90), murs_contour=True, rotation=2.0, focale=1.1, variete=Variete(absurde=True))
    L.appliquer(absurde, L.Lot2(famille="neutre"))
    assert absurde.murs == (90, 0, 90)


def test_pas_de_contour_decale_sur_un_plan_penche():
    # Défaut connu de contour_des_murs : double contour sur les plans penchés. Sous --lot2, seule une photo reste penchée.
    style = _base(famille="photo", murs_contour=True, rotation=2.0)
    L.appliquer(style, L.Lot2(famille="neutre"))
    assert style.rotation == 2.0 and style.murs_contour is False
    droit = _base(murs_contour=True)
    L.appliquer(droit, L.Lot2(famille="neutre"))
    assert droit.murs_contour is True


def test_trait_5_valeurs_du_tableau_justes(monkeypatch):
    # Le lecteur d'échelle sait lire une légende de surfaces : une valeur fausse deviendrait une échelle fausse.
    vu = {}
    monkeypatch.setattr(L, "_tableau_cote", lambda d, lignes, total: vu.update(lignes=lignes, total=total))
    _, _, _, log = _rendus(60002, L.Lot2(famille="carrez_legende", tableau="droite", noms_courts=True))
    pieces = log.niveaux[0].pieces
    assert [n for n, _ in vu["lignes"]] == [p.nom for p in pieces]
    assert [v for _, v in vu["lignes"]] == [f"{surface_piece(p) / 1e6:.2f}".replace(".", ",") for p in pieces]
    assert vu["total"] == f"{sum(surface_piece(p) for p in pieces) / 1e6:.2f}".replace(".", ",")


# ---------------------------------------------------------------- page de base : penchée et grise seulement si c'est le sujet


def test_page_sage_sauf_si_elle_est_le_sujet():
    style = _base(famille="scan", rotation=3.0, perspective=0.04, papier=230, contraste=0.8, salissure="photocopie")
    L.appliquer(style, L.Lot2(famille="neutre"))
    assert (style.rotation, style.perspective, style.papier, style.contraste) == (0.0, 0.0, 255, 1.0)
    assert style.salissure == "jpeg"
    photo = _base(famille="photo", rotation=3.0, perspective=0.04, papier=230, salissure="telephone")
    L.appliquer(photo, L.Lot2(famille="murs_noirs"))
    assert (photo.rotation, photo.perspective, photo.papier, photo.salissure) == (3.0, 0.04, 230, "telephone")
    camera = _base(rotation=3.0, focale=1.1, papier=230)
    L.appliquer(camera, L.Lot2(famille="neutre"))
    assert camera.rotation == 3.0 and camera.papier == 230


def test_la_part_de_plans_penches_ressemble_aux_vrais_plans():
    # Sur les 59 plans d'entraînement du catalogue, 5 à 10 % sont penchés. Le lot 2 hérite aussi de photos du style de base.
    penches = sum(bool(style_pour(g, 0, Options(dossier=None, lot2=True)).rotation) for g in range(70001, 70301))
    assert 5 <= penches <= 45, penches  # entre 2 et 15 % de 300 tirages


def test_le_scan_ancien_pose_sa_page():
    l = L.Lot2(famille="scan_ancien", papier=222, contraste=0.85, salissure="taches", rotation=1.2)
    style = _base(salissure="grain", contraste=1.1)
    L.appliquer(style, l)
    assert (style.papier, style.contraste, style.salissure, style.rotation) == (222, 0.85, "taches", 1.2)


# ---------------------------------------------------------------- le plan de travail le long d'un mur


def test_plan_de_travail_le_long_d_un_mur():
    from moteur.generateur.mobilier import meubler_niveau
    retournes = 0
    for graine in range(1, 80):
        try:
            log = generer(graine, Reglages())
        except RuntimeError:
            continue
        for n in log.niveaux:
            avant = meubler_niveau(n, graine)
            apres = L.plans_de_travail_au_mur(avant, n)
            pieces = {p.id: p for p in n.pieces}
            for pid, lst in apres.items():
                for m in lst:
                    if m.type == "plan_de_travail":
                        r, b = pieces[pid].rect, L._boite_meuble(m)
                        assert L._longe_un_mur(m, r), (graine, pid)
                        # _longe_un_mur ne regarde qu'un côté : un meuble sorti de sa pièce y passe, et il mordrait un mur.
                        assert r.x0 <= b.x0 and b.x1 <= r.x1 and r.y0 <= b.y0 and b.y1 <= r.y1, (graine, pid)
            retournes += sum(a.contour != b.contour for pid in avant for a, b in zip(avant[pid], apres[pid]))
            for pid in avant:  # rien d'autre ne bouge
                autres_avant = [m for m in avant[pid] if m.type != "plan_de_travail"]
                assert autres_avant == [m for m in apres[pid] if m.type != "plan_de_travail"]
    assert retournes > 0


def test_le_mobilier_des_anciens_jeux_ne_change_pas():
    # Le correctif vit dans rendre, sous --lot2 : mobilier.meubler_niveau rend le même meuble qu'avant, même de travers.
    from moteur.generateur.mobilier import meubler_niveau
    log = generer(2, Reglages())
    assert meubler_niveau(log.niveaux[0], 2) == meubler_niveau(log.niveaux[0], 2)
    ancien = rendre(log, log.niveaux[0], _base(mobilier=True))
    meubles = {pid: [m.contour for m in lst] for pid, lst in ancien.meubles.items()}
    assert meubles == {pid: [m.contour for m in lst] for pid, lst in meubler_niveau(log.niveaux[0], 2).items()}


# ---------------------------------------------------------------- le cercle HSP ne touche pas une ouverture


def test_cercle_hsp_jamais_sur_une_ouverture():
    # Comme sur la planche : petites pièces, texte gros. Le cercle ne se pose que là où il tient.
    from moteur.generateur.mobilier import _zones_de_battement
    appels = []
    vrai = L._cercle_hsp
    L._cercle_hsp = lambda d, cx, cy, valeur, taille, couleur: (appels.append((d, cx, cy, taille)), vrai(d, cx, cy, valeur, taille, couleur))
    try:
        for graine in (2, 7, 26, 60012):
            rendre(*(lambda log: (log, log.niveaux[0]))(generer(graine, Reglages())), _appliquee(L.Lot2(famille="neutre", hsp="HSP cercle")))
    finally:
        L._cercle_hsp = vrai
    assert appels
    for d, cx, cy, taille in appels:
        rayon = L._rayon_cercle_hsp(taille)
        for o in d.niv.ouvertures:
            x0, y0, x1, y1 = L._boite_px(d, rect_de_l_ouverture(o))
            assert not (x0 - rayon < cx < x1 + rayon and y0 - rayon < cy < y1 + rayon and
                        max(x0 - cx, 0, cx - x1) ** 2 + max(y0 - cy, 0, cy - y1) ** 2 < rayon ** 2)


def _appliquee(l: L.Lot2, base: Style | None = None) -> Style:
    style = base if base is not None else _base()
    L.appliquer(style, l)
    return style


def test_cercle_hsp_refuse_pres_d_une_porte():
    log = generer(2, Reglages())
    n = log.niveaux[0]
    style = _appliquee(L.Lot2(famille="neutre", hsp="HSP cercle"))
    d = rendre.__globals__["_Dessin"](log, n, style, Repere(_cadre_des_murs(n), style, random.Random(0), nb_pieces=len(n.pieces)), {}, True)
    o = next(x for x in n.ouvertures if x.type == "porte")
    p = next(q for q in n.pieces if q.rect.x0 <= rect_de_l_ouverture(o).x0 <= q.rect.x1 and q.rect.y0 <= rect_de_l_ouverture(o).y0 <= q.rect.y1 + 200)
    x0, y0, x1, y1 = L._boite_px(d, rect_de_l_ouverture(o))
    assert not L.cercle_tient(d, p, (x0 + x1) / 2, (y0 + y1) / 2, 15)
    # Trop près du bord de la pièce aussi.
    bx0, by0, _, _ = L._boite_px(d, p.rect)
    assert not L.cercle_tient(d, p, bx0 + 2, by0 + 2, 15)


# ---------------------------------------------------------------- trait 3 : promoteur gris


def _promoteur(**traits) -> L.Lot2:
    l = L.lot2_au_hasard(random.Random(11), famille="promoteur_gris", transversaux=False)
    neutres = dict(unite_cotes="cm", cote_point=False, cotes_interieures=True, sans_chaines=True, cercles_pmr=False, sols={}, numero_lot="",
                   abreviations=False, mentions_menuiseries=False, sans_mobilier=True, couleur_murs=(120, 120, 120), palette="", murs_dessin="", noms_courts=False)
    return dataclasses.replace(l, **{**neutres, **traits})


def test_trait_3_famille_tiree():
    vus = [L.lot2_au_hasard(random.Random(k), famille="promoteur_gris", transversaux=False) for k in range(120)]
    assert {l.unite_cotes for l in vus} == {"cm", "m"}
    assert any(l.cotes_interieures and l.unite_cotes == "cm" for l in vus)
    assert any(l.couleur_murs[0] > 100 for l in vus)  # du gris moyen, comme au catalogue
    style = _appliquee(vus[0], _base())
    assert style.cartouche is False and style.titre is False


def test_trait_3_cotes_en_cm_dans_les_pieces(monkeypatch):
    cotes, ecrits = _espion_cotes(monkeypatch), _espion_textes(monkeypatch)
    avec, reference, style, log = _rendus(60002, _promoteur())
    assert cotes
    pieces = log.niveaux[0].pieces
    for texte, longueur_mm, _ in cotes:
        assert texte in ecrits and abs(int(texte) * 10 - longueur_mm) <= 5.5, (texte, longueur_mm)  # arrondi au cm
    # Et elles mesurent bien une pièce, de face à face.
    assert {int(x) for x, _, h in cotes if h} <= {round(p.rect.largeur / 10) for p in pieces}
    assert {int(x) for x, _, h in cotes if not h} <= {round(p.rect.hauteur / 10) for p in pieces}
    sans, _, _, _ = _rendus(60002, _promoteur(cotes_interieures=False))
    diff = _diff(avec, sans)
    assert diff[avec.images["masque_pieces"] > 0].sum() > 150  # dans les pièces
    _verite_inchangee(avec, reference)
    assert style.cotes is True


def test_trait_3_texte_de_cote_en_cm_entier():
    l = L.Lot2(unite_cotes="cm")
    assert L.texte_cote(4053, l) == "405"
    assert L.texte_cote(4050, L.Lot2()) == "4,05"
    assert L.texte_cote(4050, L.Lot2(cote_point=True)) == "4.05"


def test_trait_3_chaines_en_cm(monkeypatch):
    vus = []
    vrai = R._Dessin.texte
    monkeypatch.setattr(R._Dessin, "texte", lambda self, xy, texte, *a, **k: (vus.append(texte), vrai(self, xy, texte, *a, **k))[1])
    log = generer(60002, Reglages())
    rendre(log, log.niveaux[0], _appliquee(_promoteur(sans_chaines=False, cotes_interieures=False, noms_courts=True)))
    assert any(t.isdigit() and len(t) in (3, 4) for t in vus)
    assert not any("," in t and t.replace(",", "").isdigit() for t in vus)  # jamais de mètres sur un plan en cm
    vus.clear()
    avec, reference, _, _ = _rendus(60002, _promoteur(sans_chaines=False, cotes_interieures=False, noms_courts=True))
    _verite_inchangee(avec, reference)


def test_cm_et_metres_jamais_ensemble():
    for k in range(600):
        l = L.lot2_au_hasard(random.Random(k))
        if l.unite_cotes == "cm":
            assert not l.dimensions and not l.cote_point and l.hsp != "HSP cercle", k


def test_trait_3_abreviations():
    assert L.abreger("Dégagement") == "Dgt"
    assert L.abreger("Chambre 2") == "Ch. 2"
    assert L.abreger("Placard 1") == "Pl. 1"
    assert L.abreger("Séjour / cuisine") == "Séjour / cuisine"
    log = generer(60002, Reglages())
    noms = [p.nom for p in log.niveaux[0].pieces]
    avec, reference, _, _ = _rendus(60002, _promoteur(abreviations=True, cotes_interieures=False))
    assert [p.nom for p in generer(60002, Reglages()).niveaux[0].pieces] == noms
    _verite_inchangee(avec, reference)


def test_trait_3_cercles_pmr():
    avec, reference, style, log = _rendus(60002, _promoteur(cercles_pmr=True, cotes_interieures=False))
    sans, _, _, _ = _rendus(60002, _promoteur(cercles_pmr=False, cotes_interieures=False))
    assert _diff(avec, sans).sum() > 100
    _verite_inchangee(avec, reference)


def test_trait_3_sols_hachures():
    avec, reference, _, _ = _rendus(60002, _promoteur(sols={"chambre": "hachures", "sejour": "parquet"}, couleur_sol=(205, 205, 205), cotes_interieures=False))
    sans, _, _, _ = _rendus(60002, _promoteur(cotes_interieures=False))
    diff = _diff(avec, sans)
    assert diff[avec.images["masque_semantique"] == CLASSES["chambre"]].sum() > 500
    assert not diff[avec.images["masque_semantique"] == CLASSES["wc"]].any()  # seulement où c'est demandé
    _verite_inchangee(avec, reference)


@pytest.mark.parametrize("numero", ["45", "A1 14", "Lot 206", "{type} G206"])
def test_trait_3_numero_de_lot(numero):
    avec, reference, _, _ = _rendus(60002, _promoteur(numero_lot=numero, cotes_interieures=False))
    sem = avec.images["masque_semantique"]
    assert np.any(avec.images["plan"][:np.nonzero(sem)[0].min() - 2] != 255)  # écrit au-dessus du logement
    _verite_inchangee(avec, reference)


def test_trait_3_numero_de_lot_sans_mesure_sous_sans_cotes():
    # « T3 G206 60.44 m² » écrit une surface : --sans-cotes qui a éteint les surfaces ne l'écrit pas.
    a, _, _, _ = _rendus(60002, _promoteur(numero_lot="{type} G206", cotes_interieures=False), _base(surfaces=False, cotes=False), sans_cotes=True)
    vus = []
    vrai = L._ecrire
    L._ecrire = lambda d, xy, texte, *r, **k: (vus.append(texte), vrai(d, xy, texte, *r, **k))[1]
    try:
        _rendus(60002, _promoteur(numero_lot="{type} G206", cotes_interieures=False), _base(surfaces=False, cotes=False), sans_cotes=True)
    finally:
        L._ecrire = vrai
    assert any("G206" in t for t in vus) and not any("m²" in t for t in vus)


def test_trait_3_mentions_menuiseries():
    avec, reference, _, _ = _rendus(60002, _promoteur(mentions_menuiseries=True, cotes_interieures=False))
    sans, _, _, _ = _rendus(60002, _promoteur(cotes_interieures=False))
    diff = _diff(avec, sans)
    assert diff.sum() > 20 and not diff[avec.images["masque_pieces"] > 0].any()  # dehors, jamais dans une pièce
    _verite_inchangee(avec, reference)


# ---------------------------------------------------------------- trait 6 : logiciel grand public


def _logiciel(**traits) -> L.Lot2:
    l = L.lot2_au_hasard(random.Random(5), famille="logiciel_public", transversaux=False)
    neutres = dict(palette="creme", couleur_murs=(160, 160, 160), couleur_cotes=(110, 110, 110), sans_mobilier=True, mobilier_couleur=False, barre_echelle=False,
                   textes_verticaux="", exterieurs=[])
    return dataclasses.replace(l, **{**neutres, **traits})


def test_trait_6_page_blanche_pieces_creme():
    avec, reference, style, _ = _rendus(60002, _logiciel())
    assert style.fond == (255, 255, 255)
    assert _couleur_de(avec, "chambre") == L.PALETTES_LOT2["creme"]["chambre"]
    assert _couleur_de(avec, "mur") == (160, 160, 160)
    _verite_inchangee(avec, reference)


def test_trait_6_cotes_par_mur_sans_chaines(monkeypatch):
    cotes, ecrits = _espion_cotes(monkeypatch), _espion_textes(monkeypatch)
    avec, reference, style, _ = _rendus(60002, _logiciel())
    assert cotes
    for texte, longueur_mm, _ in cotes:  # « 4,86 m », « 4 m » : le trait mesure ce que dit le nombre, à l'arrondi du cm près
        assert texte in ecrits and abs(float(texte.replace(" m", "").replace(",", ".")) * 1000 - longueur_mm) <= 5.5, (texte, longueur_mm)
    sans, _, _, _ = _rendus(60002, _logiciel(cotes_par_mur=False))
    diff = _diff(avec, sans)
    assert diff[avec.images["masque_pieces"] > 0].sum() > 400
    ys, _ = np.nonzero(avec.images["masque_semantique"])
    assert not diff[:ys.min()].any()  # aucune chaîne au-dessus du logement
    _verite_inchangee(avec, reference)


def test_trait_6_format_des_cotes():
    assert L.texte_metres(4860) == "4,86 m"
    assert L.texte_metres(4000) == "4 m"
    assert L.texte_metres(1800) == "1,8 m"


def test_trait_6_sans_cotes_aucune_cote():
    a, _, _, _ = _rendus(60002, _logiciel(), _base(cotes=False), sans_cotes=True)
    b, _, _, _ = _rendus(60002, _logiciel(cotes_par_mur=False, couleur_cotes=None), _base(cotes=False), sans_cotes=True)
    assert np.array_equal(a.images["plan"], b.images["plan"])


def test_trait_6_contraste_en_gris():
    # Le modèle voit du gris : le mur doit rester à 60 niveaux au moins de la pièce, même au plus clair du tirage.
    for k in range(60):
        l = L.lot2_au_hasard(random.Random(k), famille="logiciel_public", transversaux=False)
        gris_mur = float(np.dot(l.couleur_murs, (0.299, 0.587, 0.114)))
        gris_piece = float(np.dot(L.PALETTES_LOT2[l.palette]["chambre"], (0.299, 0.587, 0.114)))
        assert gris_piece - gris_mur >= 60


# ---------------------------------------------------------------- trait 7 : texte tourné


def test_trait_7_pieces_etroites():
    avec, reference, _, log = _rendus(2, L.Lot2(famille="neutre", textes_verticaux="etroites"))
    a_plat, _, _, _ = _rendus(2, L.Lot2(famille="neutre"))
    diff = _diff(avec, a_plat)
    assert diff.any()
    ids = {p.id: i + 1 for i, p in enumerate(log.niveaux[0].pieces)}
    etroites = [p for p in log.niveaux[0].pieces if p.nom == "Placard 1"]
    ys, xs = np.nonzero(diff & (avec.images["masque_pieces"] == ids[etroites[0].id]))
    assert ys.max() - ys.min() > xs.max() - xs.min()  # le texte a tourné : il s'étend en hauteur
    # Une grande pièce, où le nom tient à plat, ne change pas.
    grande = max(log.niveaux[0].pieces, key=surface_piece)
    assert not diff[avec.images["masque_pieces"] == ids[grande.id]].any()
    _verite_inchangee(avec, reference)


def test_trait_7_toutes_les_pieces():
    avec, reference, _, log = _rendus(2, L.Lot2(famille="neutre", textes_verticaux="toutes"))
    a_plat, _, _, _ = _rendus(2, L.Lot2(famille="neutre"))
    ids = {p.id: i + 1 for i, p in enumerate(log.niveaux[0].pieces)}
    grande = max(log.niveaux[0].pieces, key=surface_piece)
    assert _diff(avec, a_plat)[avec.images["masque_pieces"] == ids[grande.id]].any()
    _verite_inchangee(avec, reference)


# ---------------------------------------------------------------- trait 9 : scan ancien


def _scan(**traits) -> L.Lot2:
    return L.Lot2(famille="scan_ancien", papier=228, contraste=0.9, salissure="grain", teinte=(0.88, 0.93, 1.0), unite_cotes="cm", cotes_interieures=True,
                  sans_chaines=True, noms_courts=True, couleur_murs=(30, 30, 30), sortie_jpeg=True, **traits)


def test_trait_9_scan_bleute():
    avec, reference, style, _ = _rendus(60002, _scan())
    assert style.salissure == "grain"
    plan = avec.images["plan"]
    assert plan[..., 0].mean() < plan[..., 2].mean() - 8  # moins de rouge que de bleu
    _verite_inchangee(avec, reference)


def test_trait_9_la_salissure_de_base_n_est_pas_changee_sans_lot2():
    # Aucune branche de salir ne lit le lot 2 : la teinte s'applique après, dans rendre.
    from moteur.generateur.variantes import salir
    image = np.full((40, 40, 3), 200, np.uint8)
    style = Style(salissure="grain", papier=230)
    a = salir(image, style, random.Random(1))
    b = salir(image, dataclasses.replace(style, lot2=_scan()), random.Random(1))
    assert np.array_equal(a, b)


def test_trait_9_teinter():
    image = np.full((4, 4, 3), 200, np.uint8)
    assert L.teinter(image, (0.5, 1.0, 1.5))[0, 0].tolist() == [100, 200, 255]


def test_trait_9_murs_hachures_et_absurde():
    l = _scan()
    l.murs_dessin = "hachure"
    avec, reference, _, _ = _rendus(60002, l)
    _verite_inchangee(avec, reference)
    from moteur.generateur.variete import Variete
    absurde = _base(variete=Variete(absurde=True))
    l2 = _scan()
    L.appliquer(absurde, l2)
    assert l2.teinte is None  # un style absurde garde ses couleurs


def test_trait_9_famille_tiree():
    vus = [L.lot2_au_hasard(random.Random(k), famille="scan_ancien", transversaux=False) for k in range(120)]
    assert all(l.salissure for l in vus)
    assert any(l.teinte for l in vus) and any(not l.teinte for l in vus)
    assert {l.unite_cotes for l in vus} == {"m", "cm"}


# ---------------------------------------------------------------- trait 11 : l'écriture à la main


class _Toile:
    """Juste ce qu'il faut à texte_main."""
    def __init__(self):
        from PIL import Image
        self.image = Image.new("RGB", (400, 100), (255, 255, 255))


def test_trait_11_texte_main():
    stylo = (40, 60, 150)
    a, b, c = _Toile(), _Toile(), _Toile()
    L.texte_main(a, (200, 50), "11,6 m²", 24, stylo, random.Random(1))
    L.texte_main(b, (200, 50), "11,6 m²", 24, stylo, random.Random(1))
    L.texte_main(c, (200, 50), "11,6 m²", 24, stylo, random.Random(2))
    aa, bb, cc = np.asarray(a.image), np.asarray(b.image), np.asarray(c.image)
    assert np.array_equal(aa, bb) and not np.array_equal(aa, cc)
    pixels = aa[np.any(aa != 255, axis=2)]
    assert len(pixels) > 100 and (pixels == np.array(stylo)).all(axis=1).any()


def test_trait_11_surfaces_au_stylo():
    avec, reference, _, _ = _rendus(60002, L.Lot2(famille="neutre", manuscrit="surfaces", couleur_stylo=(40, 60, 150)))
    sans, _, _, _ = _rendus(60002, L.Lot2(famille="neutre"))
    assert _diff(avec, sans).any()
    bleu = np.all(avec.images["plan"] == np.array((40, 60, 150)), axis=2)
    assert bleu[avec.images["masque_pieces"] > 0].sum() > 30
    _verite_inchangee(avec, reference)


def test_trait_11_plan_et_plan_sans_mobilier_meme_trembler():
    style = _base(mobilier=True)
    avec, _, _, _ = _rendus(60002, L.Lot2(famille="neutre", manuscrit="tout"), style)
    ecart = np.any(avec.images["plan"] != avec.images["plan_sans_mobilier"], axis=2)
    meubles = cv2.dilate((avec.images["hauteur"] > 0).astype(np.uint8), np.ones((9, 9), np.uint8)) > 0
    assert not ecart[~meubles].any()


def test_trait_11_cotes_au_stylo():
    avec, reference, _, _ = _rendus(60002, L.Lot2(famille="neutre", manuscrit="surfaces", couleur_stylo=(40, 60, 150), noms_courts=True))
    ys, _ = np.nonzero(avec.images["masque_semantique"])
    plan = avec.images["plan"].astype(int)
    bleu = plan[..., 2] > plan[..., 0] + 40  # les bords des lettres sont lissés : du bleu, pas une seule couleur exacte
    assert bleu[:ys.min()].sum() > 20  # la chaîne du haut, à la main
    _verite_inchangee(avec, reference)


# ---------------------------------------------------------------- trait 14 : pastilles


def test_trait_14_pastilles_avec_noms():
    avec, reference, style, log = _rendus(60002, L.Lot2(famille="neutre", pastilles="avec_noms"))
    sans, _, _, _ = _rendus(60002, L.Lot2(famille="neutre"))
    diff = _diff(avec, sans)
    ids = {p.id: i + 1 for i, p in enumerate(log.niveaux[0].pieces)}
    grande = max(log.niveaux[0].pieces, key=surface_piece)
    assert diff[avec.images["masque_pieces"] == ids[grande.id]].sum() > 100
    _verite_inchangee(avec, reference)


def test_trait_14_legende_dans_la_marge():
    avec, reference, style, log = _rendus(60002, L.Lot2(famille="neutre", pastilles="legende"))
    plan, sem = avec.images["plan"], avec.images["masque_semantique"]
    xs = np.nonzero(sem.max(axis=0))[0]
    assert np.any(plan[:, xs.max() + round(L._debut_tableau(style)):] != np.array(style.fond))
    _verite_inchangee(avec, reference)


def test_trait_14_legende_sans_surface_sous_sans_cotes():
    a, _, _, _ = _rendus(60002, L.Lot2(famille="neutre", pastilles="legende"), _base(surfaces=True))
    b, _, _, _ = _rendus(60002, L.Lot2(famille="neutre", pastilles="legende"), _base(surfaces=False, cotes=False), sans_cotes=True)
    # Les deux légendes existent ; la seconde n'écrit aucune surface : moins de pixels dans la marge.
    def encre(r):
        xs = np.nonzero(r.images["masque_semantique"].max(axis=0))[0]
        return int(np.any(r.images["plan"][:, xs.max() + 40:] != 255, axis=2).sum())
    assert 0 < encre(b) < encre(a)


# ---------------------------------------------------------------- trait 15 : placards fléchés


def test_trait_15_placards_fleches():
    marges = _base(marges=(170, 140, 400, 400))  # les mêmes marges des deux côtés : les images se comparent pixel à pixel
    avec, reference, style, log = _rendus(26, L.Lot2(famille="neutre", placards_fleches=True), dataclasses.replace(marges))
    sans, _, _, _ = _rendus(26, L.Lot2(famille="neutre"), dataclasses.replace(marges))
    diff = _diff(avec, sans)
    xs = np.nonzero(avec.images["masque_semantique"].max(axis=0))[0]
    assert diff[:, :xs.min()].any() or diff[:, xs.max():].any()  # l'étiquette, dans une marge
    ids = {p.id: i + 1 for i, p in enumerate(log.niveaux[0].pieces)}
    placard = next(p for p in log.niveaux[0].pieces if p.sorte == "placard")
    assert diff[avec.images["masque_pieces"] == ids[placard.id]].any()  # la flèche arrive dans le placard
    assert diff[avec.images["masque_semantique"] == CLASSES["mur"]].any()  # et traverse le mur, sans changer son masque
    _verite_inchangee(avec, reference)


def test_trait_15_exemple_valide(tmp_path, monkeypatch):
    _fabriquer(tmp_path, monkeypatch, L.Lot2(famille="neutre", placards_fleches=True), graine=26)


# ---------------------------------------------------------------- trait 17 : escaliers


GRAINE_DUPLEX = 62


def test_trait_17_colimacon():
    avec, reference, _, log = _rendus(GRAINE_DUPLEX, L.Lot2(famille="neutre", escalier="colimacon"))
    sans, _, _, _ = _rendus(GRAINE_DUPLEX, L.Lot2(famille="neutre"))
    diff = _diff(avec, sans)
    esc = avec.images["masque_semantique"] == CLASSES["escalier"]
    assert diff[esc].sum() > 50
    assert not diff[~cv2.dilate(esc.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)].any()  # identique ailleurs
    # La carte de hauteur reste celle de l'escalier droit : seuls les traits changent.
    _verite_inchangee(avec, reference)
    assert avec.images["hauteur"][esc].max() > 1000


def test_trait_17_fleche_acces():
    avec, reference, _, _ = _rendus(GRAINE_DUPLEX, L.Lot2(famille="neutre", escalier="fleche_acces"))
    sans, _, _, _ = _rendus(GRAINE_DUPLEX, L.Lot2(famille="neutre"))
    diff = _diff(avec, sans)
    esc = avec.images["masque_semantique"] == CLASSES["escalier"]
    assert diff[esc].sum() > 20
    _verite_inchangee(avec, reference)


def test_trait_17_exemple_duplex_valide(tmp_path, monkeypatch):
    _fabriquer(tmp_path, monkeypatch, L.Lot2(famille="neutre", escalier="colimacon"), graine=GRAINE_DUPLEX)


# ---------------------------------------------------------------- trait 18 et balcons du trait 4


def _exterieur(**k) -> dict:
    e = {"sorte": "balcon", "cote": "bas", "part": 0.6, "position": 0.5, "profondeur_m": 1.5, "motif": "vide", "contour": "fin", "couleur": None, "numero": 1}
    e.update(k)
    return e


@pytest.mark.parametrize("cote", ["bas", "droite"])
@pytest.mark.parametrize("motif", ["vide", "lattes", "carrelage", "hachures", "croisillons", "herbe"])
def test_trait_18_exterieur_dessine_et_masque_fond(cote, motif):
    avec, reference, style, log = _rendus(26, L.Lot2(famille="neutre", exterieurs=[_exterieur(cote=cote, motif=motif)]))
    sans, _, _, _ = _rendus(26, L.Lot2(famille="neutre"))
    sem = avec.images["masque_semantique"]
    ys, xs = np.nonzero(sem)
    plan = avec.images["plan"]
    zone = sem == 0
    if cote == "bas":
        zone[:ys.max() + 1] = False
    else:
        zone[:, :xs.max() + 1] = False
    assert np.any(plan[zone] != np.array(style.fond))  # dessiné hors du logement
    # Marge élargie, et les images gardent la taille des masques.
    assert plan.shape[:2] == sem.shape
    assert plan.shape != sans.images["plan"].shape or not np.array_equal(plan, sans.images["plan"])
    _verite_inchangee(avec, reference)


def test_trait_18_jardin_vert():
    vert = (125, 235, 100)
    avec, reference, style, _ = _rendus(26, L.Lot2(famille="neutre", exterieurs=[_exterieur(sorte="jardin", part=1.0, profondeur_m=3.0, motif="vert", contour="gris", couleur=vert)]))
    sem = avec.images["masque_semantique"]
    plan = avec.images["plan"]
    verts = np.all(plan == np.array(vert), axis=2)
    assert verts.sum() > 2000 and not verts[sem > 0].any()  # jamais sur le logement
    _verite_inchangee(avec, reference)


def test_trait_18_contour_gris_jamais_plus_de_2_pixels():
    # La couleur des murs, l'allure d'une cloison et un masque qui dit fond : le modèle apprendrait qu'une cloison n'est pas un mur.
    mauve, vert = (90, 30, 90), (125, 235, 100)
    for px_par_m in (100.0, 130.0):
        l = L.Lot2(famille="neutre", couleur_murs=mauve, exterieurs=[_exterieur(sorte="terrasse", profondeur_m=2.0, motif="vert", contour="gris", couleur=vert)])
        avec, _, _, _ = _rendus(26, l, _base(px_par_m=px_par_m))
        trait = (np.all(avec.images["plan"] == np.array(mauve), axis=2) & (avec.images["masque_semantique"] == 0)).astype(np.uint8)
        assert trait.sum() > 100  # il est bien dessiné
        assert not cv2.erode(trait, np.ones((3, 3), np.uint8)).any()  # 3 pixels de large n'existent nulle part


def test_trait_18_surface_ecrite_est_la_vraie(monkeypatch):
    # Le lecteur d'échelle sait lire les surfaces écrites : une surface de balcon fausse serait une échelle fausse.
    vus = []
    vrai = L._ecrire_exterieur
    monkeypatch.setattr(L, "_ecrire_exterieur", lambda d, xy, texte, *r: (vus.append(texte), vrai(d, xy, texte, *r))[1])
    _, _, style, log = _rendus(26, L.Lot2(famille="neutre", exterieurs=[_exterieur(part=0.6, profondeur_m=2.4)]))
    n = log.niveaux[0]
    d = R._Dessin(log, n, style, Repere(_cadre_des_murs(n), style, random.Random(0), nb_pieces=len(n.pieces)), {}, True)
    (_, r), = L.places_des_exterieurs(d)
    attendu = f"{(r.x1 - r.x0) * (r.y1 - r.y0) / 1e6:.2f} m²".replace(".", ",")
    assert attendu in vus and sum("m²" in x for x in vus) == 1


def test_trait_18_exterieur_sans_mesure_sous_sans_cotes():
    e = [_exterieur(profondeur_m=2.0)]
    vus = []
    vrai = L._ecrire_exterieur
    L._ecrire_exterieur = lambda d, xy, texte, *r: (vus.append(texte), vrai(d, xy, texte, *r))[1]
    try:
        _rendus(26, L.Lot2(famille="neutre", exterieurs=e), _base(surfaces=False, cotes=False), sans_cotes=True)
    finally:
        L._ecrire_exterieur = vrai
    assert vus == ["Balcon"]  # le nom seul, jamais « 7,20 m² »


def _places(log, exterieurs: list[dict]) -> list:
    n = log.niveaux[0]
    style = _appliquee(L.Lot2(famille="neutre", exterieurs=exterieurs))
    return [r for _, r in L.places_des_exterieurs(R._Dessin(log, n, style, Repere(_cadre_des_murs(n), style, random.Random(0), nb_pieces=len(n.pieces)), {}, True))]


def _se_touchent(a, b) -> bool:
    return not (a.x1 <= b.x0 + 1 or b.x1 <= a.x0 + 1 or a.y1 <= b.y0 + 1 or b.y1 <= a.y0 + 1)


def test_trait_18_extérieur_ne_recouvre_rien():
    # Graine 26, à droite : le premier mur candidat donne sur un renfoncement, le balcon y entrerait dans un mur du logement.
    from moteur.generateur.annotations import rect_du_mur
    vus = 0
    for graine in (26, 60, 60012, 2, 7):
        log = generer(graine, Reglages())
        for cote in ("bas", "droite"):
            for r in _places(log, [_exterieur(cote=cote, part=0.9, profondeur_m=2.4)]):
                vus += 1
                for z in [p.rect for p in log.niveaux[0].pieces] + [rect_du_mur(m) for m in log.niveaux[0].murs]:
                    assert not _se_touchent(r, z), (graine, cote)
    assert vus >= 5  # sinon la boucle ne prouverait rien


def _boite_du_pan(m):
    xs, ys = [q[0] for q in m.polygone], [q[1] for q in m.polygone]
    return L.Rect(min(xs), min(ys), max(xs), max(ys))


def test_trait_18_sur_un_plan_en_biais():
    # Aucun extérieur sur un pan coupé, et la vérité reste celle du logement coupé.
    exterieurs = [_exterieur(cote="droite", part=0.9), _exterieur(cote="bas", part=0.9)]
    avec, reference, _, log = _rendus(101, L.Lot2(famille="neutre", exterieurs=exterieurs), biais=True)
    n = log.niveaux[0]
    assert n.murs_libres
    _verite_inchangee(avec, reference)
    places = _places(log, exterieurs)
    assert places and not any(_se_touchent(r, _boite_du_pan(m)) for r in places for m in n.murs_libres)
    # Sur 300 tirages, un mur droit raccourci par son pan coupé ne laisse jamais un balcon l'atteindre : l'obstacle ne s'est jamais
    # montré utile. Il reste la seule garde si cela change : on pose donc le pan juste là où irait le balcon, il doit aller ailleurs.
    avant = places[0]
    n.murs_libres[0].polygone = [(avant.x0, avant.y0), (avant.x1, avant.y0), (avant.x1, avant.y1), (avant.x0, avant.y1)]
    assert avant not in _places(log, exterieurs[:1])


def test_trait_4_balcons_de_la_famille():
    vus = [L.lot2_au_hasard(random.Random(k), famille="murs_noirs") for k in range(120)]
    balcons = [e for l in vus for e in l.exterieurs]
    assert balcons and all(e["sorte"] == "balcon" and e["contour"] in ("fin", "pointille") and e["motif"] == "vide" for e in balcons)
    l = dataclasses.replace(L.lot2_au_hasard(random.Random(2), famille="murs_noirs", transversaux=False), exterieurs=[_exterieur(contour="pointille")])
    avec, reference, _, _ = _rendus(26, l)
    _verite_inchangee(avec, reference)


def test_trait_18_exemple_valide(tmp_path, monkeypatch):
    _fabriquer(tmp_path, monkeypatch, L.Lot2(famille="neutre", exterieurs=[_exterieur(), _exterieur(cote="droite", sorte="terrasse", motif="lattes", contour="moyen", numero=2)]), graine=26)


# ---------------------------------------------------------------- les familles du chantier 2 avec les autres options


FAMILLES_2 = ("promoteur_gris", "logiciel_public", "scan_ancien")


@pytest.mark.parametrize("famille", FAMILLES_2)
@pytest.mark.parametrize("options", [
    {"styles_monde": True}, {"biais": True}, {"sans_cotes": True}, {"photo_realiste": True, "vraie_camera": True, "familles": ["photo"]},
])
def test_combinaisons_du_chantier_2(famille, options):
    for graine in (60002, 40002):
        opt = Options(dossier=None, lot2=True, **options)
        style = style_pour(graine, 0, dataclasses.replace(opt, lot2=False))
        l = L.lot2_au_hasard(random.Random(f"test-{graine}"), famille=famille)
        L.appliquer(style, l, sans_cotes=options.get("sans_cotes", False))
        log = generer(graine, Reglages())
        if options.get("biais"):
            from moteur.generateur.biais import couper_angles
            couper_angles(log, random.Random(f"biais-{graine}"))
        reference = dataclasses.replace(style, lot2=None, marges=L.marges_lot2(style, style.marges, len(log.niveaux[0].pieces)))
        avec = rendre(log, log.niveaux[0], style)
        _verite_inchangee(avec, rendre(log, log.niveaux[0], reference), _masques_du(style))
        if options.get("sans_cotes"):
            assert style.cotes is False and style.cotes_partielles is False
        if options.get("familles"):  # une vraie photo reste une photo, même d'un scan ancien
            assert style.focale and style.realisme is not None


@pytest.mark.parametrize("famille", FAMILLES_2)
def test_sans_cotes_aucune_mesure_dans_les_familles_du_chantier_2(famille, monkeypatch):
    """--sans-cotes gagne : aucune cote (ni cm, ni par mur, ni intérieure), aucune surface si l'option les a éteintes."""
    ecrits = []
    vrai = R._Dessin.texte
    monkeypatch.setattr(R._Dessin, "texte", lambda self, xy, texte, *a, **k: (ecrits.append(texte), vrai(self, xy, texte, *a, **k))[1])
    vrai_main = L.texte_main
    monkeypatch.setattr(L, "texte_main", lambda d, xy, texte, *a, **k: (ecrits.append(texte), vrai_main(d, xy, texte, *a, **k))[1])
    for k in range(6):
        l = L.lot2_au_hasard(random.Random(k), famille=famille)
        l.echelle_ecrite = ""
        style = _base(surfaces=False, cotes=False, cotes_partielles=False)
        L.appliquer(style, l, sans_cotes=True)
        assert style.cotes is False and style.surfaces is False
        log = generer(60002, Reglages())
        rendre(log, log.niveaux[0], style)
    assert ecrits
    for texte in ecrits:
        assert "m²" not in texte, texte
        assert not texte.replace(",", "").replace(".", "").replace(" m", "").isdigit() or len(texte) <= 2, texte  # les pastilles


def test_lot_avec_tout_le_lot2(tmp_path):
    # De bout en bout, sur le disque : tous les plans fabriqués passent le validateur.
    bilan = generer_lot(Options(dossier=tmp_path, nombre=24, depart=200, lot2=True, reprise=False), processus=1)
    assert bilan["statuts"]["rejete"] == 0 and bilan["statuts"]["accepte"] >= 18
    familles = set()
    for d in (tmp_path / "exemples").glob("*/"):
        assert valider_dossier(d, Regles.charger(None)).accepte, d.name
        familles.add(json.loads((d / "manifeste.json").read_text(encoding="utf-8"))["lot2"]["famille"])
    assert len(familles) >= 4


def test_le_lecteur_lit_des_cotes_en_cm(monkeypatch):
    """Le chemin du lecteur : ce plan à plat a des cotes en cm entiers. La vraie vérification est la mesure (b) sur OCR ;
    ici on s'assure seulement que les textes écrits sont bien des entiers à 2 ou 3 chiffres, ce qu'il reconnaît."""
    from moteur.lecture_cotes import FORME_COTE_CM
    vus = []
    vrai = R._Dessin.texte
    monkeypatch.setattr(R._Dessin, "texte", lambda self, xy, texte, *a, **k: (vus.append(texte), vrai(self, xy, texte, *a, **k))[1])
    _rendus(60002, _promoteur(noms_courts=True))
    nombres = [t for t in vus if t.isdigit()]
    assert nombres and all(FORME_COTE_CM.match(t) for t in nombres if len(t) <= 3)


# ---------------------------------------------------------------- chantier 3 : traits 12 et 13, l'exemple -ensemble


def _lot_compose(compose: str, disposition: str, famille: str = "neutre", **traits) -> L.Lot2:
    l = L.lot2_au_hasard(random.Random(f"test-{compose}-{disposition}-{famille}"), famille=famille, transversaux=False)
    l.composition, l.disposition = compose, disposition
    for k, v in traits.items():
        setattr(l, k, v)
    return l


def _ensemble(tmp_path, monkeypatch, l: L.Lot2, graine: int, **options):
    """Le parent et son -ensemble, écrits sur le disque par le vrai chemin. Plain-pied : la composition n'est plus tirée au sort."""
    monkeypatch.setattr(E, "lot2_au_hasard", lambda rng: l)
    monkeypatch.setattr(E, "PLAIN_PIED_EMPILE", 1.0)
    opt = Options(dossier=tmp_path, lot2=True, reprise=False, **options)
    r = fabriquer_exemple(graine, opt, Reglages(), Regles.charger(None))
    assert r.statut == "accepte", r.erreurs
    return r, tmp_path / "exemples" / f"{graine:06d}-ensemble"


def _lire(dossier):
    from moteur.images import lire_image
    dn = dossier / "niveau_0"
    return {nom: lire_image(str(dn / f"{nom}.png"), cv2.IMREAD_UNCHANGED) for nom in ("masque_semantique", "masque_pieces", "masque_elements")}, \
        json.loads((dn / "annotations.json").read_text(encoding="utf-8"))


def _ids(log) -> list[str]:
    n = log.niveaux[0]
    return [e.id for e in (*n.pieces, *n.murs, *n.murs_libres, *n.ouvertures)]


def test_assembler_duplex():
    log = generer(62, Reglages())
    assert log.duplex
    avant = [dataclasses.asdict(p.rect) for p in log.pieces]
    assemble, blocs = L.assembler(log, [(log.niveaux[0], 0, 0, "_n0"), (log.niveaux[1], 20000, 0, "_n1")], ["RDC", "R+1"])
    n = assemble.niveaux[0]
    assert len(assemble.niveaux) == 1 and n.index == 0 and not assemble.duplex
    assert len(n.pieces) == len(log.pieces) and len(n.murs) == len(log.murs) and len(n.ouvertures) == len(log.ouvertures)
    assert len(set(_ids(assemble))) == len(_ids(assemble))
    murs = {id(m) for m in n.murs}
    assert all(id(o.mur) in murs for o in n.ouvertures)  # chaque ouverture pointe vers un mur de l'ensemble, pas de l'original
    assert [dataclasses.asdict(p.rect) for p in log.pieces] == avant  # les niveaux du parent, déjà écrits, ne bougent pas
    assert blocs[0]["titre"] == "RDC" and blocs[1]["cadre"][0] >= 20000 - 1000


def test_assembler_chaque_ouverture_reste_dans_son_mur():
    log = generer(62, Reglages())
    assemble, _ = L.assembler(log, [(log.niveaux[0], 300, -700, "_n0"), (log.niveaux[1], 25000, 9000, "_n1")])
    for o in assemble.niveaux[0].ouvertures:
        assert o.mur.debut - 1e-6 <= o.u0 < o.u1 <= o.mur.fin + 1e-6
    r0, r1 = log.niveaux[0].ouvertures[0], assemble.niveaux[0].ouvertures[0]
    a, b = rect_de_l_ouverture(r0), rect_de_l_ouverture(r1)
    assert (b.x0 - a.x0, b.y0 - a.y0) == (300, -700)


@pytest.mark.parametrize("disposition", ["empiles", "cote_a_cote"])
def test_exemple_ensemble_valide(tmp_path, monkeypatch, disposition):
    from moteur.logement import Logement
    l = _lot_compose("niveaux", disposition, titres_place="", couleur_murs=(0, 0, 0))
    r, dossier = _ensemble(tmp_path, monkeypatch, l, 62)
    assert r.entree_manifeste["compose"] == "niveaux" and r.entree_manifeste["ensemble_accepte"] is True
    assert valider_dossier(dossier, Regles.charger(None)).accepte
    assert (dossier / "geometrie.json").exists() and (dossier / "logement_niveau0.json").exists()
    m = json.loads((dossier / "manifeste.json").read_text(encoding="utf-8"))
    assert m["parent"] == "000062" and m["compose"] == "niveaux" and m["nombre_niveaux"] == 1 and m["id"] == "000062-ensemble"
    Logement.model_validate(json.loads((dossier / "logement_niveau0.json").read_text(encoding="utf-8")))
    geo = json.loads((dossier / "geometrie.json").read_text(encoding="utf-8"))
    assert geo["parent"] == "000062" and geo["compose"] == "niveaux" and len(geo["blocs"]) == 2 and len(geo["niveaux"]) == 1
    masques, ann = _lire(dossier)
    # Le masque des pièces a exactement n valeurs 1..n : ce que relit le validateur et ce que lit le banc.
    n = len(ann["pieces"])
    assert sorted(np.unique(masques["masque_pieces"]).tolist()) == list(range(n + 1))
    # Le vide entre les blocs est du fond, d'un bout à l'autre.
    from moteur.generateur.lot2 import vides_entre_blocs
    style = ann["style"]["lot2"]
    a = ann["image"]["matrice_m_vers_px"]
    vide = vides_entre_blocs(style["blocs"])[0]
    u0, v0 = a[0][0] * vide.x0 / 1000 + a[0][2], a[1][1] * vide.y0 / 1000 + a[1][2]
    u1, v1 = a[0][0] * vide.x1 / 1000 + a[0][2], a[1][1] * vide.y1 / 1000 + a[1][2]
    zone = masques["masque_semantique"][round(min(v0, v1)) + 1:round(max(v0, v1)) - 1, round(min(u0, u1)) + 1:round(max(u0, u1)) - 1]
    assert zone.size and not zone.any()
    # Chaque bloc a bien ses pièces : aucune des pièces d'un bloc n'est dans l'autre.
    assert not set(style["blocs"][0]["pieces"]) & set(style["blocs"][1]["pieces"])
    assert len(style["blocs"][0]["pieces"]) + len(style["blocs"][1]["pieces"]) == n


def test_l_ensemble_ne_change_pas_le_parent(tmp_path, monkeypatch):
    # Les dossiers du parent sont ceux qu'il aurait eus sans composition : l'ensemble s'ajoute, il ne remplace rien.
    _ensemble(tmp_path / "a", monkeypatch, _lot_compose("niveaux", "empiles"), 62)
    sans = _lot_compose("niveaux", "empiles")
    sans.composition, sans.disposition = "", ""
    monkeypatch.setattr(E, "lot2_au_hasard", lambda rng: sans)
    fabriquer_exemple(62, Options(dossier=tmp_path / "b", lot2=True, reprise=False), Reglages(), Regles.charger(None))
    for niveau in ("niveau_0", "niveau_1"):
        for nom in ("masque_semantique.png", "masque_pieces.png", "masque_elements.png", "hauteur.png"):
            a = (tmp_path / "a" / "exemples" / "000062" / niveau / nom).read_bytes()
            b = (tmp_path / "b" / "exemples" / "000062" / niveau / nom).read_bytes()
            assert a == b, (niveau, nom)


def test_trait_12_titres_dans_l_image(monkeypatch):
    ecrits = []
    vrai = R._Dessin.texte
    monkeypatch.setattr(R._Dessin, "texte", lambda self, xy, texte, *a, **k: (ecrits.append((texte, xy)), vrai(self, xy, texte, *a, **k))[1])
    log = generer(62, Reglages())
    style = _base()
    L.appliquer(style, _lot_compose("niveaux", "empiles"))
    c = L.composer(log, None, "niveaux", "empiles", style, random.Random(2))
    L.vers_ensemble(style, c)
    style.lot2.titres_place, style.lot2.titre_tirets, style.lot2.titre_surface = "haut", True, False
    style.lot2.blocs[0]["titre"], style.lot2.blocs[1]["titre"] = "Rez-de-chaussée", "1er étage"
    rendu = rendre(c.log, c.log.niveaux[0], style, "ensemble")
    titres = {t: xy for t, xy in ecrits if "-----" in t}
    assert set(titres) == {"----- Rez-de-chaussée -----", "----- 1er étage -----"}
    sem = rendu.images["masque_semantique"]
    for _, (x, y) in titres.items():
        assert sem[int(y), int(x)] == 0  # écrit dans le vide ou la marge : jamais sur le logement


@pytest.mark.parametrize("disposition", ["empiles", "cote_a_cote"])
def test_trait_12_une_chaine_de_cotes_par_bloc(monkeypatch, disposition):
    ecrits = []
    vrai = R._Dessin.texte
    monkeypatch.setattr(R._Dessin, "texte", lambda self, xy, texte, *a, **k: (ecrits.append(texte), vrai(self, xy, texte, *a, **k))[1])
    log = generer(62, Reglages())
    style = _base(cotes=True, cotes_partielles=False, noms=False, surfaces=False)
    L.appliquer(style, _lot_compose("niveaux", disposition, couleur_cotes=None))
    style.cotes, style.noms, style.surfaces = True, False, False
    c = L.composer(log, None, "niveaux", disposition, style, random.Random(3))
    L.vers_ensemble(style, c)
    rendre(c.log, c.log.niveaux[0], style, "ensemble")
    largeurs = set()
    for b in style.lot2.blocs:
        rects = [p.rect for p in c.log.niveaux[0].pieces if p.id in b["pieces"]]
        largeurs.add(L.texte_cote(max(r.x1 for r in rects) - min(r.x0 for r in rects), style.lot2))
    assert largeurs <= set(ecrits)
    rects = [p.rect for p in c.log.niveaux[0].pieces]
    total = L.texte_cote(max(r.x1 for r in rects) - min(r.x0 for r in rects), style.lot2)
    if disposition == "cote_a_cote":
        assert total not in ecrits  # une chaîne qui traverse le vide ne mesurerait rien


def test_plain_pied_compose_une_fois_sur_quatre_seulement(tmp_path, monkeypatch):
    l = _lot_compose("niveaux", "empiles")
    monkeypatch.setattr(E, "lot2_au_hasard", lambda rng: l)
    bilan = generer_lot(Options(dossier=tmp_path, nombre=24, depart=500, lot2=True, reprise=False, types=["T1", "T2", "studio"]), processus=1)
    faits = sum(1 for d in (tmp_path / "exemples").glob("*-ensemble"))
    acceptes = bilan["statuts"]["accepte"]
    assert acceptes > 3 and faits < acceptes  # pas tous : un plain-pied ne se déguise pas toujours en maison à étages
    assert bilan["ensembles"]["acceptes"] == faits


@pytest.mark.parametrize("graine", [26, 60, 53])
def test_trait_13_palier(tmp_path, monkeypatch, graine):
    l = _lot_compose("deux_logements", "palier", titres_place="")
    r, dossier = _ensemble(tmp_path, monkeypatch, l, graine)
    assert r.entree_manifeste["compose"] == "deux_logements"
    assert valider_dossier(dossier, Regles.charger(None)).accepte
    masques, ann = _lire(dossier)
    geo = json.loads((dossier / "geometrie.json").read_text(encoding="utf-8"))
    assert geo["compose"] == "deux_logements" and geo["disposition"] == "palier"
    # Le palier est du fond : deux blocs bâtis, séparés.
    bati = ((masques["masque_semantique"] >= 1) & (masques["masque_semantique"] <= 15)).astype(np.uint8)
    n, _ = cv2.connectedComponents(bati, connectivity=8)
    assert n - 1 == 2
    a, b = geo["blocs"]
    assert a["pieces"] and b["pieces"] and len(a["pieces"]) + len(b["pieces"]) == len(ann["pieces"])
    assert all(i.endswith("_a") for i in a["pieces"]) and all(i.endswith("_b") for i in b["pieces"])
    # Deux entrées : les deux logements sont entiers.
    entrees = [o for o in geo["niveaux"][0]["ouvertures"] if o["sous_type"] == "porte_entree"]
    assert len(entrees) == 2
    assert geo["connectivite"]["connexe"] is False  # c'est vrai : on ne passe pas d'un logement à l'autre


def test_trait_13_les_portes_donnent_sur_le_palier():
    # Une porte sur le bon côté dès que le logement peut en présenter une : toutes les symétries sont essayées.
    bons = 0
    for g in (26, 60, 53, 60012, 2, 7):
        log = generer(g, Reglages())
        for dehors in (1, -1):
            c, score = L._orienter(log.niveaux[0], dehors, False, random.Random(g))
            faces = [o for o in c.ouvertures if o.sous_type == "porte_entree" and o.mur.vertical and o.mur.dehors == dehors]
            assert bool(faces) == (score == 0)
            bons += score == 0
    assert bons == 12


@pytest.mark.parametrize("graine", [26, 60, 53])
def test_trait_13_mitoyen(tmp_path, monkeypatch, graine):
    l = _lot_compose("deux_logements", "mitoyen", titres_place="")
    r, dossier = _ensemble(tmp_path, monkeypatch, l, graine)
    assert valider_dossier(dossier, Regles.charger(None)).accepte
    geo = json.loads((dossier / "geometrie.json").read_text(encoding="utf-8"))
    n0 = geo["niveaux"][0]
    a, b = geo["blocs"]
    assert geo["disposition"] == "mitoyen"
    assert a["cadre"][2] == pytest.approx(b["cadre"][0])  # les deux murs extérieurs se touchent
    contact = a["cadre"][2]
    for o in n0["ouvertures"]:
        if o["orientation"] != "verticale":
            continue
        x0 = min(q[0] for q in o["polygone"])
        x1 = max(q[0] for q in o["polygone"])
        assert not (abs(x1 - contact) < 1e-6 or abs(x0 - contact) < 1e-6), o["id"]  # ni porte ni fenêtre au contact
    # Deux éléments différents, une même classe.
    masques, ann = _lire(dossier)
    murs_a = [m for m in ann["murs"] if m["id"].endswith("_a")]
    murs_b = [m for m in ann["murs"] if m["id"].endswith("_b")]
    assert murs_a and murs_b and not {m["valeur_masque"] for m in murs_a} & {m["valeur_masque"] for m in murs_b}
    assert {m["classe"] for m in murs_a + murs_b} == {CLASSES["mur"]}
    assert len(n0["pieces"]) == len(a["pieces"]) + len(b["pieces"])


def test_trait_13_mitoyen_en_biais_aucune_fenetre_contre_le_voisin():
    # Graine 1039 : le cadre arrondi par un mur en biais laissait 1 mm entre « == contact » et le mur : la fenêtre restait.
    from moteur.generateur.annotations import rect_du_mur
    from moteur.generateur.biais import couper_angles
    reglages, regles = Reglages.charger(None), Regles()
    opt = Options(dossier=None, lot2=True, biais=True)
    log = generer(1039, reglages)
    couper_angles(log, random.Random("biais-1039"))
    rc = random.Random("revue-1039-True-deux_logements-mitoyen")
    b = E.second_logement(1039, opt, reglages, regles, rc)
    c = L.composer(log, b, "deux_logements", "mitoyen", style_pour(1039, 0, opt), rc)
    assert c.disposition == "mitoyen"
    n = c.log.niveaux[0]
    murs = {s: [m for m in n.murs if m.id.endswith(s)] for s in ("_a", "_b")}
    for o in n.ouvertures:
        ro = rect_de_l_ouverture(o)
        for m in murs["_b" if o.id.endswith("_a") else "_a"]:
            rm = rect_du_mur(m)
            ecart_x, ecart_y = max(rm.x0 - ro.x1, ro.x0 - rm.x1), max(rm.y0 - ro.y1, ro.y0 - rm.y1)
            assert not (ecart_x <= 2 and ecart_y < 0), (o.id, m.id)


def test_ensemble_sans_cartouche_ni_epaisseur_fausse(tmp_path, monkeypatch):
    # Deux logements, deux épaisseurs : le cartouche écrivait celles du premier, geometrie.json aussi (`dataclasses.replace`).
    style = _base(cartouche=True, titre=True)
    log, log_b = generer(26, Reglages()), generer(60, Reglages())
    L.appliquer(style, _lot_compose("deux_logements", "palier"))
    style.cartouche = True
    L.vers_ensemble(style, L.composer(log, log_b, "deux_logements", "palier", style, random.Random(1)))
    assert style.cartouche is False and style.titre is False
    # Chaque valeur de parametres, si elle est là, doit être vraie pour tous les murs.
    faux_b = dataclasses.replace(log, ep_ext=log.ep_ext + 100, ep_cloison=log.ep_cloison, ep_porteur=log.ep_porteur)
    parametres = {"graine": 26, "epaisseur_murs_exterieurs": 0.2, "epaisseur_cloisons": 0.07, "epaisseur_murs_porteurs": 0.2}
    assert L.parametres_vrais(parametres, log, faux_b) == {"graine": 26, "epaisseur_cloisons": 0.07, "epaisseur_murs_porteurs": 0.2}
    assert L.parametres_vrais(parametres, log, None) == parametres  # un duplex : un seul logement
    # De bout en bout, sur la graine où l'écart a été vu.
    _, dossier = _ensemble(tmp_path, monkeypatch, _lot_compose("deux_logements", "palier"), 70193)
    geo = json.loads((dossier / "geometrie.json").read_text(encoding="utf-8"))
    p = geo["parametres"]
    epaisseurs = {m["epaisseur"] for m in geo["niveaux"][0]["murs"] if m["exterieur"]}
    assert len(epaisseurs) >= 2 and "epaisseur_murs_exterieurs" not in p  # ces deux logements n'ont pas la même
    # Duplex : tout est vrai, on garde.
    _, dossier = _ensemble(tmp_path / "duplex", monkeypatch, _lot_compose("niveaux", "empiles"), 62)
    geo = json.loads((dossier / "geometrie.json").read_text(encoding="utf-8"))
    assert {m["epaisseur"] for m in geo["niveaux"][0]["murs"] if m["exterieur"]} == {geo["parametres"]["epaisseur_murs_exterieurs"]}


def test_trait_13_sur_un_plan_en_biais(tmp_path, monkeypatch):
    # Les symétries doivent aussi retourner les murs en biais et les coins coupés, sinon le masque les trahirait.
    for disposition in ("palier", "mitoyen"):
        l = _lot_compose("deux_logements", disposition, titres_place="")
        _, dossier = _ensemble(tmp_path / disposition, monkeypatch, l, 101, biais=True)
        assert valider_dossier(dossier, Regles.charger(None)).accepte
        geo = json.loads((dossier / "geometrie.json").read_text(encoding="utf-8"))
        assert any(m["orientation"] in ("oblique", "arrondi") for m in geo["niveaux"][0]["murs"])
    # Un exemple valide ne prouve rien pour les pans coupés : le validateur relit le polygone du mur, retourné ou non. Ce contrôle
    # regarde les contours des pièces, retournés à part : le pan coupé doit rester contre le coin qu'il ferme.
    from moteur.generateur.biais import couper_angles
    log = generer(101, Reglages())
    couper_angles(log, random.Random("biais-101"))
    n = log.niveaux[0]
    assert n.murs_libres
    for k in range(8):
        c = L.copy.deepcopy(n)
        L._symetrie(c, k)
        L._normaliser(c)
        _pans_contre_leur_piece(c)
    log_b = generer(60, Reglages())
    style = _base()
    L.appliquer(style, _lot_compose("deux_logements", "palier"))
    assemble = L.composer(log, log_b, "deux_logements", "palier", style, random.Random(1)).log
    _pans_contre_leur_piece(assemble.niveaux[0])


def _pans_contre_leur_piece(niv) -> None:
    def distance(q, a, b) -> float:
        ax, ay, bx, by = *a, *b
        carre = (bx - ax) ** 2 + (by - ay) ** 2
        t = max(0.0, min(1.0, ((q[0] - ax) * (bx - ax) + (q[1] - ay) * (by - ay)) / carre)) if carre else 0.0
        return math.dist(q, (ax + t * (bx - ax), ay + t * (by - ay)))

    bords = [(c[i], c[(i + 1) % len(c)]) for c in (p.contour for p in niv.pieces if p.contour) for i in range(len(c))]
    assert bords
    for m in niv.murs_libres:
        centre = (sum(q[0] for q in m.polygone) / len(m.polygone), sum(q[1] for q in m.polygone) / len(m.polygone))
        for q in (*m.axe, centre):  # l'axe et le polygone : l'un pourrait suivre sans l'autre
            assert min(distance(q, a, b) for a, b in bords) <= m.epaisseur, (m.id, q)


def test_symetrie_garde_les_surfaces():
    import random as _r
    from moteur.generateur.biais import couper_angles
    log = generer(101, Reglages())
    couper_angles(log, _r.Random("biais-101"))
    n = log.niveaux[0]
    s0 = sorted(round(surface_piece(p)) for p in n.pieces)
    m0 = sorted(rect_du_mur_surface(m) for m in n.murs)
    for k in range(8):
        c = L.copy.deepcopy(n)
        L._symetrie(c, k)
        assert sorted(round(surface_piece(p)) for p in c.pieces) == s0, k
        assert sorted(rect_du_mur_surface(m) for m in c.murs) == m0, k
        for p in c.pieces:  # le contour reste dans le cadre de sa pièce
            for x, y in (p.contour or []):
                assert p.rect.x0 - 1 <= x <= p.rect.x1 + 1 and p.rect.y0 - 1 <= y <= p.rect.y1 + 1


def rect_du_mur_surface(m) -> int:
    from moteur.generateur.annotations import rect_du_mur
    return rect_du_mur(m).surface


def test_graine_b_deterministe():
    a = E.second_logement(26, Options(dossier=None), Reglages(), Regles.charger(None), random.Random("lot2-compose-26"))
    b = E.second_logement(26, Options(dossier=None), Reglages(), Regles.charger(None), random.Random("lot2-compose-26"))
    assert a.graine == b.graine and a.graine >= 1_000_000 and not a.duplex
    assert a.surface == b.surface


def test_composition_impossible_le_manifeste_le_dit(tmp_path, monkeypatch):
    # Point 7 de la conception : le second logement est refusé, pas d'exemple -ensemble, et le manifeste le dit.
    vrai = E.generer

    def faux(graine, reglages):
        if graine >= 1_000_000:
            raise RuntimeError("refusé")
        return vrai(graine, reglages)
    monkeypatch.setattr(E, "generer", faux)
    l = _lot_compose("deux_logements", "palier")
    r, dossier = _ensemble(tmp_path, monkeypatch, l, 26)
    assert not dossier.exists()
    m = json.loads((tmp_path / "exemples" / "000026" / "manifeste.json").read_text(encoding="utf-8"))
    assert m["compose"] is False and m["compose_motif"]
    assert r.statut == "accepte"  # le plan lui-même n'y perd rien


def test_composition_trop_d_elements_refusee(tmp_path, monkeypatch):
    # Un masque d'éléments est sur 8 bits : au-delà de 255, les identifiants se replieraient et la vérité serait fausse.
    vrai = L.composer

    def gonfle(*a, **k):
        c = vrai(*a, **k)
        n = c.log.niveaux[0]
        n.ouvertures = n.ouvertures * 40
        return c
    monkeypatch.setattr(E, "composer", gonfle)
    r, dossier = _ensemble(tmp_path, monkeypatch, _lot_compose("deux_logements", "palier"), 26)
    assert not dossier.exists()
    assert r.entree_manifeste["compose"] is False and "8 bits" in r.entree_manifeste["compose_motif"]


def _jeu_compose(tmp_path, monkeypatch, nombre=8):
    l = _lot_compose("deux_logements", "palier")
    monkeypatch.setattr(E, "lot2_au_hasard", lambda rng: l)
    bilan = generer_lot(Options(dossier=tmp_path, nombre=nombre, depart=300, lot2=True, reprise=False), processus=1)
    assert bilan["statuts"]["rejete"] == 0 and bilan["statuts"]["accepte"] >= 4
    assert list((tmp_path / "exemples").glob("*-ensemble"))
    return bilan


def test_repartir_ensemble_dans_la_partition_du_parent(tmp_path, monkeypatch):
    _jeu_compose(tmp_path, monkeypatch)
    r = E.repartir(tmp_path, (0.5, 0.25, 0.25))
    partition = {i: p for p, ids in r["partitions"].items() for i in ids}
    ensembles = [d.name for d in (tmp_path / "exemples").glob("*-ensemble")]
    assert ensembles
    for i in ensembles:
        assert partition[i] == partition[i.replace("-ensemble", "")], i  # aucune fuite entre entraînement et test
    assert sum(r["comptes"].values()) == len(partition)
    assert sum(sum(c.values()) for c in r["familles"].values()) == len(partition) - len(ensembles)  # les familles ne comptent que les logements


def test_repartir_suit_le_parent_deplace(tmp_path, monkeypatch):
    # Parent déplacé vers l'entraînement car trop semblable : son ensemble le suit, sinon il resterait seul au test et le test
    # noterait des pièces déjà apprises (une fuite d'entraînement). On impose la paire semblable : sinon, selon les graines, aucun
    # parent ne bouge et le test ne prouve rien. Pas de dessin : seul `repartir` est en cause, sur un manifeste écrit à la main.
    from moteur.generateur import doublons
    exemples = []
    for k in range(1, 13):
        ident = f"{k:06d}"
        (tmp_path / "exemples" / ident).mkdir(parents=True)
        (tmp_path / "exemples" / ident / "manifeste.json").write_text(json.dumps({"empreinte": f"e{k}", "signature": {}}), encoding="utf-8")
        exemples += [{"id": ident, "accepte": True, "famille": "f"}, {"id": f"{ident}-ensemble", "accepte": True, "famille": "f", "parent": ident}]
    (tmp_path / "manifest.json").write_text(json.dumps({"exemples": exemples}), encoding="utf-8")
    monkeypatch.setattr(doublons, "chercher", lambda entrees, seuil: {"doublons_exacts": [], "trop_semblables": []})
    avant = E.repartir(tmp_path, (0.5, 0.25, 0.25))
    parent = next(i for i in avant["partitions"]["test"] if not i.endswith("-ensemble"))
    autre = next(i for i in avant["partitions"]["train"] if not i.endswith("-ensemble"))
    assert f"{parent}-ensemble" in avant["partitions"]["test"]
    monkeypatch.setattr(doublons, "chercher", lambda entrees, seuil: {"doublons_exacts": [], "trop_semblables": [{"ids": [parent, autre]}]})
    r = E.repartir(tmp_path, (0.5, 0.25, 0.25))
    assert r["deplaces_vers_train"] == [parent]
    assert parent in r["partitions"]["train"] and f"{parent}-ensemble" in r["partitions"]["train"]
    partition = {i: p for p, ids in r["partitions"].items() for i in ids}
    for e in exemples:
        if "parent" in e:
            assert partition[e["id"]] == partition[e["parent"]], e["id"]


def test_repartir_ensemble_d_un_parent_rejete_reste_dehors(tmp_path, monkeypatch):
    _jeu_compose(tmp_path, monkeypatch)
    ens = sorted((tmp_path / "exemples").glob("*-ensemble"))[0]
    parent = ens.name.replace("-ensemble", "")
    m = json.loads((tmp_path / "exemples" / parent / "manifeste.json").read_text(encoding="utf-8"))
    m["accepte"] = False
    (tmp_path / "exemples" / parent / "manifeste.json").write_text(json.dumps(m), encoding="utf-8")
    E.ecrire_manifeste(tmp_path)
    r = E.repartir(tmp_path, (0.5, 0.25, 0.25))
    tous = {i for ids in r["partitions"].values() for i in ids}
    assert parent not in tous and ens.name not in tous


def test_les_ensembles_ne_faussent_ni_statistiques_ni_doublons(tmp_path, monkeypatch, capsys):
    from moteur.generateur import statistiques
    from moteur.generateur.__main__ import main
    _jeu_compose(tmp_path, monkeypatch)
    parents = [d for d in (tmp_path / "exemples").glob("*/") if not d.name.endswith("-ensemble")]
    ensembles = list((tmp_path / "exemples").glob("*-ensemble"))
    E.repartir(tmp_path)
    stats = statistiques.ecrire(tmp_path)
    assert stats["exemples"] == len(parents)  # un ensemble n'est pas un logement de plus
    assert sum(stats["types"].values()) == len(parents)
    assert stats["ensembles"]["nombre"] == len(ensembles) and stats["ensembles"]["acceptes"] == len(ensembles)
    # Les mêmes chiffres qu'un jeu sans les ensembles : aucun type de pièce n'est compté deux fois.
    total = sum(json.loads((d / "geometrie.json").read_text(encoding="utf-8"))["resume"]["nombre_pieces"] for d in parents)
    assert sum(stats["pieces_par_type"].values()) == total
    main(["doublons", str(tmp_path)])
    rapport = json.loads((tmp_path / "rapports" / "doublons.json").read_text(encoding="utf-8"))
    assert rapport["nombre"] == len(parents)
    main(["valider", str(tmp_path)])
    m = json.loads((ensembles[0] / "manifeste.json").read_text(encoding="utf-8"))
    assert m["accepte"] is True and m["parent"]  # revérifié, sans perdre sa filiation
    from moteur.generateur.controle_qualite import page
    assert page(tmp_path, 40).exists()


def test_le_chargeur_voit_les_ensembles(tmp_path, monkeypatch):
    # Même lecture que entrainer.lire_partitions et entrainer.dessins, sans importer torch ici : la vraie vérification
    # s'est faite une fois avec le vrai chargeur (voir docs/projet/etapes/lot2-conception.md).
    _jeu_compose(tmp_path, monkeypatch)
    r = E.repartir(tmp_path)
    ids = [str(i).zfill(6) if str(i).isdigit() else str(i) for lst in r["partitions"].values() for i in lst]
    ensembles = [i for i in ids if i.endswith("-ensemble")]
    assert ensembles
    for i in ensembles:
        niveaux = sorted((tmp_path / "exemples" / i).glob("niveau_*"))
        assert [n.name for n in niveaux] == ["niveau_0"]
        assert any((niveaux[0] / f).exists() for f in ("plan.png", "plan.jpg"))
        assert (niveaux[0] / "masque_semantique.png").exists()


def test_anciens_jeux_sans_ensemble(tmp_path):
    bilan = generer_lot(Options(dossier=tmp_path, nombre=4, depart=60, reprise=False), processus=1)
    assert not list((tmp_path / "exemples").glob("*-ensemble"))
    assert "ensembles" not in bilan
    for m in (tmp_path / "exemples").glob("*/manifeste.json"):
        e = json.loads(m.read_text(encoding="utf-8"))
        assert "compose" not in e and "parent" not in e
    assert "ensembles" not in json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))


def test_la_part_des_ensembles_ressemble_aux_vrais_plans():
    tirages = [L.lot2_au_hasard(random.Random(k)) for k in range(4000)]
    niveaux = sum(l.composition == "niveaux" for l in tirages) / 4000
    deux = sum(l.composition == "deux_logements" for l in tirages) / 4000
    assert 0.28 < niveaux < 0.38 and 0.015 < deux < 0.05


# ---------------------------------------------------------------- chantier 3 : trait 10, la page vue à l'écran


def _photo_ecran(graine: int, ecran: bool):
    style = style_pour(graine, 0, Options(dossier=None, photo_realiste=True, vraie_camera=True, familles=["photo"]))
    r = style.realisme
    assert r is not None
    r.table, r.teinte_table, r.ecran = "bois", (150, 105, 65), ecran
    r.plis, r.ombre_main, r.reflet, r.flou_bord, r.bouge, r.bruit = "", 0.0, 0.0, 0.0, 0, 1.0
    style.salissure = ""
    log = generer(graine, Reglages())
    return rendre(log, log.niveaux[0], style)


def test_trait_10_realiste_sans_table():
    # Ce qui entoure la page : texturé sur une table, presque uni à l'écran. Les masques ne voient aucune différence.
    avec, sans = _photo_ecran(40002, True), _photo_ecran(40002, False)
    for nom in MASQUES:
        assert np.array_equal(avec.images[nom], sans.images[nom]), nom

    def coins(rendu):
        i = cv2.cvtColor(rendu.images["plan"], cv2.COLOR_RGB2GRAY).astype(np.float32)
        return [i[:10, :10].std(), i[:10, -10:].std(), i[-10:, :10].std(), i[-10:, -10:].std()]
    assert np.median(coins(avec)) < 6
    assert np.median(coins(avec)) < np.median(coins(sans))


def test_trait_10_le_tirage_passe_par_appliquer():
    style = style_pour(40002, 0, Options(dossier=None, photo_realiste=True, vraie_camera=True, familles=["photo"]))
    l = L.Lot2(ecran=True)
    L.appliquer(style, l)
    assert style.realisme.ecran is True
    style2 = style_pour(40002, 0, Options(dossier=None, photo_realiste=True, vraie_camera=True, familles=["photo"]))
    l2 = L.Lot2(ecran_si_photo=True)
    L.appliquer(style2, l2)
    assert style2.realisme.ecran is True and l2.ecran is True
    style3 = _base()
    l3 = L.Lot2(ecran_si_photo=True)
    L.appliquer(style3, l3)
    assert l3.ecran is False  # sans vraie photo, ce tirage-là ne vaut rien


def test_trait_10_absent_du_json_sans_lui():
    from moteur.generateur.photo import Realisme
    assert "ecran" not in Realisme().en_dict()
    assert Realisme(ecran=True).en_dict()["ecran"] is True
    s = Style(realisme=Realisme())
    assert "ecran" not in s.en_dict()["realisme"]
    assert Style(realisme=Realisme(ecran=True)).en_dict()["realisme"]["ecran"] is True
    # Le chemin de la vraie table n'a pas bougé pour les anciens jeux.
    from moteur.generateur.photo import realisme_au_hasard
    assert realisme_au_hasard(random.Random(1)).ecran is False


def test_trait_10_bord_dans_les_marges_seulement():
    h, w = 400, 600
    image = np.full((h, w, 3), 240, np.uint8)
    sem = np.zeros((h, w), np.uint8)
    sem[60:340, 80:520] = 1
    noir_vu = False
    for k in range(30):
        l = L.Lot2(ecran=True, ecran_bordure=True)
        sortie = L.ecran_pixels(image, sem, l, random.Random(k))
        assert sortie.shape == image.shape
        assert sortie[60:340, 80:520].min() > 40  # jamais sur le logement
        noir_vu = noir_vu or sortie.min() < 20
    assert noir_vu


def test_trait_10_sans_bord_aucun_noir():
    image = np.full((400, 600, 3), 240, np.uint8)
    sortie = L.ecran_pixels(image, np.ones((400, 600), np.uint8), L.Lot2(ecran=True), random.Random(4))
    assert sortie.min() > 60


def test_trait_10_masques_inchanges_et_page_grise():
    l = L.Lot2(famille="neutre")
    L._tirer_ecran_force(l, random.Random(5))
    l.rotation, l.ecran_bordure = None, True
    avec, reference, style, _ = _rendus(60002, l)
    _verite_inchangee(avec, reference, _masques_du(style))
    assert style.papier < 255 and style.salissure in ("grain", "telephone")
    assert avec.images["plan"][avec.images["masque_semantique"] == CLASSES["sejour"]].mean() < 250  # un papier gris, pas un blanc de page propre


def test_trait_10_penche_sous_la_page_sage():
    l = L.Lot2(famille="neutre")
    L._tirer_ecran_force(l, random.Random(1))
    l.rotation = 3.0
    style = _base()
    L.appliquer(style, l)
    assert style.rotation == 3.0  # la page sage retire la pente du style de base, pas celle de ce trait


def test_trait_10_plan_et_plan_sans_mobilier_meme_ecran():
    l = L.Lot2(famille="neutre", ecran=True, ecran_bordure=True)
    style = _base(mobilier=True)
    L.appliquer(style, l)
    style.mobilier = True
    log = generer(60002, Reglages())
    rendu = rendre(log, log.niveaux[0], style)
    # Le bord noir de l'écran est le même dans les deux images.
    assert np.array_equal(rendu.images["plan"] < 20, rendu.images["plan_sans_mobilier"] < 20)


def test_palier_ecrit_dans_le_vide(monkeypatch):
    ecrits = []
    vrai = R._Dessin.texte
    monkeypatch.setattr(R._Dessin, "texte", lambda self, xy, texte, *a, **k: (ecrits.append((texte, xy)), vrai(self, xy, texte, *a, **k))[1])
    log, log_b = generer(26, Reglages()), generer(60, Reglages())
    style = _base()
    L.appliquer(style, _lot_compose("deux_logements", "palier"))
    style.noms = True
    c = L.composer(log, log_b, "deux_logements", "palier", style, random.Random(1))
    L.vers_ensemble(style, c)
    style.lot2.palier["texte"] = "Palier"
    rendu = rendre(c.log, c.log.niveaux[0], style, "ensemble")
    x, y = next(xy for t, xy in ecrits if t == "Palier")
    assert rendu.images["masque_semantique"][int(y), int(x)] == 0
    assert np.any(rendu.images["plan"][int(y) - 8:int(y) + 8, int(x) - 8:int(x) + 8] < 200)  # il est bien dessiné


def test_trait_10_famille_tiree():
    tirages = [L.lot2_au_hasard(random.Random(k)) for k in range(2000)]
    part = sum(l.ecran for l in tirages) / 2000
    assert 0.03 < part < 0.09
    assert not any(l.ecran and l.recadre for l in tirages)  # le bord de l'écran a besoin de marges


# ---------------------------------------------------------------- chantier 3 : de bout en bout


@pytest.mark.parametrize("compose,disposition", [("niveaux", "empiles"), ("deux_logements", "palier"), ("deux_logements", "mitoyen")])
@pytest.mark.parametrize("options", [
    {"styles_monde": True}, {"biais": True}, {"photo_realiste": True, "vraie_camera": True, "familles": ["photo"]}, {"sans_cotes": True},
], ids=["monde", "biais", "photo", "sans_cotes"])
def test_combinaisons_avec_composition(tmp_path, monkeypatch, compose, disposition, options):
    vrai = L.lot2_au_hasard

    def tirer(rng):
        l = vrai(rng)
        l.composition, l.disposition = compose, disposition
        return l
    monkeypatch.setattr(E, "lot2_au_hasard", tirer)
    monkeypatch.setattr(E, "PLAIN_PIED_EMPILE", 1.0)
    r = fabriquer_exemple(26, Options(dossier=tmp_path, lot2=True, reprise=False, **options), Reglages(), Regles.charger(None))
    assert r.statut == "accepte", r.erreurs
    d = tmp_path / "exemples" / "000026-ensemble"
    assert valider_dossier(d, Regles.charger(None)).accepte


def test_sans_cotes_gagne_aussi_sur_l_ensemble(monkeypatch):
    ecrits = []
    vrai = R._Dessin.texte
    monkeypatch.setattr(R._Dessin, "texte", lambda self, xy, texte, *a, **k: (ecrits.append(texte), vrai(self, xy, texte, *a, **k))[1])
    log, log_b = generer(26, Reglages()), generer(60, Reglages())
    style = _base(surfaces=False, cotes=False, cotes_partielles=False)
    L.appliquer(style, _lot_compose("deux_logements", "palier", famille="promoteur_gris"), sans_cotes=True)
    c = L.composer(log, log_b, "deux_logements", "palier", style, random.Random(1))
    L.vers_ensemble(style, c)
    style.lot2.titres_place, style.lot2.titre_surface = "haut", True
    rendre(c.log, c.log.niveaux[0], style, "ensemble")
    assert ecrits
    for texte in ecrits:
        assert "m²" not in texte and not texte.replace(",", "").isdigit() or len(texte) <= 2, texte


def test_version():
    assert VERSION_GENERATEUR == "0.1.6"


def test_lot_lot2(tmp_path):
    # La contrainte de bout en bout : 0 rejeté, et chaque exemple comme chaque -ensemble passe le validateur.
    bilan = generer_lot(Options(dossier=tmp_path, nombre=12, depart=1, lot2=True, variantes=1, diversite=3, reprise=False), processus=1)
    assert bilan["statuts"]["rejete"] == 0 and bilan["statuts"]["echec"] <= 2
    assert bilan["ensembles"]["rejetes"] == 0
    dossiers = list((tmp_path / "exemples").glob("*/"))
    assert any(d.name.endswith("-ensemble") for d in dossiers), "aucun exemple -ensemble sur ces graines"
    for d in dossiers:
        assert valider_dossier(d, Regles.charger(None)).accepte, d.name
    manifeste = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifeste["ensembles"] == sum(d.name.endswith("-ensemble") for d in dossiers)
    assert manifeste["acceptes"] == manifeste["nombre"]
