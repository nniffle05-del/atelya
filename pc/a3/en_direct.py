"""Atelya en direct : une page qui montre ce que fait Atelya sur le PC, mise à jour toutes les 2 secondes.

Lancer depuis D:\\Modélisation immobilière\\atelya :
    .venv\\Scripts\\python.exe en_direct.py
Une page s'ouvre dans le navigateur. Fermer la fenêtre noire (ou Ctrl+C) arrête l'affichage, pas les calculs.

Ce script ne fait que LIRE les fichiers des calculs en cours. Il écrit seulement dans le dossier « direct ».
- Pendant un coloriage : le plan, la vérité, le coloriage d'Atelya et ses doutes, côte à côte.
- Pendant un entraînement : la courbe d'apprentissage (notes à chaque contrôle).
- En bas : les dernières lignes du journal du calcul le plus récent.
"""
from __future__ import annotations

import html
import json
import time
import webbrowser
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ICI = Path(__file__).resolve().parent
SORTIE = ICI / "direct"
RECENT_S = 15 * 60  # une activité de moins de 15 min est « en cours »

COULEURS = {
    0: (255, 255, 255), 1: (30, 30, 30), 2: (220, 60, 60), 3: (60, 120, 230), 4: (60, 200, 230),
    5: (250, 220, 150), 6: (250, 180, 120), 7: (180, 200, 250), 8: (160, 220, 230), 9: (170, 230, 200),
    10: (220, 220, 200), 11: (210, 210, 190), 12: (190, 180, 170), 13: (190, 220, 190), 14: (220, 190, 230),
    15: (200, 200, 200),
}
TABLE = np.zeros((256, 3), np.uint8)
for _k, _c in COULEURS.items():
    TABLE[_k] = _c
COURBES = {"anciens": (40, 40, 40), "photos": (60, 120, 230), "monde": (230, 140, 30), "biais": (40, 170, 90)}


def police(t: int):
    for nom in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(nom, t)
        except OSError:
            pass
    return ImageFont.load_default()


def mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def lire_texte(p: Path) -> str:
    b = p.read_bytes()
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return b.decode("utf-16", "replace")
    return b.decode("utf-8-sig", "replace")


# ---------- coloriage en cours ----------
_jeux: dict[str, Path | None] = {}


def trouver_jeu(ident: str, niv: str, dessin: str) -> Path | None:
    """Le dessin d'origine (plan) : on le cherche dans jeu-test-6-13 et donnees\\*."""
    cle = ident
    if cle not in _jeux:
        _jeux[cle] = None
        for base in [ICI / "jeu-test-6-13", *sorted((ICI / "donnees").glob("*"))]:
            f = base / "exemples" / ident / niv / dessin
            if f.exists():
                _jeux[cle] = f
                break
    return _jeux[cle]


def dernier_coloriage() -> tuple[float, Path | None]:
    meilleur, quand = None, 0.0
    for d in [*ICI.glob("coloriages-*"), *(ICI / "vrais-plans").glob("doutes-*"), *(ICI / "vrais-plans").glob("coloriages-*")]:
        ex = d / "exemples"
        t = mtime(ex) if ex.is_dir() else mtime(d)
        if t > quand and time.time() - t < RECENT_S:
            quand, meilleur = t, d
    if not meilleur:
        return 0.0, None
    ex = meilleur / "exemples"
    if ex.is_dir():
        ids = sorted(ex.iterdir(), key=mtime)
        for ident in reversed(ids[-3:]):
            pngs = [p for p in ident.glob("niveau_*.png") if not p.stem.endswith("-doute")]
            if pngs:
                return quand, max(pngs, key=mtime)
    pngs = [p for p in meilleur.glob("*.png") if not p.stem.endswith("-doute")]
    return (quand, max(pngs, key=mtime)) if pngs else (0.0, None)


def diaporama() -> Path | None:
    """Quand rien ne colorie : un plan au hasard parmi les derniers coloriages (le plus récent dossier)."""
    import random
    ds = [d for d in ICI.glob("coloriages-*") if (d / "exemples").is_dir()]
    if not ds:
        return None
    d = max(ds, key=lambda x: mtime(x / "exemples"))
    ids = [p for p in (d / "exemples").iterdir() if p.is_dir()]
    random.shuffle(ids)
    for ident in ids[:20]:
        pngs = [p for p in ident.glob("niveau_*.png") if not p.stem.endswith("-doute")]
        if pngs:
            return random.choice(pngs)
    return None


def vue_coloriage(col_png: Path) -> tuple[Image.Image, str]:
    col = np.array(Image.open(col_png))
    h, w = col.shape[:2]
    cases = []
    niv = col_png.stem
    dossier = col_png.parent / niv
    ident = col_png.parent.name
    dessin = (dossier / "dessin.txt").read_text(encoding="utf-8").strip() if (dossier / "dessin.txt").exists() else ""
    plan = trouver_jeu(ident, niv, dessin) if dessin else None
    if plan is None and col_png.parent.name.startswith("doutes-a3"):
        for ext in (".jpg", ".jpeg", ".png"):
            f = ICI / "vrais-plans" / "lot-2026-10-31" / (col_png.stem + ext)
            if f.exists():
                plan = f
    if plan is not None:
        cases.append(("Le plan", Image.open(plan).convert("RGB").resize((w, h))))
    if (dossier / "masque_semantique.png").exists():
        vrai = np.array(Image.open(dossier / "masque_semantique.png"))
        cases.append(("La vérité", Image.fromarray(TABLE[vrai]).resize((w, h), Image.NEAREST)))
    cases.append(("Ce qu'Atelya a colorié", Image.fromarray(TABLE[col])))
    dt = col_png.with_name(col_png.stem + "-doute.png")
    if dt.exists():
        d = np.array(Image.open(dt))
        rouge = np.stack([np.full_like(d, 255), 255 - d, 255 - d], -1)
        cases.append(("Ses doutes (rouge = pas sûr)", Image.fromarray(rouge.astype(np.uint8))))
    taille = 520
    f = police(22)
    img = Image.new("RGB", (len(cases) * (taille + 20) + 20, taille + 70), "white")
    dr = ImageDraw.Draw(img)
    for i, (titre, im) in enumerate(cases):
        im = im.copy()
        im.thumbnail((taille, taille))
        x = 20 + i * (taille + 20)
        img.paste(im, (x, 55))
        dr.text((x, 15), titre, fill=(20, 20, 20), font=f)
    if col_png.parent.parent.name == "vrais-plans" or col_png.parent.name.startswith("doutes-"):
        titre = f"Vrai plan en cours : {col_png.stem} ({col_png.parent.name})"
    else:
        titre = f"Coloriage en cours : {col_png.parents[2].name}, plan {ident} {niv}"
    return img, titre


# ---------- entraînement en cours ----------
def dernier_entrainement() -> tuple[float, Path | None]:
    hs = [h for h in ICI.glob("resultats-*/historique.json") if time.time() - mtime(h) < RECENT_S]
    if not hs:
        return 0.0, None
    h = max(hs, key=mtime)
    return mtime(h), h


def vue_courbe(hist: Path) -> tuple[Image.Image, str]:
    data = json.loads(hist.read_text(encoding="utf-8"))
    W, H, g, b, hb = 1300, 620, 80, 60, 50
    img = Image.new("RGB", (W, H), "white")
    dr = ImageDraw.Draw(img)
    f, fp = police(20), police(16)
    tmax = max([p.get("minutes", 0) for p in data] + [10])
    vals = [p[k]["iou_moyen_pct"] for p in data for k in COURBES if k in p]
    vmin = max(0, min(vals + [100]) - 5)

    def xy(t, v):
        return g + (W - g - 110) * t / tmax, H - b - (H - b - hb) * (v - vmin) / (100 - vmin)

    for v in range(int(vmin // 10 * 10), 101, 10):
        if v >= vmin:
            y = xy(0, v)[1]
            dr.line([(g, y), (W - 110, y)], fill=(230, 230, 230))
            dr.text((20, y - 9), f"{v} %", fill=(120, 120, 120), font=fp)
    for t in range(0, int(tmax) + 1, 30):
        x = xy(t, vmin)[0]
        dr.text((x - 10, H - b + 10), f"{t} min", fill=(120, 120, 120), font=fp)
    lx = g
    for k, c in COURBES.items():
        pts = [xy(p.get("minutes", 0), p[k]["iou_moyen_pct"]) for p in data if k in p]
        if len(pts) > 1:
            dr.line(pts, fill=c, width=3)
        for x, y in pts[-1:]:
            dr.ellipse([x - 5, y - 5, x + 5, y + 5], fill=c)
            dr.text((x + 8, y - 10), f"{data[-1][k]['iou_moyen_pct']} %", fill=c, font=fp)
        if pts:
            dr.rectangle([lx, 15, lx + 18, 33], fill=c)
            dr.text((lx + 24, 12), k, fill=c, font=f)
            lx += 160
    dernier = data[-1]
    perte = dernier.get("perte")
    titre = (f"Entraînement en cours : {hist.parent.name} — {dernier.get('minutes', 0)} min, "
             f"pas {dernier.get('pas', 0)}" + (f", perte {perte}" if perte is not None else ""))
    return img, titre


# ---------- journal ----------
def dernier_journal() -> tuple[Path | None, list[str]]:
    js = [*ICI.glob("*.suivi"), *ICI.glob("*.log"), *ICI.glob("code-*/*.suivi")]
    js = [j for j in js if time.time() - mtime(j) < RECENT_S]
    if not js:
        return None, []
    j = max(js, key=mtime)
    lignes = [l for l in lire_texte(j).splitlines() if l.strip()]
    return j, lignes[-14:]


def page(titre: str, image: str | None, journal: Path | None, lignes: list[str]) -> str:
    img = f'<img src="{image}?t={time.time():.0f}" alt="vue">' if image else "<p class='rien'>Rien ne tourne en ce moment.</p>"
    jt = html.escape(journal.name) if journal else ""
    import re
    plantes = [l for l in lignes if re.search(r"code=(?!0\b)-?\d+", l) or "Traceback" in l or "ERREUR" in l.upper()]
    alerte = (f'<div style="background:#c0392b;color:#fff;padding:12px;border-radius:6px;font-size:17px;margin:10px 0">'
              f'⚠ Une étape a planté : {html.escape(plantes[-1].strip())}</div>') if plantes else ""
    lg = html.escape("\n".join(lignes))
    return f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta http-equiv="refresh" content="2">
<title>Atelya en direct</title><style>
body{{font-family:Segoe UI,Arial,sans-serif;margin:16px;background:#f6f5f2;color:#1d1d1d}}
h1{{font-size:20px;margin:0 0 4px}} .t{{color:#555;margin:0 0 12px}} img{{max-width:100%;border:1px solid #ddd;background:#fff}}
pre{{background:#1d1d1d;color:#e8e8e8;padding:12px;border-radius:6px;white-space:pre-wrap;font-size:13px}} .rien{{font-size:18px;color:#777}}
</style></head><body><h1>Atelya en direct</h1><p class="t">{html.escape(titre)} · mis à jour {time.strftime('%H:%M:%S')}</p>
{alerte}{img}<h2 style="font-size:16px">Journal : {jt}</h2><pre>{lg}</pre></body></html>"""


def tour() -> None:
    tc, col = dernier_coloriage()
    te, hist = dernier_entrainement()
    titre, image = "En attente d'un calcul", None
    try:
        if hist and te >= tc:
            img, titre = vue_courbe(hist)
        elif col:
            img, titre = vue_coloriage(col)
        elif (dia := diaporama()) is not None and (time.time() // 2) % 3 == 0:
            img, titre = vue_coloriage(dia)
            titre = "Diaporama (rien ne colorie en ce moment) — " + titre.split(" : ", 1)[-1]
        elif (SORTIE / "vue.png").exists() and dia is not None:
            img, titre = None, "Diaporama (rien ne colorie en ce moment)"
            image = "vue.png"
        else:
            img = None
        if img is not None:
            tmp = SORTIE / "vue-tmp.png"
            img.save(tmp)
            tmp.replace(SORTIE / "vue.png")
            image = "vue.png"
    except Exception as e:  # un fichier en cours d'écriture : on réessaie au tour suivant
        titre = f"(lecture en cours… {type(e).__name__})"
        image = "vue.png" if (SORTIE / "vue.png").exists() else None
    j, lignes = dernier_journal()
    tmp = SORTIE / "index-tmp.html"
    tmp.write_text(page(titre, image, j, lignes), encoding="utf-8")
    tmp.replace(SORTIE / "index.html")


def main() -> None:
    SORTIE.mkdir(exist_ok=True)
    tour()
    webbrowser.open((SORTIE / "index.html").as_uri())
    print("Atelya en direct : la page s'est ouverte dans le navigateur. Fermer cette fenêtre pour arrêter.")
    while True:
        time.sleep(2)
        tour()


if __name__ == "__main__":
    main()
