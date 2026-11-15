r"""app-002 : la chaîne en service (« sans ») contre la variante « fin » du zoom par lignes de fuite, jugées contre le CORRIGÉ
SOIGNÉ verites/app-002/cameras-photos-soigne.json (15/11/2026).

    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\noter_app002.py [sans] [fin] [--lot 11|15] [--sans-sols]

Lot 11 = les photos de l'ancien relevé à la main (comme outils/habillage/essai_calage_seul.py : notes comparables au journal) ;
lot 15 = toutes les photos du dossier (ce qui se passe vraiment en service). Pour chaque variante : place des photos en mètres
contre le corrigé, puis sols et meubles (mêmes briques et même notation que essai_calage_seul.py). Sols et meubles sont aussi
notés avec les caméras du corrigé soigné et de l'ancien relevé (mêmes photos) : ce que donnerait un calage parfait.
La couche des fenêtres a été apprise sur app-001 et app-002 : on donne les cartes apprises sans le logement noté.
Sorties : ..\atelya\b2\app-002\corrige\ (fiches cameras-seul-<variante>-<lot>.json, bilan-<lot>.json).
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
from moteur.oeil_dinov2 import charger as charger_oeil  # noqa: E402
from moteur.reconnaitre_sols import Classifieur, noter, reconnaitre  # noqa: E402
from moteur.reperer_meubles import noter_meubles, reperer_depuis_releve  # noqa: E402
from non_recul_examens import EXAMENS, PC, lire  # noqa: E402

VARIANTES = {"sans": False, "avec": True, "fin": "fin"}


def places(resultat, corrige, titre):
    lignes = []
    for n, k in corrige.items():
        d = resultat["cameras"].get(n)
        if d is None:
            print(f"  {n} : non calée")
            continue
        c, v = d["camera"], k["camera"]
        e = math.hypot(c["x"] - v["x"], c["y"] - v["y"])
        dc = abs((c["cap"] - v["cap"] + 180) % 360 - 180)
        ax = (math.cos(math.radians(v["cap"])), math.sin(math.radians(v["cap"])))
        avance = (c["x"] - v["x"]) * ax[0] + (c["y"] - v["y"]) * ax[1]
        lignes.append((e, dc, d["piece"] == k["piece"], d["sure"]))
        print(f"  {n} {d['piece']:10s} {e:.2f} m (avance {avance:+.2f}) cap {dc:4.1f}° zoom {c['f']:.0f} (corrigé ± {k['incertitude_m']} m) "
              f"{'sûre' if d['sure'] else 'PAS SÛRE'}{'' if d['piece'] == k['piece'] else '  MAUVAISE PIÈCE'}")
    t = np.array(lignes, float)
    bilan = {"mediane_m": round(float(np.median(t[:, 0])), 2), "moyenne_m": round(float(t[:, 0].mean()), 2), "pire_m": round(float(t[:, 0].max()), 2),
             "cap_median_deg": round(float(np.median(t[:, 1])), 1), "cap_pire_deg": round(float(t[:, 1].max()), 1),
             "bien": int(((t[:, 0] < 0.5) & (t[:, 1] < 8)).sum()), "a_peu_pres": int(((t[:, 0] < 1) & (t[:, 1] < 15)).sum()),
             "bonne_piece": int(t[:, 2].sum()), "sures": int(t[:, 3].sum()), "photos": len(t),
             "par_photo": {n: round(float(e), 2) for n, e in zip([n for n in corrige if n in resultat["cameras"]], t[:, 0])}}
    print(f"== {titre} : médiane {bilan['mediane_m']} m, moyenne {bilan['moyenne_m']}, pire {bilan['pire_m']} ; cap médian {bilan['cap_median_deg']}°, "
          f"pire {bilan['cap_pire_deg']}° ; bien (<0,5 m, <8°) {bilan['bien']}, à peu près (<1 m, <15°) {bilan['a_peu_pres']}, bonne pièce "
          f"{bilan['bonne_piece']}, sûres {bilan['sures']} sur {bilan['photos']}")
    return bilan


def main():
    args = sys.argv[1:]
    lot = args[args.index("--lot") + 1] if "--lot" in args else "11"
    avec_sols = "--sans-sols" not in args
    variantes = [a for a in args if a in VARIANTES] or ["sans", "fin"]
    f = EXAMENS["app-002"]
    logement, main_ = lire(f["logement"]), lire(f["releve"])
    soigne = lire(RACINE / "verites/app-002/cameras-photos-soigne.json")
    corrige = soigne["cameras"]
    dossier = RACINE / main_["photos"]
    modele = main_.get("fichier", "{nom}.png")
    noms = list(main_["cameras"]) if lot == "11" else sorted(p.stem for p in dossier.glob("photo-*.jpg"))
    photos = {n: cv2.cvtColor(lire_image(dossier / modele.format(nom=n)), cv2.COLOR_BGR2RGB) for n in noms}
    cartes = {n: np.load(PC / "b2/cameras-seules/aspect" / f"app-002-{n}.npy")[..., 2].astype(np.float32) for n in photos
              if (PC / "b2/cameras-seules/aspect" / f"app-002-{n}.npy").is_file()}
    sortie = PC / "b2/app-002/corrige"
    o = cp.Outils()
    print(f"lot {lot} : {len(photos)} photos, {len(cartes)} cartes de fenêtres toutes faites")
    fiches, bilan = {}, {}
    for v in variantes:
        r = cp.caler(logement, photos, outils=o, journal=lambda *a: None, fenetres_de=cartes, zoom_par_fuites=VARIANTES[v])
        tout = {**r, "cameras": dict(r["cameras"])}
        print(f"\n--- {v} : {sum(1 for d in r['cameras'].values() if d['sure'])} photos sûres sur {len(photos)}")
        bilan[v] = {"places": places(tout, corrige, v)}
        fiches[v] = outil.fiche(r, dossier, modele)
        (sortie / f"cameras-seul-{v}-{lot}.json").write_text(json.dumps(fiches[v], ensure_ascii=False, indent=1), encoding="utf-8")
    if avec_sols:
        clf = Classifieur.depuis(torch.load(RACINE / "moteur/modeles/sols-vits14-v2.pt", weights_only=False))
        oeil = charger_oeil("vits14")
        sans_sols = json.loads(json.dumps(logement))
        for p in sans_sols["pieces"]:
            p.pop("sol", None)
            p["zones_sol"] = []
        verite_sols, verite_meubles = lire(f["verite_sols"]), lire(f["meubles"])["meubles"]
        cams = [camera_depuis_dict(d["camera"]) for d in main_["cameras"].values()]
        sures = list(fiches[variantes[0]]["cameras"])
        a_noter = {"ancien relevé (photos sûres)": {**main_, "cameras": {n: main_["cameras"][n] for n in sures if n in main_["cameras"]}},
                   "corrigé soigné (photos sûres)": {**soigne, "cameras": {n: corrige[n] for n in sures if n in corrige}},
                   **{f"Atelya seul, {v}": fiches[v] for v in variantes}}
        for quoi, releve in a_noter.items():
            note = noter(reconnaitre(releve, sans_sols, RACINE, oeil, clf, pas_du_sol=lambda n, rgb: o.pds.masque(f"app-002/{n}", rgb)), verite_sols)
            m = noter_meubles(reperer_depuis_releve(releve, logement, RACINE, owl=o.pds.owl), verite_meubles, cameras=cams, logement=logement)
            bilan[quoi] = {"photos": list(releve["cameras"]), "sols": {k: note.get(k) for k in ("surface_jugee_m2", "surface_juste", "pieces_justes", "par_famille", "pieces")},
                           "meubles": m}
            print(f"\n[{quoi}] {len(releve['cameras'])} photos\n   sols : {note.get('surface_juste')} justes sur {note.get('surface_jugee_m2')} m² jugés ; "
                  f"{note.get('pieces_justes')} ; {note.get('par_famille')}\n   pièces : {note.get('pieces')}\n   meubles : {m}")
    (sortie / f"bilan-{lot}.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
