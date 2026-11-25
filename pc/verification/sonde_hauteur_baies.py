r"""SONDE (23/11/2026) : LE BAS ET LE HAUT DES FENÊTRES d'après les photos, sur tous les logements.

    ..\atelya\.venv\Scripts\python.exe pc\verification\sonde_hauteur_baies.py [app-001 app-002 app-004] [--images <dossier>] [--sans-relief]

Pour chaque baie : ce que chaque photo en dit par les LIGNES lues (sol, bas et haut de la menuiserie, plafond :
moteur.hauteur_baies.niveaux_d_une_photo), le SECOND AVIS du relief de la photo, puis ce que la règle en conclut
(moteur.hauteur_baies.corriger). La lecture est prise dans verites/<logement>/lecture_des_vitrages.py (pas besoin de
réécrire vitrages.json pour essayer). Rien n'est écrit dans les logements.
Avec --images : par photo et par baie, la photo au contraste renforcé avec le tour de la menuiserie (BLEU), la ligne du sol
(MAGENTA), celle du plafond (JAUNE) et les quatre niveaux sur la verticale du milieu (ronds ROUGES) : à REGARDER.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(RACINE / "pc" / "verification"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PC = RACINE.parent / "atelya"
LOGEMENTS = {"app-001": PC / "lectures-photos" / "tringle" / "app-001" / "logement-meuble.json",
             "app-002": PC / "lectures-photos" / "dessin-fenetres" / "app-002" / "logement-meuble.json",
             "app-004": PC / "lectures-photos" / "tringle" / "app-004" / "logement-meuble.json"}


ECARTS: dict[str, list[float]] = {"bas": [], "haut": []}
ENTRE_PHOTOS: list[float] = []
BILAN = {"changees": 0, "doutes": 0}


def lecture_de(cas: str) -> dict:
    from ecrire_vitrages import notes_de
    from moteur import vitrages

    lecture = {"format": vitrages.FORMAT, "photos": notes_de(cas)}
    defauts = vitrages.controler(lecture)
    if defauts:
        raise SystemExit(f"PLANTÉ : lecture des fenêtres de {cas} à corriger\n  " + "\n  ".join(defauts))
    return lecture


def mesurer(cas: str, relief: bool = True, logement: dict | None = None, journal=print):
    """(logement, mesures par baie, changements, doutes) pour ce logement, avec la lecture du jour."""
    from banc_ressemblance import CAS
    from moteur import hauteur_baies as hb

    if logement is None:
        logement = json.loads(LOGEMENTS[cas].read_text(encoding="utf-8"))
    lecture = lecture_de(cas)
    fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
    reperes, tailles = (None, None)
    if relief:
        noms = {p for p, fs in lecture["photos"].items() if any(f.get("cadre") for f in fs)}
        reperes, tailles = hb.reperes_des_photos(fiche, RACINE, float(logement.get("hauteur_sous_plafond", 2.5)), noms=noms)
    brut: dict = {}
    mesures = hb.lire(logement, lecture, reperes, tailles, brut=brut)
    for baie, par_photo in brut.items():  # une baie dont rien ne se conclut garde ses mesures brutes (pour les montrer)
        mesures.setdefault(baie, {"sans_accord": True, "mesures": par_photo})
    _, changes, doutes = hb.corriger(logement, {b: m for b, m in mesures.items() if not m.get("sans_accord")}, journal=journal)
    return logement, mesures, changes, doutes


def sonder(cas: str, images_vers: Path | None, relief: bool) -> None:
    logement, mesures, changes, doutes = mesurer(cas, relief, journal=None)
    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    print(f"\n=== {cas} (hauteur sous plafond {hsp:.2f} m)")
    m_ = lambda v: "  ?  " if v is None else f"{v:5.2f}"  # noqa: E731
    for o in logement["ouvertures"]:
        if o["type"] == "porte":
            continue
        allege, haut = float(o.get("allege", 0.0) or 0.0), float(o.get("allege", 0.0) or 0.0) + float(o["hauteur"])
        m = mesures.get(o["id"])
        print(f"  {o['id']:4s} {o['type']:13s} aujourd'hui de {allege:.2f} à {haut:.2f} m"
              + ("" if m is None or m.get("sans_accord") else f"  →  vue de {m_(None if m['bas'] is None else m['bas'] * hsp).strip()} à {'au moins ' if m.get('haut_au_moins') else ''}{m['haut'] * hsp:.2f} m ({m['par']} ; "
                 f"écart entre photos {m.get('ecart_entre_photos', 0):.2f} m ; relief {m.get('relief')})"))
        for p in (m or {}).get("mesures", []):
            r = p.get("relief") or {}
            print(f"         {p['photo']} : lignes bas {m_(p['bas'] * hsp if 'bas' in p else None)} haut {m_(p['haut'] * hsp if 'haut' in p else None)}"
                  f" | dessous/hauteur {m_(p.get('dessous'))} dessus/hauteur {m_(p.get('dessus'))}"
                  f" | relief bas {m_(r.get('bas'))} haut {m_(r.get('haut'))}")
    for c in changes:
        a, b = c["avant"], c["apres"]
        print(f"  → {c['id']} : {a['type']} de {a['allege']:.2f} à {a['allege'] + a['hauteur']:.2f} m  devient  {b['type']} de "
              f"{b['allege']:.2f} à {b['allege'] + b['hauteur']:.2f} m ({c['par']})")
    for d in doutes:
        print(f"  ?? {d['id']} : vu {d['vu']} mais {d['raison']}")
    # LES DEUX MESURES, photo par photo : les lignes lues contre le relief de la photo (deux instruments indépendants)
    for bout in ("bas", "haut"):
        ECARTS[bout] += [abs(p[bout] * hsp - p["relief"][bout]) for m in mesures.values() for p in m.get("mesures", [])
                         if bout in p and bout in (p.get("relief") or {}) and not p.get("haut_au_moins") and not p.get("bas_cache")]
    ENTRE_PHOTOS.extend(m["ecart_entre_photos"] for m in mesures.values() if len(m.get("photos", [])) >= 2 and m.get("par") == "sol et plafond")
    BILAN["changees"] += len(changes)
    BILAN["doutes"] += len(doutes)
    if images_vers is not None:
        dessiner(cas, mesures, images_vers)


def dessiner(cas: str, mesures: dict, sortie: Path) -> None:
    import cv2
    import numpy as np

    from banc_ressemblance import CAS
    from moteur import hauteur_baies as hb
    from moteur.images import ecrire_image, lire_image
    from preparer_vitrages import agrandir, contraste, photo_de

    lecture = lecture_de(cas)
    fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
    sortie.mkdir(parents=True, exist_ok=True)
    for photo, fenetres in lecture["photos"].items():
        for baie in sorted({f["baie"] for f in fenetres if f.get("cadre")}):
            fs = [f for f in fenetres if f["baie"] == baie]
            porteur = next(f for f in fs if f.get("cadre"))
            niveaux = hb.niveaux_d_une_photo(fs)
            image = contraste(lire_image(photo_de(fiche, Path(CAS[cas]["fiche"]).parent, photo)))
            h, w = image.shape[:2]
            tour = np.array(porteur["cadre"], float)
            sol = next((hb.points(f.get("sol")) for f in fs if f.get("sol") is not None), [])
            plafond = next((hb.points(f.get("plafond")) for f in fs if f.get("plafond") is not None), [])
            tous = np.array([*tour, *sol, *plafond])
            x0, x1 = int(max(0, tous[:, 0].min() - 60)), int(min(w, tous[:, 0].max() + 60))

            def dessus(vue, k, cx, cy, tour=tour, sol=sol, plafond=plafond, niveaux=niveaux):
                vers = lambda p: (int(round((p[0] - cx) * k)), int(round((p[1] - cy) * k)))  # noqa: E731
                cv2.polylines(vue, [np.array([vers(p) for p in tour], np.int32)], True, (255, 80, 0), 1, cv2.LINE_AA)
                for pts, couleur in ((sol, (255, 0, 255)), (plafond, (0, 220, 255))):
                    for p in pts:
                        cv2.drawMarker(vue, vers(p), couleur, cv2.MARKER_CROSS, 22, 1)
                    if len(pts) >= 2:
                        cv2.line(vue, vers(pts[0]), vers(pts[-1]), couleur, 1, cv2.LINE_AA)
                for nom, p in ((niveaux or {}).get("points") or {}).items():
                    cv2.circle(vue, vers(p), 5, (0, 0, 255), 1, cv2.LINE_AA)
                return vue

            for nom, (y0, y1) in (("entier", (0, h)), ("haut", (0, int(min(h, tour[:, 1].min() + 60)))),
                                  ("bas", (int(max(0, tour[:, 1].max() - 60)), h))):
                ecrire_image(sortie / f"{cas}-{photo}-{baie}-{nom}.jpg", agrandir(image.copy(), [x0, y0, x1, y1], dessus))
    print(f"  images de contrôle → {sortie}")


if __name__ == "__main__":
    arguments = sys.argv[1:]
    images = None
    if "--images" in arguments:
        i = arguments.index("--images")
        images = Path(arguments[i + 1])
        del arguments[i:i + 2]
    relief = "--sans-relief" not in arguments
    arguments = [a for a in arguments if not a.startswith("--")]
    for cas in arguments or ["app-001", "app-002", "app-004"]:
        sonder(cas, images, relief)
    moyenne = lambda v: "?" if not v else f"{100 * sum(v) / len(v):.0f} cm (au pire {100 * max(v):.0f} cm, {len(v)} mesures)"  # noqa: E731
    print(f"\nJUGE DU BAS ET DU HAUT DES FENÊTRES : {BILAN['changees']} baie(s) changée(s), {BILAN['doutes']} doute(s) ; "
          f"lignes contre relief, photo par photo : bas {moyenne(ECARTS['bas'])}, haut {moyenne(ECARTS['haut'])} ; "
          f"entre deux photos de la même baie : {moyenne(ENTRE_PHOTOS)}")
