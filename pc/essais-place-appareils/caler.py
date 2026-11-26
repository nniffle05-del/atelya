r"""LA PLACE DES APPAREILS DES PHOTOS (24/11/2026) : le calage des quatre logements, dans les conditions du service (la pièce
de chaque photo est donnée par le client ; app-004 : les endroits pointés par NT à l'écran), pour une ou plusieurs variantes.

    ..\atelya\.venv\Scripts\python.exe pc\essais-place-appareils\caler.py <variante> [<variante>…] [--logements app-001 app-004]

Variantes : « defaut » (le calage tel qu'il sort aujourd'hui), « service » (le calage d'avant le 24/11/2026, sans affinage), « fin » et « avec » (zoom des lignes de fuite, en réserve depuis le 14/11),
et celles de VARIANTES ci-dessous. Sorties : ..\atelya\b2\place-appareils\<variante>\<logement>.json (toutes les photos
placées, sûres ou non, avec leur appareil). Le juge : pc\essais-place-appareils\juger.py.
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "habillage"))
sys.path.insert(0, str(RACINE / "pc" / "essais-cameras-seules"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import caler_photos_seul as outil  # noqa: E402
from moteur import caler_photos as cp  # noqa: E402
from moteur.images import lire_image  # noqa: E402
from jumelles import LOGEMENTS, PC, memoire  # noqa: E402
from pieces_donnees import CLIENT  # noqa: E402

SORTIE = PC / "b2/place-appareils"
APP004 = {"logement": PC / "b2/app-004/chaine-v2/logement-depart.json", "photos": PC / "photos-clients/app-004/photos", "ext": "jpg"}
VARIANTES = {"service": {"affiner": False}, "fin": {"zoom_par_fuites": "fin", "affiner": False}, "avec": {"zoom_par_fuites": True, "affiner": False},
             "defaut": {},  # « defaut » : le calage tel qu'il sort aujourd'hui (appareils affinés dans l'image)
             # 2e temps du « sol pris pour un lit » (25/11/2026) : la règle partagée du sol et du plafond (cp.sol_et_plafond)
             # dans le calage (profil), dans l'affinage (repere_du_mur), ou dans les deux. UNE sorte de drapeaux par lancement
             # (la mémoire des profils ne connaît pas les drapeaux).
             "temoin": {"drapeaux": {"calage": False, "affinage": False}},
             "sol-calage": {"drapeaux": {"calage": True, "affinage": False}},
             "sol-affinage": {"drapeaux": {"calage": False, "affinage": True}},
             "sol-partout": {"drapeaux": {"calage": True, "affinage": True}},
             # … et les mêmes quand le client n'a PAS rangé ses photos (Atelya seul : ni pièce donnée, ni endroit pointé)
             "temoin-seul": {"drapeaux": {"calage": False, "affinage": False}, "seul": True},
             "sol-seul": {"drapeaux": {"calage": True, "affinage": True}, "seul": True},
             # « l'appareil dans un meuble » (26/11/2026) : côtés ouverts entre pièces (cp.COTES_OUVERTS), sur le calage du jour
             "ouverts": {"drapeaux": {"calage": True, "affinage": True}, "ouverts": True},
             "ouverts-seul": {"drapeaux": {"calage": True, "affinage": True}, "ouverts": True, "seul": True}}


def cas(nom: str) -> dict:
    """Logement, photos, pièces données, endroits pointés d'un logement, comme en service."""
    if nom == "app-004":
        f = APP004
        logement = json.loads(f["logement"].read_text(encoding="utf-8"))
        photos, _ = outil.lire_photos(f["photos"])
        pieces, confirmees, endroits = outil.lire_pieces(f["photos"] / outil.PIECES_DES_PHOTOS, photos)
        return {"logement": logement, "photos": photos, "pieces": pieces, "confirmees": confirmees, "endroits": endroits, "cartes": None,
                "dossier": f["photos"], "ext": "jpg"}
    f = LOGEMENTS[nom]
    logement = json.loads(f["logement"].read_text(encoding="utf-8"))
    photos = {n: cv2.cvtColor(lire_image(f["photos"] / f"{n}.{f['ext']}"), cv2.COLOR_BGR2RGB) for n in f["vrai"]}
    client = {n: CLIENT.get(nom, {}).get(n, v[0]) for n, v in f["vrai"].items()}
    cartes = {}
    for n in photos:  # la couche des fenêtres a été apprise sur app-001 et app-002 : cartes apprises sans le logement noté
        c = PC / "b2/cameras-seules/aspect" / f"{nom}-{n}.npy"
        if c.is_file():
            cartes[n] = np.load(c)[..., 2].astype(np.float32)
    return {"logement": logement, "photos": photos, "pieces": {n: p for n, p in client.items() if p}, "confirmees": set(photos), "endroits": {},
            "cartes": cartes or None, "dossier": f["photos"], "ext": f["ext"]}


def main():
    args = sys.argv[1:]
    noms = args[args.index("--logements") + 1:] if "--logements" in args else ["app-001", "app-002", "app-003", "app-004"]
    variantes = [a for a in (args[:args.index("--logements")] if "--logements" in args else args)]
    drapeaux = {json.dumps(VARIANTES[v].get("drapeaux"), sort_keys=True) for v in variantes}
    if len(drapeaux) > 1:
        raise SystemExit("PLANTÉ : une seule sorte de drapeaux par lancement (la mémoire des profils ne les connaît pas)")
    d = VARIANTES[variantes[0]].get("drapeaux") if variantes else None
    if d:
        from moteur import affiner_appareils as aa
        cp.SOL_JUSTE_AU_CALAGE, aa.SOL_PARTAGE = d["calage"], d["affinage"]
        print(f"drapeaux : sol juste au calage = {cp.SOL_JUSTE_AU_CALAGE}, à l'affinage = {aa.SOL_PARTAGE}", flush=True)
    o = cp.Outils()
    memoire(o)
    gardes = []
    for nom in noms:
        c = cas(nom)
        gardes.append(c)
        for v in variantes:
            t0 = time.time()
            seul = VARIANTES[v].get("seul")
            cp.COTES_OUVERTS = bool(VARIANTES[v].get("ouverts"))
            r = cp.caler(c["logement"], c["photos"], outils=o, journal=lambda *a: None, fenetres_de=c["cartes"], pieces_donnees=None if seul else c["pieces"],
                         confirmees=() if seul else c["confirmees"], endroits_donnes=None if seul else c["endroits"],
                         **{k: x for k, x in VARIANTES[v].items() if k not in ("drapeaux", "seul", "ouverts")})
            (SORTIE / v).mkdir(parents=True, exist_ok=True)
            (SORTIE / v / f"{nom}.json").write_text(json.dumps({"photos": str(c["dossier"]), "fichier": "{nom}." + c["ext"], "cameras": r["cameras"],
                                                               "non_calees": r["non_calees"]}, ensure_ascii=False, indent=1), encoding="utf-8")
            sures = sum(1 for d in r["cameras"].values() if d["sure"])
            print(f"{nom} [{v}] : {len(r['cameras'])} photos placées sur {len(c['photos'])}, dont {sures} sûres ({time.time() - t0:.0f} s)", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
