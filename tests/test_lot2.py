"""Lot 2 du générateur (--lot2), chantiers 1 et 2 : chaque trait est dessiné, et la vérité ne bouge pas.

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


def test_le_chantier_3_n_est_pas_encore_tire():
    for k in range(300):
        l = L.lot2_au_hasard(random.Random(k))
        assert not (l.composition or l.ecran or l.disposition)


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
                        assert L._longe_un_mur(m, pieces[pid].rect), (graine, pid)
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


def test_trait_3_cotes_en_cm_dans_les_pieces():
    avec, reference, style, _ = _rendus(60002, _promoteur())
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


def test_trait_6_cotes_par_mur_sans_chaines():
    avec, reference, style, _ = _rendus(60002, _logiciel())
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


def test_trait_18_extérieur_ne_recouvre_rien():
    for graine in (26, 60, 60012, 2, 7):
        log = generer(graine, Reglages())
        for cote in ("bas", "droite"):
            style = _appliquee(L.Lot2(famille="neutre", exterieurs=[_exterieur(cote=cote, part=0.9, profondeur_m=2.4)]))
            rep = Repere(_cadre_des_murs(log.niveaux[0]), style, random.Random(0), nb_pieces=len(log.niveaux[0].pieces))
            d = R._Dessin(log, log.niveaux[0], style, rep, {}, True)
            for _, r in L.places_des_exterieurs(d):
                for p in log.niveaux[0].pieces:
                    z = p.rect
                    assert r.x1 <= z.x0 + 1 or z.x1 <= r.x0 + 1 or r.y1 <= z.y0 + 1 or z.y1 <= r.y0 + 1


def test_trait_18_sur_un_plan_en_biais():
    # Aucun extérieur sur un pan coupé, et la vérité reste celle du logement coupé.
    avec, reference, _, log = _rendus(101, L.Lot2(famille="neutre", exterieurs=[_exterieur(cote="droite", part=0.9), _exterieur(cote="bas", part=0.9)]), biais=True)
    assert log.niveaux[0].murs_libres
    _verite_inchangee(avec, reference)


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
