"""Le calcul des nappes de tissu (voilages, rideaux), sans Blender : numpy seul, pour pouvoir le tester hors de Blender.
Importé par rideaux.py (script lu par Blender) ; les tests l'importent comme moteur.blender.tissus.

- `bande` : la bande calculée d'une sorte de tissu (moteur/modeles/rideaux/*.npz, outils/bibliotheque/fabriquer_rideaux.py).
- `nappe` : un pan découpé dans sa bande : les points du tissu (x le long du mur, y distance au mur, z hauteur).
- `passer_devant` (23/11/2026) : un rideau ne passe JAMAIS derrière son voilage. Le voilage pend à 10 cm du mur et le rideau à
  16 cm, mais leurs plis (± 3 et ± 5 cm) se croisaient par endroits, de quelques millimètres : dans le film, des points clairs
  dans le rideau (vus sur les grands rideaux tirés des chambres d'app-001). Là où le voilage arrive à moins de JEU_TISSUS du
  rideau, le pli du rideau est repoussé vers la pièce, de ce qu'il faut seulement.
"""
import zlib
from pathlib import Path

import numpy as np

COLLECTION = Path(__file__).resolve().parents[1] / "modeles" / "rideaux"
# la bande de la collection pour chaque nappe, et la demi-profondeur gardée pour ses plis (les mêmes que moteur/collisions.py :
# PLIS_VOILAGE, PLIS_RIDEAUX ; la bande calculée est plus profonde, on l'aplatit pour que rien ne touche le mur ni un meuble)
BANDES = {"voilage": ("voilage", 0.03), "rideaux": ("rideau_ouvert", 0.05), "rideaux_tires": ("rideau", 0.05)}
JEU_TISSUS = 0.012  # m : le rideau reste au moins à cette distance devant le voilage
_bandes = {}


def bande(sorte):
    """La bande calculée d'une sorte : (points lignes × colonnes × 3, abscisses sur le tissu à plat, hauteur) ; None sans collection."""
    nom = BANDES.get(sorte, (None,))[0]
    if nom not in _bandes:
        chemin = COLLECTION / f"{nom}.npz"
        try:
            d = np.load(str(chemin))
            _bandes[nom] = (d["points"].astype("float32"), d["tissu"].astype("float32"), float(d["hauteur"]))
        except Exception:  # noqa: BLE001 : collection absente ou illisible : l'ancienne surface ondulée
            _bandes[nom] = None
    return _bandes[nom]


def nappe(nom, x0, x1, y, z0, z1, sorte):
    """Un pan découpé dans la bande calculée de sa sorte : de x0 à x1 le long du mur, à la distance y du mur, de z0 à z1.
    L'endroit de la bande dépend du nom du pan (toujours le même pour un même pan, différent d'une fenêtre à l'autre).
    Renvoie {"x", "y", "z" (lignes × colonnes), "u" (abscisse sur le tissu à plat, par colonne)} ; None si la collection manque."""
    b = bande(sorte)
    if b is None:
        return None
    points, tissu, hauteur = b
    tringle = points[0, :, 0]
    largeur, dispo = x1 - x0, float(tringle.max() - tringle.min())
    echelle = max(1.0, largeur / (dispo - 0.02))  # un pan plus large que la bande : étiré (jamais vu : bande de 4 m)
    besoin = largeur / echelle
    depart = float(tringle.min()) + (zlib.crc32(nom.encode("utf-8")) % 1000) / 1000.0 * max(0.0, dispo - besoin)
    cols = np.nonzero((tringle >= depart) & (tringle <= depart + besoin))[0]
    if len(cols) < 4:
        return None
    p = points[:, cols[0]:cols[-1] + 1, :]
    demi = BANDES[sorte][1]
    profondeur = max(float(np.abs(p[..., 1] - np.median(p[..., 1])).max()), 1e-6)
    return {"x": x0 + (p[..., 0] - depart) * echelle,
            "y": y + (p[..., 1] - np.median(p[..., 1])) * min(1.0, demi / profondeur),
            "z": z0 + p[..., 2] * ((z1 - z0) / hauteur),
            "u": (tissu[cols[0]:cols[-1] + 1] - tissu[cols[0]]) * echelle}


def _le_plus_loin_du_mur(derriere, x, z, autour=0.015):
    """Pour chaque point (x, z) : la plus grande distance au mur de la nappe de derrière à cet endroit (dans les deux lignes de
    mailles qui encadrent sa hauteur, et à `autour` près le long du mur) ; −inf là où cette nappe ne pend pas."""
    hauteurs = derriere["z"].mean(axis=1)
    ordre = np.argsort(hauteurs)
    hauteurs = hauteurs[ordre]
    loin = np.full(x.shape, -np.inf, dtype="float64")
    for i in range(x.shape[0]):
        k = int(np.searchsorted(hauteurs, float(z[i].mean())))
        for ligne in {min(max(k - 1, 0), len(ordre) - 1), min(k, len(ordre) - 1)}:
            xs, ys = derriere["x"][ordre[ligne]], derriere["y"][ordre[ligne]]
            rang = np.argsort(xs)
            xs, ys = xs[rang], ys[rang]
            for pas in (-autour, -autour / 2, 0.0, autour / 2, autour):
                ici = x[i] + pas
                loin[i] = np.maximum(loin[i], np.where((ici >= xs[0]) & (ici <= xs[-1]), np.interp(ici, xs, ys), -np.inf))
    return loin


def passer_devant(devant, derriere, jeu=JEU_TISSUS):
    """La nappe `devant` (un rideau) repoussée vers la pièce là où la nappe `derriere` (son voilage) arrive à moins de `jeu`
    d'elle. Change `devant["y"]` sur place ; renvoie le nombre de points déplacés."""
    seuil = _le_plus_loin_du_mur(derriere, devant["x"], devant["z"]) + jeu
    trop_pres = devant["y"] < seuil
    devant["y"] = np.where(trop_pres, seuil, devant["y"]).astype(devant["y"].dtype)
    return int(trop_pres.sum())


def ecart_au_pire(devant, derriere):
    """La plus petite distance (m) entre la nappe de devant et celle de derrière, le long de y, là où les deux pendent
    (négative : elles se traversent) ; None si elles ne se recouvrent pas. Pour les contrôles."""
    loin = _le_plus_loin_du_mur(derriere, devant["x"], devant["z"], autour=0.0)
    ecart = (devant["y"] - loin)[np.isfinite(loin)]
    return float(ecart.min()) if ecart.size else None
