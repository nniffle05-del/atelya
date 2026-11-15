r"""Image « corrigé contre Atelya » pour app-002 : le plan (dessiné d'après verites/app-002/logement.json), la vraie place de
chaque photo (vert, cercle = marge d'erreur du corrigé soigné) et la place trouvée seule par Atelya (rouge), côte à côte pour
plusieurs variantes.

    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\image_corrige_app002.py <image> <fiche 1> "<titre 1>" [<fiche 2> "<titre 2>" ...]
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[2]
K, MARGE = 84.0, 70  # pixels par mètre, marge autour du plan
DECALAGE = {1: (-118, 14), 4: (14, 14), 10: (-118, -34), 14: (-52, -46), 15: (-30, 24), 6: (20, -4)}  # place des étiquettes
VERT, ROUGE = (0, 140, 60), (220, 30, 30)
NOMS = {"sejour_1": "Séjour", "chambre_1": "Chambre", "chambre_2": "Chambre", "cuisine_1": "Cuisine", "entree_1": "Entrée"}


def police(t, gras=False):
    try:
        return ImageFont.truetype("arialbd.ttf" if gras else "arial.ttf", t)
    except OSError:
        return ImageFont.load_default()


def panneau(logement, vrai, seul, titre):
    xs = [p[0] for m in logement["murs"] for p in (m["debut"], m["fin"])]
    ys = [p[1] for m in logement["murs"] for p in (m["debut"], m["fin"])]
    x0, y1 = min(xs), max(ys)
    w, h = int((max(xs) - x0) * K) + 2 * MARGE + 40, int((y1 - min(ys)) * K) + 2 * MARGE + 150

    def px(x, y):
        return (MARGE + (x - x0) * K, 150 + MARGE + (y1 - y) * K)

    im = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(im, "RGBA")
    for p in logement["pieces"]:
        d.polygon([px(*q) for q in p["contour"]], fill=(244, 240, 232))
        if p["id"] in NOMS:
            cx = sum(q[0] for q in p["contour"]) / len(p["contour"])
            cy = sum(q[1] for q in p["contour"]) / len(p["contour"])
            d.text(px(cx - 0.5, cy - (1.2 if p["id"].startswith("chambre") else -0.2)), NOMS[p["id"]], fill=(150, 140, 125), font=police(22))
    for m in logement["murs"]:
        d.line([px(*m["debut"]), px(*m["fin"])], fill=(60, 60, 60), width=max(3, int(m.get("epaisseur", 0.1) * K)))
    murs = {m["id"]: m for m in logement["murs"]}
    for o in logement["ouvertures"]:
        m = murs[o["mur"]]
        a, b = m["debut"], m["fin"]
        long = math.hypot(b[0] - a[0], b[1] - a[1])
        u = ((b[0] - a[0]) / long, (b[1] - a[1]) / long)
        p, q = o["position"], o["position"] + o["largeur"]
        d.line([px(a[0] + u[0] * p, a[1] + u[1] * p), px(a[0] + u[0] * q, a[1] + u[1] * q)],
               fill=(120, 190, 240) if "fenetre" in o["type"] else (255, 255, 255), width=max(3, int(m.get("epaisseur", 0.1) * K)))

    def fleche(x, y, cap, couleur, long=34):
        a, b = px(x, y)
        c, s = math.cos(math.radians(cap)), -math.sin(math.radians(cap))
        d.line([(a, b), (a + long * c, b + long * s)], fill=couleur, width=4)
        for da in (150, -150):
            cc, ss = math.cos(math.radians(cap + da)), -math.sin(math.radians(cap + da))
            d.line([(a + long * c, b + long * s), (a + long * c + 11 * cc, b + long * s + 11 * ss)], fill=couleur, width=4)

    ecarts = []
    for nom, c in vrai.items():
        t = c["camera"]
        autre = seul["cameras"].get(nom) or seul.get("incertaines", {}).get(nom)
        a, b = px(t["x"], t["y"])
        r = c["incertitude_m"] * K
        d.ellipse([a - r, b - r, a + r, b + r], fill=(0, 160, 70, 40), outline=VERT)
        if autre:
            m = autre["camera"]
            d.line([px(t["x"], t["y"]), px(m["x"], m["y"])], fill=(90, 90, 90), width=2)
            fleche(m["x"], m["y"], m["cap"], ROUGE)
            u, v = px(m["x"], m["y"])
            d.ellipse([u - 6, v - 6, u + 6, v + 6], fill=ROUGE)
            ecarts.append(math.hypot(t["x"] - m["x"], t["y"] - m["y"]))
        fleche(t["x"], t["y"], t["cap"], VERT)
        d.ellipse([a - 6, b - 6, a + 6, b + 6], fill=VERT)
        texte = f"{int(nom[-2:])} : {ecarts[-1]:.1f} m".replace(".", ",") if autre else f"{int(nom[-2:])} : pas placée"
        ox, oy = DECALAGE.get(int(nom[-2:]), (10, 10))
        d.text((a + ox, b + oy), texte, fill=(0, 0, 0), font=police(22, True), stroke_width=3, stroke_fill=(255, 255, 255))
    ecarts.sort()
    mediane = ecarts[len(ecarts) // 2] if len(ecarts) % 2 else (ecarts[len(ecarts) // 2 - 1] + ecarts[len(ecarts) // 2]) / 2
    d.text((MARGE, 18), titre, fill=(0, 0, 0), font=police(28, True))
    d.text((MARGE, 58), f"écart médian {mediane:.2f} m, au pire {ecarts[-1]:.2f} m ({len(ecarts)} photos)".replace(".", ","), fill=(0, 0, 0), font=police(22))
    d.ellipse([MARGE, 100, MARGE + 14, 114], fill=VERT)
    d.text((MARGE + 24, 94), "vraie place (corrigé soigné ; cercle = sa marge d'erreur)", fill=(0, 0, 0), font=police(19))
    d.ellipse([MARGE, 128, MARGE + 14, 142], fill=ROUGE)
    d.text((MARGE + 24, 122), "place trouvée seule par Atelya ; le nombre = l'écart en mètres", fill=(0, 0, 0), font=police(19))
    return im


def main():
    logement = json.loads((RACINE / "verites/app-002/logement.json").read_text(encoding="utf-8"))
    vrai = json.loads((RACINE / "verites/app-002/cameras-photos-soigne.json").read_text(encoding="utf-8"))["cameras"]
    paires = list(zip(sys.argv[2::2], sys.argv[3::2]))
    images = [panneau(logement, vrai, json.loads(Path(f).read_text(encoding="utf-8")), t) for f, t in paires]
    tout = Image.new("RGB", (max(i.width for i in images), sum(i.height for i in images)), "white")
    y = 0
    for i in images:
        tout.paste(i, (0, y))
        y += i.height
    tout.save(sys.argv[1])
    print("Image :", sys.argv[1])


if __name__ == "__main__":
    main()
