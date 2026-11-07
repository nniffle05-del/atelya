"""Lot 2 du générateur (--lot2), chantier 1 : chaque trait est dessiné, et la vérité ne bouge pas.

La référence d'un test est le même plan dessiné SANS le lot 2, à la même échelle et avec les mêmes marges : c'est
l'ancien chemin de code. Si un trait touchait un masque, la comparaison le verrait.
"""
import dataclasses
import json
import random

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
        masques = MASQUES if not style.lot2.mobilier_fixes else MASQUES[:3]  # les meubles écartés changent la carte de hauteur
        _verite_inchangee(rendre(log, log.niveaux[0], style), rendre(log, log.niveaux[0], reference), masques)


def test_le_dessin_change():
    log = generer(60003, Reglages())
    sans = rendre(log, log.niveaux[0], style_pour(60003, 0, Options(dossier=None)))
    avec = rendre(log, log.niveaux[0], style_pour(60003, 0, Options(dossier=None, lot2=True)))
    assert sans.images["plan"].shape != avec.images["plan"].shape or not np.array_equal(sans.images["plan"], avec.images["plan"])


def test_tirages_varies():
    tirages = [L.lot2_au_hasard(random.Random(k)) for k in range(400)]
    assert {l.famille for l in tirages} == set(L.POIDS_FAMILLES)
    for attribut in ("dimensions", "etiquettes", "fenetres_pleines", "hsp", "mention_sol", "recadre", "sortie_jpeg", "triangles", "tableau", "sans_noms"):
        assert 0 < sum(bool(getattr(l, attribut)) for l in tirages) < 400, attribut


def test_seuls_les_traits_du_chantier_sont_tires():
    for k in range(200):
        l = L.lot2_au_hasard(random.Random(k))
        assert l.famille in ("agence_coloree", "murs_noirs", "carrez_legende", "cotes_rouges", "neutre")
        assert not (l.cotes_par_mur or l.exterieurs or l.manuscrit or l.composition or l.ecran or l.textes_verticaux)


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
def test_trait_2_dimensions(mode):
    sans, _, _, _ = _rendus(60002, L.Lot2(famille="neutre"))
    avec, reference, _, _ = _rendus(60002, L.Lot2(famille="neutre", dimensions=mode))
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
        masques = MASQUES if not style.lot2.mobilier_fixes else MASQUES[:3]
        _verite_inchangee(avec, rendre(log, log.niveaux[0], reference), masques)
        if options.get("sans_cotes"):
            assert style.cotes is False and style.cotes_partielles is False


def test_sans_cotes_gagne_sur_toutes_les_familles():
    for k in range(120):
        graine = 60000 + k
        sans = style_pour(graine, 0, Options(dossier=None, sans_cotes=True))
        avec = style_pour(graine, 0, Options(dossier=None, sans_cotes=True, lot2=True))
        assert avec.cotes is False and avec.cotes_partielles is False
        assert avec.surfaces == sans.surfaces  # ni rallumées, ni éteintes par une famille


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


def test_pas_de_contour_decale_sur_un_plan_penche():
    # Défaut connu de contour_des_murs : double contour sur les plans penchés.
    style = _base(murs_contour=True, rotation=2.0)
    L.appliquer(style, L.Lot2(famille="neutre"))
    assert style.murs_contour is False
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
