r"""ESSAI « LE SOL PRÉLEVÉ SUR LA PHOTO » (18/11/2026, NT : « j'aimerais juste que ça soit vraiment le même parquet que sur la
photo […] l'éclairage, pour moi, ça rajoute vraiment de la réalité »).

Au lieu de redessiner un parquet avec un autre bois, on PREND le sol de la photo du client : le sol est redressé (vu de dessus,
dans le sens du motif), le plus grand morceau propre est découpé, sa lumière est égalisée en douceur (sinon chaque répétition
montrerait la même tache claire), il est recadré pour se répéter sans couture, et il devient l'image du sol de la maquette.
La couleur est celle de la photo, rapportée au blanc des murs de la même photo.

    ..\atelya\.venv\Scripts\python.exe pc\essais-sol-photo\sol_de_la_photo.py <logement.json> <fiche des caméras> <sortie>
        <pièce> <sens en degrés> <dossier de la matière> [--photos photo-01 photo-03] [--zones lames|sans]

Écrit <dossier de la matière>/couleur.jpg, relief.jpg, brillance.jpg, fiche.json (format d'un parquet sur mesure) et, dans
<sortie>, une image de contrôle (le morceau prélevé, puis l'image répétée 2 × 2 : on y voit les coutures s'il y en a).
ESSAI : rien de branché dans la chaîne.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import parquet_photo as pp, pas_du_sol  # noqa: E402
from moteur.blanc_des_murs import blanc_des_murs  # noqa: E402
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.images import ecrire_image, lire_image  # noqa: E402
from moteur.sol_a_plat import dans_polygone, piece_de_l_appareil  # noqa: E402

RES = 0.003  # 3 mm de sol par pixel
LUMIERE_M = 0.35  # la lumière est égalisée à cette échelle (plus large que 3 lames : les nuances des lames restent)
FONDU_PX = 10  # largeur du fondu aux coutures
BLANC_PEINTURE = 0.86


def plus_grand_rectangle(masque: np.ndarray, pas: int = 4):
    """Le plus grand rectangle entièrement dans le masque (cherché sur une grille de `pas` pixels) : (ligne, colonne, h, w)."""
    m = cv2.erode(masque.astype(np.uint8), np.ones((pas, pas), np.uint8))[::pas, ::pas] > 0
    hauteurs = np.zeros(m.shape[1], int)
    meilleur = (0, 0, 0, 0, 0)
    for i in range(m.shape[0]):
        hauteurs = np.where(m[i], hauteurs + 1, 0)
        pile = []
        for j, h in enumerate(list(hauteurs) + [0]):
            debut = j
            while pile and pile[-1][1] >= h:
                d, hh = pile.pop()
                # on préfère un morceau pas trop allongé : l'aire, limitée à un rapport de 1 pour 3
                w_ = j - d
                aire = min(hh, 3 * w_) * min(w_, 3 * hh)
                if aire > meilleur[0]:
                    meilleur = (aire, i - hh + 1, d, hh, w_)
                debut = d
            pile.append((debut, h))
    _, l, c, h, w = meilleur
    return l * pas, c * pas, h * pas, w * pas


def lineaire(c):
    c = c.astype(np.float32) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def en_image(c):
    c = np.clip(c, 0.0, 1.0)
    return (np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055) * 255 + 0.5).astype(np.uint8)


def meilleure_coupe(gris: np.ndarray, axe: int, mini: float) -> int:
    """Où couper le morceau le long de `axe` pour qu'il se répète le mieux : la longueur h (≥ mini × la longueur) pour laquelle
    la bande qui commence en h ressemble le plus à la bande du début (elle tombe sur une période du motif)."""
    g = gris if axe == 0 else gris.T
    n = g.shape[0]
    b = FONDU_PX
    debut = g[:b]
    meilleur, cout_min = n - b, np.inf
    for h in range(int(mini * n), n - b + 1):
        cout = float(np.abs(g[h:h + b] - debut).mean())
        if cout < cout_min:
            meilleur, cout_min = h, cout
    return meilleur


def raccorder(image: np.ndarray, h: int, axe: int) -> np.ndarray:
    """Le morceau coupé à h le long de `axe`, son début fondu avec ce qui suivait la coupe : il se répète sans couture."""
    im = image if axe == 0 else image.transpose(1, 0, 2)
    b = FONDU_PX
    sortie = im[:h].copy()
    poids = np.linspace(1.0, 0.0, b, dtype=np.float32).reshape(b, 1, 1)
    sortie[:b] = im[h:h + b] * poids + im[:b] * (1 - poids)
    return sortie if axe == 0 else sortie.transpose(1, 0, 2)


def egaliser(image: np.ndarray, ok: np.ndarray) -> np.ndarray:
    """La lumière du sol égalisée en douceur (reflet d'une fenêtre, ombre douce), en ne comptant que les points de parquet ;
    la couleur moyenne est gardée. Rend la lumière (0-1) ; les points hors du parquet ne veulent rien dire."""
    lum = lineaire(image)
    poids = ok.astype(np.float32)
    sigma = LUMIERE_M / RES
    somme = cv2.GaussianBlur(lum * poids[..., None], (0, 0), sigma)
    compte = cv2.GaussianBlur(poids, (0, 0), sigma)
    douce = somme / np.maximum(compte, 1e-3)[..., None]
    moyenne = np.median(lum[ok], 0)
    return (lum / np.maximum(douce, 1e-4) * moyenne).astype(np.float32)


def recolter_les_lames(plat: np.ndarray, ok: np.ndarray, largeur_m: float) -> list[np.ndarray]:
    """Les vraies lames du sol, récoltées rang par rang : par bandes de sol (redressées une à une, comme pour la mesure), chaque
    rang entre deux longs joints donne un ruban de parquet, gardé là où il est entièrement vu. Rubans à la hauteur d'une lame."""
    from moteur.reconnaitre_sols import lab

    largeur_px = largeur_m / RES
    h_lame = int(round(largeur_px))
    couleur_du_bois = np.median(lab(en_image(plat[ok])), 0)
    clarte = np.log(np.maximum(plat @ np.array([0.2126, 0.7152, 0.0722], np.float32), 1e-3)).astype(np.float32)
    fl, ft = int(1.5 / RES), int(0.9 / RES)
    H, W = ok.shape
    rubans = []
    for ligne in range(0, max(1, H - ft + 1), ft):
        for colonne in range(0, max(1, W - fl + 1), fl):
            zone = (slice(ligne, min(H, ligne + ft)), slice(colonne, min(W, colonne + fl)))
            if ok[zone].mean() < 0.25:
                continue
            r = pp._redresser_bande(clarte[zone], ok[zone])
            if r is None:
                continue
            penche, _, m, profil, _ = r
            droit = pp._pencher(plat[zone], penche)
            joints = pp._rangs(profil, largeur_px)
            for haut, bas in zip(joints[:-1], joints[1:]):
                l0, l1 = int(round(haut)), int(round(bas))
                if l1 - l0 < 0.7 * largeur_px or l1 > m.shape[0]:
                    continue
                plein = m[l0:l1].mean(0) > 0.97  # colonnes où tout le rang est du parquet vu
                # les plus longs morceaux d'un seul tenant
                bords = np.flatnonzero(np.diff(np.concatenate([[0], plein.astype(np.int8), [0]])))
                for d, f in zip(bords[::2], bords[1::2]):
                    if (f - d) * RES < 0.35:
                        continue
                    # pas un ruban où passe autre chose que du bois (pied de tabouret, logo de l'annonce, reflet brûlé)
                    ecart = np.linalg.norm(lab(en_image(droit[l0:l1, d:f])) - couleur_du_bois, axis=-1)
                    if (ecart > 20).mean() <= 0.03:
                        rubans.append(cv2.resize(droit[l0:l1, d:f], (f - d, h_lame), interpolation=cv2.INTER_AREA))
    return rubans


def assembler_le_parquet(rubans: list[np.ndarray], cote_m: float, graine: int = 5) -> np.ndarray:
    """Un grand parquet fait des lames récoltées : chaque rang est une suite de rubans mis bout à bout (un fin joint sombre
    là où deux rubans se touchent), décalés d'un rang à l'autre ; il se répète sans couture."""
    alea = np.random.default_rng(graine)
    h_lame = rubans[0].shape[0]
    rangs = max(4, int(round(cote_m / RES / h_lame)))
    cote = int(round(cote_m / RES))
    sortie = np.zeros((rangs * h_lame, cote, 3), np.float32)
    ordre = []
    for rang in range(rangs):
        x, depart = 0, int(alea.integers(0, cote))
        while x < cote:
            if not ordre:
                ordre = list(alea.permutation(len(rubans)))
            ruban = rubans[ordre.pop()]
            if alea.random() < 0.5:
                ruban = ruban[:, ::-1]
            if alea.random() < 0.5:
                ruban = ruban[::-1]
            n = min(ruban.shape[1], cote - x)
            if cote - x - n < 0.3 / RES:  # pas de bout de lame de moins de 30 cm à la fin du rang
                n = min(ruban.shape[1], cote - x) if ruban.shape[1] >= cote - x else n
            colonnes = (depart + x + np.arange(n)) % cote
            morceau = ruban[:, :n].copy()
            morceau[:, 0] *= 0.55  # le bout de la lame : un joint fin
            sortie[rang * h_lame:(rang + 1) * h_lame, colonnes] = morceau
            x += n
    return sortie


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("logement", type=Path)
    ap.add_argument("fiche", type=Path)
    ap.add_argument("sortie", type=Path)
    ap.add_argument("piece")
    ap.add_argument("sens", type=float)
    ap.add_argument("matiere", type=Path)
    ap.add_argument("--photos", nargs="*")
    ap.add_argument("--zones", choices=("lames", "sans"), default="sans", help="lames : le sol des zones à parquet sur mesure ; sans : la pièce hors de ses zones")
    ap.add_argument("--cas", default="app-001")
    ap.add_argument("--lames", type=float, help="largeur des lames (m) : le parquet est fait des vraies lames récoltées une à une")
    a = ap.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    logement = json.loads(a.logement.read_text(encoding="utf-8"))
    logement = logement.get("logement", logement)
    fiche = json.loads(a.fiche.read_text(encoding="utf-8"))
    piece = next(p for p in logement["pieces"] if p["id"] == a.piece)
    zones = piece.get("zones_sol", [])
    choisies = [z["contour"] for z in zones if (a.zones == "sans" or z["sol"].get("parquet"))]

    def garder(X, Y):
        dans = np.zeros(np.shape(X), bool)
        for c in choisies:
            dans |= dans_polygone(X, Y, c)
        return dans if a.zones == "lames" else ~dans

    pds = pas_du_sol.charger(avec_dino=False)
    meilleur, rubans, blancs = None, [], []
    for nom, d in fiche["cameras"].items():
        if a.photos and nom not in a.photos:
            continue
        cam = camera_depuis_dict(d["camera"])
        p, point = piece_de_l_appareil(cam, logement["pieces"])
        if p is None or p["id"] != a.piece:
            continue
        rgb = cv2.cvtColor(lire_image(RACINE / fiche["photos"] / fiche.get("fichier", "{nom}.png").format(nom=nom)), cv2.COLOR_BGR2RGB)
        masque = pds.masque(f"{a.cas}/{nom}", rgb)
        image, vu = pp.sol_dans_le_sens(rgb, cam, piece["contour"], a.sens, masque, point, resolution=RES, finesse_min=1.2,
                                        garder=garder if choisies else None)
        # du parquet, même délavé par un reflet (la lumière est égalisée ensuite), mais pas brûlé au blanc
        propre = pp.bois_vu(image, vu) & (image.max(-1) < 250)
        propre = cv2.morphologyEx(propre.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)) > 0  # petits trous bouchés
        propre &= vu
        if propre.sum() * RES ** 2 < 0.3:
            continue
        blanc = blanc_des_murs(rgb, cam, logement, p, point)
        if a.lames:
            plat = egaliser(image, propre)
            if blanc is not None:
                plat = plat / max(float(np.max(blanc["blanc"])), 1e-4) * BLANC_PEINTURE
                blancs.append(nom)
            recolte = recolter_les_lames(plat, propre, a.lames)
            print(f"{nom} : {len(recolte)} rubans de lames récoltés, {sum(r.shape[1] for r in recolte) * RES:.1f} m en tout", flush=True)
            rubans += recolte
            continue
        l, c, h, w = plus_grand_rectangle(propre)
        print(f"{nom} : plus grand morceau propre {h * RES:.2f} m × {w * RES:.2f} m", flush=True)
        if h * RES < 0.40 or w * RES < 0.40:
            continue
        if meilleur is None or h * w > meilleur[0]:
            meilleur = (h * w, nom, image[l:l + h, c:c + w].copy(), None if blanc is None else np.asarray(blanc["blanc"], np.float32))
    if a.lames:
        if len(rubans) < 6:
            print("PLANTÉ : trop peu de lames récoltées sur ces photos")
            return 1
        plat = np.clip(assembler_le_parquet(rubans, min(2.4, max(1.2, 0.25 * sum(r.shape[1] for r in rubans) * RES))), 0, 1)
        h, w = plat.shape[:2]
        nom = "+".join(blancs) or "photos"
        return ecrire_matiere(a, plat, h, w, nom)
    if meilleur is None:
        print("PLANTÉ : aucun morceau de sol propre assez grand sur ces photos")
        return 1
    _, nom, morceau, blanc = meilleur
    ecrire_image(a.sortie / f"{a.matiere.name}-morceau-{nom}.jpg", cv2.cvtColor(morceau, cv2.COLOR_RGB2BGR))
    # 1. la lumière : égalisée en douceur (le reflet d'une fenêtre, l'ombre douce d'un meuble), la couleur moyenne gardée
    lum = lineaire(morceau)
    sigma = LUMIERE_M / RES
    douce = cv2.GaussianBlur(lum, (0, 0), sigma, borderType=cv2.BORDER_REFLECT)
    moyenne = np.median(lum.reshape(-1, 3), 0)
    plat = lum / np.maximum(douce, 1e-4) * moyenne
    # 2. la couleur : celle de la photo, rapportée au blanc des murs de la même photo (un mur blanc = la peinture de la maquette)
    if blanc is not None:
        plat = plat / max(float(blanc.max()), 1e-4) * BLANC_PEINTURE
    plat = np.clip(plat, 0, 1).astype(np.float32)
    # 3. la répétition : coupé là où le motif se répète le mieux, dans les deux sens, coutures fondues
    gris = plat @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    h = meilleure_coupe(gris, 0, 0.6)
    plat = raccorder(plat, h, 0)
    w = meilleure_coupe(plat @ np.array([0.2126, 0.7152, 0.0722], np.float32), 1, 0.6)
    plat = raccorder(plat, w, 1)
    return ecrire_matiere(a, plat, h, w, nom)


def ecrire_matiere(a, plat: np.ndarray, h: int, w: int, nom: str) -> int:
    """Écrit la matière (couleur, relief plat, brillance satinée, fiche) et l'aperçu répété 2 × 2."""
    # 4. agrandi à 1,2 mm par pixel, un peu raffermi
    k = 2.5
    grand = cv2.resize(plat, (int(round(plat.shape[1] * k)), int(round(plat.shape[0] * k))), interpolation=cv2.INTER_LANCZOS4)
    grand = np.clip(grand + 0.6 * (grand - cv2.GaussianBlur(grand, (0, 0), 2.0)), 0, 1)
    couleur = en_image(grand)
    # lames (ou rangs) de HAUT EN BAS de l'image, comme les parquets sur mesure
    couleur = np.ascontiguousarray(np.rot90(couleur, 1))
    a.matiere.mkdir(parents=True, exist_ok=True)
    ecrire_image(a.matiere / "couleur.jpg", cv2.cvtColor(couleur, cv2.COLOR_RGB2BGR))
    plat_n = np.zeros_like(couleur)
    plat_n[...] = (255, 128, 128)  # BGR d'une normale « à plat » (128, 128, 255 en RGB)
    ecrire_image(a.matiere / "relief.jpg", plat_n)
    ecrire_image(a.matiere / "brillance.jpg", np.full(couleur.shape[:2], int(0.78 * 255), np.uint8))
    travers_m, long_m = round(h * RES, 4), round(w * RES, 4)
    (a.matiere / "fiche.json").write_text(json.dumps({
        "description": f"sol prélevé sur la photo {nom} du client (essai)", "source": f"photo {nom}, sol redressé puis rendu répétable",
        "identifiant": a.matiere.name, "licence": "photo du client", "auteurs": ["Atelya"], "taille_image_m": [travers_m, long_m],
        "parquet": None}, ensure_ascii=False, indent=1), encoding="utf-8")
    apercu = np.tile(np.rot90(couleur, -1), (2, 2, 1))
    apercu = cv2.resize(apercu, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    ecrire_image(a.sortie / f"{a.matiere.name}-repete-2x2.jpg", cv2.cvtColor(apercu, cv2.COLOR_RGB2BGR))
    print(f"{a.matiere.name} : pris sur {nom}, image de {travers_m} m (en travers) × {long_m} m (le long), dans {a.matiere}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
