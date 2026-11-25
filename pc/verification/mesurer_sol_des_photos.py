r"""LE SOL PRIS POUR UN LIT (25/11/2026) : la MESURE, avant de rien changer.

    ..\atelya\.venv\Scripts\python.exe pc\verification\mesurer_sol_des_photos.py [--logements app-001 app-004] [--seuil 0.10]

Pour mesurer une hauteur sur une photo (tringle, haut et bas d'une fenêtre, objet accroché, taille d'un meuble), Atelya remet le
relief de la photo (MoGe-2) entre le SOL et le PLAFOND. Deux règles du sol existent :
  - EN SERVICE (moteur.caler_photos.repere) : le sol = la plus GRANDE surface à plat sous l'appareil (le plus gros pic) ;
  - celle de la brique des appareils (moteur.affiner_appareils.repere_du_mur) : la surface à plat la plus BASSE qui pèse au
    moins un quart de la plus grande.
Ici, sur toutes les photos des quatre logements (58), on compare les deux : hauteur de l'appareil au-dessus du sol selon
chacune, contre la hauteur de l'appareil relevé à la main (corrigés) ou affiné ; de même pour le plafond ; et la hauteur sous
plafond que chaque règle donnerait (moteur.hauteur_photos a sa propre copie de la règle en service).
Chaque photo où les deux règles diffèrent de plus de `seuil` est dessinée (rouge = le « sol » de la règle en service, vert = le
sol le plus bas ; bleu / jaune de même pour le plafond) pour être REGARDÉE : lit, plan de travail, table, tapis, estrade ?

Sorties : ..\atelya\b2\sol-des-photos\mesure\ (mesure.json, une image par photo touchée).
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "pc" / "essais-place-appareils"))
sys.path.insert(0, str(RACINE / "outils" / "habillage"))
sys.path.insert(0, str(RACINE / "pc" / "essais-cameras-seules"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import caler_photos as cp, moge  # noqa: E402
from moteur.affiner_appareils import _niveau  # noqa: E402
from moteur.hauteur_photos import ARRONDI, PHOTOS_MIN, VRAISEMBLABLE  # noqa: E402
from moteur.images import ecrire_image  # noqa: E402
from caler import cas  # noqa: E402

PC = RACINE.parent / "atelya"
SORTIE = PC / "b2/sol-des-photos/mesure"
FICHES = PC / "b2/place-appareils/defaut"  # les appareils tels qu'ils sortent aujourd'hui (affinés)
CORRIGES = {"app-001": RACINE / "verites/app-001/cameras-photos.json", "app-002": RACINE / "verites/app-002/cameras-photos-soigne.json",
            "app-003": RACINE / "verites/app-003/cameras-photos.json"}
lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731


def pics(v: np.ndarray, pas: float = 0.02) -> list[tuple[float, float]]:
    """Tous les pics de l'histogramme des hauteurs `v` : (niveau, poids en part du plus gros), les plus gros d'abord."""
    if len(v) < 30:
        return []
    h, b = np.histogram(v, bins=np.arange(v.min() - pas, v.max() + 2 * pas, pas))
    h = np.convolve(h, np.ones(3), "same")
    k = [i for i in range(len(h)) if h[i] >= 0.05 * h.max() and h[i] >= h[max(0, i - 3):i + 4].max()]
    return sorted(((float(b[i] + pas / 2), float(h[i] / h.max())) for i in k), key=lambda t: -t[1])


def niveaux(mes: dict) -> dict:
    """Sol et plafond du relief (mètres de MoGe-2, 0 = l'appareil, + = vers le haut) selon les deux règles."""
    h = mes["points"] @ mes["haut"]
    horiz = mes["masque"] & (np.abs(mes["normales"] @ mes["haut"]) > 0.95)
    bas, haut = h[horiz & (h < -0.4)], h[horiz & (h > 0.3)]
    return {"h": h, "horiz": horiz, "sol_pic": cp._pic(bas), "sol_bas": _niveau(bas, True), "plaf_pic": cp._pic(haut),
            "plaf_haut": _niveau(haut, False), "pics_bas": pics(bas), "pics_haut": pics(haut), "points_bas": int(len(bas)),
            "points_haut": int(len(haut))}


def lecture(sol, plaf, hsp):
    """Comme repere : l'échelle (recalée sur la hauteur sous plafond si sol et plafond se voient) et la hauteur de l'appareil."""
    if sol is None and plaf is None:
        return None
    ech = hsp / (plaf - sol) if sol is not None and plaf is not None and 0.75 < hsp / (plaf - sol) < 1.33 else 1.0
    if sol is None:
        sol = plaf - hsp / ech
    return {"z": -sol * ech, "ech": ech, "brut": (plaf - sol) if plaf is not None else None}


def dessin(rgb, n, chemin):
    im = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR).astype(np.float32)
    H, W = n["h"].shape[:2]
    if im.shape[:2] != (H, W):
        im = cv2.resize(im, (W, H))
    for cle, couleur in (("sol_pic", (0, 0, 255)), ("sol_bas", (0, 200, 0)), ("plaf_pic", (255, 80, 0)), ("plaf_haut", (0, 220, 255))):
        if n[cle] is None:
            continue
        m = n["horiz"] & (np.abs(n["h"] - n[cle]) < 0.04)
        im[m] = 0.45 * im[m] + 0.55 * np.array(couleur, np.float32)
    ecrire_image(chemin, im.clip(0, 255).astype(np.uint8))


def main():
    args = sys.argv[1:]
    seuil = float(args[args.index("--seuil") + 1]) if "--seuil" in args else 0.10
    noms = ["app-001", "app-002", "app-003", "app-004"]
    if "--logements" in args:
        noms = [a for a in args[args.index("--logements") + 1:] if not a.startswith("--") and a.startswith("app-")]
    SORTIE.mkdir(parents=True, exist_ok=True)
    modele = moge.charger()
    bilan = {}
    for nom in noms:
        c = cas(nom)
        hsp = float(c["logement"].get("logement", c["logement"]).get("hauteur_sous_plafond", 2.5))
        fiche = lire(FICHES / f"{nom}.json")["cameras"] if (FICHES / f"{nom}.json").is_file() else {}
        corrige = lire(CORRIGES[nom])["cameras"] if nom in CORRIGES else {}
        b = bilan[nom] = {"hsp": hsp, "photos": {}}
        print(f"\n=== {nom} (hauteur sous plafond {hsp:.2f} m, {len(c['photos'])} photos)")
        print("photo     pièce            | appareil au-dessus du sol : service  le plus bas | main  affiné | plafond brut : service  le plus haut | sol-plafond : service  bas/haut | pics à plat sous l'appareil (m sous l'appareil : poids)")
        for n in sorted(c["photos"]):
            rgb = c["photos"][n]
            d = fiche.get(n)
            f = float(d["camera"]["f"]) * rgb.shape[1] / float(d.get("largeur", rgb.shape[1])) if d else None
            ligne = {"piece": (d or {}).get("piece") or c["pieces"].get(n), "f_fiche": f}
            for mode, focale in (("fiche", f), ("libre", None)):
                if mode == "fiche" and f is None:
                    continue
                mes = cp.mesurer(modele, rgb, focale)
                nv = niveaux(mes)
                A, B = lecture(nv["sol_pic"], nv["plaf_pic"], hsp), lecture(nv["sol_bas"], nv["plaf_haut"], hsp)
                ligne[mode] = {"service": A, "bas": B, "sol_pic": nv["sol_pic"], "sol_bas": nv["sol_bas"], "plaf_pic": nv["plaf_pic"],
                               "plaf_haut": nv["plaf_haut"], "pics_bas": nv["pics_bas"][:6], "pics_haut": nv["pics_haut"][:6],
                               "points_bas": nv["points_bas"], "points_haut": nv["points_haut"], "focale": mes["focale_px"]}
                touche_sol = nv["sol_pic"] is not None and nv["sol_bas"] is not None and abs(nv["sol_pic"] - nv["sol_bas"]) > seuil
                touche_plaf = nv["plaf_pic"] is not None and nv["plaf_haut"] is not None and abs(nv["plaf_pic"] - nv["plaf_haut"]) > seuil
                ligne[mode]["touche_sol"], ligne[mode]["touche_plaf"] = bool(touche_sol), bool(touche_plaf)
                if mode == ("fiche" if f is not None else "libre"):
                    if touche_sol or touche_plaf:
                        dessin(rgb, nv, SORTIE / f"{nom}-{n}.jpg")
                    z_main = corrige.get(n, {}).get("camera", {}).get("z")
                    z_aff = d["camera"]["z"] if d and d.get("affine", {}).get("comment") not in (None, "depart") else None
                    ligne["z_main"], ligne["z_affine"] = z_main, z_aff
                    fmt = lambda x, s="{:5.2f}": s.format(x) if x is not None else "  -  "  # noqa: E731
                    print(f"{n} {str(ligne['piece'])[:16]:16s} | {fmt(A and A['z'])}  {fmt(B and B['z'])} {'SOL' if touche_sol else '   '} | {fmt(z_main)} {fmt(z_aff)} | "
                          f"{fmt(nv['plaf_pic'])}  {fmt(nv['plaf_haut'])} {'PLAFOND' if touche_plaf else '       '} | {fmt(A and A['brut'])}  {fmt(B and B['brut'])} | "
                          + "  ".join(f"{-p:.2f}:{w:.2f}" for p, w in sorted(nv["pics_bas"][:6])), flush=True)
            b["photos"][n] = ligne
        # la hauteur sous plafond que chaque règle donnerait (relief au zoom libre de MoGe-2, comme moteur.hauteur_photos)
        for cle in ("service", "bas"):
            v = [p["libre"][cle]["brut"] for p in b["photos"].values() if p["libre"][cle] and p["libre"][cle]["brut"] is not None]
            bonnes = [x for x in v if VRAISEMBLABLE[0] <= x <= VRAISEMBLABLE[1]]
            b[f"hsp_{cle}"] = round(round(float(np.median(bonnes)) / ARRONDI) * ARRONDI, 2) if len(bonnes) >= PHOTOS_MIN else None
            b[f"hsp_{cle}_brute"] = float(np.median(bonnes)) if bonnes else None
            b[f"hsp_{cle}_photos"] = len(bonnes)
        print(f"hauteur sous plafond d'après les photos : règle en service {b['hsp_service']} m (médiane {b['hsp_service_brute']:.3f}, {b['hsp_service_photos']} photos) ; "
              f"sol le plus bas / plafond le plus haut {b['hsp_bas']} m (médiane {b['hsp_bas_brute']:.3f}, {b['hsp_bas_photos']} photos)")
    (SORTIE / "mesure.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    for mode in ("fiche", "libre"):
        s = [(l, n) for l, b in bilan.items() for n, p in b["photos"].items() if mode in p and p[mode]["touche_sol"]]
        pl = [(l, n) for l, b in bilan.items() for n, p in b["photos"].items() if mode in p and p[mode]["touche_plaf"]]
        tot = sum(1 for b in bilan.values() for p in b["photos"].values() if mode in p)
        print(f"\n[zoom {mode}] sur {tot} photos : SOL différent de plus de {seuil:.2f} m sur {len(s)} : " + ", ".join(f"{l[-3:]}/{n[-2:]}" for l, n in s))
        print(f"[zoom {mode}]                PLAFOND différent sur {len(pl)} : " + ", ".join(f"{l[-3:]}/{n[-2:]}" for l, n in pl))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
