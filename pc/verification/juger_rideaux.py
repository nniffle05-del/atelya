r"""LE JUGE DES RIDEAUX, 1re pièce (19/11/2026) : les rideaux d'un logement fait par Atelya contre le relevé fait à la main.

    ..\atelya\.venv\Scripts\python.exe pc\verification\juger_rideaux.py app-004=<logement-meuble.json> [app-001=<…>]

Le relevé (verites/<logement>/rideaux.json) dit, pour chaque fenêtre dont une photo montre l'habillage : voilage ou non, rideaux
épais ou non, combien de pans et de quel côté (« gauche » / « droite », vu de la pièce, face à la fenêtre). Ce juge compare :
la SORTE (voilage, rideaux épais), le NOMBRE de pans et leur CÔTÉ. Il ne regarde pas le film : il dit si le LOGEMENT est juste ;
le film se regarde à côté de la photo (pc/verification/vues_rideaux.sh). Code de sortie 0 même s'il y a des fautes : on lit.

2e pièce (22/11/2026, étape b) : pour chaque pan relevé (« mesures » du relevé), sa LARGEUR (juste à 30 % ou 8 cm près), ce
qui pend DEVANT la fenêtre (à 10 cm près, quand le relevé le dit) et son ÉTAT (ouvert / tiré). Le relevé donne la largeur en
part de la largeur de la fenêtre (quand la fenêtre se voit) ou en mètres ; tout est comparé en mètres dans la maquette.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from moteur import equipements as eq  # noqa: E402


def pans_vus_de_la_piece(ouverture: dict, logement: dict) -> list[str]:
    """Les pans de rideaux épais de l'ouverture, dits « gauche » / « droite » vu de la pièce (sans mesure : les deux)."""
    r = ouverture.get("rideaux") or {}
    if not r.get("rideaux"):
        return []
    if not r.get("pans"):
        return ["droite", "gauche"]
    baie = eq.repere_de_la_baie(ouverture, logement)
    # vu de la pièce, la fin du mur est à gauche quand la normale (vers la pièce) est à gauche du mur
    fin_a_gauche = float(baie["t"][0] * baie["n"][1] - baie["t"][1] * baie["n"][0]) > 0
    cote = {"fin": "gauche" if fin_a_gauche else "droite", "debut": "droite" if fin_a_gauche else "gauche"}
    return sorted(cote[p["cote"]] for p in r["pans"])


TOLERANCE_LARGEUR = (0.30, 0.08)  # juste à 30 % près, ou à 8 cm près
TOLERANCE_DEVANT = 0.10  # m


def pans_mesures(ouverture: dict, logement: dict) -> dict[str, dict]:
    """Chaque pan de l'ouverture, dit « gauche » / « droite » vu de la pièce : sa largeur, ce qui pend devant la baie (m), son
    état, tels que la maquette les construit (moteur/pans_rideaux.py ; un pan jamais mesuré : 45 cm, dont 30 devant, ouvert)."""
    from moteur import pans_rideaux as pr

    r = ouverture.get("rideaux") or {}
    if not r.get("rideaux"):
        return {}
    baie = eq.repere_de_la_baie(ouverture, logement)
    fin_a_gauche = float(baie["t"][0] * baie["n"][1] - baie["t"][1] * baie["n"][0]) > 0
    sortie = {}
    for sens, pan in pr.cotes(r.get("pans")):
        interieur, exterieur = pr.etendue(baie["demi"], pan)
        nom = "gauche" if (sens > 0) == fin_a_gauche else "droite"
        sortie[nom] = {"largeur": exterieur - interieur, "devant": max(0.0, baie["demi"] - interieur), "etat": pr.etat(pan, baie["demi"]),
                       "mesure": bool((pan or {}).get("largeur"))}
    return sortie


def juger_les_mesures(verite: dict, logement: dict) -> dict:
    """Largeur, part devant la fenêtre et état de chaque pan relevé."""
    ouvertures = {o["id"]: o for o in logement.get("ouvertures", [])}
    bilan = {"pans": 0, "largeur": 0, "devant": 0, "devant_juges": 0, "etat": 0, "ecarts": [], "lignes": []}
    for ident, v in verite["fenetres"].items():
        o = ouvertures.get(ident)
        if o is None or not v.get("mesures"):
            continue
        baie = float(o["largeur"])
        atelya = pans_mesures(o, logement)
        for cote, m in v["mesures"].items():
            vraie = m["largeur_part"] * baie if "largeur_part" in m else m["largeur_m"]
            a = atelya.get(cote)
            bilan["pans"] += 1
            if a is None:
                bilan["lignes"].append(f"  FAUX   {ident:4s} pan {cote:7s} photos : {vraie:.2f} m, {m['etat']:6s} Atelya : pas de pan")
                continue
            ecart = a["largeur"] - vraie
            juste = abs(ecart) <= max(TOLERANCE_LARGEUR[0] * vraie, TOLERANCE_LARGEUR[1])
            bilan["largeur"] += juste
            bilan["ecarts"].append(abs(ecart) / vraie)
            bilan["etat"] += a["etat"] == m["etat"]
            devant = ""
            if "devant_part" in m:
                vrai_devant = m["devant_part"] * baie
                bon = abs(a["devant"] - vrai_devant) <= TOLERANCE_DEVANT
                bilan["devant_juges"] += 1
                bilan["devant"] += bon
                devant = f" ; devant la fenêtre {vrai_devant * 100:.0f} cm → {a['devant'] * 100:.0f} cm{'' if bon else ' (FAUX)'}"
            bilan["lignes"].append(f"  {'juste' if juste else 'FAUX '}  {ident:4s} pan {cote:7s} photos : {vraie:.2f} m, {m['etat']:6s} "
                                   f"Atelya : {a['largeur']:.2f} m ({ecart / vraie:+.0%}), {a['etat']:6s}{'' if a['etat'] == m['etat'] else ' (FAUX)'}"
                                   f"{devant}{'' if a['mesure'] else ' ; pan jamais mesuré'}")
    return bilan


def juger(cas: str, logement: dict) -> dict:
    verite = json.loads((RACINE / "verites" / cas / "rideaux.json").read_text(encoding="utf-8"))
    ouvertures = {o["id"]: o for o in logement.get("ouvertures", [])}
    bilan = {"fenetres": 0, "sorte": 0, "nombre": 0, "cote": 0, "lignes": []}
    for ident, v in verite["fenetres"].items():
        o = ouvertures.get(ident)
        r = (o or {}).get("rideaux") or {}
        pans = pans_vus_de_la_piece(o, logement) if o else []
        sorte = bool(r.get("voilage")) == v["voilage"] and bool(r.get("rideaux")) == v["rideaux"]
        nombre = sorte and len(pans) == len(v["pans"])
        cote = nombre and pans == sorted(v["pans"])
        bilan["fenetres"] += 1
        bilan["sorte"] += sorte
        bilan["nombre"] += bool(nombre)
        bilan["cote"] += bool(cote)
        dire = lambda voilage, epais, p: " + ".join(x for x in ("voilage" if voilage else "", f"rideaux ({', '.join(p) or '—'})" if epais else "") if x) or "rien"
        bilan["lignes"].append(f"  {'juste' if cote else 'FAUX '}  {ident:4s} {v['piece']:32s} photos : {dire(v['voilage'], v['rideaux'], sorted(v['pans'])):38s} "
                               f"Atelya : {dire(r.get('voilage'), r.get('rideaux'), pans)}")
    bilan["mesures"] = juger_les_mesures(verite, logement)
    return bilan


def main() -> int:
    total = {"fenetres": 0, "sorte": 0, "nombre": 0, "cote": 0}
    pans = {"pans": 0, "largeur": 0, "devant": 0, "devant_juges": 0, "etat": 0, "ecarts": []}
    for arg in sys.argv[1:]:
        cas, _, chemin = arg.partition("=")
        bilan = juger(cas, json.loads(Path(chemin).read_text(encoding="utf-8")))
        print(f"{cas} ({chemin})")
        print("\n".join(bilan["lignes"] + bilan["mesures"]["lignes"]))
        for k in total:
            total[k] += bilan[k]
        for k in pans:
            pans[k] += bilan["mesures"][k]
    n = total["fenetres"]
    print(f"\nRIDEAUX, {n} fenêtres relevées : bonne sorte {total['sorte']}/{n} ; bon nombre de pans {total['nombre']}/{n} ; "
          f"pans du bon côté {total['cote']}/{n}")
    if pans["pans"]:
        moyen = sum(pans["ecarts"]) / max(len(pans["ecarts"]), 1)
        print(f"PANS, {pans['pans']} pans relevés : bonne largeur {pans['largeur']}/{pans['pans']} (écart moyen {moyen:.0%}) ; "
              f"bonne part devant la fenêtre {pans['devant']}/{pans['devant_juges']} ; bon état {pans['etat']}/{pans['pans']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
