r"""LE JUGE DE LA LUMIÈRE DU FILM (point 2, 18/11/2026) : photo du client contre image du FILM Unreal, en chiffres.

    ..\atelya\.venv\Scripts\python.exe outils\unreal\juger_lumiere.py <sortie> app-001=<dossier des vues> [app-002=… …]
        [--titre "…"] [--rejouer crans[,usine][,sat=1.3]] [--sans app-002:photo-09 …]

<dossier des vues> : une sortie de outils/unreal/vues_photos_unreal.py (vue-<photo>.png = l'image du film prise de la place de
la photo, trajet-<photo>.json = comment elle a été tournée).

Pourquoi : juger la lumière du film là où le client la verra (CLAUDE.md § 0), avec les photos du client comme modèle, et avec
des chiffres qui valent pour tous les logements (moteur/juge_lumiere.py : murs, sol, sol contre mur, image entière, lumière
dans la scène). Écrit <sortie>/lumiere.json, lumiere.txt et une planche par logement (la photo | l'image du film remise
exactement dans le cadre de la photo, avec les couleurs mesurées).
LA VUE PAR LES FENÊTRES est jugée aussi (moteur/juge_lumiere.mesurer_dehors : couleur, dessin, décalage, netteté, photo contre
film sur les mêmes pixels) : planche dehors-<logement>.jpg (la fenêtre de la photo | celle du film). Si le dossier des vues
contient contexte.json (écrit par vues_photos_unreal.py --logement), son logement et ses meubles devant les fenêtres servent.
--rejouer : PRÉVISION sans relancer Unreal : les images du film sont rejouées avec d'autres réglages d'image avant d'être
jugées (crans d'exposition en plus ; « usine » = la courbe des tons d'origine d'Unreal ; « sat=1.3 » = vivacité des couleurs).
À confirmer par un vrai rendu.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(RACINE / "outils" / "atelya"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from banc_ressemblance import CAS  # noqa: E402
from moteur import juge_lumiere as jl  # noqa: E402
from moteur import pas_du_sol, photographe  # noqa: E402
from moteur import vitrages as dessin_des_fenetres  # noqa: E402
from moteur.images import ecrire_image, lire_image  # noqa: E402
from moteur.sol_a_plat import photos_a_plat  # noqa: E402

lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
MESURES = (("murs L", "murs", "L"), ("murs rouge", "murs", "a"), ("murs jaune", "murs", "b"), ("relief des murs", "murs", "relief"),
           ("sol L", "sol", "L"), ("sol rouge", "sol", "a"), ("sol jaune", "sol", "b"), ("sol vivacité", "sol", "C"),
           ("sol contre mur", "sol_contre_mur", "clarte"), ("image sombres", "image", "L5"), ("image milieu", "image", "L50"),
           ("image clairs", "image", "L95"), ("image vivacité", "image", "C"), ("image brûlée %", "image", "brule"),
           ("dehors L", "dehors", "L"), ("dehors vivacité", "dehors", "C"), ("dehors sombres", "dehors", "sombres"),
           ("dehors contraste", "dehors", "contraste"))
DEHORS = (("dehors : écart de couleur", "ecart_couleur"), ("dehors : écart point par point", "ecart_point"),
          ("dehors : dessin (1 = le même)", "ressemblance"), ("dehors : dessin, film recalé", "ressemblance_recalee"),
          ("dehors : netteté (1 = photo)", "nettete"), ("dehors : vide %", "vide"))


def decrire(image: np.ndarray, vue, logement: dict, pixels_sol, valide=None) -> dict:
    murs = jl.mesurer_murs(jl.points_de_murs_vus(image, vue.camera, logement, vue.piece, vue.point_de_vue, valide))
    sol = jl.mesurer_sol(pixels_sol)
    return {"murs": murs, "sol": sol, "sol_contre_mur": jl.sol_contre_mur(sol, murs), "image": jl.mesurer_image(image, valide)}


def scene(d: dict) -> dict | None:
    """Murs et sol du film DANS LA SCÈNE (avant la pellicule) : lumière linéaire et rapport sol / mur."""
    if not d["murs"] or not d["sol"]:
        return None
    m = jl.scene_du_film(jl.affiche(d["murs"]["lineaire"]))
    s = jl.scene_du_film(jl.affiche(d["sol"]["lineaire"]))
    return {"murs": [round(float(x), 3) for x in m], "sol": [round(float(x), 3) for x in s],
            "sol_contre_mur": round(float((s @ jl.POIDS) / (m @ jl.POIDS)), 3)}


def pastilles(d: dict, largeur: int, titre: str) -> np.ndarray:
    """Bandeau sous une image : la couleur mesurée des murs et celle du sol, avec leurs valeurs."""
    bande = np.full((64, largeur, 3), 255, np.uint8)
    x = 6
    cv2.putText(bande, titre, (x, 16), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (90, 90, 90), 1, cv2.LINE_AA)
    for nom, cle in (("murs", "murs"), ("sol", "sol")):
        c = d.get(cle)
        if not c:
            continue
        bande[24:60, x:x + 70] = c["rgb"][::-1]
        cv2.rectangle(bande, (x, 24), (x + 70, 60), (150, 150, 150), 1)
        cv2.putText(bande, f"{nom} {c['rgb'][0]} {c['rgb'][1]} {c['rgb'][2]}", (x + 78, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
        cv2.putText(bande, f"clarte {c['L']:.0f} vivacite {c['C']:.0f}", (x + 78, 57), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (90, 90, 90), 1, cv2.LINE_AA)
        x += 290
    r = d.get("sol_contre_mur")
    if r:
        cv2.putText(bande, f"sol / mur {r['clarte']:.2f}", (x, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    return bande


def juger(cas: str, dossier: Path, sortie: Path, pds, rejouer=None, sans=()) -> tuple[dict, list[np.ndarray]]:
    """Les mesures de toutes les vues d'un logement (sauf celles de `sans`), et les lignes de sa planche."""
    fiche, logement = lire(CAS[cas]["fiche"]), lire(CAS[cas]["logement"])
    logement = logement.get("logement", logement)
    fiche["cameras"] = {n: c for n, c in fiche["cameras"].items() if (dossier / f"vue-{n}.png").is_file() and f"{cas}:{n}" not in sans}
    if not fiche["cameras"]:
        print(f"PLANTÉ : aucune image vue-<photo>.png dans {dossier}", flush=True)
        sys.exit(1)
    contexte = lire(dossier / "contexte.json") if (dossier / "contexte.json").is_file() else {}
    logement_dehors = lire(contexte["logement"]) if contexte.get("logement") else logement
    logement_dehors = logement_dehors.get("logement", logement_dehors)
    a_cote = Path(contexte["logement"]).with_name("vitrages.json") if contexte.get("logement") else None
    vitrages_lus = lire(a_cote) if a_cote is not None and a_cote.is_file() else None
    cadres = sortie / "cadres" / cas
    cadres.mkdir(parents=True, exist_ok=True)
    valides = {}
    for nom, d in fiche["cameras"].items():
        film = lire_image(dossier / f"vue-{nom}.png")
        trajet = lire(dossier / f"trajet-{nom}.json") if (dossier / f"trajet-{nom}.json").is_file() else {}
        image, valides[nom] = jl.film_au_cadre(cv2.cvtColor(film, cv2.COLOR_BGR2RGB), d, trajet)
        if rejouer is not None:
            image = rejouer(image)
            image[~valides[nom]] = 0
        ecrire_image(cadres / f"vue-{nom}.png", cv2.cvtColor(image, cv2.COLOR_RGB2BGR))
    muet = lambda *_: None
    vues = photos_a_plat(fiche, logement, RACINE, journal=muet, pas_du_sol=lambda n, rgb: pds.masque(f"{cas}/{n}", rgb))
    films = photos_a_plat({**fiche, "photos": str(cadres), "fichier": "vue-{nom}.png"}, logement, RACINE, journal=muet,
                          pas_du_sol=lambda n, rgb: ~valides[n])
    films = {n: v for n, _, v in films}
    bilan, lignes, fenetres = {}, [], []
    for nom, piece, vue in vues:
        f = films.get(nom)
        if f is None:
            continue
        propre = (vue.finesse > 0) & (f.finesse > 0)
        for v in (vue, f):
            if v.douteux is not None:
                propre &= ~v.douteux
        photo = decrire(vue.photo, vue, logement, jl.dominante(vue.image[propre]))
        film = decrire(f.photo, f, logement, jl.dominante(f.image[propre]), valides[nom])
        film["scene"] = scene(film)
        # la vue par les fenêtres : les mêmes pixels de la photo et du film
        image_film = f.photo if f.photo.shape == vue.photo.shape else cv2.resize(f.photo, vue.photo.shape[1::-1])
        echelle = vue.photo.shape[1] / 1206.0
        masque = jl.masque_du_dehors(jl.camera_depuis_dict(fiche["cameras"][nom]["camera"]), vue.photo.shape[1::-1], logement_dehors,
                                     (contexte.get("caches") or {}).get(nom, []), marge_px=max(1, int(round(4 * echelle))))
        # LE DESSIN DES FENÊTRES lu sur cette photo (moteur/vitrages.py, F2, 20/11/2026) : la vue se juge sur les VITRES NUES de la
        # photo, pas sur le trou du plan (qui tombe à côté de la vraie fenêtre et couvre ses montants et son rideau : le juge
        # récompensait alors un film qui recopiait les montants de la photo dans la vue)
        lues = {i: v for i, v in dessin_des_fenetres.d_une_photo(vitrages_lus, nom, vue.photo.shape[1::-1]).items() if v["vue"] == "oui"}
        if lues:
            genre = masque.dtype
            masque = np.zeros(masque.shape, bool)
            for v in lues.values():
                masque |= v["vitres"] > 0
            for x0, y0, x1, y1 in (contexte.get("caches") or {}).get(nom, []):
                masque[max(0, int(y0)):int(np.ceil(y1)), max(0, int(x0)):int(np.ceil(x1))] = False
            masque = masque.astype(genre)
        dehors = jl.mesurer_dehors(vue.photo, image_film, masque, valides[nom])
        if dehors:
            dehors["zone"] = "vitres lues" if lues else "trou du plan"
        photo["dehors"], film["dehors"] = (dehors["photo"], dehors["film"]) if dehors else (None, None)
        bilan[nom] = {"piece": piece, "photo": photo, "film": film, "dehors": dehors,
                      "ecart_murs": jl.ecart(photo["murs"], film["murs"]), "ecart_sol": jl.ecart(photo["sol"], film["sol"])}
        if dehors:
            ys, xs = np.nonzero(masque)
            m = int(30 * echelle)
            x0, x1 = max(0, xs.min() - m), min(masque.shape[1], xs.max() + m)
            y0, y1 = max(0, ys.min() - m), min(masque.shape[0], ys.max() + m)
            hauteur = 300
            zoom = lambda im: cv2.resize(cv2.cvtColor(np.ascontiguousarray(im[y0:y1, x0:x1]), cv2.COLOR_RGB2BGR),
                                         (max(2, int(round((x1 - x0) * hauteur / (y1 - y0)))), hauteur), interpolation=cv2.INTER_CUBIC)
            contour = vue.photo.copy()
            contour[cv2.dilate(masque.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool) & ~masque] = (255, 0, 255)
            paire = np.concatenate([zoom(vue.photo), np.full((hauteur, 8, 3), 255, np.uint8), zoom(image_film),
                                    np.full((hauteur, 8, 3), 255, np.uint8), zoom(contour)], 1)
            texte = (f"{cas} {nom} ({piece}) : photo | film | zone jugee ; ecart point par point {dehors['ecart_point']}, dessin "
                     f"{dehors['ressemblance']} (recale {dehors['ressemblance_recalee']}, glisse de {dehors['decalage_px']} px), "
                     f"nettete {dehors['nettete']}, sombres {dehors['photo']['sombres']:.0f} -> {dehors['film']['sombres']:.0f}, "
                     f"vivacite {dehors['photo']['C']:.0f} -> {dehors['film']['C']:.0f}")
            fenetres.append((texte, paire))
        largeur = 760
        h = int(round(vue.photo.shape[0] * largeur / vue.photo.shape[1]))
        reduire = lambda im: cv2.resize(cv2.cvtColor(im, cv2.COLOR_RGB2BGR), (largeur, h), interpolation=cv2.INTER_AREA)
        blanc = np.full((h, 10, 3), 255, np.uint8)
        lignes.append(np.concatenate([reduire(vue.photo), blanc, reduire(f.photo)], 1))
        lignes.append(np.concatenate([pastilles(photo, largeur, f"{cas} {nom} ({piece}) : la photo"), blanc[:64],
                                      pastilles(film, largeur, "l'image du film")], 1))
    if fenetres:  # la planche des fenêtres : une ligne par vue
        largeur = max(p.shape[1] for _, p in fenetres)
        blocs = []
        for texte, paire in fenetres:
            bandeau = np.full((26, max(largeur, 1500), 3), 255, np.uint8)
            cv2.putText(bandeau, texte, (4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
            ligne = np.full((paire.shape[0], bandeau.shape[1], 3), 255, np.uint8)
            ligne[:, :paire.shape[1]] = paire[:, :bandeau.shape[1]]
            blocs += [bandeau, ligne]
        ecrire_image(sortie / f"dehors-{cas}.jpg", np.concatenate(blocs, 0))
    return bilan, lignes


def valeur(d: dict, bloc: str, cle: str):
    b = d.get(bloc)
    return None if not b or b.get(cle) is None else float(b[cle])


def resume(bilans: dict) -> list[str]:
    """Le tableau des écarts moyens film − photo, par logement et pour tous."""
    lignes = []
    groupes = {**{cas: list(b.values()) for cas, b in bilans.items()}, "TOUS": [v for b in bilans.values() for v in b.values()]}
    for cas, vues in groupes.items():
        if not vues:
            continue
        lignes.append(f"== {cas} ({len(vues)} vues) : photo -> film (film - photo)")
        for titre, bloc, cle in MESURES:
            paires = [(valeur(v["photo"], bloc, cle), valeur(v["film"], bloc, cle)) for v in vues]
            paires = [(p, f) for p, f in paires if p is not None and f is not None]
            if not paires:
                continue
            p, f = np.mean([x for x, _ in paires]), np.mean([y for _, y in paires])
            lignes.append(f"   {titre:<18} {p:7.2f} -> {f:7.2f}   ({f - p:+.2f})   [{len(paires)} vues]")
        for titre, cle in (("écart de couleur des murs", "ecart_murs"), ("écart de couleur du sol", "ecart_sol")):
            e = [v[cle] for v in vues if v[cle] is not None]
            if e:
                lignes.append(f"   {titre:<28} {np.mean(e):5.1f}   [{len(e)} vues]")
        for titre, cle in DEHORS:
            e = [v["dehors"][cle] for v in vues if v.get("dehors")]
            if e:
                lignes.append(f"   {titre:<32} {np.mean(e):6.2f}   [{len(e)} vues]")
        s = [v["film"]["scene"] for v in vues if v["film"].get("scene")]
        if s:
            lignes.append(f"   dans la scène du film (avant pellicule) : murs {np.mean([x['murs'] for x in s], 0).round(3).tolist()} "
                          f"sol {np.mean([x['sol'] for x in s], 0).round(3).tolist()} sol / mur {np.mean([x['sol_contre_mur'] for x in s]):.3f}")
    return lignes


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sortie", type=Path)
    ap.add_argument("vues", nargs="+", help="app-001=<dossier des vues du film>")
    ap.add_argument("--titre", default="")
    ap.add_argument("--rejouer", default="", help="prévision : crans d'exposition en plus[,usine] (ex. 1.5 ou 0.8,usine)")
    ap.add_argument("--sans", nargs="*", default=[], metavar="LOGEMENT:PHOTO",
                    help="vues à ne pas juger (ex. une vue de cuisine où la caméra du film est dans un meuble)")
    a = ap.parse_args()
    a.sortie.mkdir(parents=True, exist_ok=True)
    rejouer = None
    if a.rejouer.endswith(".json"):  # un réglage complet (pc/verification/prevoir_reglages_image.py)
        voulu = lire(a.rejouer)
        pellicule = {**photographe.PELLICULE, "film_slope": voulu["pente"], "film_toe": voulu["pied"], "film_shoulder": voulu["epaule"]}
        couleurs = {**photographe.PELLICULE_COULEURS, "saturation": voulu["vivacite"]}
        rejouer = lambda im: jl.refaire_l_image(im, voulu["crans"], pellicule, couleurs)
    elif a.rejouer:
        morceaux = a.rejouer.split(",")
        crans = float(morceaux[0])
        pellicule = photographe.PELLICULE_USINE if "usine" in morceaux[1:] else None
        couleurs = dict(photographe.PELLICULE_COULEURS)
        for m in morceaux[1:]:
            if m.startswith("sat="):
                couleurs["saturation"] = float(m[4:])
        rejouer = lambda im: jl.refaire_l_image(im, crans, pellicule, couleurs)
    pds = pas_du_sol.charger(avec_dino=False)
    bilans, textes = {}, [a.titre] if a.titre else []
    for demande in a.vues:
        cas, dossier = demande.split("=", 1)
        bilans[cas], lignes = juger(cas, Path(dossier), a.sortie, pds, rejouer, set(a.sans))
        for nom, v in bilans[cas].items():
            p, f = v["photo"], v["film"]
            c = lambda d, k: "—" if not d else f"{d['rgb']} L {d['L']:.0f} C {d['C']:.0f}"
            r = lambda d: "—" if not d.get("sol_contre_mur") else f"{d['sol_contre_mur']['clarte']:.2f}"
            textes.append(f"{cas} {nom} ({v['piece']}) : MURS photo {c(p['murs'], 0)} | film {c(f['murs'], 0)} | écart {v['ecart_murs']} ; "
                          f"SOL photo {c(p['sol'], 0)} | film {c(f['sol'], 0)} | écart {v['ecart_sol']} ; sol / mur photo {r(p)} film {r(f)}"
                          + (f" (scène {f['scene']['sol_contre_mur']:.2f})" if f.get("scene") else ""))
        if lignes:
            titre = np.full((44, lignes[0].shape[1], 3), 255, np.uint8)
            cv2.putText(titre, "la photo du client (le modele)", (6, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2, cv2.LINE_AA)
            cv2.putText(titre, "l'image du FILM Unreal, meme endroit, meme cadre", (776, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 0, 0), 2, cv2.LINE_AA)
            ecrire_image(a.sortie / f"lumiere-{cas}.jpg", np.concatenate([titre] + lignes, 0))
    textes += resume(bilans)
    (a.sortie / "lumiere.json").write_text(json.dumps(bilans, ensure_ascii=False, indent=1), encoding="utf-8")
    (a.sortie / "lumiere.txt").write_text("\n".join(textes), encoding="utf-8")
    print("\n".join(textes), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
