r"""ESSAI « CLAUDE LIT LES PHOTOS » (16/11/2026, accord de NT) : ce que la lecture apporte, mesuré contre les relevés faits à la main.

    ..\atelya\.venv\Scripts\python.exe pc\verification\essai_lecture_photos.py <dossier de sortie> [--cas app-001 app-002 app-004]

Trois versions du même logement, refaites par la chaîne (outils/atelya/de_l_ecran_au_film.py, jusqu'aux meubles) :
  A « aujourd'hui »   : Atelya en service (ses détecteurs, ses règles) ;
  B « mêmes rectangles » : les rectangles montrés à Claude, avec la sorte que le DÉTECTEUR leur donne, posés par le nouveau code
                        (moteur/photos_lues.py : objets au mur compris) — pour séparer ce qui vient de la pose de ce qui vient de la lecture ;
  C « avec la lecture » : les mêmes rectangles avec la sorte LUE par Claude (doublons et faux retirés, manquants ajoutés), les baies
                        et les sols lus.
Juges : les meubles relevés à la main (verites/<logement>/meubles.json : app-001 et app-002), les sols relevés à la main, la sorte
des baies du plan relevé. app-004 n'a pas de relevé : il est refait pour les images seulement.
Écrit <sortie>/<logement>/{a,b,c}/logement-meuble.json et <sortie>/bilan.json, bilan.txt.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
PC = RACINE.parent / "atelya"

from banc_ressemblance import CAS  # noqa: E402

VERITES = {"app-001": {"meubles": RACINE / "verites/app-001/meubles.json", "sols": PC / "b2/app-001/brique-photos/verite-logement-sols.json"},
           "app-002": {"meubles": RACINE / "verites/app-002/meubles.json", "sols": PC / "b2/app-002/examen/logement-verite-sols.json"}}
VERSIONS = {"a": ("aujourd'hui", []), "b": ("mêmes rectangles, sorte du détecteur", ["--sortes-du-detecteur"]), "c": ("avec la lecture de Claude", [])}
ACCROCHES = ("suspension", "television", "tableau", "miroir", "horloge", "meuble_cuisine_haut")
PRES_M = 0.8
lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))


def dire(*a) -> None:
    print(*a, flush=True)


def refaire(cas: str, version: str, sortie: Path) -> Path:
    """Le logement du cas refait par la chaîne jusqu'aux meubles, dans la version demandée."""
    d = CAS[cas]
    logement = lire(d["logement"])
    logement = logement.get("logement", logement)
    for p in logement["pieces"]:  # Atelya ne voit ni sols ni meubles déjà choisis (comme le banc de fidélité)
        if str((p.get("sol") or {}).get("statut")) != "mesure":
            p.pop("sol", None)
        p["zones_sol"] = []
    logement["meubles"] = []
    sortie.mkdir(parents=True, exist_ok=True)
    depart = sortie / "logement-du-banc.json"
    depart.write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
    options = list(VERSIONS[version][1])
    if version in ("b", "c"):
        options = ["--lecture-photos", str(PC / "lectures-photos" / cas)] + options
    r = subprocess.run([sys.executable, str(RACINE / "outils/atelya/de_l_ecran_au_film.py"), str(sortie), str(sortie), "--logement", str(depart),
                        "--fiche", str(d["fiche"]), "--sortie", str(sortie), "--jusqu-a", "meubles", *options],
                       cwd=RACINE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (sortie / "journal-chaine.txt").write_text(r.stdout + r.stderr, encoding="utf-8")
    if r.returncode != 0:
        dire(f"PLANTÉ : la chaîne a échoué pour {cas} version {version} (code {r.returncode}) : voir {sortie / 'journal-chaine.txt'}")
        sys.exit(r.returncode or 1)
    return sortie / "logement-meuble.json"


GLOUTON = False  # True : l'appariement d'avant le 17/11/2026 (dans l'ordre du relevé), pour retrouver les anciens chiffres
INTERDIT = 1e3


def affectation(cout: list[list[float]]) -> list[int]:
    """L'affectation de coût total minimal (méthode hongroise) : pour chaque ligne, sa colonne. Il faut lignes ≤ colonnes."""
    n, m = len(cout), len(cout[0]) if cout else 0
    u, v, p, chemin = [0.0] * (n + 1), [0.0] * (m + 1), [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0, mini, pris = 0, [math.inf] * (m + 1), [False] * (m + 1)
        while True:
            pris[j0] = True
            i0, delta, j1 = p[j0], math.inf, 0
            for j in range(1, m + 1):
                if not pris[j]:
                    c = cout[i0 - 1][j - 1] - u[i0] - v[j]
                    if c < mini[j]:
                        mini[j], chemin[j] = c, j0
                    if mini[j] < delta:
                        delta, j1 = mini[j], j
            for j in range(m + 1):
                if pris[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    mini[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            p[j0] = p[chemin[j0]]
            j0 = chemin[j0]
    sortie = [0] * n
    for j in range(1, m + 1):
        if p[j]:
            sortie[p[j] - 1] = j - 1
    return sortie


def _paires(a_trouver: list[dict], trouves: list[dict], meme) -> tuple[list[tuple[dict, dict]], list[dict]]:
    """Paires (vrai meuble, meuble posé) à moins de PRES_M, quand `meme(vrai, posé)` ; et les posés restés seuls.
    Depuis le 17/11/2026 l'appariement est le MEILLEUR possible (le plus de paires, puis la plus petite distance totale) : avant,
    chaque vrai meuble prenait dans l'ordre du relevé le posé le plus proche, et la 6e chaise d'une tablée pouvait être comptée
    « en trop » à 60 cm de sa place parce qu'une voisine lui avait pris sa case (GLOUTON = True : l'ancienne façon)."""
    if GLOUTON:
        libres = list(range(len(trouves)))
        paires = []
        for v in a_trouver:
            cands = [(math.dist(trouves[i]["position"], v["position"]), i) for i in libres if meme(v, trouves[i])]
            cands = [c for c in cands if c[0] <= PRES_M]
            if cands:
                _, i = min(cands)
                libres.remove(i)
                paires.append((v, trouves[i]))
        return paires, [trouves[i] for i in libres]
    if not a_trouver or not trouves:
        return [], list(trouves)
    cout = [[d if meme(v, t) and (d := math.dist(t["position"], v["position"])) <= PRES_M else INTERDIT for t in trouves] for v in a_trouver]
    if len(a_trouver) <= len(trouves):
        choix = [(i, j) for i, j in enumerate(affectation(cout))]
    else:
        choix = [(i, j) for j, i in enumerate(affectation([list(c) for c in zip(*cout)]))]
    paires = [(a_trouver[i], trouves[j]) for i, j in sorted(choix) if cout[i][j] < INTERDIT]
    pris = {id(t) for _, t in paires}
    return paires, [t for t in trouves if id(t) not in pris]


def charger_releve(cas: str, complet: bool = True) -> list[dict]:
    """Le relevé des meubles fait à la main ; `complet` : avec son complément du 17/11/2026 (verites/<logement>/
    meubles-complement.json : vrais meubles oubliés, places corrigées), contrôlé par pc/verification/boites_sur_photos.py."""
    meubles = [dict(m) for m in lire(VERITES[cas]["meubles"])["meubles"]]
    f = Path(VERITES[cas]["meubles"]).with_name("meubles-complement.json")
    if complet and f.is_file():
        comp = lire(f)
        for m in meubles:
            m.update(comp.get("corrections", {}).get(m["id"], {}))
        meubles += [dict(m, statut="estime") for m in comp["meubles"]]
    return meubles


def _dans_l_emprise(point, v: dict, marge: float = 0.1) -> bool:
    """Le point est-il dans l'emprise au sol du meuble `v` (à `marge` près) ?"""
    a = math.radians(v.get("face", 0.0) or 0.0)
    dx, dy = point[0] - v["position"][0], point[1] - v["position"][1]
    en_avant, de_cote = dx * math.cos(a) + dy * math.sin(a), -dx * math.sin(a) + dy * math.cos(a)
    return abs(de_cote) <= v["dimensions"][0] / 2 + marge and abs(en_avant) <= v["dimensions"][1] / 2 + marge


def noter_meubles(logement: dict, verite: list[dict], fiche: dict) -> dict:
    """Contre le relevé à la main, pour les meubles qu'une photo montre : au sol (retrouvés à la bonne famille, à la bonne SORTE,
    en trop) et accrochés (luminaires, télévisions, tableaux, miroirs, horloges, meubles hauts : retrouvés à la bonne sorte, en trop)."""
    from moteur.camera_photo import camera_depuis_dict
    from moteur.reperer_meubles import groupe as _groupe, vu_sur_une_photo
    # un réfrigérateur posé vaut la « colonne » que le relevé du 10/11/2026 appelait réfrigérateur (la sorte n'existait pas encore)
    groupe = lambda c: _groupe("colonne_cuisine" if c == "refrigerateur" else c)

    from moteur.meubles import EQUIPEMENTS

    cams = [camera_depuis_dict(c["camera"]) for c in fiche["cameras"].values()]
    # les équipements (cheminée, radiateur, évier…) ne sont pas dans les relevés de meubles faits à la main : jugés à l'image
    poses = [m for m in logement.get("meubles", []) if m["categorie"] not in EQUIPEMENTS or m["categorie"] == "refrigerateur"]
    au_sol = lambda m: bool(groupe(m["categorie"])) and float(m.get("altitude") or 0) < 0.3 and m["categorie"] not in ACCROCHES
    vrais_sol = [v for v in verite if au_sol(v) and vu_sur_une_photo(v, cams, logement)]
    poses_sol = [m for m in poses if au_sol(m)]
    # d'abord la bonne sorte exacte, puis, pour ceux qui restent, la bonne famille (canapé pour canapé, table pour bureau…)
    exacts, reste = _paires(vrais_sol, poses_sol, lambda v, m: v["categorie"] == m["categorie"])
    pris = {id(v) for v, _ in exacts}
    proches, en_trop = _paires([v for v in vrais_sol if id(v) not in pris], reste, lambda v, m: groupe(v["categorie"]) == groupe(m["categorie"]))
    # un meuble posé qui tombe sur un vrai meuble qu'aucune photo de SA pièce ne montre (vu par une porte) n'est pas « en trop »
    hors_liste = [v for v in verite if au_sol(v) and not any(v is x for x in vrais_sol)]
    _, en_trop = _paires(hors_liste, en_trop, lambda v, m: groupe(v["categorie"]) == groupe(m["categorie"]))
    # un MORCEAU d'un grand meuble du relevé n'est pas « en trop » : la seconde colonne d'un bloc de colonnes relevé d'un seul
    # tenant, le second meuble bas d'un linéaire de 3,60 m (son milieu est dans l'emprise du vrai meuble, même groupe)
    morceaux = [] if GLOUTON else [m for m in en_trop if any(groupe(v["categorie"]) == groupe(m["categorie"]) and _dans_l_emprise(m["position"], v)
                                                             for v in verite if au_sol(v))]
    en_trop = [m for m in en_trop if not any(m is x for x in morceaux)]
    vrais_acc = [v for v in verite if v["categorie"] in ACCROCHES and vu_sur_une_photo(v, cams, logement)]
    poses_acc = [m for m in poses if m["categorie"] in ACCROCHES]
    acc, acc_en_trop = _paires(vrais_acc, poses_acc, lambda v, m: v["categorie"] == m["categorie"])
    _, acc_en_trop = _paires([v for v in verite if v["categorie"] in ACCROCHES and not any(v is x for x in vrais_acc)], acc_en_trop,
                             lambda v, m: v["categorie"] == m["categorie"])
    ecarts = [math.dist(v["position"], m["position"]) for v, m in exacts + proches]
    par_sorte: dict[str, list[int]] = {}
    for v in vrais_sol:
        par_sorte.setdefault(v["categorie"], [0, 0])[1] += 1
    for v, _ in exacts:
        par_sorte[v["categorie"]][0] += 1
    return {"a_trouver": len(vrais_sol), "retrouves": len(exacts) + len(proches), "bonne_sorte": len(exacts), "en_trop": len(en_trop),
            "ecart_moyen_m": round(sum(ecarts) / len(ecarts), 2) if ecarts else None,
            "accroches_a_trouver": len(vrais_acc), "accroches_retrouves": len(acc), "accroches_en_trop": len(acc_en_trop),
            "morceaux": len(morceaux), "poses": len(poses), "manques_bonne_sorte": {k: f"{a}/{b}" for k, (a, b) in sorted(par_sorte.items()) if a < b},
            "en_trop_detail": sorted(m["categorie"] for m in en_trop), "accroches_en_trop_detail": sorted(m["categorie"] for m in acc_en_trop)}


def noter_sols(logement: dict, verite: dict) -> dict:
    """La famille du sol de chaque pièce du logement refait contre celle du relevé (pièces dont les deux sont connus)."""
    from moteur.reconnaitre_sols import famille

    vraies = {p["id"]: p for p in verite["pieces"] if p.get("sol")}
    justes, details, zones = 0, {}, [0, 0]
    for p in logement["pieces"]:
        v = vraies.get(p["id"])
        sol = p.get("sol") or {}
        if v is None or not str(sol.get("source", "")).startswith("brique photos"):
            continue
        trouve, attendu = famille(sol["matiere"]), famille(v["sol"]["matiere"])
        justes += trouve == attendu
        details[p["id"]] = {"trouve": trouve, "attendu": attendu}
        zones[0] += len(p.get("zones_sol", []))
        zones[1] += len(v.get("zones_sol", []))
    # LA SURFACE JUSTE (17/11/2026) : part du sol des pièces jugées dont la famille est la bonne, zones comprises, sur une grille
    # de 10 cm. Le compte des zones ne juge rien : une vraie zone relevée en trois morceaux convexes en vaut trois, et une
    # fausse zone compte comme une vraie (« zones 4 pour 5 » en service sur app-001 : deux des quatre étaient fausses).
    import numpy as np

    from moteur.reconnaitre_sols import familles_verite
    from moteur.sol_a_plat import dans_polygone

    surface = [0, 0]
    for p in logement["pieces"]:
        if p["id"] not in details:
            continue
        c = np.asarray(p["contour"], float)
        X, Y = np.meshgrid(np.arange(c[:, 0].min() + 0.05, c[:, 0].max(), 0.1), np.arange(c[:, 1].min() + 0.05, c[:, 1].max(), 0.1))
        dedans = dans_polygone(X, Y, p["contour"])
        trouve = familles_verite({"pieces": [p]}, X[dedans], Y[dedans])
        attendu = familles_verite({"pieces": [vraies[p["id"]]]}, X[dedans], Y[dedans])
        surface[0] += int((trouve == attendu).sum())
        surface[1] += int(dedans.sum())
    return {"pieces_jugees": len(details), "pieces_justes": justes, "zones_posees": zones[0], "zones_vraies": zones[1], "pieces": details,
            "surface_juste": round(surface[0] / surface[1], 3) if surface[1] else None, "surface_jugee_m2": round(surface[1] * 0.01, 1)}


def noter_baies(depart: dict, refait: dict) -> dict:
    """La sorte de chaque baie après la chaîne contre celle du plan relevé (départ) : une baie changée à tort est une erreur."""
    avant = {o["id"]: o["type"] for o in depart.get("ouvertures", []) if o["type"] != "porte"}
    apres = {o["id"]: o["type"] for o in refait.get("ouvertures", []) if o["id"] in avant}
    changees = {i: f"{avant[i]} → {t}" for i, t in apres.items() if t != avant[i]}
    return {"baies": len(avant), "changees_a_tort": changees}


def _equipements(note: dict) -> str:
    """Ce que la chaîne a fait des équipements lus (depuis le 16/11/2026 ils sont posés : moteur/equipements.py), et le contrôle
    « zéro collision » (moteur/collisions.py)."""
    c = note.get("collisions")
    fin = f" | collisions : {c['total']}" + (f" (au pire {c['au_pire_cm']} cm)" if c and c["total"] else "") if c is not None else ""
    e = note.get("equipements")
    if e is None:
        return fin
    if isinstance(e, list):  # ancien fichier : la liste des équipements vus, aucun n'était dessiné
        return f" | équipements vus, non dessinés : {len(e)}" + fin
    return (f" | équipements : {len(e['meubles'])} posés, {len(e['rideaux'])} fenêtre(s) habillée(s), {len(e['passe_plats'])} passe-plat(s), "
            f"{len(e['non_poses'])} non posé(s)") + fin


def main() -> int:
    ap = argparse.ArgumentParser(description="Essai : ce que la lecture des photos par Claude apporte à la maquette")
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--cas", nargs="*", default=list(CAS))
    ap.add_argument("--versions", nargs="*", default=list(VERSIONS))
    ap.add_argument("--sans-chaine", action="store_true", help="reprendre les logements déjà refaits dans ce dossier")
    ap.add_argument("--ancien-juge", action="store_true", help="le juge d'avant le 17/11/2026 : relevé d'origine, appariement dans l'ordre")
    ap.add_argument("--bilan", default="bilan", help="nom des fichiers du bilan (bilan.json, bilan.txt)")
    a = ap.parse_args()
    global GLOUTON
    GLOUTON = a.ancien_juge
    bilan = {"date": time.strftime("%Y-%m-%d %H:%M"), "versions": {v: VERSIONS[v][0] for v in a.versions}, "logements": {}}
    for cas in a.cas:
        fiche = lire(CAS[cas]["fiche"])
        bilan["logements"][cas] = {}
        for version in a.versions:
            dossier = a.sortie / cas / version
            fait = dossier / "logement-meuble.json"
            if not (a.sans_chaine and fait.is_file()):
                debut = time.time()
                refaire(cas, version, dossier)
                dire(f"{cas} version {version} ({VERSIONS[version][0]}) : refait en {time.time() - debut:.0f} s")
            logement = lire(fait)
            from moteur import collisions
            note = {"meubles_poses": len(logement.get("meubles", [])), "collisions": collisions.resume(collisions.mesurer(logement))}
            if cas in VERITES:
                note["meubles"] = noter_meubles(logement, charger_releve(cas, complet=not a.ancien_juge), fiche)
                note["sols"] = noter_sols(logement, lire(VERITES[cas]["sols"]))
                note["baies"] = noter_baies(lire(dossier / "logement-du-banc.json"), logement)
            equip = dossier / "logement-meuble.equipements.json"
            if equip.is_file():
                note["equipements"] = lire(equip)
            bilan["logements"][cas][version] = note
    a.sortie.mkdir(parents=True, exist_ok=True)
    (a.sortie / f"{a.bilan}.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    lignes = [f"ESSAI « CLAUDE LIT LES PHOTOS » ({bilan['date']})", ""]
    for cas, versions in bilan["logements"].items():
        lignes.append(cas)
        for v, n in versions.items():
            if "meubles" not in n:
                lignes.append(f"  {v} {VERSIONS[v][0]:38s} {n['meubles_poses']} meubles posés" + _equipements(n))
                continue
            m, s, b = n["meubles"], n["sols"], n["baies"]
            lignes.append(f"  {v} {VERSIONS[v][0]:38s} au sol : retrouvés {m['retrouves']}/{m['a_trouver']}, bonne sorte {m['bonne_sorte']}/{m['a_trouver']}, "
                          f"en trop {m['en_trop']}, morceaux {m.get('morceaux', 0)}, écart {m['ecart_moyen_m']} m | accrochés : {m['accroches_retrouves']}/{m['accroches_a_trouver']}, "
                          f"en trop {m['accroches_en_trop']} | sols : {s['pieces_justes']}/{s['pieces_jugees']} pièces, "
                          + (f"surface juste {100 * s['surface_juste']:.0f} % de {s['surface_jugee_m2']} m²" if s.get("surface_juste") is not None else "surface non jugée")
                          + f" | baies changées à tort : {len(b['changees_a_tort'])}/{b['baies']}"
                          + _equipements(n))
        lignes.append("")
    texte = "\n".join(lignes)
    (a.sortie / f"{a.bilan}.txt").write_text(texte, encoding="utf-8")
    dire(texte)
    return 0


if __name__ == "__main__":
    sys.exit(main())
