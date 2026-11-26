"""L'APPAREIL DANS UN MEUBLE (26/11/2026), la CAUSE de chaque cas : on croise appareils et meubles d'Atelya avec ceux relevés à la main.

Pour chaque photo touchée : (1) l'appareil d'Atelya dans les meubles relevés à la main ; (2) l'appareil relevé à la main dans les
meubles d'Atelya ; (3) l'appareil relevé à la main dans les meubles relevés à la main ; et l'écart entre les deux appareils.
Si (3) est propre et (2) bouché : le meuble d'Atelya est faux. Si (3) est propre et (1) bouché : l'appareil d'Atelya est faux.
Si (3) est bouché lui-même : le photographe est vraiment contre le meuble (ou le relevé est approché).

    python pc/verification/croiser_appareils_dans_meubles.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mesurer_appareils_dans_meubles import boites, mesurer_photo  # noqa: E402

ICI = Path(__file__).resolve().parents[2]
L = ICI.parent / "atelya" / "lectures-photos"
C = ICI.parent / "atelya" / "b2" / "place-appareils" / "chaine" / "sol-partout"

CAS = {
    "app-001": {"atelya_log": C / "app-001/c/logement-meuble.json", "atelya_cam": C / "app-001/c/cameras-photos-affinees.json",
                "film_log": L / "sol-des-photos/app-001/logement-meuble.json", "main_cam": ICI / "verites/app-001/cameras-photos.json",
                "main_log": ICI / "verites/app-001/logement.json",
                "main_meubles": [ICI / "verites/app-001/meubles.json", ICI / "verites/app-001/meubles-complement.json"]},
    "app-002": {"atelya_log": C / "app-002/c/logement-meuble.json", "atelya_cam": C / "app-002/c/cameras-photos-affinees.json",
                "film_log": L / "sol-des-photos/app-002/logement-meuble.json", "main_cam": ICI / "verites/app-002/cameras-photos.json",
                "soigne_cam": ICI / "verites/app-002/cameras-photos-soigne.json",
                "main_log": ICI / "verites/app-002/logement.json",
                "main_meubles": [ICI / "verites/app-002/meubles.json", ICI / "verites/app-002/meubles-complement.json"]},
}


def lire(p: Path) -> dict:
    return json.loads(Path(p).read_text(encoding="utf-8"))


def cams(p: Path) -> dict:
    return {k: (v.get("camera") or v, v) for k, v in lire(p).get("cameras", {}).items() if "x" in (v.get("camera") or v)}


def avec_meubles(logement: dict, meubles: list[dict]) -> dict:
    d = dict(logement)
    d["meubles"] = meubles
    return d


def resume(r: dict) -> str:
    t = f"bouché {r['bouche']:.0%}"
    if r["dedans"]:
        t += " DEDANS " + ",".join(r["dedans"])
    if r["bouche_par"]:
        t += " par " + ", ".join(f"{k} {v:.0%}" for k, v in list(r["bouche_par"].items())[:2])
    return t


def main() -> None:
    for nom, c in CAS.items():
        log_a = lire(c["atelya_log"])
        log_m = lire(c["main_log"])
        meubles_m = [m for f in c["main_meubles"] for m in lire(f).get("meubles", [])]
        b_aa = boites(log_a)  # plan + meubles d'Atelya
        b_mm = boites(avec_meubles(log_m, meubles_m))  # plan relevé + meubles relevés
        ca, cm = cams(c["atelya_cam"]), cams(c["main_cam"])
        cs = cams(c["soigne_cam"]) if "soigne_cam" in c else {}
        print(f"\n===== {nom}")
        for photo in sorted(set(ca) | set(cm)):
            lignes = []
            if photo in ca:
                cam, e = ca[photo]
                lignes.append(("Atelya, meubles d'Atelya", mesurer_photo(cam, e.get("largeur", 1206), e.get("hauteur", 800), b_aa)))
                lignes.append(("Atelya, meubles à la main", mesurer_photo(cam, e.get("largeur", 1206), e.get("hauteur", 800), b_mm)))
            for etiquette, src in (("main", cm), ("soigné", cs)):
                if photo in src:
                    cam, e = src[photo]
                    lignes.append((f"{etiquette}, meubles d'Atelya", mesurer_photo(cam, e.get("largeur", 1206), e.get("hauteur", 800), b_aa)))
                    lignes.append((f"{etiquette}, meubles à la main", mesurer_photo(cam, e.get("largeur", 1206), e.get("hauteur", 800), b_mm)))
            if not any(r["bouche"] >= 0.05 or r["dedans"] for _, r in lignes):
                continue
            ecart = ""
            if photo in ca and photo in cm:
                a, m = ca[photo][0], cm[photo][0]
                ecart = (f"  appareil Atelya ↔ main : {math.hypot(a['x'] - m['x'], a['y'] - m['y']):.2f} m à plat, "
                         f"hauteur {a['z']:.2f} / {m['z']:.2f}, cap {a['cap']:.0f} / {m['cap']:.0f}, "
                         f"qualité main « {cm[photo][1].get('qualite', '?')} »")
            print(f"--- {photo} (pièce {ca.get(photo, cm.get(photo, ({}, {})))[1].get('piece')}){ecart}")
            for etiquette, r in lignes:
                print(f"      {etiquette:28s} {resume(r)}")


if __name__ == "__main__":
    main()
