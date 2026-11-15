r"""CHAMBRES JUMELLES (15/11/2026) : Atelya se dit-il « sûr » quand il peut échanger deux pièces qui se ressemblent ?

    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\jumelles.py mesurer [app-001 app-002 app-003]
    ..\atelya\.venv\Scripts\python.exe pc\essais-cameras-seules\jumelles.py juger

POURQUOI : trois logements, c'est trois tirages : la bonne réponse sur les chambres jumelles d'app-002 « tenait à peu de chose »
(elle bascule dès qu'on change le zoom). Pour savoir si un « sûr » est solide, on rejoue chaque logement dans des conditions un
peu différentes mais réalistes, et on compte les photos dites « sûres » dans une MAUVAISE pièce (il en faut zéro) :
  service        : toutes les photos, comme en service ;
  zoom           : zoom donné par les lignes de fuite (la variante qui échangeait les chambres d'app-002) ;
  plan+5, plan-5, plan-ns+5, plan-eo+5 : le plan agrandi, rétréci, étiré de 5 % (les plans d'annonce sont faux de cet ordre) ;
  sans-NN        : une photo en moins (le client aurait pu ne pas l'envoyer).
  plan+3, -3, +8, -8 et sans-2-NN-MM (deux photos en moins, tirées au sort) : ajoutés APRÈS le choix des règles, jamais
                   regardés pour les régler.
Chaque tirage est joué deux fois : « avant » (chaîne du 14/11/2026) et « coupe » (chaîne 0.2.0 : marge d'ensemble,
sous-groupes de photos qui se revoient, seuil × racine du nombre de photos).
« mesurer » fait tourner la chaîne (mesures des photos gardées en mémoire d'un tirage à l'autre) et range, pour chaque tirage,
les candidats de chaque bloc : « juger » peut alors essayer d'autres règles du « sûr » sans rien recalculer.
Sorties : ..\atelya\b2\cameras-seules\jumelles\<logement>.json
"""
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from moteur import caler_photos as cp  # noqa: E402
from moteur.images import lire_image  # noqa: E402

PC = RACINE.parent / "atelya"
SORTIE = PC / "b2/cameras-seules/jumelles"
SDE = ["salle_d_eau_1", "salle_d_eau_2"]
VARIANTES = {"avant": False, "coupe": True}  # groupes de photos : comme avant le 15/11/2026 / coupés en sous-groupes qui se revoient
# la VRAIE pièce de chaque photo (relevés à la main ; à l'œil pour les photos sans relevé ; plusieurs = on ne sait pas trancher)
LOGEMENTS = {
    "app-001": {"logement": PC / "lectures-claude/app-001/logement.json", "photos": PC / "photos-clients/app-001/photos", "ext": "png",
                "vrai": {"photo-01": ["sejour_1"], "photo-02": ["sejour_1"], "photo-03": ["sejour_1"], "photo-04": ["sejour_1"],
                         "photo-05": ["sejour_1"], "photo-06": ["sejour_1"], "photo-07": ["sejour_1"], "photo-08": ["chambre_1"],
                         "photo-10": ["chambre_2"], "photo-11": ["chambre_2"], "photo-12": ["salle_d_eau_1"]}},
    "app-002": {"logement": RACINE / "verites/app-002/logement.json", "photos": PC / "photos-clients/app-002/photos", "ext": "jpg",
                "vrai": {"photo-01": ["sejour_1"], "photo-02": ["entree_1", "degagement_1"], "photo-03": ["sejour_1"], "photo-04": ["sejour_1"],
                         "photo-05": ["sejour_1"], "photo-06": ["sejour_1"], "photo-07": ["sejour_1"], "photo-08": ["cuisine_1", "entree_1"],
                         "photo-09": ["cuisine_1"], "photo-10": ["chambre_1"], "photo-11": ["chambre_1"], "photo-12": SDE, "photo-13": SDE,
                         "photo-14": ["chambre_2"], "photo-15": ["chambre_2"]}},
    "app-003": {"logement": RACINE / "verites/app-003/logement.json", "photos": PC / "photos-clients/app-003/photos", "ext": "jpg",
                "vrai": {**{f"photo-{i:02d}": ["sejour_2"] for i in (1, 6, 7, 8, 12)}, **{f"photo-{i:02d}": ["sejour_1"] for i in (2, 3, 4, 5)},
                         **{f"photo-{i:02d}": ["cuisine_1"] for i in (9, 10, 11)}, "photo-13": ["chambre_3"], "photo-14": ["chambre_3"],
                         "photo-15": ["chambre_1", "chambre_4"], **{f"photo-{i:02d}": ["chambre_2"] for i in (16, 17, 18)},
                         "photo-19": ["salle_d_eau_2"]}},
}


def etirer(logement: dict, sx: float, sy: float) -> dict:
    """Le même logement, plan étiré (sx d'est en ouest, sy du nord au sud)."""
    L = json.loads(json.dumps(logement))
    longueurs = {}
    for m in L["murs"]:
        a, b = np.array(m["debut"], float), np.array(m["fin"], float)
        avant = np.linalg.norm(b - a)
        m["debut"], m["fin"] = [a[0] * sx, a[1] * sy], [b[0] * sx, b[1] * sy]
        longueurs[m["id"]] = np.linalg.norm(np.array(m["fin"]) - np.array(m["debut"])) / max(avant, 1e-9)
    for o in L.get("ouvertures", []):
        k = longueurs.get(o.get("mur"), 1.0)
        o["position"], o["largeur"] = float(o["position"]) * k, float(o["largeur"]) * k
    for p in L["pieces"]:
        p["contour"] = [[x * sx, y * sy] for x, y in p["contour"]]
    return L


def memoire(o: cp.Outils):
    """Les mesures d'une photo ne dépendent pas des autres photos du lot : on les garde d'un tirage à l'autre."""
    garde = {}

    def avec_memoire(f, cle):
        def g(*a, **k):
            c = cle(*a, **k)
            if c not in garde:
                garde[c] = f(*a, **k)
            return garde[c]
        return g
    cle_plan = lambda t: (tuple(t.shape), round(float(torch.nan_to_num(t[:200].float(), posinf=0.0).sum()), 2))
    cp.mesurer = avec_memoire(cp.mesurer, lambda m, rgb, focale_px=None: ("mes", id(rgb), None if focale_px is None else round(focale_px, 2)))
    cp.profil = avec_memoire(cp.profil, lambda mes, hsp, fen=None: ("prof", id(mes), hsp, id(fen)))
    cp.notes_sur_le_plan = avec_memoire(cp.notes_sur_le_plan, lambda tp, pr, app, ech=cp.ECHELLES: ("notes", cle_plan(tp[0]), id(pr), tuple(ech)))
    cp.meme_lieu = avec_memoire(cp.meme_lieu, lambda m, a, b: ("lieu", id(a), id(b)))
    cp.recouper = avec_memoire(cp.recouper, lambda m, noms, photos, mes: ("bloc", tuple(id(photos[n]) for n in noms), tuple(id(mes[n]) for n in noms)))
    cp.fuites.mesurer = avec_memoire(cp.fuites.mesurer, lambda rgb: ("fuites", id(rgb)))
    empreinte = lambda T, n: (T[n].shape, round(float(T[n][::5, ::5, ::20].sum()), 3))
    cp.poser_bloc = avec_memoire(cp.poser_bloc, lambda T, rel, noms, combien=40: ("pose", tuple(noms), tuple(empreinte(T, n) for n in noms),
                                                                                  tuple((round(float(rel[n][0][0]), 4), round(float(rel[n][1]), 4)) for n in noms)))
    brut = o.pds.brut
    # seulement pour les appels du calage (photos gardées en mémoire, reconnues à leur adresse) : les sols et les meubles relisent
    # les photos dans des tableaux provisoires dont l'adresse resservirait à une AUTRE photo (objets d'une photo donnés à une autre)
    o.pds.brut = lambda cle, rgb: brut(f"jumelles/{id(rgb)}" if cle.startswith("caler/") else cle, rgb)
    return garde


def mesurer(noms_logements):
    SORTIE.mkdir(parents=True, exist_ok=True)
    o = cp.Outils()
    memoire(o)
    gardees = []  # les photos restent en mémoire : la mémoire des mesures les reconnaît à leur adresse
    for nom in noms_logements:
        f = LOGEMENTS[nom]
        logement = json.loads(f["logement"].read_text(encoding="utf-8"))
        photos = {}
        for n in f["vrai"]:
            im = lire_image(f["photos"] / f"{n}.{f['ext']}")
            if im is None:
                raise FileNotFoundError(f["photos"] / f"{n}.{f['ext']}")
            photos[n] = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
        gardees.append(photos)
        cartes = {}
        for n, rgb in photos.items():  # cartes des fenêtres : apprises SANS le logement noté quand elles existent
            c = PC / "b2/cameras-seules/aspect" / f"{nom}-{n}.npy"
            cartes[n] = np.load(c)[..., 2].astype(np.float32) if c.is_file() else o.fenetres.proba(cp.Fenetres.carres(o.oeil, rgb))
        tirages = [("service", list(photos), False, (1.0, 1.0)), ("zoom", list(photos), True, (1.0, 1.0)),
                   ("plan+5", list(photos), False, (1.05, 1.05)), ("plan-5", list(photos), False, (0.95, 0.95)),
                   ("plan-ns+5", list(photos), False, (1.0, 1.05)), ("plan-eo+5", list(photos), False, (1.05, 1.0))]
        tirages += [(f"sans-{n[-2:]}", [m for m in photos if m != n], False, (1.0, 1.0)) for n in photos]
        # tirages ajoutés APRÈS le choix des règles (jamais regardés pour les régler) : le contrôle le moins flatteur
        tirages += [(f"plan{k:+d}", list(photos), False, (1 + k / 100, 1 + k / 100)) for k in (3, -3, 8, -8)]
        rng = np.random.default_rng(2026)
        for _ in range(8):
            a, b = sorted(rng.choice(len(photos), 2, replace=False))
            tirages.append((f"sans-2-{list(photos)[a][-2:]}-{list(photos)[b][-2:]}", [m for i, m in enumerate(photos) if i not in (a, b)], False, (1.0, 1.0)))
        bilan = {v: {} for v in VARIANTES}
        for (titre, lot, zoom, (sx, sy)), variante in [(t, v) for t in tirages for v in VARIANTES]:
            t0 = time.time()
            detail = {}
            cp.SOUS_GROUPES = cp.MARGE_D_ENSEMBLE = cp.SEUIL_PAR_RACINE = VARIANTES[variante]
            r = cp.caler(etirer(logement, sx, sy) if (sx, sy) != (1.0, 1.0) else logement, {n: photos[n] for n in lot}, outils=o,
                         journal=lambda *a: None, fenetres_de=cartes, zoom_par_fuites=zoom, detail=detail)
            bilan[variante][titre] = {"cameras": {n: {k: d[k] for k in ("piece", "sure", "marge", "bloc", "hesite_avec")} | {"cam": [d["camera"]["x"], d["camera"]["y"], d["camera"]["cap"]]}
                                        for n, d in r["cameras"].items()},
                            "non_calees": r["non_calees"], **detail}
            faux = [n for n, d in r["cameras"].items() if d["sure"] and d["piece"] not in f["vrai"][n]]
            print(f"{nom} {variante} {titre:10s} {time.time() - t0:4.0f} s : {sum(d['sure'] for d in r['cameras'].values())} sûres sur {len(lot)}"
                  f"{' ; SÛRES ET FAUSSES : ' + ', '.join(f'{n[-2:]}→{r['cameras'][n]['piece']}' for n in faux) if faux else ''}", flush=True)
        (SORTIE / f"{nom}.json").write_text(json.dumps(bilan, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    try:
        if sys.argv[1] == "mesurer":
            mesurer(sys.argv[2:] or list(LOGEMENTS))
        else:
            import jumelles_juger
            jumelles_juger.main(sys.argv[2:])
    except Exception as e:
        print(f"PLANTÉ : {type(e).__name__} : {e}", flush=True)
        raise
