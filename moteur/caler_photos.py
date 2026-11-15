"""Les photos du client CALÉES SEULES : d'où chaque photo a-t-elle été prise ? (14/11/2026)

POURQUOI : les briques « sols » et « meubles » ont besoin de savoir quelle pièce chaque photo montre, et depuis où. Jusqu'ici
cette fiche (`cameras-photos.json`) était relevée à la main. Ici Atelya l'écrit seul, à partir du plan et des photos, et dit
pour chaque photo s'il en est SÛR : seules les photos sûres doivent servir (une photo mal placée mettrait le parquet d'une
chambre dans une autre).

MÉTHODE (mise au point dans pc/essais-cameras-seules, moge1 à moge18) :
 1. chaque photo est mesurée en mètres par MoGe-2 (moteur/moge.py) : à quelle distance est le mur dans chaque direction,
    où sont les creux (portes, fenêtres) ; l'œil DINOv2 + une petite couche apprise reconnaît les fenêtres à leur aspect ;
 2. cette mesure est comparée au plan pour TOUTES les places possibles (une tous les 20 cm, 360 directions) : une note par
    place ; les meubles vus (OWLv2) disent le type de pièce (un lit = une chambre) ;
 3. premier choix photo par photo, toutes ensemble (chaque pièce importante montrée, pas deux photos au même endroit) ;
 4. les photos tombées dans la même pièce sont RECOUPÉES entre elles par Depth Anything 3 (moteur/da3.py) : on sait alors
    où sont les appareils les uns par rapport aux autres, et on pose le BLOC entier sur le plan (un grand morceau de pièce
    se confond bien moins qu'une photo seule) ; une photo qu'aucune autre du groupe ne « revoit » sort du groupe ;
 5. second choix d'ensemble, par blocs ; réglage fin ; « sûre » = l'ensemble perdrait beaucoup si le bloc changeait de pièce.

« SÛRE », règle du 15/11/2026 (version 0.2.0, étape « chambres jumelles ») : trois défauts faisaient dire « sûr » à tort
quand deux pièces se ressemblent (deux chambres jumelles, un séjour et une salle à manger de taille voisine) :
 a. l'échange de deux pièces qui ont chacune leurs photos n'était jamais essayé (un seul bloc déplacé à la fois : la pièce
    d'arrivée étant « prise », l'échange paraissait coûteux) → `marges_d_ensemble` : les autres blocs peuvent bouger aussi ;
 b. les photos de deux pièces tombées dans le même groupe formaient UN bloc, posé d'un coup et « sûr » pour toutes
    → `sous_groupes` : le groupe est coupé en sous-groupes de photos qui se revoient ;
 c. le seuil était le même pour une photo et pour un bloc de cinq → `seuil_sure` : × la racine du nombre de photos.
Mesuré par pc/essais-cameras-seules/jumelles.py (99 rejouements des trois logements : une ou deux photos en moins, plan faux
de 3 à 8 %, zoom des lignes de fuite ; 36 d'entre eux jamais regardés pour régler) : photos sûres et FAUSSES 41 → 3, dont
entre pièces de même sorte 30 → 0, sans perdre de photo sûre en service hors des chambres jumelles d'app-002 (qui n'étaient
justes que par chance : marge d'échange 0,04). Restent : une photo seule de chambre ou de cuisine accrochée au bloc du séjour
par un faux accord « même lieu ». Une photo pas sûre dit avec quelle pièce elle hésite (`hesite_avec`).

LA PIÈCE DONNÉE PAR LE CLIENT (15/11/2026, version 0.3.0, décision NT : le client range chaque photo par pièce au dépôt) :
`caler(..., pieces_donnees=…)`. Atelya ne cherche alors que la place DANS la pièce (ou sur le seuil d'une de ses portes), et
garde son propre avis comme SECOND AVIS (`doute_sur_la_piece_donnee` → « a_verifier »). Mesuré par
pc/essais-cameras-seules/pieces_donnees.py : photos utilisables 23 → 43 sur 45 sur les trois logements ; la place dans les
petites pièces (cuisine, salle d'eau, entrée) reste peu fiable.
EN DEUX TEMPS (NT, 15/11/2026) : le client nomme la pièce ; quand Atelya ne sait pas où ranger la photo, l'écran de
vérification demande d'où elle est prise et NT pointe l'endroit : `caler(..., endroits_donnes=…)`.

Mesuré sur les 22 photos calées à la main d'app-001 et app-002 (examens déjà vus, réglages regardés dessus) : bonne pièce
16/22, à peu près placées (< 1 m, < 15°) 12, bien placées 7 ; photos « sûres » : 15, toutes dans la bonne pièce.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
import torch

from . import da3, fuites, moge
from .oeil_dinov2 import ECART, MOYENNE, charger as charger_oeil, empreintes

VERSION = "0.4.0"
PAS = 0.2                                   # une place possible tous les 20 cm
HAUT_DES_MURS = 2.1                         # au-dessus : ni portes ni meubles, on y mesure la distance du mur
ECHELLES = (0.72, 0.8, 0.88, 0.96, 1.04)    # MoGe-2 voit souvent trop profond : on essaie plusieurs tailles
LIMITES = (0.68, 1.08)
ECHELLES_ZOOM_JUSTE = (0.86, 0.93, 1.0, 1.07, 1.14)  # zoom donné par les lignes de fuite : plus de profondeur à corriger
LIMITES_ZOOM_JUSTE = (0.82, 1.18)
A_FEN, B_FEN, P_SOL = 0.6, 0.2, 0.3         # poids des fenêtres vues / attendues, et du « creux jusqu'au sol »
ECHELLES_BLOC = (0.85, 0.92, 1.0, 1.08, 1.16)
JEU_M, JEU_DEG = 2, 4                       # jeu laissé à chaque photo dans son bloc : cases de 20 cm, degrés
L_TYPE, L_COUV, L_DOUBLE, L_MEME, SEUIL_MEME = 1.0, 0.15, 0.5, 0.4, 0.6
PRINCIPALES = ("sejour", "chambre", "cuisine")
SEUIL_INTRUS = 0.4                          # part d'accord en dessous de laquelle deux photos ne montrent pas le même lieu
SOUS_GROUPES = True                         # groupes coupés en sous-groupes de photos qui se revoient (False = avant le 15/11/2026)
MARGE_D_ENSEMBLE = True                     # « sûre » jugé en laissant les autres blocs bouger (False = avant le 15/11/2026)
SEUIL_PAR_RACINE = True                     # seuil du « sûr » × racine du nombre de photos du bloc (False = avant le 15/11/2026)
MARGE_SURE = 0.4                            # « sûre » : changer de pièce ferait perdre au moins autant (× racine du nombre de photos du bloc)
SENS_POINTE_DEG = 45.0                      # … et, si le sens du regard est indiqué aussi, le cap à 45° près
RAYON_POINTE = 1.0                          # endroit pointé à la vérification : l'appareil est cherché à moins de 1 m du point (1,5 m jusqu'au 16/11/2026 :
                                            # 33 photos pointées à 0,5 m près, à plus de 1 m de la vraie place 8 → 4, écart moyen 0,67 → 0,53 m ; pc/essais-cameras-seules/rayon_pointe.py)
VERS_PORTE_DEG = 50.0                       # … et regarde alors vers cette porte, à 50° près
PORTE_M = 1.2                               # pièce donnée par le client : l'appareil peut être sur le seuil, à moins de 1,2 m d'une de ses portes
MEUBLES_MIN = 0.3                           # pièce donnée : meubles vus qui ne vont pas avec cette sorte de pièce (un lit dans une « cuisine ») → à vérifier
COLLE_MIN = 0.6                             # pièce donnée : en dessous de cette part de sa meilleure note ailleurs, la photo « colle mal » → à vérifier
LOIN_M, TOURNE_DEG = 1.0, 60.0              # « endroit douteux » : une autre place à plus de 1 m, ou le même endroit tourné de plus de 60°
AUTRE_POSE_MIN = 0.95                       # … douteux si une autre pose du bloc, ailleurs dans la pièce, vaut au moins 95 % de la pose choisie
ACCORD_MIN = 0.6                            # … ou si une photo du bloc est à moins de 60 % de sa propre meilleure place
ECART_POINTE = 0.75                         # photo pointée par NT que son bloc met à plus de 75 cm du point : elle se place seule, près du point
PETITES_PIECES = ("cuisine", "salle_d_eau", "entree", "wc", "degagement")  # … et toujours dans ces petites pièces (demande de NT)
CAP_FUITES = 12.0                          # le cap des lignes de fuite remplace celui du calage s'il en est à moins de 12°
MODELE_FENETRES = Path(__file__).resolve().parent / "modeles" / "fenetres-vitb14-v1.npz"


# ================================================================ le plan
def plan_du_logement(logement: dict) -> dict:
    """Le logement en faces vues d'en haut : chaque contour de pièce découpé en murs pleins (sorte 0), portes (1) et
    fenêtres ou baies (2), avec le bas et le haut de chaque ouverture."""
    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    murs = {m["id"]: m for m in logement["murs"]}
    ouv = []
    for o in logement.get("ouvertures", []):
        m = murs.get(o.get("mur"))
        if m is None:
            continue
        a, b = np.array(m["debut"], float), np.array(m["fin"], float)
        L = np.linalg.norm(b - a)
        if L < 1e-6:
            continue
        t = (b - a) / L
        z0 = float(o.get("allege", 0.0) or 0.0)
        ouv.append({"a": a + t * float(o["position"]), "b": a + t * (float(o["position"]) + float(o["largeur"])),
                    "ep": float(m.get("epaisseur", 0.2)), "porte": o["type"] == "porte", "bas": z0,
                    "haut": min(z0 + float(o.get("hauteur", 2.1)), hsp)})
    A, B, sorte, bas, haut, face_piece = [], [], [], [], [], []
    for num, p in enumerate(logement["pieces"]):
        avant = len(A)
        c = np.array(p["contour"], float)
        for i in range(len(c)):
            a, b = c[i], c[(i + 1) % len(c)]
            L = np.linalg.norm(b - a)
            if L < 0.02:
                continue
            t = (b - a) / L
            n = np.array([-t[1], t[0]])
            coupes = []
            for o in ouv:
                d = abs(float((o["a"] - a) @ n))
                if d > o["ep"] / 2 + 0.2 or abs(float((o["b"] - o["a"]) @ t)) < 0.9 * np.linalg.norm(o["b"] - o["a"]):
                    continue
                s0, s1 = sorted((float((o["a"] - a) @ t), float((o["b"] - a) @ t)))
                s0, s1 = max(s0, 0.0), min(s1, L)
                if s1 - s0 > 0.2:
                    coupes.append((s0, s1, o))
            coupes.sort(key=lambda x: x[0])
            cur = 0.0
            for s0, s1, o in coupes:
                if s0 < cur - 1e-6:
                    continue
                if s0 - cur > 0.02:
                    A.append(a + t * cur); B.append(a + t * s0); sorte.append(0); bas.append(0.0); haut.append(hsp)
                A.append(a + t * s0); B.append(a + t * s1); sorte.append(1 if o["porte"] else 2); bas.append(o["bas"]); haut.append(o["haut"])
                cur = s1
            if L - cur > 0.02:
                A.append(a + t * cur); B.append(a + t * L); sorte.append(0); bas.append(0.0); haut.append(hsp)
        face_piece += [num] * (len(A) - avant)
    return {"hsp": hsp, "A": np.array(A), "B": np.array(B), "sorte": np.array(sorte), "bas": np.array(bas), "haut": np.array(haut),
            "face_piece": np.array(face_piece),
            "pieces": [np.array(p["contour"], float) for p in logement["pieces"]], "ids": [p["id"] for p in logement["pieces"]]}


def _dans_poly(P, c):
    x, y = P[:, 0], P[:, 1]
    r = np.zeros(len(P), bool)
    for i in range(len(c)):
        x1, y1 = c[i]; x2, y2 = c[(i + 1) % len(c)]
        cond = (y1 > y) != (y2 > y)
        xi = x1 + (y - y1) * (x2 - x1) / np.where(y2 != y1, y2 - y1, 1.0)
        r ^= cond & (x < xi)
    return r


def piece_de(plan: dict, P: np.ndarray) -> np.ndarray:
    """Numéro de la pièce de chaque point (-1 : hors du logement)."""
    r = np.full(len(P), -1)
    for i, c in enumerate(plan["pieces"]):
        r[_dans_poly(P, c) & (r < 0)] = i
    return r


def _dist_seg(P, A, B):
    e = B - A
    t = np.clip(((P[:, None, :] - A[None]) * e[None]).sum(2) / (e * e).sum(1)[None], 0, 1)
    return np.linalg.norm(P[:, None, :] - (A[None] + t[..., None] * e[None]), axis=2)


def tirs(plan: dict, P: np.ndarray, angles: np.ndarray):
    """De chaque point, dans chaque direction (degrés) : distance du premier mur, sa sorte (0 mur, 1 porte, 2 fenêtre),
    et si l'ouverture touchée a un appui (bas à plus de 40 cm)."""
    D = np.stack([np.cos(np.radians(angles)), np.sin(np.radians(angles))], 1)
    A, B = plan["A"], plan["B"]; e = B - A
    T, S, Ap = [], [], []
    for i in range(0, len(P), 200):
        p = P[i:i + 200]
        ap = A[None] - p[:, None, :]
        den = D[None, :, None, 0] * e[None, None, :, 1] - D[None, :, None, 1] * e[None, None, :, 0]
        ok = np.abs(den) > 1e-9
        den = np.where(ok, den, 1.0)
        t = (ap[:, None, :, 0] * e[None, None, :, 1] - ap[:, None, :, 1] * e[None, None, :, 0]) / den
        s = (ap[:, None, :, 0] * D[None, :, None, 1] - ap[:, None, :, 1] * D[None, :, None, 0]) / den
        t = np.where(ok & (t > 0.03) & (s >= 0) & (s <= 1), t, np.inf)
        j = np.argmin(t, 2)
        T.append(np.take_along_axis(t, j[..., None], 2)[..., 0]); S.append(plan["sorte"][j]); Ap.append(plan["bas"][j] > 0.4)
    return np.concatenate(T), np.concatenate(S), np.concatenate(Ap)


def grille(plan: dict) -> np.ndarray:
    """Les places possibles : un point tous les 20 cm, dans une pièce, pas collé à un mur."""
    c = np.concatenate(plan["pieces"]); x0, y0 = c.min(0); x1, y1 = c.max(0)
    G = np.stack(np.meshgrid(np.arange(x0, x1, PAS), np.arange(y0, y1, PAS)), -1).reshape(-1, 2)
    return G[(piece_de(plan, G) >= 0) & (_dist_seg(G, plan["A"], plan["B"]).min(1) > 0.06)]


def sens_des_murs(plan: dict) -> float:
    """La direction dominante des murs du plan, en degrés entre 0 et 90 (0 = murs le long des axes du plan)."""
    d = plan["B"] - plan["A"]
    a = np.arctan2(d[:, 1], d[:, 0]) * 4  # un mur et son voisin à l'équerre comptent pour la même direction
    w = np.hypot(d[:, 0], d[:, 1])
    return float(np.degrees(np.arctan2((w * np.sin(a)).sum(), (w * np.cos(a)).sum())) / 4 % 90)


def cap_par_fuites(cap: float, fu: dict | None, sens: float) -> float:
    """Le cap trouvé par le calage (au degré près), remplacé par celui des lignes de fuite (au dixième de degré) quand la
    photo en a de nettes et que les deux sont d'accord à CAP_FUITES près (les fuites ne connaissent le cap qu'à 90° près)."""
    if not fu or not fu["oriente"]:
        return cap
    ecart = (fu["alpha"] + sens - cap + 45) % 90 - 45
    return cap + ecart if abs(ecart) <= CAP_FUITES else cap


# ================================================================ la photo
def verticale(normales: np.ndarray, masque: np.ndarray) -> np.ndarray:
    """Le « haut » dans le repère de l'appareil (x droite, y bas, z devant), d'après les surfaces horizontales."""
    n = normales[::4, ::4].reshape(-1, 3)[masque[::4, ::4].ravel()]
    haut = np.array([0.0, -1.0, 0.0])
    for seuil in (0.8, 0.9, 0.96, 0.98):
        s = n[np.abs(n @ haut) > seuil]
        if len(s) < 50:
            break
        s = s * np.sign(s @ haut)[:, None]
        haut = s.mean(0); haut /= np.linalg.norm(haut)
    return haut


def _pic(v, pas=0.02):
    if len(v) < 30:
        return None
    h, b = np.histogram(v, bins=np.arange(v.min(), v.max() + pas, pas))
    h = np.convolve(h, np.ones(3), "same")
    return float(b[h.argmax()] + pas / 2)


def mesurer(modele_moge, rgb: np.ndarray, focale_px: float | None = None) -> dict:
    """MoGe-2 sur une photo : points en mètres, inclinaison des surfaces, zoom (trouvé, ou imposé), et le « haut »."""
    r = moge.lire(modele_moge, rgb, focale_px=focale_px)
    m = {"points": r["points"].astype(np.float32), "normales": r["normales"].astype(np.float32), "masque": r["masque"],
         "focale_px": float(r["focale_px"])}
    m["haut"] = verticale(m["normales"], m["masque"])
    return m


def repere(mes: dict, hsp: float) -> dict | None:
    """Chaque point de la photo dans le repère de la pièce : hauteur au-dessus du sol, direction (degrés, + = à gauche),
    distance à plat ; la taille est recalée sur la hauteur sous plafond quand sol et plafond sont visibles."""
    P, N, M, haut = mes["points"], mes["normales"], mes["masque"], mes["haut"]
    av = np.array([0, 0, 1.0]) - haut * haut[2]; av /= np.linalg.norm(av)
    dr = np.cross(av, haut)
    if dr[0] < 0:
        dr = -dr
    h, a, b = P @ haut, P @ dr, P @ av
    nh = N @ haut
    horiz = M & (np.abs(nh) > 0.95)
    sol, plaf = _pic(h[horiz & (h < -0.4)]), _pic(h[horiz & (h > 0.3)])
    ech = 1.0
    if sol is not None and plaf is not None and 0.75 < hsp / (plaf - sol) < 1.33:
        ech = hsp / (plaf - sol)
    elif sol is None and plaf is None:
        return None
    if sol is None:
        sol = plaf - hsp / ech
    return {"h": (h - sol) * ech, "phi": np.degrees(np.arctan2(-a, b)), "r": np.hypot(a, b) * ech, "M": M,
            "vert": np.abs(nh) < 0.35, "devant": b > 0.2, "ech": ech, "z": -sol * ech}


def _mur_par_direction(R, hsp):
    bande = R["M"] & R["vert"] & R["devant"] & (R["h"] > HAUT_DES_MURS) & (R["h"] < hsp - 0.04)
    if bande.sum() < 1600:
        bande = R["M"] & R["vert"] & R["devant"] & (R["h"] > 1.5) & (R["h"] < hsp - 0.04)
    k = np.round(R["phi"][bande]).astype(int); ray = R["r"][bande]
    mur = {}
    for d in np.unique(k):
        v = ray[k == d]
        if len(v) >= 40:
            mur[int(d)] = float(np.median(v))
    return mur


def profil(mes: dict, hsp: float, fenetres: np.ndarray | None = None) -> dict | None:
    """Ce que la photo dit de la pièce, direction par direction (degrés, 0 = droit devant) : distance du mur, creux vu
    (1 = relief, 2 = fenêtre reconnue à son aspect, 3 = les deux), creux jusqu'au sol (1 oui, -1 non, 0 caché)."""
    R = repere(mes, hsp)
    if R is None:
        return None
    mur = _mur_par_direction(R, hsp)
    if len(mur) < 15:
        return None
    d = np.array(sorted(mur)); v = np.array([mur[i] for i in d])
    rw = np.interp(R["phi"], d, v, left=np.nan, right=np.nan).astype(np.float32)
    rw[np.interp(R["phi"], d[:-1] + 0.5, np.diff(d), left=1, right=1) > 3] = np.nan  # pas de mur mesuré entre deux directions
    rel = R["r"] - rw
    rel[~R["M"]] = np.where(np.isnan(rw[~R["M"]]), np.nan, 9.0)  # pas de mesure = ciel : très loin
    m = (~np.isnan(rel)) & (rel > 0.05) & (R["h"] > 0.05) & (R["h"] < hsp - 0.05)
    kk = max(5, int(R["M"].shape[1] / 80)) | 1
    c = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((kk, kk), np.uint8)) > 0
    k = np.round(R["phi"]).astype(int)
    mesure = ~np.isnan(rel)
    mi = mesure & (R["h"] > 1.0) & (R["h"] < 1.9)
    ba = mesure & (R["h"] > 0.15) & (R["h"] < 0.8) & (rel > -0.12)
    creux, sol = np.zeros(len(d), np.int8), np.zeros(len(d), np.int8)
    fen = None
    if fenetres is not None:
        H, W = R["M"].shape
        fen = cv2.resize(fenetres.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR) > 0.5
        mf = mesure & (R["h"] > 1.0) & (R["h"] < 1.9) & (rel > -0.35)
    for i, deg in enumerate(d):
        col = k == int(deg)
        n = (col & mi).sum()
        if n >= 20 and (col & mi & c).sum() / n > 0.5:
            creux[i] |= 1
        nb = (col & ba).sum()
        if nb >= 20:
            sol[i] = 1 if (col & ba & c).sum() / nb > 0.5 else -1
        if fen is not None:
            nf = (col & mf).sum()
            if nf >= 20 and (col & mf & fen).sum() / nf > 0.5:
                creux[i] |= 2
    return {"phi": d.astype(float), "r": v, "creux": creux, "sol": sol, "z": R["z"], "ech": R["ech"]}


class Fenetres:
    """Fenêtre ou non, pour chaque petit carré de la photo : l'œil DINOv2 ViT-B/14 (figé) + une couche apprise sur les
    fenêtres du plan projetées sur les photos calées à la main d'app-001 et app-002 (pc/essais-cameras-seules/moge19.py)."""
    LARGEUR = 1204

    def __init__(self, chemin: Path = MODELE_FENETRES):
        z = np.load(chemin)
        self.W, self.b, self.mu, self.sd = z["W"], z["b"], z["mu"], z["sd"]

    @staticmethod
    def carres(oeil, rgb: np.ndarray) -> np.ndarray:
        h = int(round(rgb.shape[0] * Fenetres.LARGEUR / rgb.shape[1] / 14)) * 14
        x = (cv2.resize(rgb, (Fenetres.LARGEUR, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0 - MOYENNE) / ECART
        x = torch.from_numpy(x).permute(2, 0, 1)[None].to(next(oeil.parameters()).device)
        with torch.no_grad(), torch.autocast(device_type=x.device.type, enabled=x.device.type == "cuda"):
            _, c = oeil(x)
        return c[0].float().cpu().numpy().reshape(h // 14, Fenetres.LARGEUR // 14, -1)

    def proba(self, carres: np.ndarray) -> np.ndarray:
        s = ((carres - self.mu) / self.sd) @ self.W.T + self.b
        s = np.exp(s - s.max(-1, keepdims=True))
        return (s / s.sum(-1, keepdims=True))[..., 2]


# ================================================================ la note d'une place
def _note(xp, rm, rp, creux, sol, sorte, appui):
    """La photo colle-t-elle au plan vu de cette place ? rm : distances mesurées, rp : distances du plan (dernier axe = les
    directions). xp = numpy ou torch (mêmes opérations)."""
    nombre = (lambda c: c.astype(np.float32)) if xp is np else (lambda c: c.float())
    rp = np.minimum(rp, 40.0) if xp is np else rp.clamp(max=40.0)
    v = xp.exp(-0.5 * ((rm - rp) / (0.10 + 0.04 * rp)) ** 2)
    cr, fen, pf = (creux & 1) > 0, (creux & 2) > 0, sorte == 2
    v = v * (1 - 0.3 * nombre(cr & ~fen & (sorte == 0)))                                             # creux vu, mur plein au plan
    v = v * (1 - P_SOL * nombre(cr & (sorte > 0) & (((sol == 1) & appui) | ((sol == -1) & ~appui))))  # porte contre fenêtre à appui
    base = v.mean(-1)
    nf, npf, les2 = int(fen.sum()), nombre(pf).sum(-1), nombre(fen & pf).sum(-1)
    if nf >= 5:  # la fenêtre VUE doit tomber sur une fenêtre du plan
        base = base * (1 - A_FEN + A_FEN * les2 / nf)
    attendue = nombre(npf >= 5)  # les fenêtres du plan en vue devraient être vues (rideaux : pas toujours)
    return base * (1 - attendue * B_FEN * (1 - les2 / (npf + (npf < 1))))


@torch.no_grad()
def notes_sur_le_plan(tirs_plan, pr: dict, appareil: str, echelles=ECHELLES) -> tuple[np.ndarray, np.ndarray]:
    """Note de la photo pour chaque place de la grille et chaque cap (0 à 359°) : (n, 360), et l'échelle retenue."""
    tour, tsorte, tappui = tirs_plan
    ip = torch.from_numpy(pr["phi"].astype(np.int64)).to(appareil)
    rm = torch.from_numpy(pr["r"].astype(np.float32)).to(appareil)
    creux = torch.from_numpy(pr["creux"].astype(np.int64)).to(appareil); sol = torch.from_numpy(pr["sol"].astype(np.int64)).to(appareil)
    n = tour.shape[0]
    N = torch.zeros((n, 360), device=appareil); E = torch.zeros((n, 360), dtype=torch.uint8, device=appareil)
    lot = max(1, int(2e7 / (n * len(ip))))
    for c0 in range(0, 360, lot):
        idx = (torch.arange(c0, min(360, c0 + lot), device=appareil)[:, None] + ip[None]) % 360
        rp, so, ap = tour[:, idx], tsorte[:, idx], tappui[:, idx]
        for k, e in enumerate(echelles):
            v = _note(torch, rm * e, rp, creux, sol, so, ap)
            mieux = v > N[:, c0:c0 + lot]
            N[:, c0:c0 + lot] = torch.where(mieux, v, N[:, c0:c0 + lot])
            E[:, c0:c0 + lot] = torch.where(mieux, torch.full_like(E[:, c0:c0 + lot], k), E[:, c0:c0 + lot])
    return N.cpu().numpy(), E.cpu().numpy()


def regler(plan: dict, pr: dict, cam: np.ndarray, limites=LIMITES) -> tuple[np.ndarray, float]:
    """Réglage fin d'une place (x, y, cap, échelle) : petits pas tant que la note monte."""
    creux, sol = pr["creux"].astype(np.int64), pr["sol"].astype(np.int64)

    def f(c):
        if piece_de(plan, c[None, :2])[0] < 0:
            return -1.0
        t, s, b = tirs(plan, c[None, :2], c[2] + pr["phi"])
        return float(_note(np, pr["r"] * c[3], t, creux, sol, s, b)[0])
    best, pas = f(cam), np.array([0.1, 0.1, 2.0, 0.03])
    for _ in range(40):
        bouge = False
        for i in range(4):
            for sg in (-1, 1):
                c = cam.copy(); c[i] += sg * pas[i]
                if i == 3 and not limites[0] <= c[3] <= limites[1]:
                    continue
                v = f(c)
                if v > best + 1e-6:
                    best, cam, bouge = v, c, True
        if not bouge:
            pas = pas / 2
            if pas[0] < 0.005:
                break
    return cam, best


# ================================================================ le type de pièce d'après les meubles
def sorte_de_piece(piece: str) -> str:
    return piece.rsplit("_", 1)[0]


def indices_des_meubles(objs: list[dict]) -> dict:
    """Ce que les meubles vus (OWLv2) disent : {type de pièce: facteur} (1 = compatible). Vide = rien de net."""
    m = lambda *noms: max([o["note"] for o in objs if o["nom"] in noms] or [0.0])
    nb = lambda nom, s: sum(o["nom"] == nom and o["note"] >= s for o in objs)
    lit = m("a bed", "a bed with a duvet", "a bunk bed", "a loft bed")
    salon = max(m("a sofa", "a couch"), m("a coffee table"), m("a dining table"))
    cuisine = nb("a cabinet", 0.4) + nb("kitchen cabinets", 0.3) >= 3
    repas = m("a dining table") >= 0.35 or nb("a chair", 0.4) + nb("a stool", 0.4) >= 3
    if lit >= 0.45:
        return {"chambre": 1.0, "sejour": 0.6}
    if salon >= 0.45:
        return {"sejour": 1.0, "chambre": 0.5}
    if repas:
        return {"sejour": 1.0, "cuisine": 0.9, "chambre": 0.3}
    if cuisine:
        return {"cuisine": 1.0, "sejour": 0.8, "entree": 0.6, "degagement": 0.5}
    return {}


def _facteur(f: dict, piece: str) -> float:
    return 1.0 if not f else f.get(sorte_de_piece(piece), 0.25)


# ================================================================ la pièce donnée par le client
def pieces_permises(plan: dict, valeur) -> list[int]:
    """Ce que le client a dit d'une photo → numéros des pièces du plan : un identifiant (« chambre_2 », désignée sur le plan),
    une sorte de pièce (« chambre » : toutes les chambres), ou une liste des deux."""
    v = [valeur] if isinstance(valeur, str) else list(valeur or [])
    return [i for i, q in enumerate(plan["ids"]) if q in v or sorte_de_piece(q) in v]


def pieces_montrees(plan: dict, G: np.ndarray, pg: np.ndarray, permises: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """Pour chaque place de la grille : la pièce (parmi les permises) que montre une photo prise de là, ou -1 ; et, pour chaque
    place et chaque cap (0 à 359°), si la photo peut être prise ainsi. Dans une pièce permise : elle-même, tous les caps ;
    ailleurs, à moins de PORTE_M d'une porte d'une pièce permise : cette pièce, à condition de REGARDER vers cette porte (à
    VERS_PORTE_DEG près) : on photographie souvent une cuisine ou une salle d'eau depuis le seuil, l'appareil encore dans le
    couloir, mais tourné vers elle."""
    hors = ~np.isin(pg, permises)
    r = np.where(hors, -1, pg)
    plus_pres = np.full(len(G), np.inf)
    cap_porte = np.full(len(G), np.nan)
    for q in permises:
        portes = (plan["face_piece"] == q) & (plan["sorte"] == 1)
        if not portes.any():
            continue
        A, B = plan["A"][portes], plan["B"][portes]
        e = B - A
        t = np.clip(((G[:, None, :] - A[None]) * e[None]).sum(2) / (e * e).sum(1)[None], 0, 1)
        vers = A[None] + t[..., None] * e[None] - G[:, None, :]   # de chaque place vers le point le plus proche de chaque porte
        d = np.linalg.norm(vers, axis=2)
        j = d.argmin(1); d = d[np.arange(len(G)), j]; vers = vers[np.arange(len(G)), j]
        prend = hors & (d < PORTE_M) & (d < plus_pres)
        r[prend] = q; plus_pres[prend] = d[prend]
        cap_porte[prend] = np.degrees(np.arctan2(vers[prend, 1], vers[prend, 0]))
    ecart = np.abs((np.arange(360.0)[None] - np.nan_to_num(cap_porte)[:, None] + 180) % 360 - 180)
    permis = (r >= 0)[:, None] & (np.isnan(cap_porte)[:, None] | (ecart <= VERS_PORTE_DEG))
    return r, permis


def zone_pointee(plan: dict, G: np.ndarray, pg: np.ndarray, point, donnee: list[int] | None) -> tuple[list[int], np.ndarray, bool]:
    """L'endroit pointé à l'écran de vérification (« d'où est prise cette photo ? ») → (pièces permises, places de la grille à
    moins de RAYON_POINTE du point, True si le point contredit la pièce donnée par le client). La pièce est celle du point :
    c'est elle qui départage deux chambres jumelles. Si le point tombe hors de la pièce donnée mais sur son seuil (une cuisine
    photographiée du couloir), la pièce donnée reste ; entre DEUX pièces données dont les portes sont voisines (deux salles
    d'eau sur le même couloir), c'est celle vers laquelle on regarde si le sens est indiqué, sinon celle dont la porte est la
    plus proche ; si le point tombe franchement ailleurs, c'est le point qui compte."""
    ecart = np.hypot(G[:, 0] - point[0], G[:, 1] - point[1])
    pres, pointee = ecart < RAYON_POINTE, int(pg[ecart.argmin()])
    ailleurs = donnee is not None and pointee not in donnee
    if ailleurs:
        seuils = []  # (écart au sens du regard, distance de la porte, pièce) pour chaque pièce donnée dont une porte est à portée
        cap = float(point[2]) if len(point) > 2 and point[2] is not None else None
        for q in donnee:
            portes = (plan["face_piece"] == q) & (plan["sorte"] == 1)
            if not portes.any():
                continue
            A, B = plan["A"][portes], plan["B"][portes]
            e = B - A
            t = np.clip(((np.asarray(point[:2], float)[None] - A) * e).sum(1) / (e * e).sum(1), 0, 1)
            vers = A + t[:, None] * e - np.asarray(point[:2], float)[None]
            d = np.linalg.norm(vers, axis=1)
            j = int(d.argmin())
            if d[j] < PORTE_M:
                biais = 0.0 if cap is None else abs((np.degrees(np.arctan2(vers[j, 1], vers[j, 0])) - cap + 180) % 360 - 180)
                seuils.append((round(float(biais) / 20), float(d[j]), q))  # le sens d'abord (par tranches de 20°), puis la porte la plus proche
        if seuils:
            return [min(seuils)[2]], pres, False
    return [pointee], pres, bool(ailleurs)


def doute_sur_la_piece_donnee(sure_ailleurs: str | None, facteur_meubles: float, colle: float) -> str | None:
    """Le SECOND AVIS d'Atelya sur la pièce donnée par le client : la raison d'envoyer la photo à la vérification, ou None.
    sure_ailleurs : la pièce dont Atelya, seul, est sûr quand ce n'est pas la pièce donnée (ni son seuil) ; facteur_meubles :
    accord des meubles vus avec la sorte de pièce donnée (1 = d'accord ou rien de net) ; colle : meilleure note de la photo
    dans la pièce donnée, rapportée à sa meilleure note partout. Mesuré le 15/11/2026 sur les trois logements (chaque photo
    avec chacune des autres pièces du plan) : une fausse pièce d'une AUTRE sorte est signalée 4 fois sur 5 ; une fausse pièce
    de même sorte (l'autre chambre jumelle) ne peut pas l'être ; la bonne pièce est mise en doute à tort environ 1 fois sur 45."""
    if sure_ailleurs:
        return f"Atelya, seul, la voit dans une autre pièce ({sure_ailleurs})"
    if facteur_meubles <= MEUBLES_MIN:
        return "les meubles vus sur la photo ne vont pas avec cette pièce"
    if colle < COLLE_MIN:
        return "la photo colle mal à cette pièce (bien mieux ailleurs)"
    return None


def endroit_douteux(endroit: dict | None, piece: str | None = None) -> str | None:
    """Le signal « ENDROIT DOUTEUX » (15/11/2026, demande de NT) : la pièce est la bonne, mais la PLACE dans la pièce est-elle
    fiable ? La raison d'aller le demander à la vérification, ou None. Jugé pour le BLOC de la photo (ses photos bougent
    ensemble), avec ce que le calage calcule déjà (champ « endroit » de chaque caméra) :
      - autre_pose ≥ AUTRE_POSE_MIN : une autre pose du bloc, ailleurs dans la même pièce (à plus de LOIN_M, ou tournée de plus
        de TOURNE_DEG), va presque aussi bien (petite pièce sans repère : salle d'eau placée à l'envers) ;
      - accord < ACCORD_MIN : une photo du bloc est loin de sa propre meilleure place : les photos de la pièce ne s'accordent
        pas (cuisine d'app-002 : une photo juste, l'autre à 2 m).
      - et, d'abord, la PETITE PIÈCE (cuisine, salle d'eau, entrée, WC, dégagement : PETITES_PIECES) : toujours douteuse. Mesuré le
        16/11/2026 dans les conditions du service : sur les 4 photos de petites pièces dont on connaît la vraie place, 3 à 4
        sont mal placées, et les deux indices ci-dessus ne voient pas la cuisine d'app-002 (autre_pose 0,76 à 0,93 selon de
        petits changements du plan, accord 1,0).
    Regarder la photo SEULE ne suffit pas (mesuré : dans un grand séjour, une photo juste a souvent une autre place aussi
    bonne ; c'est le bloc qui tranche). On ne sait PAS dire laquelle des photos d'un bloc douteux est mal placée.
    Mesures et limites : pc/essais-cameras-seules/endroit_douteux.py et le journal."""
    if piece and sorte_de_piece(piece) in PETITES_PIECES:
        return "c'est une petite pièce, où Atelya se repère mal"
    if not endroit:
        return None
    if endroit.get("autre_pose", 0.0) >= AUTRE_POSE_MIN:
        return "une autre place dans la pièce irait presque aussi bien"
    if endroit.get("accord", 1.0) < ACCORD_MIN:
        return "les photos de cette pièce ne s'accordent pas entre elles"
    return None


def _signaler_les_endroits(cameras: dict, journal) -> None:
    """Pose « endroit_douteux » sur les photos SÛRES de leur pièce dont la place ne l'est pas. Ne change pas « sure » : les
    sols et les meubles s'en servent comme avant ; c'est la vérification qui pose la question. Une photo pointée par NT est
    déjà une réponse."""
    for n, d in cameras.items():
        raison = None if (not d["sure"] or d.get("pointee")) else endroit_douteux(d.get("endroit"), d.get("piece"))
        if raison:
            d["endroit_douteux"] = raison
            journal(f"  {n} : ENDROIT DOUTEUX dans {d['piece']}, {raison}")


# ================================================================ les choix d'ensemble
def _monter(total, nb, nombres, rng, essais=30, depart=None):
    """Meilleur choix (un indice par élément) par petites améliorations, depuis plusieurs départs."""
    meilleur = (None, -1e18)
    for essai in range(essais):
        ch = list(depart) if essai == 0 and depart is not None else [int(rng.integers(k)) for k in nombres]
        v = total(ch); bouge = True
        while bouge:
            bouge = False
            for i in rng.permutation(nb):
                for k in range(nombres[i]):
                    c2 = list(ch); c2[i] = k; v2 = total(c2)
                    if v2 > v + 1e-9:
                        ch, v, bouge = c2, v2, True
        if v > meilleur[1]:
            meilleur = (ch, v)
    return meilleur


def _meme_endroit(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1]) < 1.0 and abs((a[2] - b[2] + 180) % 360 - 180) < 25


def choisir_les_pieces(cands: dict, types: dict, sim: dict) -> dict:
    """Premier choix, photo par photo mais toutes ensemble. cands : {photo: [{piece, cam, note}]} → {photo: pièce}."""
    noms = [n for n in cands if cands[n]]
    seul = [[math.log(max(c["note"], 1e-3)) + L_TYPE * math.log(_facteur(types[n], c["piece"])) for c in cands[n]] for n in noms]
    plus_proche = {a: max((x for x in noms if x != a), key=lambda x: sim[a][x], default=None) for a in noms}
    lies = {(a, b): sim[a][b] >= SEUIL_MEME or (plus_proche[a] == b and plus_proche[b] == a and sim[a][b] >= 0.5) for a in noms for b in noms if a != b}

    def total(ch):
        s = sum(seul[i][k] for i, k in enumerate(ch))
        s += L_COUV * sum(sorte_de_piece(p) in PRINCIPALES for p in {cands[n][k]["piece"] for n, k in zip(noms, ch)})
        for i, a in enumerate(noms):
            ca = cands[a][ch[i]]
            for j in range(i + 1, len(noms)):
                cb = cands[noms[j]][ch[j]]
                if _meme_endroit(ca["cam"], cb["cam"]):
                    s -= L_DOUBLE
                if lies[(a, noms[j])] and ca["piece"] == cb["piece"]:
                    s += L_MEME
        return s
    ch, _ = _monter(total, len(noms), [len(cands[n]) for n in noms], np.random.default_rng(0), depart=[int(np.argmax(s)) for s in seul])
    return {n: cands[n][k]["piece"] for n, k in zip(noms, ch)}


def note_d_ensemble(unites: list[list[dict]]):
    """La note d'un choix d'ensemble (un candidat par bloc) : → (fonction total(choix), notes de chaque candidat seul)."""
    seul = [[sum(math.log(max(p["note"], 1e-3)) for p in c["photos"].values()) for c in u] for u in unites]

    def total(ch):
        s = sum(seul[i][k] for i, k in enumerate(ch))
        vues = {p["piece"] for i, k in enumerate(ch) for p in unites[i][k]["photos"].values()}
        s += L_COUV * sum(sorte_de_piece(p) in PRINCIPALES for p in vues)
        for i in range(len(ch)):
            for j in range(i + 1, len(ch)):
                for a in unites[i][ch[i]]["photos"].values():
                    for b in unites[j][ch[j]]["photos"].values():
                        if _meme_endroit(a["cam"], b["cam"]):
                            s -= L_DOUBLE
        return s
    return total, seul


def choisir_les_blocs(unites: list[list[dict]]) -> tuple[list[int], list[float]]:
    """Second choix, par blocs. unites : [[candidat]], candidat = {photos: {nom: {cam, note, piece}}}.
    → indices choisis, et pour chaque bloc ce que l'ensemble perdrait s'il changeait de pièce (la « marge »)."""
    total, seul = note_d_ensemble(unites)
    ch, v = _monter(total, len(unites), [len(u) for u in unites], np.random.default_rng(0), depart=[int(np.argmax(s)) for s in seul])
    marges = []
    for i, u in enumerate(unites):
        ici = {p["piece"] for p in u[ch[i]]["photos"].values()}
        autres = [total([*ch[:i], k, *ch[i + 1:]]) for k in range(len(u)) if {p["piece"] for p in u[k]["photos"].values()} != ici]
        marges.append(float(v - max(autres)) if autres else 9.0)
    return ch, marges


def marges_d_ensemble(unites: list[list[dict]], choix: list[int]) -> tuple[list[float], list[list[str]]]:
    """Pour chaque bloc : ce que l'ensemble perd si ce bloc change de pièce, LES AUTRES BLOCS POUVANT BOUGER AUSSI, et les
    pièces où il irait alors (ses « rivales »).
    POURQUOI : deux chambres jumelles qui ont chacune leurs photos ne s'échangent qu'à deux. La marge de `choisir_les_blocs`
    ne déplace qu'un bloc à la fois : mettre les photos de la chambre A dans la chambre B, déjà occupée, « perd » une pièce
    montrée, et l'échange paraît coûteux alors qu'il ne coûte presque rien (app-002 : 0,42 et 0,65 au lieu de ~0,1)."""
    total, _ = note_d_ensemble(unites)
    v = total(choix)
    pieces = lambda i, k: {p["piece"] for p in unites[i][k]["photos"].values()}
    marges, rivales = [], []
    for i, u in enumerate(unites):
        ici, meilleur = pieces(i, choix[i]), (None, -1e18)
        for k in range(len(u)):
            la = pieces(i, k)
            if la == ici:
                continue
            ch = list(choix); ch[i] = k; w = total(ch)
            deloges = [j for j in range(len(unites)) if j != i and pieces(j, ch[j]) & la]  # ceux dont on prend la place
            vus = set()
            while deloges:
                j = deloges.pop(0)
                if j in vus:
                    continue
                vus.add(j)
                for kj in range(len(unites[j])):
                    c2 = list(ch); c2[j] = kj; w2 = total(c2)
                    if w2 > w + 1e-9:
                        ch, w = c2, w2
                deloges += [m for m in range(len(unites)) if m != i and m not in vus and pieces(m, ch[m]) & pieces(j, ch[j])]
            if w > meilleur[1]:
                meilleur = (k, w)
        marges.append(float(v - meilleur[1]) if meilleur[0] is not None else 9.0)
        rivales.append(sorted(pieces(i, meilleur[0])) if meilleur[0] is not None else [])
    return marges, rivales


def seuil_sure(photos_du_bloc: int) -> float:
    """La marge qu'un bloc doit dépasser pour être « sûr » : MARGE_SURE pour une photo seule, × la racine du nombre de photos
    pour un bloc. POURQUOI : la marge d'un bloc est une SOMME sur ses photos ; avec un seuil fixe, un bloc de cinq photos
    passait pour sûr avec un avantage de 8 % par photo, qu'un plan faux de 5 % suffit à retourner (app-003, plan rétréci :
    séjour et salle à manger échangés, marge 0,46)."""
    return MARGE_SURE * (math.sqrt(max(1, photos_du_bloc)) if SEUIL_PAR_RACINE else 1.0)


# ================================================================ les blocs (Depth Anything 3)
def recouper(modele_da3, noms: list[str], photos: dict, mesures: dict) -> dict:
    """Les appareils d'un groupe de photos les uns par rapport aux autres : {photo: (place à plat en m, cap en rad)}.
    Mise en mètres par les profondeurs de MoGe-2 ; le « haut » est celui de MoGe-2."""
    r = da3.lire(modele_da3, [photos[n] for n in noms])
    h, w = r["taille"]
    ech, hauts = [], []
    for i, n in enumerate(noms):
        z = mesures[n]
        zm = cv2.resize(z["points"][..., 2], (w, h), interpolation=cv2.INTER_NEAREST)
        ok = cv2.resize(z["masque"].astype(np.uint8), (w, h), interpolation=cv2.INTER_NEAREST) > 0
        ok &= r["confiance"][i] > np.median(r["confiance"][i])
        ech.append(np.median(zm[ok] / r["profondeur"][i][ok]))
        hauts.append(r["appareils"][i][:, :3] @ z["haut"])
    e = float(np.median(ech))
    haut = np.mean(hauts, 0); haut /= np.linalg.norm(haut)
    ax = np.cross(haut, [0.0, 0.0, 1.0]); ax /= np.linalg.norm(ax); ay = np.cross(haut, ax)
    sortie = {}
    for i, n in enumerate(noms):
        R, t = r["appareils"][i][:, :3], r["appareils"][i][:, 3] * e
        f = R[:, 2] - haut * (R[:, 2] @ haut)
        sortie[n] = (np.array([t @ ax, t @ ay]), float(np.arctan2(f @ ay, f @ ax)))
    return sortie


def meme_lieu(modele_da3, a: np.ndarray, b: np.ndarray) -> float:
    """Deux photos montrent-elles le même lieu ? Part des points de l'une qui, revus depuis l'autre appareil, tombent à la
    profondeur que l'autre mesure (dans la partie commune, moyenne des deux sens). 0 = rien en commun."""
    r = da3.lire(modele_da3, [a, b])
    h, w = r["taille"]
    v, u = np.meshgrid(np.arange(h) + 0.5 - h / 2, np.arange(w) + 0.5 - w / 2, indexing="ij")
    parts = []
    for i, j in ((0, 1), (1, 0)):
        d = r["profondeur"][i]; fx, fy = r["focale_px"][i]; gx, gy = r["focale_px"][j]
        Pw = np.stack([u / fx * d, v / fy * d, d], -1) @ r["appareils"][i][:, :3].T + r["appareils"][i][:, 3]
        Pj = (Pw - r["appareils"][j][:, 3]) @ r["appareils"][j][:, :3]
        z = Pj[..., 2]
        x = np.round(Pj[..., 0] / np.maximum(z, 1e-6) * gx + w / 2 - 0.5).astype(int)
        y = np.round(Pj[..., 1] / np.maximum(z, 1e-6) * gy + h / 2 - 0.5).astype(int)
        dedans = (r["confiance"][i] > np.percentile(r["confiance"][i], 30)) & (z > 0) & (x >= 0) & (x < w) & (y >= 0) & (y < h)
        if dedans.sum() < 50:
            parts.append(0.0); continue
        dj = r["profondeur"][j][y[dedans], x[dedans]]
        parts.append(float((np.abs(z[dedans] - dj) / dj < 0.10).mean()))
    return float(np.mean(parts))


def _sans_les_isoles(g: list[str], acc: dict) -> list[list[str]]:
    """Ancienne règle (avant le 15/11/2026) : seules les photos qu'aucune autre ne revoit sortent du groupe."""
    reste = [n for n in g if max(acc.get((n, m), acc.get((m, n), 0.0)) for m in g if m != n) >= SEUIL_INTRUS]
    return ([reste] if reste else []) + [[n] for n in g if n not in reste]


def sous_groupes(g: list[str], acc: dict) -> list[list[str]]:
    """Un groupe de photos coupé en sous-groupes de photos qui se REVOIENT, de proche en proche (accord « même lieu » d'au
    moins SEUIL_INTRUS). POURQUOI : deux pièces qui se ressemblent (deux chambres, séjour et salle à manger) tombent souvent
    dans le même groupe au premier choix ; sans cette coupe, leurs photos formaient UN bloc, posé d'un coup dans une seule
    pièce et dit « sûr » pour toutes (app-003 : la chambre d'enfants mise dans la chambre d'angle)."""
    lie = lambda a, b: acc.get((a, b), acc.get((b, a), 0.0)) >= SEUIL_INTRUS
    reste, sortie = list(g), []
    while reste:
        sg, i = [reste.pop(0)], 0
        while i < len(sg):
            for m in list(reste):
                if lie(sg[i], m):
                    sg.append(m); reste.remove(m)
            i += 1
        sortie.append(sorted(sg, key=g.index))
    return sortie


def _glisse(A, dy, dx):
    B = np.zeros_like(A); h, w = A.shape
    y0, y1, x0, x1 = max(0, -dy), min(h, h - dy), max(0, -dx), min(w, w - dx)
    if y1 > y0 and x1 > x0:
        B[y0:y1, x0:x1] = A[y0 + dy:y1 + dy, x0 + dx:x1 + dx]
    return B


def poser_bloc(T: dict, rel: dict, noms: list[str], combien: int = 40) -> list[dict]:
    """Les meilleures places d'un bloc sur le plan. T : {photo: notes rangées (ligne, colonne, cap), avec jeu} ; rel : sortie
    de `recouper`. → [{photo: (colonne, ligne, cap)}], de la meilleure à la moins bonne, la 1re photo servant d'ancre."""
    a = noms[0]; c0, t0 = rel[a]; trouves = []
    for s in (ECHELLES_BLOC if len(noms) > 1 else (1.0,)):
        for cap in range(360):
            rot = math.radians(cap) - t0; cr, sr = math.cos(rot), math.sin(rot)
            tot = T[a][:, :, cap].copy(); ou = {a: (0, 0, cap)}
            for n in noms[1:]:
                d = (rel[n][0] - c0) * s
                dx, dy = int(round((cr * d[0] - sr * d[1]) / PAS)), int(round((sr * d[0] + cr * d[1]) / PAS))
                k = int(round(cap + math.degrees(rel[n][1] - t0))) % 360
                tot += _glisse(T[n][:, :, k], dy, dx); ou[n] = (dx, dy, k)
            for _ in range(3):
                iy, ix = np.unravel_index(tot.argmax(), tot.shape)
                trouves.append((float(tot[iy, ix]), int(ix), int(iy), cap, ou))
                tot[max(0, iy - 4):iy + 5, max(0, ix - 4):ix + 5] = 0
    trouves.sort(key=lambda x: -x[0]); garde = []
    for v, ix, iy, cap, ou in trouves:
        if all(math.hypot(ix - g[1], iy - g[2]) > 4 or abs((cap - g[3] + 180) % 360 - 180) > 20 for g in garde):
            garde.append((v, ix, iy, cap, ou))
        if len(garde) == combien:
            break
    return [{n: (ix + dx, iy + dy, k) for n, (dx, dy, k) in ou.items()} for v, ix, iy, cap, ou in garde]


# ================================================================ la chaîne entière
def _affiner(plan, o, rgb, fen, zoom, cam, fu, sens):
    """La place dans la pièce DÉJÀ choisie, refaite avec le zoom des lignes de fuite : la photo est remesurée à ce zoom, puis
    on cherche autour de la place trouvée (9 départs, 0,5 m) celle qui colle le mieux au plan, sans changer de pièce ni
    s'éloigner de plus de 1,5 m."""
    pr = profil(mesurer(o.moge, rgb, zoom * rgb.shape[1]), plan["hsp"], fen)
    if pr is None:
        return cam
    piece = piece_de(plan, cam[None, :2])[0]
    meilleur = (-1.0, cam)
    for dx in (0.0, -0.5, 0.5):
        for dy in (0.0, -0.5, 0.5):
            c0 = np.array([cam[0] + dx, cam[1] + dy, cam[2], 1.0])
            if piece_de(plan, c0[None, :2])[0] != piece:
                continue
            c, v = regler(plan, pr, c0, LIMITES_ZOOM_JUSTE)
            if v > meilleur[0] and piece_de(plan, c[None, :2])[0] == piece and math.hypot(*(c[:2] - cam[:2])) < 1.5                     and abs((c[2] - cam[2] + 180) % 360 - 180) < 10:
                meilleur = (v, c)
    c = meilleur[1].copy()
    c[2] = cap_par_fuites(float(c[2]), fu, sens)
    return c


class Outils:
    """Les réseaux dont la chaîne a besoin, chargés une fois : MoGe-2, Depth Anything 3, l'œil DINOv2 ViT-B/14, OWLv2."""

    def __init__(self, appareil: str | None = None):
        from .pas_du_sol import charger as charger_pds
        self.appareil = appareil or ("cuda" if torch.cuda.is_available() else "cpu")
        self.moge = moge.charger(self.appareil)
        self.da3 = da3.charger(appareil=self.appareil)
        self.oeil = charger_oeil("vitb14", self.appareil)
        self.pds = charger_pds(self.appareil, avec_dino=False)
        self.fenetres = Fenetres()


def caler(logement: dict, photos: dict[str, np.ndarray], outils: Outils | None = None, journal=print, fenetres_de: dict | None = None,
          zoom_par_fuites: bool | str = False, detail: dict | None = None, pieces_donnees: dict | None = None,
          confirmees=(), endroits_donnes: dict | None = None) -> dict:
    """logement : le logement lu (pièces, murs, ouvertures) ; photos : {nom: photo RGB}.
    → {"cameras": {nom: {"camera": {x, y, z, cap, tangage, f, u0, v0}, "largeur", "hauteur", "piece", "sure", "marge", "bloc",
                         "hesite_avec"}},
       "non_calees": {nom: raison}}. Seules les photos « sure » : True doivent servir aux sols et aux meubles ; une photo pas
    sûre porte « hesite_avec » : les pièces où elle irait sinon (deux chambres jumelles : l'autre chambre).
    pieces_donnees (15/11/2026, décision NT : le client range chaque photo par pièce au dépôt) : {nom: pièce}, la pièce étant
    un identifiant du plan (« chambre_2 »), une sorte (« chambre ») ou une liste. Atelya ne cherche alors la place de la photo
    que là (ou sur le seuil d'une porte de la pièce) ; la photo est « sure » puisque la pièce est donnée, SAUF si Atelya la
    voit ailleurs : s'il est sûr, seul, d'une autre pièce, si les meubles vus ne vont pas avec cette sorte de pièce, ou si la
    photo colle bien moins à cette pièce qu'ailleurs (« colle » < COLLE_MIN) → « a_verifier » : la raison, et « sure » False (écran de vérification : NT confirme). confirmees : noms des
    photos dont la pièce a été confirmée à la vérification (plus de doute levé). Champs en plus : « donnee », « colle »,
    « avis_seul » ({piece, sure} : ce qu'Atelya aurait dit sans le client).
    endroits_donnes (15/11/2026, NT : « en deux temps » : le client nomme la pièce, puis, quand Atelya ne sait pas où ranger
    la photo, l'écran de vérification demande d'où elle est prise et NT POINTE l'endroit sur le plan) : {nom: (x, y)} en mètres
    du plan, ou (x, y, cap) si le sens du regard est indiqué aussi (cap en degrés, 0 = vers les x croissants, sens inverse des
    aiguilles ; alors à SENS_POINTE_DEG près). L'appareil est cherché à moins de RAYON_POINTE du point, dans la pièce pointée (ou sur son seuil) ; la photo
    est « sure » (c'est une réponse de NT : plus de second avis), champ « pointee ».
    fenetres_de : {nom: carte « fenêtre ou non »} toute faite, pour les ESSAIS seulement (noter la chaîne sur les photos qui
    ont servi à apprendre la couche des fenêtres, avec une carte apprise sans elles).
    zoom_par_fuites : EN RÉSERVE (14/11/2026 nuit), pas en service. Zoom et cap donnés par les lignes de fuite
    (moteur/fuites.py) quand les photos du lot s'accordent. True = dès la mesure des photos : app-003 écart médian 0,53 → 0,46 m,
    pire 1,45 → 0,98 m, mais app-002 chambres jumelles échangées et dites « sûres », meubles 19 → 16 sur 30. "fin" = pièces
    choisies comme avant, zoom juste seulement pour affiner la place. Rejugée le 15/11/2026 contre le corrigé soigné d'app-002
    (verites/app-002/cameras-photos-soigne.json), après correction de l'orientation (`fuites.orienter_au_zoom`) : app-002
    médiane 0,36 → 0,39 m, pire 0,90 → 0,75 m, orientation 2,2° → 0,9°, sols 87,9 → 90,2 %, meubles 19 → 20 sur 30 ; app-003
    médiane 0,53 → 0,51 m, pire 1,45 → 1,21 m mais une photo passe au-delà de 1 m (0,82 → 1,21). Pas de gain net en mètres :
    reste en réserve."""
    o = outils or Outils()
    plan = plan_du_logement(logement)
    G = grille(plan); pg = piece_de(plan, G)
    orig = np.concatenate(plan["pieces"]).min(0); ij = np.round((G - orig) / PAS).astype(int); forme = tuple((ij.max(0) + 1)[::-1])
    P = np.full(forme, -1); P[ij[:, 1], ij[:, 0]] = pg
    tp = tuple(torch.from_numpy(np.ascontiguousarray(t)).to(o.appareil) for t in tirs(plan, G, np.arange(360.0)))
    tp = (tp[0].float(), tp[1].to(torch.int8), tp[2].bool())

    # le zoom : celui des lignes de fuite quand les photos du lot s'accordent (moteur/fuites.py), sinon celui de MoGe-2
    fu = {nom: {**fuites.mesurer(rgb), "largeur": rgb.shape[1]} for nom, rgb in photos.items()} if zoom_par_fuites else {}
    zoom_fin = fuites.zoom_du_lot(fu) if fu else None
    zoom = None if zoom_par_fuites == "fin" else zoom_fin  # « fin » : pièces choisies comme avant, zoom juste pour la place seulement
    if zoom_fin:  # l'orientation de chaque photo refaite au zoom du lot (celle de `mesurer` est liée à son propre zoom, parfois faux)
        for nom, rgb in photos.items():
            fu[nom].update(fuites.orienter_au_zoom(fu[nom], zoom_fin * rgb.shape[1], rgb.shape[1], rgb.shape[0]))
    fens = {}
    journal(f"  zoom par les lignes de fuite : {'%.3f × la largeur' % zoom if zoom else 'pas net, on garde celui de MoGe-2'}")
    sens = sens_des_murs(plan)
    echelles, limites = (ECHELLES_ZOOM_JUSTE, LIMITES_ZOOM_JUSTE) if zoom else (ECHELLES, LIMITES)
    donnees = {}
    for nom, valeur in (pieces_donnees or {}).items():
        permises = pieces_permises(plan, valeur)
        if nom in photos and permises:
            donnees[nom] = permises
        elif nom in photos:
            journal(f"  {nom} : pièce donnée inconnue du plan ({valeur}), photo calée comme si rien n'était dit")

    pres_du_point, sens_pointes = {}, {}
    for nom, point in (endroits_donnes or {}).items():
        if nom not in photos:
            continue
        donnees[nom], pres_du_point[nom], contredit = zone_pointee(plan, G, pg, point, donnees.get(nom))
        if len(point) > 2 and point[2] is not None:  # le sens du regard est indiqué aussi (cliquer puis tirer vers ce qu'on voit)
            sens_pointes[nom] = np.abs((np.arange(360.0) - float(point[2]) + 180) % 360 - 180) <= SENS_POINTE_DEG
        if contredit:
            journal(f"  {nom} : l'endroit pointé n'est pas dans la pièce donnée, c'est l'endroit pointé qui compte")

    def avec_jeu(r):
        """La meilleure note dans le jeu laissé à chaque photo dans son bloc (cases voisines, caps voisins)."""
        t = torch.nn.functional.max_pool2d(torch.from_numpy(r).permute(2, 0, 1)[None], 2 * JEU_M + 1, 1, JEU_M)[0].permute(1, 2, 0).numpy()
        return np.max([np.roll(t, d, 2) for d in range(-JEU_DEG, JEU_DEG + 1)], 0)

    mes, prof, types, R, T, Er, non = {}, {}, {}, {}, {}, {}, {}
    masques = None
    Rd, Td, PM, colle = {}, {}, {}, {}  # photos dont la pièce est donnée : notes limitées à cette pièce, pièce montrée par case
    for nom, rgb in photos.items():
        mes[nom] = mesurer(o.moge, rgb, zoom * rgb.shape[1] if zoom else None)
        fen = fenetres_de[nom] if fenetres_de and nom in fenetres_de else o.fenetres.proba(Fenetres.carres(o.oeil, rgb))
        fens[nom] = fen
        pr = profil(mes[nom], plan["hsp"], fen)
        if pr is None:
            non[nom] = "trop peu de murs visibles"; journal(f"  {nom} : trop peu de murs visibles, photo laissée de côté"); continue
        prof[nom] = pr
        types[nom] = indices_des_meubles(o.pds.brut(f"caler/{id(photos)}/{nom}", rgb)["objets"])
        N, E = notes_sur_le_plan(tp, pr, o.appareil, echelles)
        fac = np.array([_facteur(types[nom], plan["ids"][p]) for p in pg], np.float32)
        R[nom] = np.zeros((*forme, 360), np.float32); R[nom][ij[:, 1], ij[:, 0]] = N * fac[:, None]
        Er[nom] = np.zeros((*forme, 360), np.uint8); Er[nom][ij[:, 1], ij[:, 0]] = E
        T[nom] = avec_jeu(R[nom])
        if detail is not None:  # essais : à quel point la photo collerait à chaque pièce si le client la lui donnait
            if masques is None:
                masques = [pieces_montrees(plan, G, pg, [q])[1] for q in range(len(plan["ids"]))]
            detail.setdefault("colle_par_piece", {})[nom] = {plan["ids"][q]: round(float((N * m).max() / max(float(N.max()), 1e-6)), 3)
                                                             for q, m in enumerate(masques) if m.any()}
            detail.setdefault("types", {})[nom] = types[nom]
        if nom in donnees:  # la pièce est donnée : plus besoin des meubles pour deviner sa sorte, seules ses cases comptent
            montree, permis = pieces_montrees(plan, G, pg, donnees[nom])
            if nom in pres_du_point:
                permis = permis & pres_du_point[nom][:, None]
            if nom in sens_pointes:
                permis = permis & sens_pointes[nom][None, :]
            PM[nom] = np.full(forme, -1); PM[nom][ij[:, 1], ij[:, 0]] = montree
            Rd[nom] = np.zeros((*forme, 360), np.float32); Rd[nom][ij[:, 1], ij[:, 0]] = N * permis
            Td[nom] = avec_jeu(Rd[nom])
            colle[nom] = float(Rd[nom].max() / max(float(N.max()), 1e-6))
        journal(f"  {nom} : mesurée (meubles : {'/'.join(types[nom]) or 'rien de net'})")
    noms = list(prof)
    if not noms:
        return {"cameras": {}, "non_calees": non}
    e = empreintes(o.oeil, np.stack([cv2.resize(photos[n], (518, 350)) for n in noms]))
    sim = {a: {b: float(e[i] @ e[j]) for j, b in enumerate(noms)} for i, a in enumerate(noms)}
    lieux, blocs = {}, {}  # gardés d'un passage à l'autre (avis d'Atelya seul, puis avec les pièces données)

    def lieu(a, b):
        cle = tuple(sorted((a, b)))
        if cle not in lieux:
            lieux[cle] = meme_lieu(o.da3, photos[a], photos[b])
        return lieux[cle]

    def choisir(R, T, PM, journal):
        """Le choix d'ensemble (groupes, blocs, pièces, « sûr ») pour des notes données. PM : {photo: pièce montrée par case}
        pour les photos dont la pièce est donnée ; les autres : la pièce où se tient l'appareil."""
        non = {}

        def place(n, ix, iy, k, jm, jd):
            """Dans le jeu laissé autour d'une case : la meilleure vraie case de la photo."""
            h, w, _ = R[n].shape
            y0, y1, x0, x1 = max(0, iy - jm), min(h, iy + jm + 1), max(0, ix - jm), min(w, ix + jm + 1)
            if y1 <= y0 or x1 <= x0:
                return ix, iy, k, 0.0
            caps = np.arange(k - jd, k + jd + 1) % 360
            s = R[n][y0:y1, x0:x1][:, :, caps]
            a, b, c = np.unravel_index(s.argmax(), s.shape)
            return x0 + int(b), y0 + int(a), int(caps[c]), float(s[a, b, c])

        def candidat(ou, jeu=True):
            c = {"photos": {}}
            for n, (ix, iy, k) in ou.items():
                x, y, k2, v = place(n, ix, iy, k, JEU_M if jeu else 0, JEU_DEG if jeu else 0)
                pm = PM.get(n, P)
                ok = v > 0 and pm[y, x] >= 0
                c["photos"][n] = {"cam": [float(orig[0] + x * PAS), float(orig[1] + y * PAS), float(k2), float(echelles[int(Er[n][y, x, k2])]) if ok else 1.0],
                                  "note": v, "piece": plan["ids"][pm[y, x]] if ok else "hors du plan"}
            return c

        def par_piece(n, combien=2):
            """Les meilleures places d'une photo seule dans chaque pièce."""
            cs, pm = [], PM.get(n, P)
            for p in range(len(plan["pieces"])):
                Rp = R[n] * (pm == p)[:, :, None]
                for _ in range(combien):
                    iy, ix, k = np.unravel_index(Rp.argmax(), Rp.shape)
                    if Rp[iy, ix, k] <= 0:
                        break
                    cs.append(candidat({n: (int(ix), int(iy), int(k))}, jeu=False))
                    Rp[max(0, iy - 4):iy + 5, max(0, ix - 4):ix + 5] = 0
            return cs

        def detache(n, cam, piece):
            """À quel point la place trouvée se détache, pour cette photo SEULE, des autres places possibles dans la MÊME
            pièce : sa note ici, la meilleure note AILLEURS (à plus de LOIN_M), la meilleure au même endroit mais TOURNÉE (cap
            à plus de TOURNE_DEG), et la meilleure de toute la pièce. Sert au signal « endroit douteux »."""
            M = R[n] * (PM.get(n, P) == plan["ids"].index(piece))[:, :, None]
            h, w, _ = M.shape
            yy, xx = np.mgrid[:h, :w]
            d = np.hypot(xx - (cam[0] - orig[0]) / PAS, yy - (cam[1] - orig[1]) / PAS) * PAS
            dk = np.abs((np.arange(360) - cam[2] + 180) % 360 - 180)
            haut = lambda t: round(float(t.max(initial=0.0)), 4)
            return {"ici": haut(M[d <= 0.5][:, dk <= 12]), "ailleurs": haut(M[d > LOIN_M]), "tournee": haut(M[d <= LOIN_M][:, dk > TOURNE_DEG]),
                    "meilleure": haut(M)}

        # 1er choix photo par photo → groupes de photos de la même pièce
        seules = {n: par_piece(n, 3) for n in noms}
        piece1 = choisir_les_pieces({n: [{**c["photos"][n]} for c in cs] for n, cs in seules.items()}, {n: {} for n in noms}, sim)  # le type de pièce est déjà dans les notes
        groupes = [[n for n in noms if piece1.get(n, n) == q] for q in dict.fromkeys(piece1.get(n, n) for n in noms)]
        nouveaux, accords = [], {}
        for g in groupes:  # le groupe est coupé en sous-groupes de photos qui se revoient ; une photo que personne ne revoit reste seule
            if len(g) == 1:
                nouveaux.append(g); continue
            acc = {(a, b): lieu(a, b) for i, a in enumerate(g) for b in g[i + 1:]}
            accords.update(acc)
            nouveaux += sous_groupes(g, acc) if SOUS_GROUPES else _sans_les_isoles(g, acc)
        groupes = nouveaux
        journal("  groupes : " + " | ".join("+".join(g) for g in groupes))

        # 2e choix par blocs
        unites = []
        for g in groupes:
            if len(g) == 1:
                unites.append(par_piece(g[0])); continue
            if tuple(g) not in blocs:
                blocs[tuple(g)] = recouper(o.da3, g, photos, mes)
            cs = [candidat(ou) for ou in poser_bloc(T, blocs[tuple(g)], g)]
            garde, vues = cs[:6], set()
            for c in cs:  # + la meilleure place du bloc pour chaque pièce où il peut tomber
                cle = tuple(sorted({p["piece"] for p in c["photos"].values()}))
                if cle not in vues:
                    vues.add(cle)
                    if c not in garde:
                        garde.append(c)
            unites.append(garde)
        for g, u in zip(groupes, unites):  # aucune place possible (endroit pointé dans un mur, hors des pièces…) : photo laissée de côté,
            if not u:                      # au lieu de faire planter tout le calage (16/11/2026)
                non.update({n: "aucune place ne colle au plan" for n in g})
        groupes, unites = [g for g, u in zip(groupes, unites) if u], [u for u in unites if u]
        if not unites:
            return {}, non, dict(unites=[], choix=[], marges=[], groupes=[], seules={}, accords={})
        ch, marges_seul = choisir_les_blocs(unites)
        marges, rivales = marges_d_ensemble(unites, ch) if MARGE_D_ENSEMBLE else (marges_seul, [[] for _ in unites])
        det = dict(unites=unites, choix=ch, marges=marges, groupes=groupes, seules={n: [c["photos"][n] for c in cs] for n, cs in seules.items()},
                   accords={f"{a}|{b}": round(v, 3) for (a, b), v in accords.items()})

        cameras = {}
        for u, k, g, marge, rivale in zip(unites, ch, groupes, marges, rivales):
            sure = marge > seuil_sure(len(u[k]["photos"]))
            for n, p in u[k]["photos"].items():
                cam, note, montree = np.array(p["cam"]), p["note"], p["piece"]
                if n in PM and n in pres_du_point and (note <= 0 or math.hypot(cam[0] - endroits_donnes[n][0], cam[1] - endroits_donnes[n][1]) > ECART_POINTE):
                    # la photo a été POINTÉE par NT et son bloc la met ailleurs (bloc mal recoupé : cuisine d'app-002, une photo
                    # confirmée, l'autre pointée à 2 m) : la réponse de NT passe avant le bloc, la photo prend sa propre
                    # meilleure place près du point (ses notes sont déjà limitées à la zone pointée)
                    iy, ix, kk = np.unravel_index(R[n].argmax(), R[n].shape)
                    if R[n][iy, ix, kk] > 0:
                        cam = np.array([orig[0] + ix * PAS, orig[1] + iy * PAS, float(kk), float(echelles[int(Er[n][iy, ix, kk])])])
                        note, montree = float(R[n][iy, ix, kk]), plan["ids"][PM[n][iy, ix]]
                if note <= 0:
                    non[n] = "aucune place ne colle au plan"; continue
                # (essayé le 14/11/2026 puis retiré : laisser la photo chercher seule sa meilleure place dans un rayon plus large
                #  autour du bloc DÉGRADE : app-001 5 → 3 photos à peu près placées ; le bloc est le meilleur guide)
                c2, _ = regler(plan, prof[n], cam.copy(), limites)  # réglage fin, gardé s'il reste près de la place du bloc
                if math.hypot(*(c2[:2] - cam[:2])) < 0.6 and abs((c2[2] - cam[2] + 180) % 360 - 180) < 10:
                    cam = c2
                if zoom_fin:  # le cap des fuites seulement quand les photos du lot s'accordent (sinon pièces biscornues : app-001)
                    cam[2] = cap_par_fuites(float(cam[2]), fu.get(n), sens)
                if zoom_par_fuites == "fin" and zoom_fin:
                    cam = _affiner(plan, o, photos[n], fens[n], zoom_fin, cam, fu.get(n), sens)
                ip = piece_de(plan, cam[None, :2])[0]
                if ip < 0:
                    non[n] = "placée hors des pièces"; continue
                piece = montree if n in PM else plan["ids"][ip]  # pièce donnée : celle que la photo MONTRE (l'appareil peut être sur le seuil)
                H, W = photos[n].shape[:2]; f = zoom_fin * W if (zoom_par_fuites == "fin" and zoom_fin) else mes[n]["focale_px"]; haut = mes[n]["haut"]
                cameras[n] = {
                    "camera": {"x": round(float(cam[0]), 3), "y": round(float(cam[1]), 3), "z": round(float(np.clip(prof[n]["z"], 0.3, plan["hsp"] - 0.2)), 3),
                               "cap": round(float((cam[2] + 180) % 360 - 180), 2), "tangage": 0.0, "f": round(f, 2), "u0": W / 2,
                               "v0": round(H / 2 + f * float(haut[2] / max(-haut[1], 0.2)), 2)},
                    "largeur": W, "hauteur": H, "piece": piece, "sure": bool(sure), "marge": round(float(marge), 2), "bloc": list(g),
                    "hesite_avec": [] if sure else [q for q in rivale if q != piece], "endroit": detache(n, cam, piece)}
                journal(f"  {n} : {piece}" + ("" if sure else " (pas sûr" + (", hésite avec " + " / ".join(rivale) if rivale else "") + ")"))
        # « endroit douteux » : jugé pour le BLOC entier (ses photos bougent ensemble). autre_pose : la meilleure autre pose du
        # bloc dans les mêmes pièces mais ailleurs (une photo à plus de LOIN_M, ou tournée de plus de TOURNE_DEG), en part de la
        # note de la pose choisie ; accord : la photo du bloc la plus loin de sa propre meilleure place (1 = toutes d'accord).
        for u, k in zip(unites, ch):
            la = u[k]["photos"]
            total = sum(p["note"] for p in la.values())
            autre = 0.0
            for j, c in enumerate(u):
                if j == k or any(c["photos"][n]["piece"] != p["piece"] for n, p in la.items()):
                    continue
                if any(math.hypot(c["photos"][n]["cam"][0] - p["cam"][0], c["photos"][n]["cam"][1] - p["cam"][1]) > LOIN_M
                       or abs((c["photos"][n]["cam"][2] - p["cam"][2] + 180) % 360 - 180) > TOURNE_DEG for n, p in la.items()):
                    autre = max(autre, sum(p["note"] for p in c["photos"].values()) / max(total, 1e-6))
            dans = [n for n in la if n in cameras]
            accord = min((cameras[n]["endroit"]["ici"] / max(cameras[n]["endroit"]["meilleure"], 1e-6) for n in dans), default=1.0)
            for n in dans:
                cameras[n]["endroit"].update(autre_pose=round(autre, 3), accord=round(accord, 3))
        return cameras, non, det

    muet = lambda *a: None
    seul, non_seul, det = choisir(R, T, {}, muet if PM else journal)  # l'avis d'Atelya seul
    if not PM:
        if detail is not None:  # pour les essais : de quoi rejuger le choix d'ensemble sans tout recalculer
            detail.update(det)
        _signaler_les_endroits(seul, journal)
        return {"cameras": seul, "non_calees": {**non, **non_seul}}
    cameras, non_avec, det = choisir({**R, **Rd}, {**T, **Td}, PM, journal)  # avec les pièces données par le client
    if detail is not None:
        detail.update(det, seul=seul)
    for n, d in cameras.items():
        if n not in PM:
            continue
        s = seul.get(n)
        d.update(donnee=True, colle=round(colle[n], 2), avis_seul={"piece": s["piece"], "sure": s["sure"]} if s else None)
        if n in pres_du_point:  # pointée par NT à la vérification : c'est déjà une réponse, pas de second avis
            d.update(pointee=True)
            continue
        ailleurs = None
        if s and s["sure"] and s["piece"] not in [plan["ids"][q] for q in donnees[n]]:
            ix, iy = int(round((s["camera"]["x"] - orig[0]) / PAS)), int(round((s["camera"]["y"] - orig[1]) / PAS))
            if not (0 <= iy < forme[0] and 0 <= ix < forme[1]) or PM[n][iy, ix] < 0:  # … et pas sur le seuil de la pièce donnée
                ailleurs = s["piece"]
        raison = doute_sur_la_piece_donnee(ailleurs, max(_facteur(types[n], plan["ids"][q]) for q in donnees[n]), colle[n])
        if raison and n not in confirmees:
            d.update(sure=False, a_verifier=raison)
            journal(f"  {n} : À VÉRIFIER, {raison}")
    _signaler_les_endroits(cameras, journal)
    return {"cameras": cameras, "non_calees": {**non, **non_avec}}
