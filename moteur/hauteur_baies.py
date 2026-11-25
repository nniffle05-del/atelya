r"""LE BAS ET LE HAUT D'UNE FENÊTRE, LUS SUR LES PHOTOS (23/11/2026).

Pourquoi. Un plan d'annonce ne dit RIEN de la hauteur des fenêtres : dans la maquette elles prennent toutes la hauteur par
défaut de leur sorte (fenêtre : de 0,95 à 2,20 m ; porte-fenêtre : du sol à 2,15 m ; l'écran de vérification ne sait pas la
changer : « la hauteur suit le type »). Les photos montrent autre chose : les fenêtres d'app-004 montent à ~2,35 m sous un
plafond de 2,70 m et s'arrêtent à ~33 cm du sol ; celles de la cuisine et du coin repas d'app-001 montent à ~2,6-2,75 m sous
3,00 m. Dans le film, la fenêtre était trop basse : la tringle (à sa vraie hauteur depuis le 23/11) flottait loin au-dessus
d'elle, le garde-corps et la vue par la fenêtre étaient décalés d'autant.
ACCORD DE NT (23/11/2026) : les photos peuvent corriger le bas et le haut d'une fenêtre du plan, comme sa largeur (F1).

Moyen : la LECTURE dit le sens, Atelya garde la géométrie. La lecture des fenêtres (moteur/vitrages.py, format 0.3) dit, sur
la photo : le TOUR de la menuiserie (`cadre`), un ou deux points de la ligne où le MUR de la fenêtre touche le SOL (`sol`,
n'importe où le long de ce mur : sous la fenêtre ou à côté d'un meuble) et de celle où il touche le PLAFOND (`plafond`).
Ces quatre lignes (sol, bas de la menuiserie, haut de la menuiserie, plafond) sont des horizontales d'un même mur : sur la
photo elles visent le même point de fuite. Le long d'une verticale du mur, leurs écarts donnent le bas et le haut de la
fenêtre en PARTS de la hauteur du sol au plafond (`niveaux_d_une_photo`). Rien ne dépend de la place de l'appareil (connue à
30-50 cm), ni de son zoom ; la hauteur sous plafond du logement donne les mètres.
  - une photo qui montre le sol ET le plafond du mur : le bas et le haut, directement ;
  - une photo qui ne montre que le plafond (lit ou canapé devant le bas du mur), ou que le sol : un RAPPORT (ce qu'il reste
    au-dessus de la fenêtre, ou en dessous, rapporté à sa hauteur) ; deux photos qui se complètent donnent tout (`accorder`) ;
  - SECOND AVIS, indépendant : le RELIEF de la photo (MoGe-2 remis entre le sol et le plafond, moteur.caler_photos.repere),
    lu sur le mur juste au-dessus et juste au-dessous de la menuiserie (`relief_d_une_photo`, juste à 5-8 cm). Il complète
    une mesure partielle et il contrôle les autres : un désaccord de plus de DESACCORD_M est un DOUTE (rien n'est changé).
  - une fenêtre derrière un VOILAGE : le haut de sa menuiserie est caché par le haut du tissu ; la lecture dit seulement
    jusqu'où on VOIT ses vitres (`haut_au_moins`) : ce minimum ne peut que MONTER le haut de la baie ; son bas, s'il est
    caché (`bas_cache`), reste celui d'avant.

La règle (`corriger`). La hauteur d'une baie n'a jamais été mesurée par personne : dès que les photos la mesurent, la baie
prend le bas et le haut qu'elles montrent (statut « estime », source « photos »), sauf si l'écart est plus petit que ce que
la mesure sait voir (ECART_MIN). Une baie dont le bas est à moins d'AU_SOL_M du sol descend jusqu'au sol ; à partir
d'ALLEGE_FENETRE_M c'est une fenêtre (on n'y passe pas), en dessous une porte-fenêtre sur sa marche ; la sorte choisie par
une personne à l'écran de vérification n'est pas changée. Une baie qu'une personne a refusé de changer (`refusees`, pour
l'écran de vérification) n'est jamais touchée. Une baie qu'aucune photo ne mesure reste comme avant.
La baie devient alors la MENUISERIE elle-même : son dessin (moteur/dessin_fenetres.py) n'a plus de partie pleine à compter
dedans (`mesuree`).

Dans la chaîne : étape « baies » (outils/atelya/de_l_ecran_au_film.py), après la largeur et la sorte des baies, avant leur
dessin, quand la lecture des photos a son `vitrages.json`.
"""
from __future__ import annotations

import copy
import math
import statistics

import numpy as np

from moteur.vitrages import points_du_sol

VERSION = "0.1.0"
ECART_MIN = 0.05  # m : un bas et un haut qui bougent chacun de moins ne changent rien (la mesure vaut 3 à 5 cm)
AU_SOL_M = 0.06  # m : un bas plus près du sol « descend jusqu'au sol » (un rail, un seuil)
ALLEGE_FENETRE_M = 0.25  # m : à partir de cette hauteur de mur sous la menuiserie, c'est une fenêtre (on n'y passe pas)
SOUS_PLAFOND_MIN = 0.03  # m : ce qui reste au moins de mur entre le haut d'une baie et le plafond
HAUTEUR_MIN = 0.35  # m : une menuiserie plus basse n'est pas une fenêtre (lecture douteuse)
DESACCORD_M = 0.20  # m : au-delà, la mesure par les lignes et le relief de la photo ne disent pas la même chose : doute
ENTRE_PHOTOS_M = 0.15  # m : au-delà, deux photos de la même baie ne disent pas la même chose : doute
CONVERGE_MIN = math.radians(1.5)  # deux montants qui se rapprochent de moins : verticales parallèles (photo redressée)
DEVANT_LE_MUR_M = 0.3  # m : un point du relief plus près de l'appareil que le mur n'est pas sur le mur (un meuble devant)
HORS_DU_MUR = 4.0  # px (photo de 1206 px) : le relief est lu à cette distance au-dessus et au-dessous de la menuiserie
MARQUE = "photos (bas et haut de la baie"


def _h(p) -> np.ndarray:
    return np.array([float(p[0]), float(p[1]), 1.0])


def _droite(p, q) -> np.ndarray:
    d = np.cross(_h(p), _h(q))
    n = math.hypot(d[0], d[1])
    return d / n if n > 1e-12 else d


def _point(l1, l2) -> np.ndarray | None:
    p = np.cross(l1, l2)
    return p[:2] / p[2] if abs(p[2]) > 1e-9 * max(1.0, float(np.abs(p[:2]).max())) else None


def points(valeur) -> list[tuple[float, float]]:
    """Les points [x, y] d'un « sol » ou d'un « plafond » lu (un point, ou une liste de points)."""
    return points_du_sol(valeur) if valeur is not None else []


def niveaux_d_une_photo(fenetres: list[dict]) -> dict | None:
    """Ce qu'UNE photo dit du bas et du haut d'UNE baie, d'après ses vitrages lus (moteur/vitrages.py) :
    {"bas", "haut" : parts de la hauteur du sol au plafond (si la photo montre le sol ET le plafond du mur),
     "dessous" : bas / (haut − bas) (si elle montre le sol), "dessus" : (1 − haut) / (haut − bas) (si elle montre le
     plafond), "points" : {"sol", "bas", "haut", "plafond"} les quatre niveaux sur la verticale du milieu (pixels, pour
     contrôler), "haut_au_moins" : vrai si le haut lu n'est que le plus haut endroit où l'on VOIT la fenêtre (voilage)}.
    Un tour dont le bas est caché (`bas_cache`) ne dit que le haut. None sans tour de menuiserie lu, ou sans sol ni plafond."""
    porteur = next((f for f in fenetres if f.get("cadre")), None)
    if porteur is None:
        return None
    sol = next((points(f.get("sol")) for f in fenetres if f.get("sol") is not None), [])
    plafond = next((points(f.get("plafond")) for f in fenetres if f.get("plafond") is not None), [])
    if not sol and not plafond:
        return None
    coins = np.array(porteur["cadre"], float)
    centre = coins.mean(0)
    taille = float(np.linalg.norm(coins.max(0) - coins.min(0))) or 1.0
    n = lambda p: (np.asarray(p, float) - centre) / taille  # noqa: E731 : repère centré sur la menuiserie (calcul stable)
    hg, hd, bd, bg = (n(c) for c in coins)
    haut, bas = _droite(hg, hd), _droite(bg, bd)
    # le point de fuite des horizontales du mur : celui que visent le haut et le bas de la menuiserie, et les lignes du sol
    # et du plafond quand elles sont dites par deux points (moindres carrés)
    lignes = [haut, bas] + [_droite(n(pts[0]), n(pts[-1])) for pts in (sol, plafond) if len(pts) >= 2]
    fuite = np.linalg.svd(np.array(lignes))[2][-1]

    def ligne(pts):
        if len(pts) >= 2:
            return _droite(n(pts[0]), n(pts[-1]))
        return np.cross(_h(n(pts[0])), fuite)  # un seul point : la ligne qui va de lui au point de fuite du mur

    # la VERTICALE du milieu de la menuiserie : parallèle à ses montants ; s'ils se rapprochent (photo penchée), elle vise
    # leur point de rencontre (le point de fuite des verticales)
    d_g, d_d = bg - hg, bd - hd
    d_g, d_d = d_g / np.linalg.norm(d_g), d_d / np.linalg.norm(d_d)
    vers_le_haut = -(d_g + d_d) / np.linalg.norm(d_g + d_d)
    t_fuite = math.inf
    if abs(math.asin(float(np.clip(d_g[0] * d_d[1] - d_g[1] * d_d[0], -1, 1)))) > CONVERGE_MIN:
        rencontre = _point(_droite(hg, bg), _droite(hd, bd))
        if rencontre is not None:
            vers_le_haut = (rencontre if rencontre[1] < 0 else -rencontre)
            vers_le_haut = vers_le_haut / np.linalg.norm(vers_le_haut)
            t_fuite = float(rencontre @ vers_le_haut)
    verticale = _droite((0.0, 0.0), vers_le_haut)

    def sur_la_verticale(droite) -> float | None:
        p = _point(verticale, droite)
        return None if p is None else float(p @ vers_le_haut)

    t = {"haut": sur_la_verticale(haut), "bas": sur_la_verticale(bas),
         "sol": sur_la_verticale(ligne(sol)) if sol else None, "plafond": sur_la_verticale(ligne(plafond)) if plafond else None}
    if t["haut"] is None or t["bas"] is None or t["haut"] <= t["bas"]:
        return None

    def au_dessus(de: str, a: str) -> float:
        """La hauteur du niveau `a` au-dessus du niveau `de`, à un facteur près (le même pour toute la verticale)."""
        if not math.isfinite(t_fuite):
            return t[a] - t[de]
        return math.copysign(1.0, t_fuite) * (t[a] - t[de]) / (t_fuite - t[a])  # le signe : verticales qui se rejoignent en bas

    sortie: dict = {"points": {k: [float(c) for c in (vers_le_haut * v * taille + centre)] for k, v in t.items() if v is not None}}
    if porteur.get("haut_au_moins"):
        sortie["haut_au_moins"] = True
    if porteur.get("bas_cache"):  # le bas du tour n'est pas celui de la fenêtre : la photo ne dit que le haut
        if t["sol"] is None or t["plafond"] is None:
            return None
        h, p = au_dessus("sol", "haut"), au_dessus("sol", "plafond")
        if not 0 < h <= p:
            return None
        sortie["haut"] = h / p
        return sortie
    if t["sol"] is not None:
        b, h = au_dessus("sol", "bas"), au_dessus("sol", "haut")
        if not 0 < h - b or b < -0.08 * (h - b):
            return None  # le sol lu passe au-dessus du bas de la menuiserie : lecture fausse
        sortie["dessous"] = max(0.0, b) / (h - b)
        if t["plafond"] is not None:
            p = au_dessus("sol", "plafond")
            if p <= h * 0.98:
                return None  # le plafond lu passe sous le haut de la menuiserie
            sortie["bas"], sortie["haut"] = max(0.0, b) / p, h / p
    if t["plafond"] is not None:
        h, b = -au_dessus("plafond", "haut"), -au_dessus("plafond", "bas")  # ce qu'il y a SOUS le plafond jusqu'à eux
        if not 0 < b - h or h < -0.02 * (b - h):
            return None
        sortie["dessus"] = max(0.0, h) / (b - h)
    return sortie


def relief_d_une_photo(repere: dict | None, fenetres: list[dict], taille: tuple[int, int]) -> dict | None:
    """SECOND AVIS : le bas et le haut de la menuiserie (mètres au-dessus du sol) lus dans le RELIEF de la photo (remis entre
    le sol et le plafond de la pièce, moteur.caler_photos.repere) : sur le mur, juste au-dessus de son bord haut et juste
    au-dessous de son bord bas. {"bas", "haut"}, chacun seulement s'il est mesuré ; None sans tour lu ni relief."""
    porteur = next((f for f in fenetres if f.get("cadre")), None)
    if porteur is None or repere is None:
        return None
    largeur, hauteur = taille
    hg, hd, bd, bg = (np.array(c, float) for c in porteur["cadre"])
    ecart = HORS_DU_MUR * largeur / 1206.0
    au_dessus = 0.0 if porteur.get("haut_au_moins") else ecart  # un haut « au moins » se lit SUR sa ligne (ce que l'on voit)
    Hm, Wm = repere["M"].shape

    def lu(p) -> tuple[float, float] | None:
        """(hauteur au-dessus du sol, distance à l'appareil) du relief à ce pixel ; None s'il n'est pas mesuré."""
        i, j = int(p[1] * Hm / hauteur), int(p[0] * Wm / largeur)
        if 0 <= i < Hm and 0 <= j < Wm and repere["M"][i, j] and np.isfinite(repere["h"][i, j]):
            return float(repere["h"][i, j]), float(repere["r"][i, j])
        return None

    hauts, bas = [], []
    for f in np.linspace(0.1, 0.9, 17):
        dessus, dessous = lu(hg + (hd - hg) * f - (0, au_dessus)), lu(bg + (bd - bg) * f + (0, ecart))
        if dessus is None:
            continue
        hauts.append(dessus[0])
        # le bas ne compte que s'il est lu sur le MUR : à la même distance que le mur du dessus (sinon c'est un lit, un
        # canapé, un meuble posé devant la fenêtre)
        if dessous is not None and abs(dessous[1] - dessus[1]) <= DEVANT_LE_MUR_M:
            bas.append(dessous[0])
    if porteur.get("bas_cache"):
        bas = []
    sortie = {k: round(float(np.median(v)), 3) for k, v in (("bas", bas), ("haut", hauts)) if len(v) >= 3}
    return sortie or None


def accorder(mesures: list[dict], hsp: float) -> dict | None:
    """Le bas et le haut d'UNE baie (parts de la hauteur du sol au plafond) d'après toutes ses photos
    [{"photo", "bas"?, "haut"?, "dessous"?, "dessus"?, "haut_au_moins"?, "bas_cache"?, "relief": {"bas"?, "haut"?}?} …] :
    {"bas" (None : inconnu), "haut", "par" : comment (« sol et plafond », « sol et plafond de deux photos », « plafond et
    relief », « sol et relief », « haut vu au moins »), "photos", "ecart_entre_photos" (m), "haut_au_moins" : vrai si le haut
    n'est qu'un minimum (fenêtre derrière un voilage), "relief" : {"bas", "haut"} médians (m) s'il y en a}.
    Les photos qui voient le tour ENTIER de la menuiserie font foi ; à défaut, celles qui n'en voient qu'une partie.
    None quand rien ne se mesure."""
    med = lambda v: float(statistics.median(list(v)))  # noqa: E731
    entieres = [m for m in mesures if not m.get("haut_au_moins") and not m.get("bas_cache")]
    directes = [m for m in entieres if "bas" in m and "haut" in m]
    dessous = [m["dessous"] for m in entieres if "dessous" in m]
    dessus = [m["dessus"] for m in entieres if "dessus" in m]
    # le relief qui contrôle : celui des photos qui mesurent par les lignes (une photo où un lit cache le pied du mur ne
    # donne pas de ligne du sol, et son relief du bas est celui du lit)
    reliefs = [m["relief"] for m in (directes or entieres) if m.get("relief")]
    relief = {k: med(r[k] for r in reliefs if k in r) for k in ("bas", "haut") if any(k in r for r in reliefs)}
    sortie = None
    if directes:
        sortie = {"bas": med(m["bas"] for m in directes), "haut": med(m["haut"] for m in directes), "par": "sol et plafond",
                  "photos": sorted(str(m["photo"]) for m in directes),
                  "ecart_entre_photos": round(hsp * max(max(m[k] for m in directes) - min(m[k] for m in directes) for k in ("bas", "haut")), 3)}
    elif dessous and dessus:
        hauteur = 1.0 / (1.0 + med(dessous) + med(dessus))  # bas + hauteur + dessus = 1, en parts de la hauteur de la baie
        sortie = {"bas": med(dessous) * hauteur, "haut": (med(dessous) + 1.0) * hauteur, "par": "sol et plafond de deux photos",
                  "photos": sorted(str(m["photo"]) for m in entieres if "dessous" in m or "dessus" in m), "ecart_entre_photos": 0.0}
    elif dessus and "bas" in relief:  # 1 − haut = dessus × (haut − bas), le bas pris dans le relief
        bas = max(0.0, relief["bas"]) / hsp
        sortie = {"bas": bas, "haut": (1.0 + med(dessus) * bas) / (1.0 + med(dessus)), "par": "plafond et relief",
                  "photos": sorted(str(m["photo"]) for m in entieres if "dessus" in m), "ecart_entre_photos": 0.0}
    elif dessous and "haut" in relief:  # bas = dessous × (haut − bas), le haut pris dans le relief
        haut = min(relief["haut"], hsp) / hsp
        sortie = {"bas": med(dessous) * haut / (1.0 + med(dessous)), "haut": haut, "par": "sol et relief",
                  "photos": sorted(str(m["photo"]) for m in entieres if "dessous" in m), "ecart_entre_photos": 0.0}
    if sortie is not None:
        if relief:
            sortie["relief"] = {k: round(v, 3) for k, v in relief.items()}
        return sortie
    # aucune photo ne voit le tour entier : celles qui voient la fenêtre AU MOINS jusqu'à une hauteur (derrière un voilage)
    partielles = [m for m in mesures if m.get("haut_au_moins")]
    hauts = [(m["haut"], "lignes") if "haut" in m else (m["relief"]["haut"] / hsp, "relief")
             for m in partielles if "haut" in m or "haut" in (m.get("relief") or {})]
    if not hauts:
        return None
    bas = [m["bas"] for m in partielles if "bas" in m and not m.get("bas_cache")]
    return {"bas": med(bas) if bas else None, "haut": med(h for h, _ in hauts), "haut_au_moins": True,
            "par": "haut vu au moins" + (" (relief)" if all(c == "relief" for _, c in hauts) else ""),
            "photos": sorted(str(m["photo"]) for m in partielles), "ecart_entre_photos": 0.0}


def lire(logement: dict, lecture: dict | None, reperes: dict[str, dict] | None = None,
         tailles: dict[str, tuple[int, int]] | None = None, brut: dict | None = None) -> dict[str, dict]:
    """Pour chaque baie du logement que la lecture des fenêtres permet de mesurer : {id: accorder(…) + "mesures" (une par
    photo)}. `reperes` : le relief de chaque photo ({nom: moteur.caler_photos.repere}) et `tailles` ({nom: (largeur,
    hauteur)}) pour le second avis ; sans eux, les lignes seules. `brut` : rempli de {baie: mesures par photo}."""
    hsp = float(logement.get("hauteur_sous_plafond", 2.5))
    par_baie: dict[str, list[dict]] = {}
    for photo, fenetres in ((lecture or {}).get("photos") or {}).items():
        groupes: dict[str, list[dict]] = {}
        for f in fenetres:
            groupes.setdefault(f["baie"], []).append(f)
        for baie, fs in groupes.items():
            porteur = next((f for f in fs if f.get("cadre")), None)
            if porteur is None:
                continue
            m = niveaux_d_une_photo(fs) or {}
            if reperes and tailles and photo in reperes and photo in tailles:
                relief = relief_d_une_photo(reperes[photo], fs, tailles[photo])
                if relief:
                    m["relief"] = relief
            if m:
                m.update({k: True for k in ("haut_au_moins", "bas_cache") if porteur.get(k)})
                par_baie.setdefault(baie, []).append({"photo": photo, **m})
    if brut is not None:  # pour les sondes : ce que chaque photo dit, même quand rien ne s'en conclut
        brut.update(par_baie)
    sortie = {}
    for o in logement.get("ouvertures", []):
        if o.get("type") == "porte" or o["id"] not in par_baie:
            continue
        accord = accorder(par_baie[o["id"]], hsp)
        if accord is not None:
            sortie[o["id"]] = {**accord, "mesures": par_baie[o["id"]]}
    return sortie


def mesuree(ouverture: dict) -> bool:
    """Le bas de cette baie vient-il des photos (la baie commence alors au bas de la menuiserie elle-même) ?"""
    return MARQUE in str(ouverture.get("source") or "")


def corriger(logement: dict, mesures: dict[str, dict], journal=None, refusees=()) -> tuple[dict, list[dict], list[dict]]:
    """Le logement dont les fenêtres ont le bas et le haut que les photos montrent. Rend le logement, ce qui a changé
    ([{"id", "avant": {type, allege, hauteur}, "apres": {…}, "photos", "par"}]) et les doutes (rien n'est changé) : photos
    qui ne s'accordent pas, lignes et relief qui ne s'accordent pas, mesure qui n'est pas celle d'une fenêtre.
    Un haut vu « au moins » (fenêtre derrière un voilage) ne fait que MONTER le haut de la baie ; un bas inconnu reste.
    refusees : les baies qu'une personne a refusé de changer (réponse de l'écran de vérification) : jamais touchées."""
    lg = copy.deepcopy(logement)
    hsp = float(lg.get("hauteur_sous_plafond", 2.5))
    changes, doutes = [], []
    refusees = set(refusees)
    for o in lg.get("ouvertures", []):
        m = mesures.get(o["id"])
        if m is None or o.get("type") == "porte" or o["id"] in refusees:
            continue
        avant = {"type": o["type"], "allege": round(float(o.get("allege", 0.0) or 0.0), 3), "hauteur": round(float(o["hauteur"]), 3)}
        haut_d_avant = avant["allege"] + avant["hauteur"]
        au_moins = bool(m.get("haut_au_moins"))
        bas = avant["allege"] if m["bas"] is None else m["bas"] * hsp
        haut = max(m["haut"] * hsp, haut_d_avant) if au_moins else m["haut"] * hsp
        vu = {"id": o["id"], "avant": avant, "par": m["par"], "photos": m["photos"],
              "vu": {"bas": None if m["bas"] is None else round(m["bas"] * hsp, 2), "haut": round(m["haut"] * hsp, 2)}}

        def doute(raison: str, vu=vu, bas=bas, haut=haut, m=m, o=o) -> None:
            doutes.append({**vu, "raison": raison})
            if journal:
                journal(f"  baie {o['id']} : vue de {bas:.2f} à {haut:.2f} m ({m['par']}), mais {raison} : rien n'est changé")

        if not (-0.05 <= bas and haut <= hsp + 0.05 and haut - bas >= HAUTEUR_MIN):
            doute("ce n'est pas la mesure d'une fenêtre")
            continue
        if m.get("ecart_entre_photos", 0.0) > ENTRE_PHOTOS_M:
            doute(f"ses photos ne s'accordent pas ({m['ecart_entre_photos']:.2f} m d'écart)")
            continue
        relief = m.get("relief") or {}
        if not au_moins:  # DEUX CLÉS : les lignes et le relief de la photo doivent dire la même chose
            ecarts = [abs(relief[k] - v) for k, v in (("bas", bas), ("haut", haut)) if k in relief]
            if "relief" in m["par"] and len(ecarts) < 2:
                # la mesure s'appuie sur le relief pour un bout : sans son autre bout pour la contrôler, elle ne vaut rien
                # (chambre d'app-002 : relief faux, le bas de la baie « sous le sol », la baie aurait été abaissée de 18 cm)
                doute("le relief de la photo, qui la complète, ne peut pas être contrôlé")
                continue
            if ecarts and max(ecarts) > DESACCORD_M:
                doute(f"le relief de la photo dit autre chose ({', '.join(f'{k} {relief[k]:.2f} m' for k in ('bas', 'haut') if k in relief)})")
                continue
        bas = 0.0 if bas < AU_SOL_M else bas
        haut = min(haut, hsp - SOUS_PLAFOND_MIN)
        apres = {"type": o["type"], "allege": round(bas, 2), "hauteur": round(haut - bas, 2)}
        if m["bas"] is not None and "verification" not in str(o.get("source") or ""):  # la sorte choisie par une personne reste
            apres["type"] = "fenetre" if bas >= ALLEGE_FENETRE_M else "porte_fenetre"
        if (abs(apres["allege"] - avant["allege"]) < ECART_MIN and abs(apres["allege"] + apres["hauteur"] - haut_d_avant) < ECART_MIN
                and apres["type"] == avant["type"]):
            continue
        quoi = MARQUE if m["bas"] is not None else "photos (haut de la baie"
        source = (f"{quoi} lus sur {len(m['photos'])} photo(s) du client, {m['par']} ; avant : de {avant['allege']:.2f} à "
                  f"{haut_d_avant:.2f} m)")
        if str(o.get("source") or "").startswith("photos ("):  # déjà élargie, ou sa sorte lue sur les photos : on garde les deux
            source = f"{o['source']} ; {source}"
        o.update(apres, statut="estime", source=source)
        changes.append({"id": o["id"], "avant": avant, "apres": apres, "photos": m["photos"], "par": m["par"],
                        **({"haut_au_moins": True} if au_moins else {}), **({"relief": relief} if relief else {})})
        if journal:
            journal(f"  baie {o['id']} : de {avant['allege']:.2f} à {haut_d_avant:.2f} m → de {apres['allege']:.2f} à "
                    f"{apres['allege'] + apres['hauteur']:.2f} m ({m['par']}, {', '.join(m['photos'])})"
                    + (f" ; {avant['type']} → {apres['type']}" if apres["type"] != avant["type"] else ""))
    return lg, changes, doutes


def reperes_des_photos(fiche: dict, racine, hsp: float, noms=None, outils=None) -> tuple[dict[str, dict], dict[str, tuple[int, int]]]:
    """Le relief de chaque photo placée d'une fiche (cameras-photos.json), remis entre le sol et le plafond, et sa taille :
    ({nom: repere}, {nom: (largeur, hauteur)}). `noms` : seulement ces photos."""
    from pathlib import Path

    import cv2

    from moteur import caler_photos as cp
    from moteur import moge
    from moteur.images import lire_image

    modele = outils.moge if outils is not None else moge.charger()
    dossier = Path(racine) / fiche["photos"]
    fichier = fiche.get("fichier", "{nom}.png")
    reperes, tailles = {}, {}
    for nom, d in fiche.get("cameras", {}).items():
        if noms is not None and nom not in noms:
            continue
        image = lire_image(dossier / fichier.format(nom=nom))
        if image is None:
            raise FileNotFoundError(dossier / fichier.format(nom=nom))
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        tailles[nom] = (rgb.shape[1], rgb.shape[0])
        r = cp.repere(cp.mesurer(modele, rgb, float(d["camera"]["f"])), hsp)
        if r is not None:
            reperes[nom] = r
    return reperes, tailles
