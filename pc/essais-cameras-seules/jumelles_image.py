r"""Images de l'étape « chambres jumelles » (15/11/2026), d'après les tirages rangés par jumelles.py :

    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\jumelles_image.py

  ..\atelya\b2\cameras-seules\jumelles\avant-apres-app-002.png : le deuxième logement, AVANT / APRÈS, toutes les photos puis une
        photo du séjour en moins (les chambres jumelles s'échangent) ;
  ..\atelya\b2\cameras-seules\jumelles\avant-apres-app-003.png : le troisième logement, deux tirages où un bloc mêlait deux pièces ;
  ..\atelya\b2\cameras-seules\jumelles\bilan.png : le décompte de tous les tirages (lit bilan.json, écrit par « juger »).
Chaque photo est un disque à son numéro, posé où Atelya la place, avec un trait vers où elle regarde.
"""
import json
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from jumelles import LOGEMENTS, SORTIE  # noqa: E402

VERT, ROUGE, ORANGE, GRIS = (20, 150, 70), (215, 30, 30), (235, 140, 0), (150, 150, 150)
POLICE = RACINE / "moteur/polices/DejaVuSans.ttf"
NOMS = {"sejour": "Séjour", "chambre": "Chambre", "cuisine": "Cuisine", "salle_d_eau": "Salle d'eau", "entree": "Entrée", "degagement": "Couloir"}


def police(t):
    return ImageFont.truetype(str(POLICE), t)


def nom_de_piece(logement_nom, ident):
    if logement_nom == "app-003" and ident == "sejour_2":
        return "Salle à manger"
    sorte, _, num = ident.rpartition("_")
    if sorte not in NOMS:
        return ""
    return NOMS[sorte] + (f" {num}" if sorte == "chambre" else "")


def panneau(nom, logement, cameras, vrai, titre, largeur=760):
    pts = [q for p in logement["pieces"] for q in p["contour"]]
    x0, x1 = min(q[0] for q in pts), max(q[0] for q in pts)
    y0, y1 = min(q[1] for q in pts), max(q[1] for q in pts)
    marge, haut = 26, 64
    k = (largeur - 2 * marge) / (x1 - x0)
    h = int((y1 - y0) * k) + 2 * marge + haut
    px = lambda x, y: (marge + (x - x0) * k, haut + marge + (y1 - y) * k)
    im = Image.new("RGB", (largeur, h), "white")
    d = ImageDraw.Draw(im)
    d.text((marge, 14), titre, fill=(20, 20, 20), font=police(24))
    for p in logement["pieces"]:
        d.polygon([px(*q) for q in p["contour"]], fill=(246, 242, 234), outline=(70, 70, 70))
        d.line([px(*q) for q in p["contour"]] + [px(*p["contour"][0])], fill=(70, 70, 70), width=3)
    murs = {m["id"]: m for m in logement["murs"]}
    for o in logement.get("ouvertures", []):
        m = murs.get(o.get("mur"))
        if m is None:
            continue
        a, b = m["debut"], m["fin"]
        long = math.hypot(b[0] - a[0], b[1] - a[1])
        u = ((b[0] - a[0]) / long, (b[1] - a[1]) / long)
        p, q = o["position"], o["position"] + o["largeur"]
        d.line([px(a[0] + u[0] * p, a[1] + u[1] * p), px(a[0] + u[0] * q, a[1] + u[1] * q)],
               fill=(246, 242, 234) if o["type"] == "porte" else (90, 170, 235), width=7)
    for p in logement["pieces"]:
        t = nom_de_piece(nom, p["id"])
        xs, ys = [q[0] for q in p["contour"]], [q[1] for q in p["contour"]]
        if t and (max(xs) - min(xs)) * k > 90:
            f = police(17)
            c = px((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
            d.text((c[0] - d.textlength(t, font=f) / 2, c[1] - 10), t, fill=(150, 140, 125), font=f)
    compte = {"juste": 0, "fausse": 0, "hesite": 0, "pas_sure": 0}
    ordre = sorted(cameras.items(), key=lambda x: x[1]["sure"])  # les photos sûres dessinées par-dessus
    for n, c in ordre:
        juste = c["piece"] in vrai[n]
        if c["sure"]:
            couleur = VERT if juste else ROUGE; compte["juste" if juste else "fausse"] += 1
        elif any(h.rpartition("_")[0] == c["piece"].rpartition("_")[0] for h in c.get("hesite_avec", [])):  # hésite avec une pièce de même sorte
            couleur = ORANGE; compte["hesite"] += 1
        else:
            couleur = GRIS; compte["pas_sure"] += 1
        x, y = px(c["cam"][0], c["cam"][1])
        cap = math.radians(c["cam"][2])
        d.line([(x, y), (x + 30 * math.cos(cap), y - 30 * math.sin(cap))], fill=couleur, width=5)
        r = 15 if c["sure"] else 12
        d.ellipse([x - r, y - r, x + r, y + r], fill=couleur, outline="white", width=2)
        f = police(15 if c["sure"] else 12)
        t = n[-2:].lstrip("0")
        d.text((x - d.textlength(t, font=f) / 2, y - (9 if c["sure"] else 7)), t, fill="white", font=f)
    return im, compte


def legende(largeur):
    im = Image.new("RGB", (largeur, 46), "white")
    d = ImageDraw.Draw(im)
    x = 26
    for couleur, texte in ((VERT, "sûre et juste"), (ROUGE, "dite sûre mais dans la MAUVAISE pièce"), (ORANGE, "pas sûre : hésite entre deux pièces semblables (mise de côté)"),
                           (GRIS, "pas sûre (mise de côté)")):
        d.ellipse([x, 12, x + 22, 34], fill=couleur)
        d.text((x + 30, 12), texte, fill=(30, 30, 30), font=police(17))
        x += 30 + d.textlength(texte, font=police(17)) + 34
    return im


def planche(nom, rangs, sortie):
    f = LOGEMENTS[nom]
    logement = json.loads(f["logement"].read_text(encoding="utf-8"))
    tout = json.loads((SORTIE / f"{nom}.json").read_text(encoding="utf-8"))
    lignes = []
    for tirage, quoi in rangs:
        paire = []
        for variante, quand in (("avant", "AVANT"), ("coupe", "APRÈS")):
            im, c = panneau(nom, logement, tout[variante][tirage]["cameras"], f["vrai"], f"{quand} — {quoi}")
            d = ImageDraw.Draw(im)
            bilan = f"{c['juste']} sûres et justes"
            bilan += f", {c['fausse']} sûres mais FAUSSES" if c["fausse"] else ", aucune sûre à tort"
            d.text((26, 42), bilan, fill=ROUGE if c["fausse"] else VERT, font=police(18))
            paire.append(im)
        ligne = Image.new("RGB", (paire[0].width + paire[1].width + 20, max(p.height for p in paire)), "white")
        ligne.paste(paire[0], (0, 0)); ligne.paste(paire[1], (paire[0].width + 20, 0))
        ImageDraw.Draw(ligne).line([(paire[0].width + 10, 10), (paire[0].width + 10, ligne.height - 10)], fill=(200, 200, 200), width=2)
        lignes.append(ligne)
    leg = legende(lignes[0].width)
    total = Image.new("RGB", (lignes[0].width, sum(l.height for l in lignes) + leg.height + 10 * len(lignes)), "white")
    y = 0
    for l in lignes:
        total.paste(l, (0, y)); y += l.height + 10
    total.paste(leg, (0, y))
    total.save(sortie)
    print(sortie)


def image_bilan(sortie):
    b = json.loads((SORTIE / "bilan.json").read_text(encoding="utf-8"))
    titres = {"app-001": "Logement 1", "app-002": "Logement 2", "app-003": "Logement 3"}
    L, H = 1330, 150 + 118 * len(b)
    im = Image.new("RGB", (L, H), "white")
    d = ImageDraw.Draw(im)
    d.text((30, 20), "Photos dites « sûres » mais rangées dans la MAUVAISE pièce", fill=(20, 20, 20), font=police(26))
    nb = sum(x[f"{lot} / AVANT"]["tirages"] for x in b.values() for lot in ("tirages regardés", "tirages NOUVEAUX"))
    d.text((30, 58), f"sur {nb} rejouements des trois logements (une ou deux photos en moins, plan faux de 3 à 8 %, autre zoom)", fill=(90, 90, 90), font=police(17))
    maxi = max(1, max(sum(x[f"{lot} / AVANT"][k] for lot in ("tirages regardés", "tirages NOUVEAUX") for k in ("fausses_meme_sorte", "fausses_autre_sorte")) for x in b.values()))
    y = 110
    for nom, x in b.items():
        d.text((30, y + 22), titres.get(nom, nom), fill=(30, 30, 30), font=police(20))
        for i, (quand, couleur) in enumerate((("AVANT", ROUGE), ("APRÈS", VERT))):
            meme = sum(x[f"{lot} / {quand}"]["fausses_meme_sorte"] for lot in ("tirages regardés", "tirages NOUVEAUX"))
            autre = sum(x[f"{lot} / {quand}"]["fausses_autre_sorte"] for lot in ("tirages regardés", "tirages NOUVEAUX"))
            justes = sum(x[f"{lot} / {quand}"]["justes"] for lot in ("tirages regardés", "tirages NOUVEAUX"))
            yy = y + 6 + i * 40
            d.text((190, yy + 4), quand.lower(), fill=(60, 60, 60), font=police(17))
            w1, w2 = int(330 * meme / maxi), int(330 * autre / maxi)
            d.rectangle([270, yy, 270 + w1, yy + 28], fill=couleur)
            d.rectangle([270 + w1, yy, 270 + w1 + w2, yy + 28], fill=(190, 190, 190))
            d.text((270 + w1 + w2 + 12, yy + 4), f"{meme + autre} sûres à tort, dont {meme} entre pièces de même sorte   |   {justes} sûres et justes", fill=(40, 40, 40), font=police(17))
        y += 118
    d.text((30, H - 34), "couleur : chambre prise pour une autre chambre, séjour pour la salle à manger ; gris : cuisine, salle d'eau ou chambre rangée dans le séjour (étape suivante)",
           fill=(110, 110, 110), font=police(14))
    im.save(sortie)
    print(sortie)


if __name__ == "__main__":
    planche("app-002", [("service", "toutes les photos"), ("sans-03", "une photo du séjour en moins")], SORTIE / "avant-apres-app-002.png")
    planche("app-003", [("sans-01", "une photo de la salle à manger en moins"), ("sans-05", "une photo du séjour en moins")], SORTIE / "avant-apres-app-003.png")
    if (SORTIE / "bilan.json").is_file():
        image_bilan(SORTIE / "bilan.png")
