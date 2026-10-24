"""Tests du générateur de plans synthétiques (moteur/generateur) : géométrie reproductible et valide,
masques fidèles aux annotations, duplex cohérents, 3D relisible, lot écrit et réparti correctement."""

import json
import random

import cv2
import numpy as np
import pytest

from moteur.generateur import VERSION_GENERATEUR
from moteur.generateur.annotations import CLASSES, SCHEMA, decrire
from moteur.generateur.doublons import chercher, empreinte, signature
from moteur.generateur.exportateur import Options, generer_lot, repartir
from moteur.generateur.logements import LogementGenere, Rate, en_logement, generer
from moteur.generateur.reglages import Reglages
from moteur.generateur.rendu import rendre
from moteur.generateur.validateur import Regles, valider_dossier, valider_geometrie
from moteur.generateur.variantes import style_au_hasard
from moteur.logement import Logement

GRAINES = range(1, 31)


def _generer_ou_rien(graine: int, reglages: Reglages | None = None) -> LogementGenere | None:
    try:
        return generer(graine, reglages)
    except (Rate, RuntimeError):  # aucun logement habitable pour cette graine
        return None


@pytest.fixture(scope="module")
def logements() -> dict[int, LogementGenere]:
    """Les logements des 30 premières graines (celles qui aboutissent)."""
    faits = {g: _generer_ou_rien(g) for g in GRAINES}
    return {g: log for g, log in faits.items() if log is not None}


# ---------------------------------------------------------------- géométrie


def test_meme_graine_meme_logement():
    assert decrire(generer(3)) == decrire(generer(3))
    assert decrire(generer(3)) != decrire(generer(4))


def test_la_plupart_des_graines_aboutissent(logements):
    assert len(logements) >= 0.8 * len(GRAINES), f"seulement {len(logements)} logements sur {len(GRAINES)} graines"


def test_geometrie_valide_pour_le_validateur(logements):
    for g, log in logements.items():
        v = valider_geometrie(log, decrire(log))
        assert v.accepte, (g, v.erreurs)


def test_pieces_sans_chevauchement_et_dans_le_contour(logements):
    for g, log in logements.items():
        for niveau in log.niveaux:
            rects = [p.rect for p in niveau.pieces]
            cadre = niveau.cadre
            for p in niveau.pieces:
                assert p.rect.largeur > 0 and p.rect.hauteur > 0, (g, p.nom)
                assert cadre.x0 <= p.rect.x0 < p.rect.x1 <= cadre.x1, (g, p.nom)
                assert cadre.y0 <= p.rect.y0 < p.rect.y1 <= cadre.y1, (g, p.nom)
            for i, a in enumerate(rects):
                for b in rects[i + 1:]:
                    assert a.x1 <= b.x0 or b.x1 <= a.x0 or a.y1 <= b.y0 or b.y1 <= a.y0, g


def test_ouvertures_dans_leur_mur(logements):
    for g, log in logements.items():
        for niveau in log.niveaux:
            for o in niveau.ouvertures:
                m = o.mur
                assert m in niveau.murs, (g, o.id)
                assert m.debut <= o.u0 < o.u1 <= m.fin, (g, o.id)
                assert o.hauteur > 0, (g, o.id)
                if o.type == "porte":
                    assert o.allege == 0, (g, o.id)


def test_toutes_les_pieces_sont_reliees(logements):
    for g, log in logements.items():
        geo = decrire(log)
        assert geo["connectivite"]["connexe"] and not geo["connectivite"]["non_atteintes"], (g, geo["connectivite"])


def test_format_logement_de_l_etape_1(logements):
    """Le niveau 0 se relit avec les règles pydantic de l'étape 1 (donc Blender saurait le construire)."""
    for g, log in logements.items():
        Logement.model_validate(en_logement(log, log.niveaux[0]))


def test_description_versionnee(logements):
    g, log = next(iter(logements.items()))
    geo = decrire(log)
    assert geo["schema"] == SCHEMA
    assert geo["version_generateur"] == VERSION_GENERATEUR
    assert geo["unites"] == "m"
    assert set(geo["classes"]) == set(CLASSES.values()) or len(geo["classes"]) == len(set(CLASSES.values()))
    for n in geo["niveaux"]:
        for p in n["pieces"]:
            assert abs(p["surface"] - p["largeur"] * p["profondeur"]) < 0.02, (g, p["id"])


def test_duplex_coherents():
    """Dans un duplex, l'escalier occupe le même rectangle aux deux niveaux et seul le bas a une porte d'entrée."""
    r = Reglages({"TYPES": {"studio": 0, "chambre": 0, "T1": 0, "T2": 0, "T3": 1, "T4": 1, "T5": 0},
                  "DUPLEX": {"T3": 1.0, "T4": 1.0}})
    duplex = [log for log in (_generer_ou_rien(g, r) for g in range(1, 9)) if log]
    assert len(duplex) >= 4 and all(log.duplex for log in duplex)
    for log in duplex:
        assert len(log.niveaux) == 2
        bas = [p for p in log.niveaux[0].pieces if p.sorte == "escalier"]
        haut = [p for p in log.niveaux[1].pieces if p.sorte == "escalier"]
        assert len(bas) == 1 and len(haut) == 1, log.graine
        assert bas[0].rect == haut[0].rect, log.graine
        assert any(o.sous_type == "porte_entree" for o in log.niveaux[0].ouvertures), log.graine
        assert not any(o.sous_type == "porte_entree" for o in log.niveaux[1].ouvertures), log.graine
        assert log.niveaux[1].z_sol > log.niveaux[0].z_sol
    # Même sans mobilier, l'escalier est dessiné et ses marches montent dans la carte de hauteur.
    log = duplex[0]
    style = style_au_hasard(random.Random(1), diversite=0)
    style.mobilier = False
    rendu = rendre(log, log.niveaux[0], style)
    escalier = next(p for p in rendu.annotations["pieces"] if p["classe"] == CLASSES["escalier"])
    hauteurs = rendu.images["hauteur"][rendu.images["masque_pieces"] == escalier["valeur_masque"]]
    assert hauteurs.min() < 400 and hauteurs.max() >= 1000, log.graine  # première marche en bas, plan de coupe en haut
    assert any(m["type"] == "escalier" for m in rendu.annotations["mobilier"])


def test_reglages_surcharges():
    """Un réglage JSON change vraiment la fabrication : ici, uniquement des T2."""
    r = Reglages({"TYPES": {"studio": 0, "chambre": 0, "T1": 0, "T2": 1, "T3": 0, "T4": 0, "T5": 0}})
    types = {log.type for log in (_generer_ou_rien(g, r) for g in range(1, 15)) if log}
    assert types == {"T2"}
    with pytest.raises(KeyError):
        Reglages({"REGLAGE_INEXISTANT": 1})
    assert json.loads(json.dumps(r.en_dict()))["TYPES"]["T2"] == 1


# ---------------------------------------------------------------- rendu et masques


def test_masques_fideles_aux_annotations(logements):
    """Chaque pièce, mur et ouverture du masque couvre la même aire que son polygone annoté."""
    for g in list(logements)[:6]:
        log = logements[g]
        niveau = log.niveaux[0]
        style = style_au_hasard(random.Random(g), diversite=0)
        rendu = rendre(log, niveau, style)
        ann = rendu.annotations
        sem, pieces_m, elements = rendu.images["masque_semantique"], rendu.images["masque_pieces"], rendu.images["masque_elements"]
        assert sem.shape == pieces_m.shape == elements.shape == rendu.images["hauteur"].shape
        assert rendu.images["plan"].shape[:2] == sem.shape
        for p in ann["pieces"]:
            aire = cv2.contourArea(np.array(p["polygone_px"], np.float32))
            compte = int((pieces_m == p["valeur_masque"]).sum())
            assert abs(compte - aire) <= max(60, 0.06 * aire), (g, p["id"], compte, aire)
            assert (sem[pieces_m == p["valeur_masque"]] == p["classe"]).all(), (g, p["id"])
        for o in ann["ouvertures"]:
            aire = cv2.contourArea(np.array(o["polygone_px"], np.float32))
            compte = int((elements == o["valeur_masque"]).sum())
            assert abs(compte - aire) <= max(40, 0.15 * aire), (g, o["id"], compte, aire)
            assert (sem[elements == o["valeur_masque"]] == o["classe"]).all(), (g, o["id"])
        murs_px = int((sem == CLASSES["mur"]).sum())
        assert murs_px > 0
        # la carte de hauteur : plafond sur les murs, 0 au sol nu des pièces sans mobilier
        hauteur = rendu.images["hauteur"]
        hsp_mm = round(niveau.hsp)
        assert hauteur[sem == CLASSES["mur"]].max() == hsp_mm, g
        assert hauteur[sem == 0].max() == 0, g


def test_rotation_annotations_toujours_alignees():
    """Un plan tourné et déformé (style photo) : les polygones annotés tombent sur le masque."""
    log = generer(2)
    style = style_au_hasard(random.Random(2), diversite=3, famille="photo")
    assert style.rotation or style.perspective
    rendu = rendre(log, log.niveaux[0], style)
    H = np.array(rendu.annotations["image"]["matrice_m_vers_px"])
    pieces_m = rendu.images["masque_pieces"]
    for p in rendu.annotations["pieces"]:
        poly = np.array(p["polygone_px"], np.float32)
        cx, cy = poly.mean(axis=0)
        assert pieces_m[int(round(cy)), int(round(cx))] == p["valeur_masque"], p["id"]
    # la matrice annoncée est bien celle qui a servi : un coin du cadre tombe dans l'image
    cadre = log.niveaux[0].cadre
    u, v, w = H @ (cadre.x0 / 1000, cadre.y0 / 1000, 1)
    assert 0 <= u / w <= pieces_m.shape[1] and 0 <= v / w <= pieces_m.shape[0]


def test_meme_style_meme_image():
    log = generer(5)
    a = rendre(log, log.niveaux[0], style_au_hasard(random.Random(5), 2))
    b = rendre(log, log.niveaux[0], style_au_hasard(random.Random(5), 2))
    assert np.array_equal(a.images["plan"], b.images["plan"])
    assert a.annotations == b.annotations


# ---------------------------------------------------------------- 3D


def test_modele_3d_relisible(tmp_path):
    from moteur.generateur.modele3d import briques_du_logement, ecrire_glb, ecrire_obj, emprise_des_murs, lire_glb
    from moteur.generateur.validateur import _aire
    log = generer(5)
    briques = briques_du_logement(log)
    bilan = ecrire_glb(log, tmp_path / "m.glb", briques)
    ecrire_obj(log, tmp_path / "m.obj", briques)
    assert (tmp_path / "m.glb").stat().st_size > 1000
    assert (tmp_path / "m.obj").exists() and (tmp_path / "materiaux.mtl").exists()
    relu = lire_glb(tmp_path / "m.glb")  # relu depuis les octets : en-tête, JSON et bloc binaire cohérents
    assert len(relu["nodes"]) == bilan["noeuds"] > 0 and bilan["triangles"] > 0 and relu["meshes"]
    # l'emprise au sol des murs 3D (niveau 0) est celle des polygones 2D, moins les passages et les angles
    # comptés deux fois par les murs extérieurs, à 3 % près (le même calcul que le validateur)
    n0 = decrire(log)["niveaux"][0]
    emprise_2d = sum(_aire(m["polygone"]) for m in n0["murs"]) - sum(
        _aire(o["polygone"]) for o in n0["ouvertures"] if o["type"] != "fenetre" or o["allege"] == 0)
    emprise_2d -= len([m for m in n0["murs"] if m["exterieur"]]) * log.ep_ext ** 2 / 1e6
    assert abs(emprise_des_murs(briques) - emprise_2d) <= 0.03 * emprise_2d


# ---------------------------------------------------------------- doublons


def test_empreinte_et_doublons(logements):
    ids = list(logements)[:5]
    empreintes = {g: empreinte(logements[g]) for g in ids}
    assert len(set(empreintes.values())) == len(ids)
    assert empreinte(generer(ids[0])) == empreintes[ids[0]]
    entrees = [{"id": str(g), "empreinte": empreintes[g], "signature": signature(logements[g], decrire(logements[g])).en_dict()}
               for g in ids]
    entrees.append(dict(entrees[0], id="copie"))
    rapport = chercher(entrees)
    assert rapport["doublons_exacts"] == [[str(ids[0]), "copie"]]
    assert {"ids": [str(ids[0]), "copie"], "distance": 0.0} in rapport["trop_semblables"]


# ---------------------------------------------------------------- le lot complet


@pytest.fixture(scope="module")
def lot(tmp_path_factory):
    dossier = tmp_path_factory.mktemp("jeu")
    opt = Options(dossier=dossier, nombre=8, depart=1, variantes=1, modele_3d=True, masques_par_classe=True, diversite=3)
    bilan = generer_lot(opt, processus=1)
    return dossier, opt, bilan


def test_lot_ecrit_et_valide(lot):
    dossier, opt, bilan = lot
    assert bilan["acceptes_dans_le_manifeste"] >= 6, bilan
    assert bilan["statuts"]["rejete"] == 0, bilan
    manifeste = json.loads((dossier / "manifest.json").read_text(encoding="utf-8"))
    assert manifeste["version_generateur"] == VERSION_GENERATEUR and manifeste["schema"].startswith("manifest-")
    assert all(e["version_generateur"] == VERSION_GENERATEUR for e in manifeste["exemples"])
    assert (dossier / "reglages.json").exists() and (dossier / "journal.log").exists()
    for e in manifeste["exemples"]:
        d = dossier / "exemples" / e["id"]
        for nom in ("geometrie.json", "logement_niveau0.json", "validation.json", "manifeste.json",
                    "construction.json", "modele.glb", "modele.obj", "materiaux.mtl"):
            assert (d / nom).exists(), (e["id"], nom)
        for niveau in range(e["nombre_niveaux"]):
            dn = d / f"niveau_{niveau}"
            assert (dn / "plan.png").exists() or (dn / "plan.jpg").exists(), e["id"]
            for nom in ("masque_semantique.png", "masque_pieces.png", "masque_elements.png", "contours.png", "hauteur.png",
                        "annotations.json"):
                assert (dn / nom).exists(), (e["id"], nom)
            assert (dn / "variante_1" / "annotations.json").exists()
            assert list((dn / "classes").glob("*.png"))
            hauteur = cv2.imread(str(dn / "hauteur.png"), cv2.IMREAD_UNCHANGED)
            assert hauteur.dtype == np.uint16
        for f in e["fichiers"]:
            assert (d / f).exists(), (e["id"], f)
        # la revérification depuis les fichiers seuls donne le même verdict
        v = valider_dossier(d, Regles())
        assert v.accepte, (e["id"], v.erreurs)


def test_reprise_sans_refaire(lot):
    dossier, opt, bilan = lot
    bilan2 = generer_lot(opt, processus=1)
    assert bilan2["statuts"]["deja_fait"] == bilan["statuts"]["accepte"]
    assert bilan2["acceptes_dans_le_manifeste"] == bilan["acceptes_dans_le_manifeste"]


def test_repartition_reproductible_et_par_familles(lot):
    dossier, _, _ = lot
    a = repartir(dossier, (0.5, 0.25, 0.25), graine=0)
    b = repartir(dossier, (0.5, 0.25, 0.25), graine=0)
    assert a["partitions"] == b["partitions"]
    assert sum(a["comptes"].values()) == sum(len(v) for v in a["partitions"].values())
    assert set(a["comptes"]) == {"train", "validation", "test"}
    rep = json.loads((dossier / "repartition.json").read_text(encoding="utf-8"))
    assert rep["comptes"] == a["comptes"]


def test_statistiques_et_controle(lot):
    from moteur.generateur import controle_qualite, statistiques
    dossier, _, _ = lot
    stats = statistiques.ecrire(dossier)
    assert stats["acceptes"] >= 6 and stats["taux_acceptation_pct"] == 100.0
    assert (dossier / "rapports" / "statistiques.txt").exists()
    page = controle_qualite.page(dossier, 3)
    assert page.exists() and list((dossier / "rapports" / "planches").glob("*.jpg"))


def test_ligne_de_commande(tmp_path):
    from moteur.generateur.__main__ import main
    main(["generer", "--nombre", "3", "--dossier", str(tmp_path), "--types", "T2,T3", "--familles", "architecte", "--diversite", "0"])
    manifeste = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert all(e["type"] in ("T2", "T3") for e in manifeste["exemples"])
    assert all(e["style"] == "architecte" for e in manifeste["exemples"])
    main(["valider", str(tmp_path)])
    main(["doublons", str(tmp_path)])
    assert (tmp_path / "rapports" / "doublons.json").exists()
