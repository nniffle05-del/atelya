r"""Image « corrigé contre Atelya » pour app-003 : sur le plan, la vraie place de chaque photo (vert, cercle = incertitude du
corrigé) et la place trouvée seule par Atelya (rouge), reliées par un trait.

    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\image_corrige.py
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[2]
E, X0, Y0, K = 0.02463, 200, 620, 2  # mêmes nombres que verites/app-003/plan_vers_logement.py ; K = agrandissement


def police(t, gras=False):
    try:
        return ImageFont.truetype("arialbd.ttf" if gras else "arial.ttf", t)
    except OSError:
        return ImageFont.load_default()


def px(x, y):
    return ((x / E + X0) * K, (Y0 - y / E) * K)


def fleche(d, x, y, cap, couleur, long=38):
    a, b = px(x, y)
    c, s = math.cos(math.radians(cap)), -math.sin(math.radians(cap))
    d.line([(a, b), (a + long * c, b + long * s)], fill=couleur, width=4)
    for da in (150, -150):
        cc, ss = math.cos(math.radians(cap + da)), -math.sin(math.radians(cap + da))
        d.line([(a + long * c, b + long * s), (a + long * c + 12 * cc, b + long * s + 12 * ss)], fill=couleur, width=4)


def main():
    vrai = json.loads((RACINE / "verites/app-003/cameras-photos.json").read_text(encoding="utf-8"))["cameras"]
    seul = json.loads((RACINE / "../atelya/b2/app-003/cameras-photos-seul.json").read_text(encoding="utf-8"))
    plan = Image.open(RACINE / "../atelya/photos-clients/app-003/plan.jpg").convert("RGB")
    plan = Image.blend(plan, Image.new("RGB", plan.size, "white"), 0.45).resize((plan.width * K, plan.height * K), Image.LANCZOS)
    d = ImageDraw.Draw(plan, "RGBA")
    VERT, ROUGE = (0, 140, 60), (220, 30, 30)
    for nom, c in vrai.items():
        t = c["camera"]
        m = (seul["cameras"].get(nom) or seul["incertaines"][nom])["camera"]
        a, b = px(t["x"], t["y"])
        r = c["incertitude_m"] / E * K
        d.ellipse([a - r, b - r, a + r, b + r], fill=(0, 160, 70, 45), outline=VERT)
        d.line([px(t["x"], t["y"]), px(m["x"], m["y"])], fill=(90, 90, 90), width=2)
        fleche(d, m["x"], m["y"], m["cap"], ROUGE)
        fleche(d, t["x"], t["y"], t["cap"], VERT)
        for (x, y), coul in (((t["x"], t["y"]), VERT), ((m["x"], m["y"]), ROUGE)):
            u, v = px(x, y)
            d.ellipse([u - 7, v - 7, u + 7, v + 7], fill=coul)
        ecart = math.hypot(t["x"] - m["x"], t["y"] - m["y"])
        d.text((a + 10, b + 8), f"{int(nom[-2:])} : {ecart:.1f} m".replace(".", ","), fill=(0, 0, 0), font=police(22, True),
               stroke_width=3, stroke_fill=(255, 255, 255))
    d.rectangle([20, 20, 760, 150], fill=(255, 255, 255, 235), outline=(0, 0, 0))
    d.text((34, 28), "Troisième logement : d'où chaque photo est prise", fill=(0, 0, 0), font=police(26, True))
    d.ellipse([36, 72, 50, 86], fill=VERT)
    d.text((60, 66), "vraie place (corrigé fait à la main ; cercle = sa marge d'erreur)", fill=(0, 0, 0), font=police(21))
    d.ellipse([36, 108, 50, 122], fill=ROUGE)
    d.text((60, 102), "place trouvée seule par Atelya ; le nombre = l'écart en mètres", fill=(0, 0, 0), font=police(21))
    sortie = RACINE / "../atelya/b2/app-003/corrige/corrige-contre-atelya.png"
    plan.save(sortie)
    print("Image :", sortie)


if __name__ == "__main__":
    main()
