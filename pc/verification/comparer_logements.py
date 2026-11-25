r"""Ce qui a BOUGÉ entre deux passages de la chaîne, objet par objet (25/11/2026, « le sol pris pour un lit »).

    ..\atelya\.venv\Scripts\python.exe pc\verification\comparer_logements.py <dossier avant> <dossier après> [--seuil 0.01]

Chaque dossier est une sortie de pc\verification\essai_lecture_photos.py (<logement>/<version>/logement-meuble.json). Pour chaque
logement et chaque version : les meubles (apparus, disparus, déplacés, taille ou hauteur changée), les ouvertures (bas, haut,
sorte, largeur, rideaux, tringle, dessin), les sols de chaque pièce. Un écart sous `seuil` (mètres) n'est pas dit.
Code de sortie 0 ; la dernière ligne dit le nombre de choses qui ont bougé.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))  # noqa: E731


def aplati(o, prefixe="") -> dict:
    """Un objet JSON mis à plat : {"rideaux.tringle.hauteur": 2.55, …}."""
    if isinstance(o, dict):
        s = {}
        for k, v in o.items():
            s.update(aplati(v, f"{prefixe}{k}."))
        return s
    if isinstance(o, list):
        s = {}
        for i, v in enumerate(o):
            s.update(aplati(v, f"{prefixe}{i}."))
        return s
    return {prefixe[:-1]: o}


def ecarts(a: dict, b: dict, seuil: float, sauf=()) -> list[str]:
    fa, fb = aplati(a), aplati(b)
    dits = []
    for k in sorted(set(fa) | set(fb)):
        if any(k == s or k.startswith(s + ".") for s in sauf):
            continue
        x, y = fa.get(k), fb.get(k)
        if x == y:
            continue
        if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
            if abs(x - y) < seuil:
                continue
            dits.append(f"{k} {x:.3g} → {y:.3g}")
        else:
            dits.append(f"{k} {str(x)[:60]} → {str(y)[:60]}")
    return dits


def cle_meuble(m: dict) -> tuple:
    return (m.get("piece"), m.get("categorie") or m.get("type"))


def apparier(avant: list[dict], apres: list[dict]) -> tuple[list[tuple[dict, dict]], list[dict], list[dict]]:
    """Les meubles d'avant et d'après mis par paires : même identifiant d'abord, sinon même pièce et même sorte, le plus proche."""
    reste = list(apres)
    paires, perdus = [], []
    par_id = {m.get("id"): m for m in apres if m.get("id")}
    for m in avant:
        n = par_id.get(m.get("id"))
        if n is not None and n in reste and cle_meuble(n) == cle_meuble(m):
            paires.append((m, n)); reste.remove(n)
            continue
        memes = [n for n in reste if cle_meuble(n) == cle_meuble(m)]
        if memes:
            p = m.get("position") or [0, 0]
            n = min(memes, key=lambda n: math.hypot((n.get("position") or [0, 0])[0] - p[0], (n.get("position") or [0, 0])[1] - p[1]))
            paires.append((m, n)); reste.remove(n)
        else:
            perdus.append(m)
    return paires, perdus, reste


def nom(m: dict) -> str:
    p = m.get("position") or [float("nan")] * 2
    return f"{m.get('categorie') or m.get('type')} ({m.get('piece')}, {p[0]:.2f} ; {p[1]:.2f})"


def comparer(a: dict, b: dict, seuil: float) -> list[str]:
    a, b = a.get("logement", a), b.get("logement", b)
    dits = []
    for k in ("hauteur_sous_plafond",):
        if a.get(k) != b.get(k):
            dits.append(f"{k} {a.get(k)} → {b.get(k)}")
    paires, perdus, nouveaux = apparier(a.get("meubles", []), b.get("meubles", []))
    dits += [f"meuble DISPARU : {nom(m)}" for m in perdus] + [f"meuble APPARU : {nom(m)}" for m in nouveaux]
    for m, n in paires:
        e = ecarts(m, n, seuil, sauf=("id", "source"))
        if e:
            dits.append(f"meuble {nom(m)} : " + " ; ".join(e))
    oa, ob = {o["id"]: o for o in a.get("ouvertures", [])}, {o["id"]: o for o in b.get("ouvertures", [])}
    for i in sorted(set(oa) | set(ob)):
        if i not in oa or i not in ob:
            dits.append(f"ouverture {i} : {'apparue' if i in ob else 'disparue'}")
            continue
        e = ecarts(oa[i], ob[i], seuil, sauf=("source",))
        if e:
            dits.append(f"ouverture {i} ({oa[i].get('type')}) : " + " ; ".join(e))
    pa, pb = {p["id"]: p for p in a.get("pieces", [])}, {p["id"]: p for p in b.get("pieces", [])}
    for i in sorted(set(pa) & set(pb)):
        e = ecarts({k: pa[i].get(k) for k in ("sol", "zones_sol")}, {k: pb[i].get(k) for k in ("sol", "zones_sol")}, seuil, sauf=("sol.source",))
        if e:
            dits.append(f"sols de {i} : " + " ; ".join(e[:6]) + (" …" if len(e) > 6 else ""))
    for k in ("passe_plats",):
        e = ecarts({k: a.get(k)}, {k: b.get(k)}, seuil)
        if e:
            dits.append(f"{k} : " + " ; ".join(e))
    return dits


def main() -> int:
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    seuil = float(sys.argv[sys.argv.index("--seuil") + 1]) if "--seuil" in sys.argv else 0.01
    if "--seuil" in sys.argv:
        args.remove(sys.argv[sys.argv.index("--seuil") + 1])
    avant, apres = Path(args[0]), Path(args[1])
    total = 0
    for f in sorted(avant.glob("*/*/logement-meuble.json")):
        g = apres / f.relative_to(avant)
        titre = f"{f.parent.parent.name} version {f.parent.name}"
        if not g.is_file():
            print(f"{titre} : absent du dossier d'après")
            continue
        dits = comparer(lire(f), lire(g), seuil)
        total += len(dits)
        print(f"{titre} : " + ("IDENTIQUE" if not dits else f"{len(dits)} chose(s) ont bougé"))
        for d in dits:
            print("    " + d)
    print(f"TOTAL : {total} chose(s) ont bougé")
    return 0


if __name__ == "__main__":
    sys.exit(main())
