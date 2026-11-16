r"""LE BANC DE FIDÉLITÉ : la maquette d'Atelya jugée contre les photos, objet par objet, sur tous les logements à la fois.

    ..\atelya\.venv\Scripts\python.exe outils\atelya\banc_fidelite.py <dossier du banc> [--titre "…"] [--cas app-001 app-004]
        [--logement NOM logement.json fiche.json …] [--sans-chaine]

Pourquoi : juger chaque changement d'Atelya sur TOUS les logements, en quelques minutes, par une note qui voit ce qui manque,
ce qui est en trop et ce qui est mal placé (moteur/fidelite_photos.py). C'est le juge de la maquette 3D (priorité de NT du
16/11/2026). Les planches « photo | maquette rendue » se font avec outils/atelya/banc_ressemblance.py.

Pour chaque cas de CAS (outils/atelya/banc_ressemblance.py) : la maquette est REFAITE par Atelya seul avec le code du jour
(enveloppe, baies, sols, meubles : pas besoin de Blender), puis chaque photo est jugée. Écrit dans le dossier du banc :
bilan.json (tout le détail), bilan.txt (le tableau), planche-<logement>.jpg (les photos annotées : vert = la maquette l'a,
rouge = il manque, bleu = la maquette l'a en trop).
--logement (répétable) : juger un logement DÉJÀ fait (comparer deux versions sans rien refaire).
Les rectangles du détecteur sont gardés dans ..\atelya\banc-fidelite\detections (les mêmes pour toutes les versions).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
PC = RACINE.parent / "atelya"

from banc_ressemblance import CAS, construire, dire, lire_photo  # noqa: E402

from moteur import fidelite_photos as fp  # noqa: E402

VERT, ROUGE, BLEU, CYAN = (20, 170, 60), (225, 30, 30), (40, 90, 235), (0, 190, 210)
NOMS = {"lit": "lit", "canape": "canapé", "fauteuil": "fauteuil", "chaise": "chaise", "table": "table", "rangement": "rangement",
        "tapis": "tapis", "lampe": "lampe", "plante": "plante", "baie": "fenêtre", "porte": "porte", "cheminee": "cheminée",
        "television": "télévision", "luminaire": "luminaire", "rideaux": "rideaux", "radiateur": "radiateur", "tableau": "tableau",
        "miroir": "miroir", "baignoire": "baignoire", "douche": "douche", "wc": "WC", "lavabo": "lavabo / évier",
        "cuisine": "meubles de cuisine", "electromenager": "électroménager"}


def _police(taille: int):
    try:
        return ImageFont.truetype("arialbd.ttf", taille)
    except OSError:
        return ImageFont.load_default()


class Detecteur:
    """OWLv2 avec le vocabulaire du banc ; les rectangles bruts de chaque photo sont gardés sur le disque."""

    def __init__(self):
        self.phrases = list(fp.VOCABULAIRE)
        self.cle = hashlib.sha1("|".join(self.phrases).encode()).hexdigest()[:10]
        self.dossier = PC / "banc-fidelite" / "detections" / self.cle
        self.dossier.mkdir(parents=True, exist_ok=True)
        self.owl = self.requetes = None

    def brut(self, fiche: dict, nom: str, rgb: np.ndarray) -> list[dict]:
        cache = self.dossier / (hashlib.sha1(f"{fiche['photos']}/{nom}".encode()).hexdigest()[:16] + ".json")
        if cache.is_file():
            return json.loads(cache.read_text(encoding="utf-8"))
        if self.owl is None:
            from moteur.owlv2 import charger
            self.owl = charger()
            self.requetes = self.owl.textes(self.phrases)
        from moteur.owlv2 import objets
        d = objets(self.owl.detecter(rgb, self.requetes), self.phrases, seuil=0.1, recouvrement_max=0.7)
        cache.write_text(json.dumps(d), encoding="utf-8")
        return d


def juger(nom: str, logement: dict, fiche: dict, detecteur: Detecteur) -> dict:
    from moteur.camera_photo import camera_depuis_dict

    elements, murs = fp.elements_de_la_maquette(logement), fp._murs_et_trous(logement)
    photos = {}
    for photo, c in fiche["cameras"].items():
        rgb = lire_photo(fiche, photo)
        h, w = rgb.shape[:2]
        cam = camera_depuis_dict(c["camera"])
        photos[photo] = fp.juger_une_photo(detecteur.brut(fiche, photo, rgb), logement, cam, w, h, elements, murs)
    return {"resume": fp.compter(list(photos.values())), "photos": photos}


def planche(titre: str, fiche: dict, jugement: dict, sortie: Path, colonnes: int = 3, largeur: int = 640) -> None:
    police, grande = _police(15), _police(24)
    cases = []
    for nom in sorted(jugement["photos"]):
        j = jugement["photos"][nom]
        image = Image.fromarray(lire_photo(fiche, nom))
        k = largeur / image.width
        image = image.resize((largeur, int(image.height * k)), Image.LANCZOS)
        d = ImageDraw.Draw(image)
        def cadre(o, couleur, texte, epais=3, pointille=False):
            x0, y0, x1, y1 = (v * k for v in o["boite"])
            if pointille:
                for x in range(int(x0), int(x1), 14):
                    d.line([(x, y0), (min(x + 7, x1), y0)], fill=couleur, width=epais)
                    d.line([(x, y1), (min(x + 7, x1), y1)], fill=couleur, width=epais)
                for y in range(int(y0), int(y1), 14):
                    d.line([(x0, y), (x0, min(y + 7, y1))], fill=couleur, width=epais)
                    d.line([(x1, y), (x1, min(y + 7, y1))], fill=couleur, width=epais)
            else:
                d.rectangle([x0, y0, x1, y1], outline=couleur, width=epais)
            if texte:
                l = d.textlength(texte, font=police)
                d.rectangle([x0, max(0, y0 - 18), x0 + l + 6, max(18, y0)], fill=couleur)
                d.text((x0 + 3, max(0, y0 - 18)), texte, fill="white", font=police)
        for o in j["maquette"]:
            if o["paire"] is None:
                cadre(o, BLEU, "en trop : " + NOMS.get(o["sorte"], o["sorte"]), 3, pointille=True)
        for o in j["photo"]:
            if o["paire"] is None:
                cadre(o, ROUGE, "manque : " + NOMS.get(o["sorte"], o["sorte"]), 3)
            else:
                cadre(o, VERT, NOMS.get(o["sorte"], o["sorte"]) + (" (bien placé)" if o["recouvrement"] >= fp.BIEN_PLACE else ""), 3)
        bande = Image.new("RGB", (largeur, 26), "white")
        ImageDraw.Draw(bande).text((6, 4), nom, fill="black", font=police)
        case = Image.new("RGB", (largeur, image.height + 26), "white")
        case.paste(bande, (0, 0))
        case.paste(image, (0, 26))
        cases.append(case)
    if not cases:
        return
    h = max(c.height for c in cases)
    lignes = (len(cases) + colonnes - 1) // colonnes
    feuille = Image.new("RGB", (colonnes * (largeur + 10), 78 + lignes * (h + 8)), "white")
    t = ImageDraw.Draw(feuille)
    t.text((8, 6), titre, fill="black", font=grande)
    t.text((8, 42), "vert : la maquette l'a   |   rouge : visible sur la photo, absent de la maquette   |   bleu pointillé : dans la maquette, pas sur la photo",
           fill=(70, 70, 70), font=police)
    for i, c in enumerate(cases):
        feuille.paste(c, ((i % colonnes) * (largeur + 10), 78 + (i // colonnes) * (h + 8)))
    feuille.save(sortie, quality=88)


def tableau(bilan: dict) -> str:
    lignes = [f"BANC DE FIDÉLITÉ {bilan.get('titre', '')} ({bilan['date']})", ""]
    lignes.append(f"{'logement':14s} {'photos':>6s} {'fidélité':>9s} {'couverture':>11s} {'bien placé':>11s} {'justesse':>9s}")
    for nom, l in (*bilan["logements"].items(), ("ENSEMBLE", {"resume": bilan["ensemble"]})):
        r = l["resume"]
        lignes.append(f"{nom:14s} {r['photos']:6d} {r['fidelite']:8.1f}  {100 * r['couverture']:9.1f} %  {100 * r['bien_place']:9.1f} %  {100 * r['justesse']:7.1f} %")
    lignes += ["", "Par sorte d'objet, tous logements (du plus lourd manque au plus léger) :",
               f"{'sorte':20s} {'vus':>5s} {'présents':>9s} {'bien placés':>12s} {'dans la maquette':>17s} {'en trop':>8s} {'poids du manque':>16s}"]
    for sorte, s in sorted(bilan["ensemble"]["par_sorte"].items(), key=lambda kv: -kv[1]["poids_manque"]):
        lignes.append(f"{NOMS.get(sorte, sorte):20s} {s['vus']:5d} {s['presents']:9d} {s['bien_places']:12d} {s['dans_la_maquette']:17d} {s['en_trop']:8d} {s['poids_manque']:16.2f}")
    return "\n".join(lignes)


def main() -> int:
    ap = argparse.ArgumentParser(description="Banc de fidélité de la maquette aux photos, objet par objet")
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--cas", nargs="*", default=list(CAS))
    ap.add_argument("--logement", nargs=3, action="append", default=[], metavar=("NOM", "LOGEMENT.json", "FICHE.json"))
    ap.add_argument("--titre", default="")
    ap.add_argument("--sans-chaine", action="store_true", help="reprendre les logements déjà refaits dans ce dossier")
    a = ap.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
    travaux = []
    if a.logement:
        travaux = [(nom, lire(logement), lire(fiche)) for nom, logement, fiche in a.logement]
    else:
        for cas in a.cas:
            fait = a.sortie / cas / "logement-meuble.json"
            if not (a.sans_chaine and fait.is_file()):
                debut = time.time()
                dire(f"{cas} : Atelya refait le logement (sols, baies, meubles)…")
                construire(cas, CAS[cas], a.sortie / cas, jusqu_a="meubles")
                dire(f"{cas} : refait en {time.time() - debut:.0f} s")
            travaux.append((cas, lire(fait), lire(CAS[cas]["fiche"])))
    detecteur = Detecteur()
    bilan = {"version": fp.VERSION, "titre": a.titre, "date": time.strftime("%Y-%m-%d %H:%M"), "logements": {}}
    toutes = []
    for nom, logement, fiche in travaux:
        j = juger(nom, logement, fiche, detecteur)
        bilan["logements"][nom] = j
        toutes += list(j["photos"].values())
        r = j["resume"]
        planche(f"{nom} {a.titre} : fidélité {r['fidelite']:.0f}/100 (la maquette a {100 * r['couverture']:.0f} % de ce que les photos montrent)",
                fiche, j, a.sortie / f"planche-{nom}.jpg")
    bilan["ensemble"] = fp.compter(toutes)
    (a.sortie / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    texte = tableau(bilan)
    (a.sortie / "bilan.txt").write_text(texte, encoding="utf-8")
    dire(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
