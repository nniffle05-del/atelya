"""La hauteur sous plafond estimée d'après les photos (moteur/hauteur_photos.py) et les jointures de la suite de la chaîne."""
import sys
from pathlib import Path

import numpy as np

from moteur import hauteur_photos as hp

RACINE = Path(__file__).resolve().parents[1]


def _mesure(sol: float | None, plafond: float | None, n: int = 60) -> dict:
    """Une photo fabriquée : un sol et un plafond horizontaux (appareil droit, « haut » = −y), plus un mur vertical."""
    haut = np.array([0.0, -1.0, 0.0])
    points, normales = [], []
    xs, zs = np.meshgrid(np.linspace(-2, 2, n), np.linspace(1, 5, n))
    for h in (sol, plafond):
        if h is None:
            continue
        points.append(np.stack([xs, np.full_like(xs, -h), zs], -1))  # hauteur h au-dessus de l'appareil → y = −h
        normales.append(np.broadcast_to(haut if h < 0 else -haut, (n, n, 3)))
    ys, zs2 = np.meshgrid(np.linspace(-1, 1, n), np.linspace(1, 5, n))
    points.append(np.stack([np.full_like(ys, 2.0), ys, zs2], -1))
    normales.append(np.broadcast_to(np.array([-1.0, 0.0, 0.0]), (n, n, 3)))
    P, N = np.concatenate(points).astype(np.float32), np.concatenate(normales).astype(np.float32)
    return {"points": P, "normales": N, "masque": np.ones(P.shape[:2], bool), "haut": haut}


def test_hauteur_d_une_photo_sol_et_plafond_visibles():
    v = hp.hauteur_d_une_photo(_mesure(sol=-1.4, plafond=1.3))
    assert v is not None and abs(v - 2.7) < 0.03


def test_hauteur_d_une_photo_sans_plafond():
    assert hp.hauteur_d_une_photo(_mesure(sol=-1.4, plafond=None)) is None


def test_estimer_prend_la_mediane_et_ecarte_l_invraisemblable(monkeypatch):
    import moteur.caler_photos as cp

    fabriquees = {"a": _mesure(-1.4, 1.3), "b": _mesure(-1.5, 1.25), "c": _mesure(-1.3, 1.36), "d": _mesure(-1.0, 0.6),
                  "e": _mesure(-1.4, None)}
    monkeypatch.setattr(cp, "mesurer", lambda modele, rgb, focale_px=None: fabriquees[rgb])
    r = hp.estimer({k: k for k in fabriquees}, modele_moge=object())
    assert r["hauteur"] == 2.7  # médiane de 2,70 / 2,75 / 2,66 ; « d » (1,60 m) invraisemblable, « e » sans plafond
    assert r["gardees"] == 3 and r["photos"]["e"] is None


def test_estimer_trop_peu_de_photos(monkeypatch):
    import moteur.caler_photos as cp

    fabriquees = {"a": _mesure(-1.4, 1.3), "b": _mesure(-1.5, 1.25)}
    monkeypatch.setattr(cp, "mesurer", lambda modele, rgb, focale_px=None: fabriquees[rgb])
    assert hp.estimer({k: k for k in fabriquees}, modele_moge=object())["hauteur"] is None


def test_nom_sans_accent_pour_unreal():
    sys.path.insert(0, str(RACINE / "outils" / "atelya"))
    import de_l_ecran_au_film as chaine

    assert chaine.nom_sans_accent("app-004") == "app004"
    assert chaine.nom_sans_accent("séjour_été 2") == "sjourt2"
