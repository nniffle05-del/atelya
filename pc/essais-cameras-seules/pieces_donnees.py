r"""LA PIÈCE DONNÉE PAR LE CLIENT (15/11/2026, décision NT : le client range chaque photo par pièce au dépôt) : que vaut le
calage quand on dit à Atelya quelle pièce chaque photo montre ?

    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\pieces_donnees.py [app-001 app-002 app-003] [--sans-sols]

Pour chaque logement, trois passages de moteur/caler_photos.py :
  seul    : comme en service jusqu'ici (Atelya devine la pièce) ;
  client  : chaque photo avec SA pièce, désignée sur le plan (la vraie pièce de jumelles.py ; CLIENT ci-dessous quand il
            faut trancher) ;
  sorte   : seulement la sorte de pièce (« chambre », « cuisine »), comme si le client nommait sans désigner sur le plan.
Mesures : photos utilisables ; place en mètres contre les relevés quand il y en a ; sols et meubles (app-001, app-002, mêmes
briques et même notation que outils/habillage/essai_calage_seul.py) ; et le SECOND AVIS : si le client se trompe de pièce,
Atelya le signale-t-il (« à vérifier ») ? Pour chaque photo et chaque AUTRE pièce du plan on regarde, sans rien recalculer,
si l'alerte se lèverait (colle < COLLE_MIN, ou Atelya seul sûr d'une autre pièce).
Sorties : ..\atelya\b2\cameras-seules\pieces-donnees\ (fiches <logement>-<passage>.json, bilan.json)
"""
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
import torch

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "habillage"))
import caler_photos_seul as outil  # noqa: E402
from moteur import caler_photos as cp  # noqa: E402
from moteur.camera_photo import camera_depuis_dict  # noqa: E402
from moteur.images import lire_image  # noqa: E402
from jumelles import LOGEMENTS, PC, memoire  # noqa: E402

SORTIE = PC / "b2/cameras-seules/pieces-donnees"
# ce que dirait le client quand la vérité de jumelles.py laisse deux pièces possibles (None : photo laissée sans pièce)
CLIENT = {"app-002": {"photo-02": "entree_1", "photo-08": "cuisine_1", "photo-12": "salle_d_eau_2", "photo-13": "salle_d_eau_2"},
          "app-003": {"photo-15": None}}
RELEVES = {"app-001": [RACINE / "verites/app-001/cameras-photos.json"],
           "app-002": [RACINE / "verites/app-002/cameras-photos-soigne.json", RACINE / "verites/app-002/cameras-photos.json"],
           "app-003": [RACINE / "verites/app-003/cameras-photos.json"]}


def ecarts(resultat, releves):
    """Écart en mètres et en degrés de chaque photo placée, contre le premier relevé qui la contient."""
    e = {}
    for n, d in resultat["cameras"].items():
        for r in releves:
            if n in r["cameras"]:
                k, c = r["cameras"][n]["camera"], d["camera"]
                e[n] = (math.hypot(c["x"] - k["x"], c["y"] - k["y"]), abs((c["cap"] - k["cap"] + 180) % 360 - 180))
                break
    return e


def resume(e, noms):
    v = [e[n] for n in noms if n in e]
    if not v:
        return "aucun relevé"
    m = np.array(v)
    return (f"{len(v)} photos au relevé : médiane {np.median(m[:, 0]):.2f} m, pire {m[:, 0].max():.2f} m ; à peu près (< 1 m, < 15°) "
            f"{int(((m[:, 0] < 1) & (m[:, 1] < 15)).sum())}, bien (< 0,5 m, < 8°) {int(((m[:, 0] < 0.5) & (m[:, 1] < 8)).sum())}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    avec_sols = "--sans-sols" not in sys.argv
    SORTIE.mkdir(parents=True, exist_ok=True)
    o = cp.Outils()
    memoire(o)
    gardees, bilan = [], {}
    if avec_sols:
        from moteur.oeil_dinov2 import charger as charger_oeil
        from moteur.reconnaitre_sols import Classifieur, noter, reconnaitre
        from moteur.reperer_meubles import noter_meubles, reperer_depuis_releve
        from non_recul_examens import EXAMENS, lire
        clf = Classifieur.depuis(torch.load(RACINE / "moteur/modeles/sols-vits14-v2.pt", weights_only=False))
        oeil = charger_oeil("vits14")
    for nom in (args or list(LOGEMENTS)):
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
        b = bilan[nom] = {"photos": len(photos)}
        res, det = {}, {}
        centre = {p["id"]: np.array(p["contour"], float).mean(0) for p in logement["pieces"]}
        for passage, pieces in (("seul", None), ("client", client), ("sorte", sorte), ("deux-temps", sorte)):
            det[passage] = {}
            endroits = {}
            if passage == "deux-temps":  # 2e temps : NT pointe d'où est prise chaque photo qu'Atelya n'a pas su ranger au 1er temps
                for n in photos:
                    if n in b["sorte"]["sures"] or n not in client:
                        continue
                    vraie = next((np.array([r_["cameras"][n]["camera"]["x"], r_["cameras"][n]["camera"]["y"]]) for r_ in releves if n in r_["cameras"]), None)
                    cap = next((r_["cameras"][n]["camera"]["cap"] for r_ in releves if n in r_["cameras"]), None)
                    c = centre[client[n]]
                    if vraie is None:  # pas de relevé : on pointe le milieu de la vraie pièce
                        endroits[n] = (float(c[0]), float(c[1]))
                    else:               # relevé : on pointe à 0,5 m de la vraie place (NT ne pointe pas au centimètre)
                        v = c - vraie; v = v / max(np.linalg.norm(v), 1e-6) * 0.5
                        endroits[n] = (float(vraie[0] + v[0]), float(vraie[1] + v[1])) + ((cap + 20.0,) if "--sens" in sys.argv else ())  # sens indiqué à 20° près
                b["pointees"] = sorted(endroits)
            r = res[passage] = cp.caler(logement, photos, outils=o, journal=lambda *a: None, fenetres_de=cartes, pieces_donnees=pieces, detail=det[passage],
                                        endroits_donnes=endroits)
            utiles = [n for n, d in r["cameras"].items() if d["sure"]]
            justes = [n for n in utiles if r["cameras"][n]["piece"] in f["vrai"][n]]
            alertes = {n: d["a_verifier"] for n, d in r["cameras"].items() if d.get("a_verifier")}
            e = ecarts(r, releves)
            b[passage] = {"utilisables": len(utiles), "bonne_piece": len(justes), "a_verifier": alertes, "non_calees": r["non_calees"],
                          "ecarts_m": {n: round(v[0], 2) for n, v in e.items()}, "pieces": {n: d["piece"] for n, d in r["cameras"].items()},
                          "sures": utiles,
                          "cameras": {n: {"piece": d["piece"], "sure": d["sure"], "cam": [d["camera"]["x"], d["camera"]["y"], d["camera"]["cap"]],
                                          "a_verifier": d.get("a_verifier"), "colle": d.get("colle")} for n, d in r["cameras"].items()}}
            print(f"\n{nom} [{passage}] utilisables {len(utiles)} sur {len(photos)}, dont dans la bonne pièce {len(justes)} ; à vérifier {len(alertes)} ; "
                  f"non calées {len(r['non_calees'])}", flush=True)
            print(f"   place, photos utilisables : {resume(e, utiles)}")
            if passage != "seul":
                nouvelles = [n for n in utiles if n not in b["sorte" if passage == "deux-temps" else "seul"]["sures"]]
                print(f"   place, photos NOUVELLES ({'pointées par NT' if passage == 'deux-temps' else 'pas sûres quand Atelya est seul'}) : {resume(e, nouvelles)}")
                for n in nouvelles:
                    if n in e:
                        print(f"      {n} {r['cameras'][n]['piece']:14s} {e[n][0]:.2f} m, {e[n][1]:.0f}°  (colle {r['cameras'][n].get('colle')})")
                for n, raison in alertes.items():
                    print(f"      À VÉRIFIER {n} (donnée : {pieces[n]}) : {raison}")
            fiche = outil.fiche(r, f["photos"], "{nom}." + f["ext"])
            (SORTIE / f"{nom}-{passage}.json").write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
            if avec_sols and nom in EXAMENS:
                ex = EXAMENS[nom]
                main_ = lire(ex["releve"])
                sans_sols = json.loads(json.dumps(logement))
                for p in sans_sols["pieces"]:
                    p.pop("sol", None); p["zones_sol"] = []
                cams = [camera_depuis_dict(d["camera"]) for d in main_["cameras"].values()]
                note = noter(reconnaitre(fiche, sans_sols, RACINE, oeil, clf, pas_du_sol=lambda n, rgb: o.pds.masque(f"{nom}/{n}", rgb)), lire(ex["verite_sols"]))
                m = noter_meubles(reperer_depuis_releve(fiche, logement, RACINE, owl=o.pds.owl), lire(ex["meubles"])["meubles"], cameras=cams, logement=logement)
                b[passage]["sols"] = {k: note.get(k) for k in ("surface_jugee_m2", "surface_juste", "pieces_justes")}
                b[passage]["meubles"] = m
                print(f"   sols : {note.get('surface_juste')} justes sur {note.get('surface_jugee_m2')} m² jugés ({note.get('pieces_justes')}) | meubles : {m}", flush=True)
        # le second avis : si le client donnait une AUTRE pièce, l'alerte se lèverait-elle ?
        colles = det["seul"]["colle_par_piece"]
        seul = res["seul"]["cameras"]
        plan = cp.plan_du_logement(logement)
        G = cp.grille(plan); pg = cp.piece_de(plan, G)
        lignes = []
        for n in photos:
            if n not in colles:
                continue
            for q, c in colles[n].items():
                vraie = q in f["vrai"][n]
                alerte = c < cp.COLLE_MIN or cp._facteur(det["seul"]["types"][n], q) <= cp.MEUBLES_MIN
                s = seul.get(n)
                if s and s["sure"] and not alerte and s["piece"] != q:
                    montree = cp.pieces_montrees(plan, G, pg, cp.pieces_permises(plan, q))[0]
                    i = int(np.argmin(np.hypot(G[:, 0] - s["camera"]["x"], G[:, 1] - s["camera"]["y"])))
                    alerte = montree[i] < 0
                meme = cp.sorte_de_piece(q) in {cp.sorte_de_piece(x) for x in f["vrai"][n]}
                lignes.append({"photo": n, "piece": q, "vraie": vraie, "meme_sorte": meme, "colle": c, "alerte": bool(alerte),
                               "meubles": cp._facteur(det["seul"]["types"][n], q)})
        b["second_avis"] = lignes
        vraies = [x for x in lignes if x["vraie"]]
        fausses = [x for x in lignes if not x["vraie"]]
        for titre, lot in (("bonne pièce donnée", vraies), ("fausse pièce, autre sorte", [x for x in fausses if not x["meme_sorte"]]),
                           ("fausse pièce, même sorte", [x for x in fausses if x["meme_sorte"]])):
            if lot:
                print(f"   second avis, {titre} : alerte {sum(x['alerte'] for x in lot)} fois sur {len(lot)} ; colle médiane {np.median([x['colle'] for x in lot]):.2f}"
                      f" (de {min(x['colle'] for x in lot):.2f} à {max(x['colle'] for x in lot):.2f})", flush=True)
    (SORTIE / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
