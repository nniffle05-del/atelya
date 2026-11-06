"""Essai 8 : le jeu d'entraînement fabriqué depuis les vérités des vrais plans (outils/atelya/preparer_jeu_vrais.py)."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "outils" / "atelya"))
import preparer_jeu_vrais as pj  # noqa: E402

LARGEUR, HAUTEUR = 200, 150


def fausse_verite(dossier: Path, nom: str) -> None:
    """Un petit « vrai plan » : murs noirs, une porte, deux pièces ; masque aux classes du générateur."""
    d = dossier / nom
    d.mkdir(parents=True)
    img = np.full((HAUTEUR, LARGEUR, 3), 255, np.uint8)
    msq = np.zeros((HAUTEUR, LARGEUR), np.uint8)
    msq[30:120, 40:160] = 5          # séjour
    msq[30:120, 100:160] = 7         # chambre
    for (y0, y1, x0, x1) in ((30, 36, 40, 160), (114, 120, 40, 160), (30, 120, 40, 46), (30, 120, 154, 160), (30, 120, 98, 103)):
        msq[y0:y1, x0:x1] = 1
        img[y0:y1, x0:x1] = 30
    msq[60:80, 98:103] = 2           # porte dans la cloison
    img[60:80, 98:103] = 255
    Image.fromarray(img).save(d / f"{nom}.jpg", quality=92)
    Image.fromarray(msq, mode="L").save(d / "masque_semantique.png")
    (d / "verite.json").write_text(json.dumps({"image": f"{nom}.jpg", "px_par_m": 20.0}), encoding="utf-8")


def repartition(dossier: Path) -> Path:
    f = dossier / "repartition-vrais-plans.json"
    f.write_text(json.dumps({"examen_anciens": ["fr-003"], "examen_nouveaux": ["fr-020"],
                             "entrainement": ["fr-021", "fr-022", "fr-023"]}), encoding="utf-8")
    return f


def test_jeu_fabrique_au_format_entrainer(tmp_path):
    verites = tmp_path / "verites"
    for nom in ("fr-021", "fr-022"):
        fausse_verite(verites, nom)
    fausse_verite(verites, "fr-020")  # plan d'examen glissé là par erreur
    sortie = tmp_path / "jeu"
    m = pj.fabriquer_jeu(verites, repartition(tmp_path), sortie, variantes=3, controle=0, silencieux=True)
    assert m["refuses_examen"] == ["fr-020"]
    assert sorted(m["plans_appris"]) == ["fr-021", "fr-022"] and m["plans_controle"] == []
    rep = json.loads((sortie / "repartition.json").read_text(encoding="utf-8"))
    assert rep["schema"] == "repartition/1.0"
    assert sorted(rep["partitions"]["train"]) == [f"fr-02{p}-v0{k}" for p in (1, 2) for k in range(3)]
    assert rep["partitions"]["validation"] == [] and rep["partitions"]["test"] == []
    assert not list((sortie / "exemples").glob("fr-020*"))
    for ident in rep["partitions"]["train"]:
        niv = sortie / "exemples" / ident / "niveau_0"
        img, msq = Image.open(niv / "plan.png"), Image.open(niv / "masque_semantique.png")
        assert img.size == msq.size == (LARGEUR, HAUTEUR)
        a = np.asarray(msq)
        assert msq.mode == "L" and a.max() <= 15
        assert set(np.unique(a)) <= {0, 1, 2, 5, 7}, ident  # NEAREST : aucune classe inventée par le mélange
        assert (a == 1).sum() > 100, ident  # les murs ont survécu à la transformation
        ann = json.loads((niv / "annotations.json").read_text(encoding="utf-8"))
        assert ann["source"] == "vrai plan" and ann["image"] == {"largeur": LARGEUR, "hauteur": HAUTEUR}
        assert ann["plan"] == ident[:6] and ann["variante"] == int(ident[-2:])
    # v00 = l'original ; les variantes changent le dessin.
    orig = np.asarray(Image.open(sortie / "exemples" / "fr-021-v00" / "niveau_0" / "plan.png"))
    v1 = np.asarray(Image.open(sortie / "exemples" / "fr-021-v01" / "niveau_0" / "plan.png"))
    assert not np.array_equal(orig, v1)


def test_controle_garde_l_original_seul(tmp_path):
    verites = tmp_path / "verites"
    for nom in ("fr-021", "fr-022", "fr-023"):
        fausse_verite(verites, nom)
    sortie = tmp_path / "jeu"
    m = pj.fabriquer_jeu(verites, repartition(tmp_path), sortie, variantes=3, controle=1, silencieux=True)
    assert len(m["plans_controle"]) == 1
    c = m["plans_controle"][0]
    rep = json.loads((sortie / "repartition.json").read_text(encoding="utf-8"))
    assert rep["partitions"]["validation"] == [f"{c}-v00"]
    assert len(rep["partitions"]["train"]) == 6 and not any(i.startswith(c) for i in rep["partitions"]["train"])
    assert [p.name for p in (sortie / "exemples").glob(f"{c}-*")] == [f"{c}-v00"]
    # Même tirage d'une fois sur l'autre (graine fixe), et contrôles imposables.
    m2 = pj.fabriquer_jeu(verites, repartition(tmp_path), tmp_path / "jeu2", variantes=2, controle=1, silencieux=True)
    assert m2["plans_controle"] == m["plans_controle"]
    m3 = pj.fabriquer_jeu(verites, repartition(tmp_path), tmp_path / "jeu3", variantes=2, controle=1,
                          controles_imposes=["fr-023"], silencieux=True)
    assert m3["plans_controle"] == ["fr-023"]


def test_recette_deterministe_et_variee():
    msq = np.zeros((HAUTEUR, LARGEUR), np.uint8)
    msq[30:120, 40:160] = 5
    img = np.full((HAUTEUR, LARGEUR, 3), 255, np.uint8)
    a1 = pj.variante(img, msq, "fr-021", 3)
    a2 = pj.variante(img, msq, "fr-021", 3)
    assert a1[2] == a2[2] and np.array_equal(a1[0], a2[0]) and np.array_equal(a1[1], a2[1])
    recettes = [pj.variante(img, msq, "fr-021", k)[2] for k in range(1, 40)]
    assert all(r != pj.Recette() for r in recettes)  # au moins un changement par variante
    assert any(r.rotation_deg for r in recettes) and any(r.echelle != 1.0 for r in recettes)
    assert any(r.coins for r in recettes) and any(r.salissure for r in recettes) and any(r.capture for r in recettes)
    assert all(1.0 <= abs(r.rotation_deg) <= 5.0 for r in recettes if r.rotation_deg)
    assert all(0.6 <= r.echelle <= 1.4 for r in recettes)


def test_un_plan_sans_verite_finie_attend(tmp_path):
    verites = tmp_path / "verites"
    fausse_verite(verites, "fr-021")
    (verites / "fr-022").mkdir()  # dossier commencé, pas de masque
    m = pj.fabriquer_jeu(verites, repartition(tmp_path), tmp_path / "jeu", variantes=2, controle=0, silencieux=True)
    assert m["sans_verite_finie"] == ["fr-022"] and m["plans_appris"] == ["fr-021"]


def test_aucune_verite_arrete(tmp_path):
    verites = tmp_path / "verites"
    fausse_verite(verites, "fr-003")  # examen seulement
    with pytest.raises(SystemExit):
        pj.fabriquer_jeu(verites, repartition(tmp_path), tmp_path / "jeu", variantes=2, controle=0, silencieux=True)


def test_la_vraie_repartition_protege_les_examens():
    rep = pj.lire_repartition(Path(__file__).resolve().parents[1] / "verites" / "repartition-vrais-plans.json")
    examen = pj.plans_d_examen(rep)
    assert {"fr-003", "fr-019", "fr-020", "fr-121"} <= examen
    assert not examen & set(rep["entrainement"])
    assert len(rep["entrainement"]) == 78
