r"""Image de l'essai « pièce donnée par le client » (15/11/2026), d'après le bilan de pieces_donnees.py :

    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\pieces_donnees_image.py

→ ..\atelya\b2\cameras-seules\pieces-donnees\aujourd-hui-contre-piece-donnee.png : pour chaque logement, à gauche Atelya seul
(il devine la pièce), à droite avec la pièce de chaque photo donnée par le client.
"""
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from jumelles import LOGEMENTS, PC  # noqa: E402
from jumelles_image import GRIS, ORANGE, VERT, panneau, police  # noqa: E402

SORTIE = PC / "b2/cameras-seules/pieces-donnees"
TITRES = {"app-001": "Logement 1", "app-002": "Logement 2", "app-003": "Logement 3"}


def main():
    bilan = json.loads((SORTIE / "bilan.json").read_text(encoding="utf-8"))
    lignes = []
    for nom, b in bilan.items():
        f = LOGEMENTS[nom]
        logement = json.loads(f["logement"].read_text(encoding="utf-8"))
        paire = []
        for passage, quoi in (("seul", "aujourd'hui, Atelya devine la pièce"), ("client", "la pièce est donnée par le client")):
            cams = {n: {**c, "hesite_avec": [c["piece"]] if c.get("a_verifier") else []} for n, c in b[passage]["cameras"].items()}
            im, compte = panneau(nom, logement, cams, f["vrai"], f"{TITRES[nom]} — {quoi}")
            d = ImageDraw.Draw(im)
            texte = f"{compte['juste']} photos utilisées sur {b['photos']}"
            if compte["hesite"]:
                texte += f", {compte['hesite']} envoyée{'s' if compte['hesite'] > 1 else ''} en vérification"
            d.text((26, 42), texte, fill=VERT, font=police(18))
            paire.append(im)
        ligne = Image.new("RGB", (paire[0].width + paire[1].width + 20, max(p.height for p in paire)), "white")
        ligne.paste(paire[0], (0, 0)); ligne.paste(paire[1], (paire[0].width + 20, 0))
        ImageDraw.Draw(ligne).line([(paire[0].width + 10, 10), (paire[0].width + 10, ligne.height - 10)], fill=(200, 200, 200), width=2)
        lignes.append(ligne)
    leg = Image.new("RGB", (lignes[0].width, 46), "white")
    d = ImageDraw.Draw(leg)
    x = 26
    for couleur, texte in ((VERT, "photo utilisée pour les sols et les meubles (bonne pièce)"), (ORANGE, "envoyée en vérification (Atelya doute de la pièce donnée)"),
                           (GRIS, "mise de côté (Atelya n'est pas sûr de la pièce)")):
        d.ellipse([x, 12, x + 22, 34], fill=couleur)
        d.text((x + 30, 12), texte, fill=(30, 30, 30), font=police(17))
        x += 30 + d.textlength(texte, font=police(17)) + 34
    total = Image.new("RGB", (lignes[0].width, sum(l.height for l in lignes) + leg.height + 10 * len(lignes)), "white")
    y = 0
    for l in lignes:
        total.paste(l, (0, y)); y += l.height + 10
    total.paste(leg, (0, y))
    total.save(SORTIE / "aujourd-hui-contre-piece-donnee.png")
    print(SORTIE / "aujourd-hui-contre-piece-donnee.png")


if __name__ == "__main__":
    main()
