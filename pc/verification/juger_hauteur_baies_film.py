r"""LE JUGE DU BAS ET DU HAUT DES FENÊTRES DANS LE FILM (23/11/2026) : la photo du client contre l'image du film prise du même
endroit.

    ..\atelya\.venv\Scripts\python.exe pc\verification\juger_hauteur_baies_film.py <sortie> app-004=<vues hier>,<logement hier>,<vues aujourd'hui>,<logement aujourd'hui> [app-001=…]

Plusieurs dossiers de vues peuvent être donnés pour « hier » (séparés par « + ») : la vue est prise dans le premier qui l'a.

Sur la PHOTO, le haut et le bas de la fenêtre sont ceux de son tour lu (verites/<logement>/lecture_des_vitrages.py), au milieu
de sa largeur. Dans l'image du FILM, la fenêtre est là où la maquette la construit : le milieu de son bord haut et de son bord
bas, sur la face du mur côté pièce, projetés par l'appareil de la vue ; le bord est ensuite cherché dans l'image, tout près
(le plus fort changement de clarté de haut en bas), pour lire ce que le film MONTRE et non ce que la maquette prétend.
On compare la PLACE dans l'image (part de la hauteur de l'image) du haut et du bas, photo contre film, hier et aujourd'hui.
Un haut dit « au moins » (fenêtre derrière un voilage) est jugé de même : le film doit montrer la fenêtre au moins jusque-là.
Sorties : le tableau, et <sortie>/fenetre-<logement>-<photo>-<baie>.jpg (photo | hier | aujourd'hui, à REGARDER : trait ROUGE =
le haut, trait BLEU = le bas).
La PLACE dans l'image mêle la hauteur de la fenêtre et la place de l'appareil (calé à 0,3-0,5 m : un appareil trop près grossit
toute l'image). Seconde mesure, qui s'en affranchit : la fenêtre ENTRE LE SOL ET LE PLAFOND de l'image (où tombent son bas et
son haut, en parts de la hauteur du mur, à la colonne de la fenêtre) : sur la photo d'après les lignes lues du sol et du
plafond, dans le film d'après le pied et le haut du mur de la maquette cherchés de même dans l'image. Les mètres se jugent sur
le papier (sonde_hauteur_baies.py : lignes contre relief).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "lecture_photos"))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
sys.path.insert(0, str(RACINE / "pc" / "verification"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GRIS = np.array([0.299, 0.587, 0.114])
QUAND = {"hier": "hier", "auj": "aujourd'hui"}
AUTOUR = 0.02  # le bord est cherché à ± 2 % de la hauteur de l'image de l'endroit où la maquette le met


def bord_dans_l_image(rgb: np.ndarray, x: float, y: float) -> float:
    """Le bord couché le plus net de l'image près de (x, y) : la ligne où la clarté change le plus de haut en bas, sur une
    bande de 30 pixels de large. Rend y tel quel si rien de net (changement de moins de 6 niveaux)."""
    H, W = rgb.shape[:2]
    x0, x1 = int(max(0, x - 15)), int(min(W, x + 15))
    m = int(AUTOUR * H)
    y0, y1 = int(max(1, y - m)), int(min(H - 1, y + m))
    if x1 - x0 < 5 or y1 - y0 < 4:
        return float(y)
    profil = (rgb[y0 - 1:y1 + 1, x0:x1].astype(float) @ GRIS).mean(1)
    saut = np.abs(profil[2:] - profil[:-2])
    k = int(np.argmax(saut))
    return float(y0 + k) if saut[k] >= 6 else float(y)


def juger(cas: str, spec: str, sortie: Path) -> list[dict]:
    import cv2

    from banc_ressemblance import CAS
    from moteur import hauteur_baies as hb
    from moteur.camera_photo import camera_depuis_dict, projeter
    from moteur.equipements import repere_de_la_baie
    from moteur.images import ecrire_image, lire_image
    from preparer_vitrages import photo_de
    from sonde_hauteur_baies import lecture_de

    vues_hier, logement_hier, vues_auj, logement_auj = spec.split(",")
    logements = {"hier": json.loads(Path(logement_hier).read_text(encoding="utf-8")), "auj": json.loads(Path(logement_auj).read_text(encoding="utf-8"))}
    dossiers = {"hier": [Path(p) for p in vues_hier.split("+")], "auj": [Path(p) for p in vues_auj.split("+")]}
    fiche = json.loads(Path(CAS[cas]["fiche"]).read_text(encoding="utf-8"))
    lignes = []
    for nom, fenetres in lecture_de(cas)["photos"].items():
        for f in (f for f in fenetres if f.get("cadre")):
            photo = lire_image(photo_de(fiche, Path(CAS[cas]["fiche"]).parent, nom))
            Hp, Wp = photo.shape[:2]
            hg, hd, bd, bg = (np.array(c, float) for c in f["cadre"])
            x_photo = float((hg[0] + hd[0] + bd[0] + bg[0]) / 4)
            ligne = {"cas": cas, "photo": nom, "baie": f["baie"], "au_moins": bool(f.get("haut_au_moins")),
                     "photo_haut": float((hg[1] + hd[1]) / 2) / Hp, "photo_bas": None if f.get("bas_cache") else float((bg[1] + bd[1]) / 2) / Hp}
            parts = hb.niveaux_d_une_photo([g for g in fenetres if g["baie"] == f["baie"]]) or {}
            ligne["photo_part_haut"], ligne["photo_part_bas"] = parts.get("haut"), parts.get("bas")
            cam = camera_depuis_dict(fiche["cameras"][nom]["camera"])
            cases = [("la photo du client", photo, 1.0, x_photo, ligne["photo_haut"] * Hp, None if ligne["photo_bas"] is None else ligne["photo_bas"] * Hp)]
            for quand in QUAND:
                fichier = next((d / f"vue-{nom}.png" for d in dossiers[quand] if (d / f"vue-{nom}.png").exists()), None)
                o = next((o for o in logements[quand]["ouvertures"] if o["id"] == f["baie"]), None)
                r = repere_de_la_baie(o, logements[quand]) if o is not None else None
                if fichier is None or r is None:
                    continue
                film = cv2.cvtColor(lire_image(fichier), cv2.COLOR_BGR2RGB)
                k = film.shape[1] / Wp
                allege = float(o.get("allege", 0.0) or 0.0)
                # le bas de la MENUISERIE : au-dessus de la partie pleine que son dessin compte dans la baie, s'il y en a une
                plein = float((o.get("dessin") or {}).get("soubassement") or 0.0) * float(o["hauteur"])
                haut, bas = (projeter([*r["centre"], z], cam) for z in (allege + float(o["hauteur"]), allege + plein))
                if haut[2] <= 0.1 or bas[2] <= 0.1:
                    continue
                y_haut, y_bas = bord_dans_l_image(film, haut[0] * k, haut[1] * k), bord_dans_l_image(film, bas[0] * k, bas[1] * k)
                ligne[f"{quand}_haut"], ligne[f"{quand}_bas"] = y_haut / film.shape[0], y_bas / film.shape[0]
                # la fenêtre entre le sol et le plafond de l'IMAGE du film (à sa colonne) : indépendant de la place de l'appareil
                sol, plafond = (projeter([*r["centre"], z], cam) for z in (0.0, float(logements[quand].get("hauteur_sous_plafond", 2.5))))
                y_sol, y_plafond = bord_dans_l_image(film, sol[0] * k, sol[1] * k), bord_dans_l_image(film, plafond[0] * k, plafond[1] * k)
                if y_sol - y_plafond > 20:
                    ligne[f"{quand}_part_haut"] = (y_sol - y_haut) / (y_sol - y_plafond)
                    ligne[f"{quand}_part_bas"] = (y_sol - y_bas) / (y_sol - y_plafond)
                cases.append((f"le film, {QUAND[quand]}", cv2.cvtColor(film, cv2.COLOR_RGB2BGR), k, haut[0] * k, y_haut, y_bas))
            bandes = []
            for titre, img, k, x, y_haut, y_bas in cases:
                demi = int(190 * k)
                x0 = int(max(0, min(img.shape[1] - 2 * demi, x - demi)))
                coupe = img[:, x0:x0 + 2 * demi].copy()
                cv2.line(coupe, (int(x - x0) - int(60 * k), int(y_haut)), (int(x - x0) + int(60 * k), int(y_haut)), (0, 0, 255), max(1, int(k)))
                if y_bas is not None:
                    cv2.line(coupe, (int(x - x0) - int(60 * k), int(y_bas)), (int(x - x0) + int(60 * k), int(y_bas)), (255, 80, 0), max(1, int(k)))
                coupe = cv2.resize(coupe, (380, int(380 * coupe.shape[0] / coupe.shape[1])), interpolation=cv2.INTER_AREA)[:800]
                cv2.rectangle(coupe, (0, 0), (250, 20), (255, 255, 255), -1)
                cv2.putText(coupe, titre.replace("'", " "), (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)
                bandes.append(coupe)
            h = min(b.shape[0] for b in bandes)
            ecrire_image(sortie / f"fenetre-{cas}-{nom}-{f['baie']}.jpg", np.hstack([b[:h] for b in bandes]))
            lignes.append(ligne)
    return lignes


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    sortie = Path(sys.argv[1])
    sortie.mkdir(parents=True, exist_ok=True)
    lignes = []
    for arg in sys.argv[2:]:
        cas, _, spec = arg.partition("=")
        lignes += juger(cas, spec, sortie)
    dire = lambda x: "  —  " if x is None else f"{100 * x:5.1f}"  # noqa: E731
    print("vue                 baie  | HAUT de la fenêtre dans l'image (% de sa hauteur) : photo, hier, aujourd'hui | BAS : photo, hier, aujourd'hui")
    for l in lignes:
        print(f"{l['cas']} {l['photo']:9s} {l['baie']:5s} | {dire(l['photo_haut'])}{'+' if l['au_moins'] else ' '} {dire(l.get('hier_haut'))} {dire(l.get('auj_haut'))}"
              f" | {dire(l['photo_bas'])} {dire(l.get('hier_bas'))} {dire(l.get('auj_bas'))}")
    for quand in QUAND:
        # seulement les vues tournées hier ET aujourd'hui : la même liste des deux côtés
        deux = [l for l in lignes if l.get("hier_haut") is not None and l.get("auj_haut") is not None]
        # un haut « au moins » : le film ne se trompe que s'il montre la fenêtre moins haut que la photo
        hauts = [max(0.0, l[f"{quand}_haut"] - l["photo_haut"]) if l["au_moins"] else abs(l[f"{quand}_haut"] - l["photo_haut"]) for l in deux]
        bas = [abs(l[f"{quand}_bas"] - l["photo_bas"]) for l in deux if l["photo_bas"] is not None]
        print(f"{QUAND[quand]:12s}: écart moyen du HAUT {100 * np.mean(hauts) if hauts else float('nan'):.1f} % de la hauteur de l'image "
              f"({len(hauts)} vues), du BAS {100 * np.mean(bas) if bas else float('nan'):.1f} % ({len(bas)} vues)")
    print()
    print("LA FENÊTRE ENTRE LE SOL ET LE PLAFOND DE L'IMAGE (parts de la hauteur du mur ; ne dépend pas de la place de l'appareil)")
    print("vue                 baie  | HAUT : photo, hier, aujourd'hui | BAS : photo, hier, aujourd'hui")
    part = lambda x: "  —  " if x is None else f"{x:5.2f}"  # noqa: E731
    for l in lignes:
        if l.get("photo_part_haut") is not None:
            print(f"{l['cas']} {l['photo']:9s} {l['baie']:5s} | {part(l['photo_part_haut'])}{'+' if l['au_moins'] else ' '} {part(l.get('hier_part_haut'))} {part(l.get('auj_part_haut'))}"
                  f" | {part(l.get('photo_part_bas'))} {part(l.get('hier_part_bas'))} {part(l.get('auj_part_bas'))}")
    for quand in QUAND:
        deux = [l for l in lignes if l.get("photo_part_haut") is not None and l.get("hier_part_haut") is not None and l.get("auj_part_haut") is not None]
        hauts = [max(0.0, l["photo_part_haut"] - l[f"{quand}_part_haut"]) if l["au_moins"] else abs(l[f"{quand}_part_haut"] - l["photo_part_haut"]) for l in deux]
        bas = [abs(l[f"{quand}_part_bas"] - l["photo_part_bas"]) for l in deux if l.get("photo_part_bas") is not None]
        print(f"{QUAND[quand]:12s}: écart moyen du HAUT {100 * np.mean(hauts) if hauts else float('nan'):.1f} % de la hauteur du mur "
              f"({len(hauts)} vues), du BAS {100 * np.mean(bas) if bas else float('nan'):.1f} % ({len(bas)} vues)")
    (sortie / "hauteur-baies-film.json").write_text(json.dumps(lignes, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
