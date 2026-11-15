r"""LE SIGNAL « ENDROIT DOUTEUX » (15/11/2026, étape 2 de l'écran enchaîné) : quand la pièce d'une photo est connue, Atelya
peut encore se tromper de PLACE dans la pièce (cuisine d'app-002 : 2 m à côté ; salle d'eau d'app-001 : tournée à l'envers)
sans le savoir. Y a-t-il, dans ce que le calage calcule déjà, de quoi le deviner ?

    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\endroit_douteux.py mesurer [app-001 app-002 app-003]
    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\endroit_douteux.py juger [seuil autre_pose] [seuil accord]

« mesurer » : pour chaque logement, moteur/caler_photos.py avec la pièce donnée par le client, dans plusieurs TIRAGES (comme
jumelles.py : trois logements, c'est trois tirages, un seuil réglé dessus serait flatteur) :
  client, sorte       : la pièce exacte / seulement la sorte de pièce (« chambre ») ;
  plan±3, ±5, ±8, ns+5, eo+5 : le plan agrandi, rétréci, étiré (pièce exacte donnée) ;
  sans-NN             : une photo en moins.
Pour chaque photo qui a un relevé de sa vraie place : l'écart en mètres et en degrés, et les indices du champ « endroit » de
caler_photos (ici, ailleurs, tournee, meilleure : la photo seule ; autre_pose, accord : son bloc).
« juger » : une photo est MAL PLACÉE à plus de 1 m ou de 45° du relevé. Le signal se juge par BLOC (les photos d'un bloc
bougent ensemble) : combien de blocs qui contiennent une photo mal placée sont signalés, combien de blocs sains le sont à tort.
Sorties : ..\atelya\b2\cameras-seules\endroit-douteux\mesures.json (une ligne par photo et par tirage).
"""
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "habillage"))
from moteur import caler_photos as cp  # noqa: E402
from moteur.images import lire_image  # noqa: E402
from jumelles import LOGEMENTS, PC, etirer, memoire  # noqa: E402
from pieces_donnees import CLIENT, RELEVES  # noqa: E402

SORTIE = PC / "b2/cameras-seules/endroit-douteux"
MAL_M, MAL_DEG = 1.0, 45.0
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def surface(contour) -> float:
    c = np.array(contour, float)
    return float(abs(np.sum(c[:, 0] * np.roll(c[:, 1], -1) - np.roll(c[:, 0], -1) * c[:, 1])) / 2)


def mesurer(noms: list[str]) -> list[dict]:
    o = cp.Outils()
    memoire(o)
    gardees, lignes = [], []
    for nom in noms:
        f = LOGEMENTS[nom]
        logement = json.loads(f["logement"].read_text(encoding="utf-8"))
        photos = {n: cv2.cvtColor(lire_image(f["photos"] / f"{n}.{f['ext']}"), cv2.COLOR_BGR2RGB) for n in f["vrai"]}
        gardees.append(photos)
        cartes = {}
        for n, rgb in photos.items():
            c = PC / "b2/cameras-seules/aspect" / f"{nom}-{n}.npy"
            cartes[n] = np.load(c)[..., 2].astype(np.float32) if c.is_file() else o.fenetres.proba(cp.Fenetres.carres(o.oeil, rgb))
        client = {n: CLIENT.get(nom, {}).get(n, v[0]) for n, v in f["vrai"].items()}
        client = {n: p for n, p in client.items() if p}
        sorte = {n: cp.sorte_de_piece(p) for n, p in client.items()}
        releves = [json.loads(r.read_text(encoding="utf-8")) for r in RELEVES[nom]]
        surfaces = {p["id"]: surface(p["contour"]) for p in logement["pieces"]}
        tirages = [("client", list(photos), client, (1.0, 1.0)), ("sorte", list(photos), sorte, (1.0, 1.0))]
        tirages += [(f"plan{k:+d}", list(photos), client, (1 + k / 100, 1 + k / 100)) for k in (3, -3, 5, -5, 8, -8)]
        tirages += [("plan-ns+5", list(photos), client, (1.0, 1.05)), ("plan-eo+5", list(photos), client, (1.05, 1.0))]
        tirages += [(f"sans-{n[-2:]}", [m for m in photos if m != n], client, (1.0, 1.0)) for n in photos]
        for titre, lot, pieces, (sx, sy) in tirages:
            r = cp.caler(etirer(logement, sx, sy) if (sx, sy) != (1.0, 1.0) else logement, {n: photos[n] for n in lot}, outils=o, journal=lambda *a: None,
                         fenetres_de=cartes, pieces_donnees={n: p for n, p in pieces.items() if n in lot})
            for n, d in sorted(r["cameras"].items()):
                vraie = next((x["cameras"][n]["camera"] for x in releves if n in x["cameras"]), None)
                c = d["camera"]
                lignes.append({
                    "logement": nom, "tirage": titre, "photo": n, "piece": d["piece"], "bonne_piece": d["piece"] in f["vrai"][n], "sure": d["sure"],
                    "ecart_m": None if vraie is None else round(math.hypot(c["x"] - vraie["x"] * sx, c["y"] - vraie["y"] * sy), 2),
                    "ecart_deg": None if vraie is None else round(abs((c["cap"] - vraie["cap"] + 180) % 360 - 180), 1),
                    **d["endroit"], "bloc": d["bloc"], "surface": round(surfaces.get(d["piece"], 0.0) * sx * sy, 1),
                    "colle": d.get("colle"), "marge": d["marge"], "a_verifier": bool(d.get("a_verifier")), "cam": [c["x"], c["y"], c["cap"]]})
            mal = [x for x in lignes if x["logement"] == nom and x["tirage"] == titre and x["ecart_m"] is not None and (x["ecart_m"] > MAL_M or x["ecart_deg"] > MAL_DEG)]
            print(f"{nom} {titre:10s} : {len(r['cameras'])} photos placées, mal placées (relevé) : {', '.join(x['photo'][-2:] + ' ' + str(x['ecart_m']) + ' m' for x in mal) or 'aucune'}", flush=True)
    return lignes


def mal_placee(x: dict) -> bool | None:
    return None if x["ecart_m"] is None else (x["ecart_m"] > MAL_M or x["ecart_deg"] > MAL_DEG)


def tableau(lignes: list[dict], tirages=("client", "sorte")) -> None:
    print(f"{'':8s} {'':7s} {'photo':9s} {'pièce':15s} {'m²':>5s} {'bloc':>4s} {'écart':>6s} {'cap':>5s} | {'ici':>6s} {'aill.':>6s} {'tourn.':>6s} {'meill.':>6s} | "
          f"{'a/i':>5s} {'t/i':>5s} | {'autre':>5s} {'accord':>6s} {'colle':>5s}")
    for x in sorted(lignes, key=lambda x: (x["tirage"], x["logement"], x["photo"])):
        if x["tirage"] not in tirages:
            continue
        i = max(x["ici"], 1e-6)
        ecart = "     ?" if x["ecart_m"] is None else f"{x['ecart_m']:6.2f}"
        cap = "    ?" if x["ecart_deg"] is None else f"{x['ecart_deg']:5.0f}"
        print(f"{x['logement']:8s} {x['tirage']:7s} {x['photo']:9s} {x['piece']:15s} {x['surface']:5.1f} {len(x['bloc']):4d} {ecart} {cap} | {x['ici']:6.3f} {x['ailleurs']:6.3f} "
              f"{x['tournee']:6.3f} {x['meilleure']:6.3f} | {x['ailleurs'] / i:5.2f} {x['tournee'] / i:5.2f} | {x['autre_pose']:5.2f} {x['accord']:6.2f} "
              f"{x['colle'] if x['colle'] is not None else 0:5.2f}{'' if x['sure'] else '  (pas sûre)'}{'  <<< MAL PLACÉE' if mal_placee(x) else ''}")


def juger(lignes: list[dict], seuil_autre: float, seuil_accord: float) -> None:
    """Par bloc : signalé (autre_pose ≥ seuil, ou accord < seuil) contre « contient une photo mal placée ». Les blocs dont
    aucune photo n'a de relevé ne comptent pas ; ceux dont la pièce est fausse ou pas sûre non plus (déjà une question)."""
    blocs = {}
    for x in lignes:
        blocs.setdefault((x["logement"], x["tirage"], tuple(x["bloc"])), []).append(x)
    lots = {"client + sorte (regardés pour choisir les seuils)": lambda t: t in ("client", "sorte"), "plans faux de 3 à 8 %": lambda t: t.startswith("plan"),
            "une photo en moins": lambda t: t.startswith("sans")}
    print(f"\nSeuils : autre pose ≥ {seuil_autre}, accord < {seuil_accord}")
    for titre, dans in lots.items():
        vp = fp = fn = vn = photos_signalees = photos = mal_vues = mal = 0
        rates = []
        for (lg, tirage, _), xs in blocs.items():
            if not dans(tirage):
                continue
            xs = [x for x in xs if x["sure"] and x["bonne_piece"]]  # photos qui partiraient aux sols et aux meubles sans question
            connues = [x for x in xs if mal_placee(x) is not None]
            if not connues:
                continue
            signale = xs[0]["autre_pose"] >= seuil_autre or xs[0]["accord"] < seuil_accord
            fautif = any(mal_placee(x) for x in connues)
            vp += signale and fautif; fp += signale and not fautif; fn += fautif and not signale; vn += not signale and not fautif
            photos += len(xs); photos_signalees += len(xs) * signale
            mal += sum(bool(mal_placee(x)) for x in connues); mal_vues += sum(bool(mal_placee(x)) for x in connues) * signale
            if fautif and not signale:
                rates.append(f"{lg} {tirage} {xs[0]['piece']} ({', '.join(x['photo'][-2:] + ' ' + str(x['ecart_m']) + ' m' for x in connues if mal_placee(x))} ; autre {xs[0]['autre_pose']}, accord {xs[0]['accord']})")
        print(f"  {titre} : blocs avec une photo mal placée {vp + fn}, signalés {vp} ; blocs sains {fp + vn}, signalés à tort {fp} ; "
              f"photos mal placées vues {mal_vues} sur {mal} ; questions en plus : {photos_signalees} photos sur {photos}")
        for x in rates[:12]:
            print(f"      manqué : {x}")


if __name__ == "__main__":
    try:
        SORTIE.mkdir(parents=True, exist_ok=True)
        args = sys.argv[2:]
        if sys.argv[1] == "mesurer":
            L = mesurer(args or list(LOGEMENTS))
            (SORTIE / "mesures.json").write_text(json.dumps(L, ensure_ascii=False, indent=1), encoding="utf-8")
        else:
            L = json.loads((SORTIE / "mesures.json").read_text(encoding="utf-8"))
        tableau(L)
        juger(L, float(args[0]) if sys.argv[1] == "juger" and args else 0.95, float(args[1]) if sys.argv[1] == "juger" and len(args) > 1 else 0.6)
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
