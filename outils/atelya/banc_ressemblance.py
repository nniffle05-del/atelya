r"""LE BANC DE RESSEMBLANCE : pour chaque photo de chaque logement, la maquette d'Atelya vue du même endroit, et une note.

    ..\atelya\.venv\Scripts\python.exe outils\atelya\banc_ressemblance.py <dossier du banc> [--cas app-001 app-004] [--titre "…"]
        [--maquette NOM maquette.blend fiche.json …] [--echantillons 64] [--sans-chaine]

Pourquoi : juger chaque correction d'Atelya sur TOUS les logements à la fois, par une note automatique (moteur/ressemblance.py),
au lieu de regarder le film d'un seul logement (NT, 16/11/2026).

Ce que fait le banc, pour chaque cas de CAS :
1. la maquette est REFAITE par Atelya seul, avec le code du jour (outils/atelya/de_l_ecran_au_film.py … --jusqu-a maquette :
   enveloppe, baies, sols, meubles, maquette), à partir du plan du cas et de la fiche de ses photos placées ;
2. la maquette est rendue depuis la place de chaque photo (outils/habillage/caler_photos.py, éclairage « 2 Jour voilé ») ;
3. chaque photo est comparée à sa vue (note locale, vue reconnue ou non) ; planche côte à côte par logement ; bilan.json.

--maquette (répétable) : noter des maquettes DÉJÀ construites (comparer deux versions d'un même logement sans rien refaire).
Les caméras d'app-001 et app-002 sont celles relevées à la main (le banc juge la maquette, pas la place des photos) ; celles
d'app-004 sont celles qu'Atelya a trouvées seul (pas de relevé à la main).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "habillage"))
PC = RACINE.parent / "atelya"

# Les logements du banc : le plan (logement lu ou relevé, sans sols ni meubles) et la fiche des photos placées.
CAS = {
    "app-001": {"logement": PC / "lectures-claude/app-001/logement.json", "fiche": RACINE / "verites/app-001/cameras-photos.json"},
    "app-002": {"logement": RACINE / "verites/app-002/logement.json", "fiche": RACINE / "verites/app-002/cameras-photos.json"},
    "app-004": {"logement": PC / "lectures-claude/v2/app-004/verification.json", "fiche": PC / "b2/app-004/chaine-v2/cameras-photos-seul.json"},
}
SCENE = "2 Jour voilé"


def dire(*a) -> None:
    print(*a, flush=True)


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def lire_photo(fiche: dict, nom: str) -> np.ndarray:
    from moteur.images import lire_image

    image = lire_image(RACINE / fiche["photos"] / fiche.get("fichier", "{nom}.png").format(nom=nom))
    if image is None:
        raise FileNotFoundError(f"photo {nom} de {fiche['photos']}")
    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def construire(cas: str, d: dict, sortie: Path, jusqu_a: str = "maquette") -> Path:
    """Le logement du cas refait par Atelya seul (code du jour), jusqu'à l'étape `jusqu_a` de la chaîne. Rend le chemin de la
    maquette (.blend), ou du logement meublé si la chaîne s'arrête avant la maquette."""
    logement = json.loads(Path(d["logement"]).read_text(encoding="utf-8"))
    logement = logement.get("logement", logement)  # un verification.json contient le logement lu
    for p in logement["pieces"]:  # Atelya ne voit ni sols ni meubles déjà choisis
        if str((p.get("sol") or {}).get("statut")) != "mesure":
            p.pop("sol", None)
        p["zones_sol"] = []
    logement["meubles"] = []
    sortie.mkdir(parents=True, exist_ok=True)
    depart = sortie / "logement-du-banc.json"
    depart.write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
    r = subprocess.run([sys.executable, str(RACINE / "outils/atelya/de_l_ecran_au_film.py"), str(sortie), str(sortie),
                        "--logement", str(depart), "--fiche", str(d["fiche"]), "--sortie", str(sortie), "--jusqu-a", jusqu_a],
                       cwd=RACINE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (sortie / "journal-chaine.txt").write_text(r.stdout + r.stderr, encoding="utf-8")
    if r.returncode != 0:
        dire(f"PLANTÉ : la chaîne a échoué pour {cas} (code {r.returncode}) : voir {sortie / 'journal-chaine.txt'}")
        sys.exit(r.returncode or 1)
    return sortie / "3d" / "maquette.blend" if jusqu_a == "maquette" else sortie / "logement-meuble.json"


def rendre(fiche: dict, maquette: Path, dossier: Path, echantillons: int) -> dict[str, Path]:
    """La maquette rendue depuis la place de chaque photo, à la taille de la photo."""
    import caler_photos

    releve = {**fiche, "cameras": {}}
    for nom, c in fiche["cameras"].items():
        h, w = lire_photo(fiche, nom).shape[:2]
        releve["cameras"][nom] = {**c, "largeur": w, "hauteur": h}
    caler_photos.rendre(releve, maquette, dossier, echantillons=echantillons, scene=SCENE)
    return {nom: dossier / "rendus" / f"vue-{nom}.png" for nom in releve["cameras"] if (dossier / "rendus" / f"vue-{nom}.png").is_file()}


def planche(titre: str, fiche: dict, vues: dict[str, Path], notes: dict, sortie: Path, colonnes: int = 3, largeur: int = 420) -> None:
    """Photo et maquette côte à côte pour chaque photo, avec sa note (vert : vue reconnue ; rouge : confondue avec une autre)."""
    cases = []
    for nom in sorted(vues):
        photo = lire_photo(fiche, nom)
        vue = cv2.cvtColor(cv2.imdecode(np.fromfile(str(vues[nom]), np.uint8), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB)
        h = int(photo.shape[0] * largeur / photo.shape[1])
        paire = np.hstack([cv2.resize(photo, (largeur, h)), cv2.resize(vue, (largeur, h))])
        bande = np.full((30, paire.shape[1], 3), 255, np.uint8)
        n = notes.get(nom, {})
        couleur = (0, 130, 40) if n.get("rang") == 1 else (200, 0, 0)
        cv2.putText(bande, f"{nom}   note {100 * n.get('locale', 0):.0f}/100   rang {n.get('rang', '?')}", (8, 21),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, couleur, 2, cv2.LINE_AA)
        cases.append(np.vstack([bande, paire]))
    if not cases:
        return
    hmax = max(c.shape[0] for c in cases)
    cases = [np.vstack([c, np.full((hmax - c.shape[0], c.shape[1], 3), 255, np.uint8)]) for c in cases]
    while len(cases) % colonnes:
        cases.append(np.full_like(cases[0], 255))
    lignes = [np.hstack([np.hstack([c, np.full((hmax, 12, 3), 255, np.uint8)]) for c in cases[i:i + colonnes]]) for i in range(0, len(cases), colonnes)]
    feuille = np.vstack(lignes)
    tete = np.full((46, feuille.shape[1], 3), 255, np.uint8)
    cv2.putText(tete, titre.encode("ascii", "replace").decode(), (8, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.imencode(".jpg", cv2.cvtColor(np.vstack([tete, feuille]), cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tofile(str(sortie))


def noter(fiche: dict, vues: dict[str, Path], oeil) -> dict:
    from moteur import ressemblance

    photos = {n: ressemblance.carres(oeil, lire_photo(fiche, n)) for n in vues}
    rendus = {n: ressemblance.carres(oeil, cv2.cvtColor(cv2.imdecode(np.fromfile(str(p), np.uint8), cv2.IMREAD_COLOR), cv2.COLOR_BGR2RGB))
              for n, p in vues.items()}
    return ressemblance.tableau(photos, rendus)


def main() -> int:
    ap = argparse.ArgumentParser(description="Banc de ressemblance photo / maquette sur tous les logements")
    ap.add_argument("sortie", type=Path)
    ap.add_argument("--cas", nargs="*", default=list(CAS))
    ap.add_argument("--maquette", nargs=3, action="append", default=[], metavar=("NOM", "MAQUETTE.blend", "FICHE.json"),
                    help="noter une maquette déjà construite (répétable)")
    ap.add_argument("--echantillons", type=int, default=64)
    ap.add_argument("--titre", default="")
    ap.add_argument("--sans-chaine", action="store_true", help="reprendre les maquettes déjà refaites dans ce dossier")
    a = ap.parse_args()
    from moteur import ressemblance
    from moteur.oeil_dinov2 import charger

    a.sortie.mkdir(parents=True, exist_ok=True)
    travaux = []  # (nom, fiche, maquette)
    if a.maquette:
        for nom, blend, fiche in a.maquette:
            travaux.append((nom, json.loads(Path(fiche).read_text(encoding="utf-8")), Path(blend)))
    else:
        for cas in a.cas:
            d = CAS[cas]
            debut = time.time()
            blend = a.sortie / cas / "3d" / "maquette.blend"
            if not (a.sans_chaine and blend.is_file()):
                dire(f"{cas} : Atelya refait la maquette…")
                blend = construire(cas, d, a.sortie / cas)
                dire(f"{cas} : maquette refaite en {time.time() - debut:.0f} s")
            travaux.append((cas, json.loads(Path(d["fiche"]).read_text(encoding="utf-8")), blend))
    oeil = None
    bilan = {"version": ressemblance.VERSION, "titre": a.titre, "date": time.strftime("%Y-%m-%d %H:%M"), "logements": {}}
    for nom, fiche, blend in travaux:
        debut = time.time()
        vues = rendre(fiche, blend, a.sortie / nom / "vues", a.echantillons)
        dire(f"{nom} : {len(vues)} vues rendues en {time.time() - debut:.0f} s")
        oeil = oeil or charger("vitb14")
        notes = noter(fiche, vues, oeil)
        r = ressemblance.resume(notes)
        bilan["logements"][nom] = {"resume": r, "photos": notes}
        planche(f"{nom} {a.titre} : note {100 * r.get('locale', 0):.1f}/100, {r.get('reconnues', 0)} vues reconnues sur {r.get('photos', 0)}",
                fiche, vues, notes, a.sortie / f"planche-{nom}.jpg")
        dire(f"{nom} : note {100 * r.get('locale', 0):.1f}/100, vues reconnues {r.get('reconnues', 0)}/{r.get('photos', 0)}, marge {100 * r.get('marge', 0):+.1f}")
    toutes = [v for l in bilan["logements"].values() for v in l["photos"].values()]
    if toutes:
        bilan["ensemble"] = {"photos": len(toutes), "locale": round(float(np.mean([v["locale"] for v in toutes])), 4),
                             "reconnues": sum(v["rang"] == 1 for v in toutes)}
        dire(f"ENSEMBLE : note {100 * bilan['ensemble']['locale']:.1f}/100, vues reconnues {bilan['ensemble']['reconnues']}/{len(toutes)}")
    (a.sortie / "bilan.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
