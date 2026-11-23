r"""LE DESSIN DE CHAQUE FENÊTRE DANS LA MAQUETTE, d'après les photos (F2 pièce 3, 20/11/2026).

Pourquoi. Depuis F2 la vue par les fenêtres du film est propre : plus de montants ni de garde-corps peints au loin. Ce que la
photo montre DEVANT la vue doit donc exister pour de vrai dans la maquette, sinon la fenêtre du film est un grand trou nu.
Jusqu'ici toutes les fenêtres d'Atelya avaient le même cadre (6 cm tout autour, un montant au milieu au-delà d'un mètre), sans
petits bois, sans partie pleine sous les vitres, sans garde-corps. Et une chose construite tient quand la caméra bouge (visite
libre), pas une chose peinte sur une toile à 30 m.

Moyen. La lecture des photos dit déjà le dessin de chaque fenêtre (moteur/vitrages.py : un vitrage par vantail, ses barres, le
tour de la menuiserie, la ligne du sol sous la fenêtre, le garde-corps). Ici Atelya en tire la GÉOMÉTRIE :
  - chaque photo est redressée de sa perspective sur le TOUR de la menuiserie (`cadre`) : tout devient des PARTS de la baie
    (0 à 1 en largeur et en hauteur). On ne mesure rien en mètres sur la photo : la fenêtre de la maquette est décalée de la
    vraie de 30 à 50 cm (place des photos), ses parts, elles, sont justes ;
  - si le plan fait descendre la baie jusqu'au sol et que la photo montre une partie PLEINE entre le bas de la menuiserie et le
    sol (allège basse d'une fenêtre ancienne, marche d'une baie coulissante), elle est gardée (`soubassement`) ;
  - plusieurs photos de la même fenêtre sont ACCORDÉES : celles qui voient le tour de la menuiserie font foi, le dessin le plus
    souvent vu l'emporte (à égalité : la photo la plus de face), chaque part est la médiane des photos d'accord ;
  - une fenêtre jamais lue garde le cadre d'avant.
Le dessin est écrit dans le champ `dessin` de l'ouverture (moteur/logement.py : DessinFenetre), dans le sens du MUR (du début
vers la fin), statut « estime », source « photos ». moteur/habillage.py le construit (mêmes briques : Blender, le paquet et
Unreal suivent).

Dans la chaîne : étape « baies » (outils/atelya/de_l_ecran_au_film.py), quand la lecture des photos a son `vitrages.json`.
"""
from __future__ import annotations

import copy
import statistics

import cv2
import numpy as np

from moteur import hauteur_baies
from moteur.vitrages import _sur_le_bord, points_du_sol

VERSION = "0.1.0"
BORD_SUPPOSE_M = 0.07  # sans « cadre » lu : largeur supposée des montants du tour et de la traverse du haut
BAS_SUPPOSE_M = 0.09  # … et de la traverse du bas
BORD_MIN_M = 0.03  # un bord de menuiserie plus mince n'existe pas (lecture à 2-3 pixels près)
VITRE_MIN_M = 0.12  # un vantail dont la vitre est plus étroite n'est pas construit (lecture douteuse) : cadre d'avant
SOUBASSEMENT_MAX = 0.30  # part de la hauteur de la baie : au-delà ce n'est plus une allège basse, la lecture est douteuse
SOUBASSEMENT_MIN_M = 0.06  # une partie pleine plus basse est comptée dans la traverse du bas
ALLEGE_AU_SOL = 0.30  # m : une baie dont l'allège est plus basse « descend jusqu'au sol » sur le plan
BARRE_MIN_M = 0.015  # un petit bois plus mince est construit à cette largeur


def _carre(quad) -> np.ndarray:
    """La mise à plat d'un quadrilatère (haut-gauche, haut-droit, bas-droit, bas-gauche) sur le carré unité."""
    return cv2.getPerspectiveTransform(np.array(quad, np.float32), np.array([[0, 0], [1, 0], [1, 1], [0, 1]], np.float32))


def _vers(h: np.ndarray, p) -> np.ndarray:
    return cv2.perspectiveTransform(np.array([[p]], np.float32), h)[0, 0].astype(float)


def _droite(a: np.ndarray, b: np.ndarray, x: float) -> float:
    """y de la droite (a, b) à l'abscisse x."""
    return float(a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0])) if abs(b[0] - a[0]) > 1e-9 else float(a[1])


def part_pleine_sous_la_menuiserie(cadre, sol) -> float | None:
    """La hauteur de la partie pleine entre le bas de la menuiserie et le sol, en part de la hauteur de la MENUISERIE, mesurée
    à l'aplomb de chaque point du sol lu (les verticales restent verticales sur une photo d'annonce). None sans point."""
    hg, hd, bd, bg = [np.array(c, float) for c in cadre]
    parts = []
    for x, y in points_du_sol(sol) if sol is not None else []:
        haut, bas = _droite(hg, hd, x), _droite(bg, bd, x)
        if bas - haut > 5:
            parts.append((y - bas) / (bas - haut))
    return max(0.0, float(statistics.mean(parts))) if parts else None


def tour_sur_la_photo(vitrages: list[dict], hauteur: float, jusqu_au_sol: bool) -> tuple[list[np.ndarray], float]:
    """Le tour de la BAIE sur la photo (4 coins : haut-gauche, haut-droit, bas-droit, bas-gauche, en pixels) et la part de sa
    hauteur qui est pleine sous la menuiserie. Le tour lu de la menuiserie (`cadre`), prolongé jusqu'au sol lu (`sol`) si le plan
    fait descendre la baie jusqu'au sol ; sans tour lu : celui des vitres (les bords du cadre restent à supposer)."""
    vantaux = sorted((f for f in vitrages if f.get("coins")), key=lambda f: f["coins"][0][0])
    cadre = next((f["cadre"] for f in vantaux if f.get("cadre")), None)
    sol = next((f["sol"] for f in vantaux if f.get("sol") is not None), None)
    if cadre is None:
        return [np.array(vantaux[0]["coins"][0], float), np.array(vantaux[-1]["coins"][1], float),
                np.array(vantaux[-1]["coins"][2], float), np.array(vantaux[0]["coins"][3], float)], 0.0
    tour = [np.array(c, float) for c in cadre]
    plein = part_pleine_sous_la_menuiserie(cadre, sol) if jusqu_au_sol else None
    if plein is not None and plein * hauteur / (1 + plein) >= SOUBASSEMENT_MIN_M:
        hg, hd, bd, bg = tour
        return [hg, hd, bd + (bd - hd) * plein, bg + (bg - hg) * plein], plein / (1 + plein)  # la menuiserie et sa partie pleine
    return tour, 0.0


def d_une_photo(vitrages: list[dict], largeur: float, hauteur: float, jusqu_au_sol: bool) -> dict | None:
    """Le dessin d'UNE baie d'après UNE photo (ses vitrages lus, moteur/vitrages.py), en parts de la baie, de GAUCHE à DROITE
    comme sur la photo et de BAS en HAUT : {"vantaux": [{"vitrage": (début, fin), "montants": [(a, b) …], "traverses":
    [(a, b) …]} …], "vitrage_bas", "vitrage_haut", "soubassement", "garde_corps": part ou None, "genre_garde_corps",
    "cadre_lu": le tour de la menuiserie a été lu (sinon ses bords sont supposés), "face": taille de la fenêtre sur la photo}.
    None si la photo ne dit pas de vitrage. `largeur`, `hauteur` : celles de la baie (m) ; `jusqu_au_sol` : le plan la fait
    descendre jusqu'au sol (la partie pleine lue sous la menuiserie fait alors partie de la baie)."""
    vantaux = sorted((f for f in vitrages if f.get("coins")), key=lambda f: f["coins"][0][0])
    if not vantaux:
        return None
    cadre = next((f["cadre"] for f in vantaux if f.get("cadre")), None)
    sol = next((f["sol"] for f in vantaux if f.get("sol") is not None), None)
    tour, soubassement = tour_sur_la_photo(vantaux, hauteur, jusqu_au_sol)
    a_plat = _carre(tour)
    if cadre is None:
        gd, haut_, bas_ = BORD_SUPPOSE_M / largeur, BORD_SUPPOSE_M / hauteur, BAS_SUPPOSE_M / hauteur

        def u_de(u):
            return gd + u * (1 - 2 * gd)

        def v_de(v):
            return haut_ + v * (1 - haut_ - bas_)
    else:
        def u_de(u):
            return u

        def v_de(v):
            return v

    sortie, hauts, bas, gardes = [], [], [], []
    for f in vantaux:
        hg, hd, bd, bg = [np.array(c, float) for c in f["coins"]]
        c = [_vers(a_plat, p) for p in (hg, hd, bd, bg)]
        u0, u1 = u_de((c[0][0] + c[3][0]) / 2), u_de((c[1][0] + c[2][0]) / 2)
        hauts.append(1 - v_de((c[0][1] + c[1][1]) / 2))
        bas.append(1 - v_de((c[3][1] + c[2][1]) / 2))
        montants, traverses = [], []
        for g_h, d_h, g_b, d_b in f.get("montants") or []:
            p = [_vers(a_plat, _sur_le_bord(hg, hd, x, 0))[0] for x in (g_h, d_h)] \
                + [_vers(a_plat, _sur_le_bord(bg, bd, x, 0))[0] for x in (g_b, d_b)]
            montants.append((u_de((p[0] + p[2]) / 2), u_de((p[1] + p[3]) / 2)))
        for h_g, b_g, h_d, b_d in f.get("traverses") or []:
            p = [_vers(a_plat, _sur_le_bord(hg, bg, y, 1))[1] for y in (h_g, b_g)] \
                + [_vers(a_plat, _sur_le_bord(hd, bd, y, 1))[1] for y in (h_d, b_d)]
            traverses.append((1 - v_de((p[1] + p[3]) / 2), 1 - v_de((p[0] + p[2]) / 2)))  # (bas, haut) de la barre
        if f.get("garde_corps"):
            y_g, y_d = f["garde_corps"]
            gardes.append(1 - v_de((_vers(a_plat, _sur_le_bord(hg, bg, y_g, 1))[1] + _vers(a_plat, _sur_le_bord(hd, bd, y_d, 1))[1]) / 2))
        sortie.append({"vitrage": (float(u0), float(u1)), "montants": sorted((float(a), float(b)) for a, b in montants),
                       "traverses": sorted((float(a), float(b)) for a, b in traverses)})
    aire = 0.5 * abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(tour, tour[1:] + tour[:1])))
    return {"vantaux": sortie, "vitrage_bas": float(statistics.median(bas)), "vitrage_haut": float(statistics.median(hauts)),
            "soubassement": float(soubassement), "sol_lu": cadre is not None and sol is not None and jusqu_au_sol,
            "garde_corps": float(statistics.median(gardes)) if gardes else None,
            "genre_garde_corps": next((f["genre_garde_corps"] for f in vantaux if f.get("genre_garde_corps")), None),
            "cadre_lu": cadre is not None, "face": float(aire)}


def _signature(d: dict) -> tuple:
    return (len(d["vantaux"]), tuple(len(v["traverses"]) for v in d["vantaux"]), tuple(len(v["montants"]) for v in d["vantaux"]))


def accorder(dessins: list[tuple[str, dict]]) -> tuple[dict, list[str]] | None:
    """Les dessins d'une même baie vus par plusieurs photos [(photo, dessin d_une_photo) …] réduits à UN : ceux qui ont lu le
    tour de la menuiserie font foi ; le dessin (nombre de vantaux, de petits bois) le plus souvent vu l'emporte, à égalité
    celui de la photo la plus de face ; chaque part est la médiane des photos d'accord. Rend (dessin, photos retenues)."""
    if not dessins:
        return None
    if any(d["cadre_lu"] for _, d in dessins):
        dessins = [(p, d) for p, d in dessins if d["cadre_lu"]]
    groupes: dict[tuple, list[tuple[str, dict]]] = {}
    for p, d in dessins:
        groupes.setdefault(_signature(d), []).append((p, d))
    retenus = max(groupes.values(), key=lambda g: (len(g), max(d["face"] for _, d in g)))
    ds = [d for _, d in retenus]

    def med(valeurs):
        return float(statistics.median(valeurs))

    vantaux = []
    for i in range(len(ds[0]["vantaux"])):
        vs = [d["vantaux"][i] for d in ds]
        vantaux.append({"vitrage": (med(v["vitrage"][0] for v in vs), med(v["vitrage"][1] for v in vs)),
                        "montants": [(med(v["montants"][k][0] for v in vs), med(v["montants"][k][1] for v in vs))
                                     for k in range(len(vs[0]["montants"]))],
                        "traverses": [(med(v["traverses"][k][0] for v in vs), med(v["traverses"][k][1] for v in vs))
                                      for k in range(len(vs[0]["traverses"]))]})
    # la partie pleine sous la menuiserie : médiane des photos qui ont VU le sol ; les autres parts verticales de ces photos-là
    # sont comptées dans la même baie (menuiserie + partie pleine), celles des autres dans la menuiserie seule : on les ramène
    avec_sol = [d for d in ds if d["sol_lu"]]
    soubassement = med(d["soubassement"] for d in avec_sol) if avec_sol else 0.0

    def ramener(d: dict, v: float) -> float:
        """Une part verticale de la photo d (comptée dans SA baie) ramenée dans la baie commune."""
        dans_la_menuiserie = (v - d["soubassement"]) / (1 - d["soubassement"])
        return soubassement + dans_la_menuiserie * (1 - soubassement)

    for i, v in enumerate(vantaux):
        v["traverses"] = [(med(ramener(d, d["vantaux"][i]["traverses"][k][0]) for d in ds),
                           med(ramener(d, d["vantaux"][i]["traverses"][k][1]) for d in ds)) for k in range(len(v["traverses"]))]
    gardes = [ramener(d, d["garde_corps"]) for d in ds if d["garde_corps"] is not None]
    return ({"vantaux": vantaux, "vitrage_bas": med(ramener(d, d["vitrage_bas"]) for d in ds),
             "vitrage_haut": med(ramener(d, d["vitrage_haut"]) for d in ds), "soubassement": soubassement,
             "garde_corps": med(gardes) if gardes else None,
             "genre_garde_corps": next((d["genre_garde_corps"] for d in ds if d["genre_garde_corps"]), None),
             "cadre_lu": ds[0]["cadre_lu"]}, [p for p, _ in retenus])


def _retourner(d: dict) -> dict:
    """Le même dessin vu dans l'autre sens (de droite à gauche)."""
    return {**d, "vantaux": [{"vitrage": (1 - v["vitrage"][1], 1 - v["vitrage"][0]),
                              "montants": sorted((1 - b, 1 - a) for a, b in v["montants"]), "traverses": v["traverses"]}
                             for v in reversed(d["vantaux"])]}


def pour_la_maquette(d: dict, largeur: float, hauteur: float, photos: list[str]) -> dict | None:
    """Le dessin accordé mis au format du logement (DessinFenetre), borné : bords d'au moins BORD_MIN_M, petits bois d'au moins
    BARRE_MIN_M. None s'il n'est pas constructible (vitre trop étroite, parts dans le désordre) : la fenêtre garde son cadre."""
    bord_u, bord_v = BORD_MIN_M / largeur, BORD_MIN_M / hauteur
    soubassement = d["soubassement"]
    if soubassement > SOUBASSEMENT_MAX:
        return None
    bas = max(d["vitrage_bas"], soubassement + bord_v, bord_v)
    haut = min(d["vitrage_haut"], 1 - bord_v)
    if haut - bas < 0.3:
        return None
    vantaux, fin_d_avant = [], 0.0
    for v in d["vantaux"]:
        u0, u1 = max(v["vitrage"][0], fin_d_avant + bord_u), min(v["vitrage"][1], 1 - bord_u)
        if (u1 - u0) * largeur < VITRE_MIN_M:
            return None

        def barres(liste, lo, hi, mini):
            sortie = []
            for a, b in liste:
                if b - a < mini:
                    a, b = (a + b) / 2 - mini / 2, (a + b) / 2 + mini / 2
                if lo < a and b < hi:
                    sortie.append((round(a, 4), round(b, 4)))
            return sortie

        vantaux.append({"debut": round(u0, 4), "fin": round(u1, 4),
                        "montants": barres(v["montants"], u0, u1, BARRE_MIN_M / largeur),
                        "traverses": barres(v["traverses"], bas, haut, BARRE_MIN_M / hauteur)})
        fin_d_avant = u1
    dessin = {"vantaux": vantaux, "vitrage_bas": round(bas, 4), "vitrage_haut": round(haut, 4),
              "soubassement": round(soubassement, 4), "statut": "estime",
              "source": "photos (dessin de la fenêtre lu sur " + ", ".join(photos) + ("" if d["cadre_lu"] else " ; bords supposés") + ")",
              "confiance": 0.7 if d["cadre_lu"] else 0.5}
    if d["garde_corps"] is not None and soubassement + 0.1 < d["garde_corps"] < haut:
        dessin["garde_corps"] = {"bas": round(soubassement, 4), "haut": round(d["garde_corps"], 4),
                                 "genre": d["genre_garde_corps"] or "barreaudage"}
    return dessin


def gauche_est_le_debut(ouverture: dict, logement: dict) -> bool:
    """Vue de la pièce, la gauche de la fenêtre est-elle son bord le plus proche du DÉBUT de son mur ?"""
    from moteur.equipements import repere_de_la_baie

    r = repere_de_la_baie(ouverture, logement)
    if r is None:
        return True
    droite_de_qui_regarde = np.array([-r["n"][1], r["n"][0]])  # il regarde vers le mur (−n)
    return float(r["t"] @ droite_de_qui_regarde) > 0


def lire(logement: dict, lecture: dict | None) -> dict[str, dict]:
    """Pour chaque baie du logement dont la lecture des photos dit le dessin : {id: DessinFenetre (dict)}."""
    par_baie: dict[str, dict[str, list[dict]]] = {}
    for photo, fenetres in ((lecture or {}).get("photos") or {}).items():
        for f in fenetres:
            par_baie.setdefault(f["baie"], {}).setdefault(photo, []).append(f)
    sortie = {}
    for o in logement.get("ouvertures", []):
        if o.get("type") == "porte" or o["id"] not in par_baie:
            continue
        largeur, hauteur = float(o["largeur"]), float(o["hauteur"])
        # une baie dont le bas a été MESURÉ sur les photos (moteur/hauteur_baies.py, 23/11/2026) commence au bas de sa
        # menuiserie : plus de partie pleine à compter dedans
        au_sol = float(o.get("allege", 0.0) or 0.0) < ALLEGE_AU_SOL and not hauteur_baies.mesuree(o)
        vus = [(photo, d) for photo, fs in sorted(par_baie[o["id"]].items())
               if (d := d_une_photo(fs, largeur, hauteur, au_sol)) is not None]
        accord = accorder(vus)
        if accord is None:
            continue
        d, photos = accord
        if not gauche_est_le_debut(o, logement):
            d = _retourner(d)
        dessin = pour_la_maquette(d, largeur, hauteur, photos)
        if dessin is not None:
            sortie[o["id"]] = dessin
    return sortie


def appliquer(logement: dict, lecture: dict | None, journal=None) -> tuple[dict, list[dict]]:
    """Le logement avec le DESSIN de chaque fenêtre lue sur les photos (champ `dessin` de l'ouverture), et la liste de ce qui a
    été posé. Une fenêtre dont le dessin a été choisi par une personne (statut « mesure ») n'est pas touchée."""
    logement = copy.deepcopy(logement)
    dessins = lire(logement, lecture)
    poses = []
    for o in logement.get("ouvertures", []):
        d = dessins.get(o["id"])
        if d is None or (o.get("dessin") or {}).get("statut") == "mesure":
            continue
        o["dessin"] = d
        resume = {"baie": o["id"], "vantaux": len(d["vantaux"]),
                  "petits_bois": sum(len(v["montants"]) + len(v["traverses"]) for v in d["vantaux"]),
                  "partie_pleine_m": round(d["soubassement"] * float(o["hauteur"]), 2),
                  "garde_corps_m": round(d["garde_corps"]["haut"] * float(o["hauteur"]) + float(o.get("allege", 0.0) or 0.0), 2)
                  if d.get("garde_corps") else None, "source": d["source"]}
        poses.append(resume)
        if journal:
            journal(f"{o['id']} : {resume['vantaux']} vantail(aux), {resume['petits_bois']} petit(s) bois"
                    + (f", partie pleine de {resume['partie_pleine_m']:.2f} m sous les vitres" if resume["partie_pleine_m"] else "")
                    + (f", garde-corps ({d['garde_corps']['genre']}) jusqu'à {resume['garde_corps_m']:.2f} m" if d.get("garde_corps") else ""))
    return logement, poses
