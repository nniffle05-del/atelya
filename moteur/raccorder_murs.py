r"""RACCORDER LES MURS : fermer les petites fentes entre deux bouts de murs avant de construire (examen app-004, 15/11/2026).

Pourquoi : après la vérification à l'écran, le mur en biais de la salle de bains d'app-004 avait deux fentes de 17 cm entre
ses pans (un pan raccourci à la main) ; l'écran n'a rien dit, rien ne les refermait, et la maquette avait deux trous dans son
mur extérieur. Une fente plus étroite qu'une porte entre deux bouts de murs n'est jamais un passage : c'est un défaut de
saisie. Règle 21 de NT : le bon résultat doit sortir SEUL de la chaîne.

Ce que fait `raccorder` : pour chaque bout de mur LIBRE (qui ne touche aucun autre mur), il cherche le mur le plus proche à
moins de ECART_MAX ; le bout est prolongé le long de son propre axe jusqu'à l'axe de ce voisin (deux pans qui font un angle se
rejoignent ainsi au croisement de leurs axes) ou, s'ils sont dans le prolongement l'un de l'autre, jusqu'au bout du voisin.
Un bout libre sans voisin proche (mur qui s'arrête dans la pièce, poteau) n'est pas touché.
`fermer_les_fentes` (ce que la chaîne appelle) ne raccorde QUE là où le contrôle de la maquette trouve une fente entre le sol
d'une pièce et le dehors (moteur.controle_maquette.fentes_vers_dehors) : un logement sans fente ressort identique (mesuré sur
10 logements : raccorder partout ajoutait des bouche-trous sur fr-026 et un trou sur fr-024, sans rien fermer). Les ouvertures du mur gardent leur
place (leur position est comptée depuis le début du mur : elle est décalée d'autant). Le logement d'entrée n'est pas modifié.
"""
from __future__ import annotations

import copy
import math

VERSION = "0.1.0"
ECART_MAX = 0.35  # m : fente maximale refermée (plus étroite que toute porte)
TOUCHE = 0.03  # m : un bout à moins de 3 cm de la matière d'un autre mur le touche déjà
PRES_M = 0.5  # m : un bout de mur à moins de ça d'une fente trouvée peut servir à la refermer
PARALLELES_DEG = 20.0  # en dessous, deux murs sont dans le prolongement l'un de l'autre (pas de croisement d'axes fiable)


def _distance_au_segment(p, a, b) -> tuple[float, float]:
    """(distance du point au segment, position le long du segment en mètres, non bornée)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy) or 1e-9
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L
    tb = min(max(t, 0.0), L)
    return math.hypot(p[0] - a[0] - tb * dx / L, p[1] - a[1] - tb * dy / L), t


def raccorder(logement: dict, ecart_max: float = ECART_MAX, pres_de: list | None = None) -> tuple[dict, list[dict]]:
    """Le logement avec ses petites fentes refermées, et la liste des raccords faits ({mur, bout, vers, allonge_m}).
    `pres_de` : des boîtes [x0, y0, x1, y1] en mètres ; seuls les bouts à moins de PRES_M d'une de ces boîtes sont raccordés."""
    lg = copy.deepcopy(logement)
    murs = lg.get("murs", [])
    avant = [(tuple(m["debut"]), tuple(m["fin"]), float(m["epaisseur"])) for m in murs]  # on raisonne sur les murs d'origine
    raccords = []
    for i, m in enumerate(murs):
        a, b, ep = avant[i]
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L == 0:
            continue
        u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
        for bout in ("debut", "fin"):
            e = a if bout == "debut" else b
            d = (-u[0], -u[1]) if bout == "debut" else u  # la direction qui sort du mur par ce bout
            if pres_de is not None and not any(z[0] - PRES_M <= e[0] <= z[2] + PRES_M and z[1] - PRES_M <= e[1] <= z[3] + PRES_M
                                               for z in pres_de):
                continue
            meilleur = None
            libre = True
            for j, (c, f, epj) in enumerate(avant):
                if j == i or (c == f):
                    continue
                dist, _ = _distance_au_segment(e, c, f)
                if dist - epj / 2 <= TOUCHE:
                    libre = False
                    break
                if dist - epj / 2 > ecart_max:
                    continue
                Lj = math.hypot(f[0] - c[0], f[1] - c[1])
                v = ((f[0] - c[0]) / Lj, (f[1] - c[1]) / Lj)
                sinus = d[0] * v[1] - d[1] * v[0]
                if abs(sinus) < math.sin(math.radians(PARALLELES_DEG)):
                    # dans le prolongement : jusqu'au bout le plus proche du voisin, s'il est bien devant ce bout
                    cible = min((c, f), key=lambda q: math.hypot(q[0] - e[0], q[1] - e[1]))
                    allonge = (cible[0] - e[0]) * d[0] + (cible[1] - e[1]) * d[1]
                    travers = abs((cible[0] - e[0]) * d[1] - (cible[1] - e[1]) * d[0])
                    if allonge <= 0 or travers > max(ep, epj) / 2:
                        continue
                else:
                    # en angle : jusqu'au croisement des deux axes, s'il tombe sur le voisin (à ecart_max près)
                    allonge = ((c[0] - e[0]) * v[1] - (c[1] - e[1]) * v[0]) / sinus
                    s = ((c[0] - e[0]) * d[1] - (c[1] - e[1]) * d[0]) / sinus  # position du croisement le long du voisin
                    if allonge <= 0 or not -ecart_max <= s <= Lj + ecart_max:
                        continue
                if allonge > ecart_max + epj:
                    continue
                if meilleur is None or dist < meilleur[0]:
                    meilleur = (dist, allonge, murs[j]["id"])
            if not libre or meilleur is None:
                continue
            _, allonge, vers = meilleur
            if bout == "debut":
                m["debut"] = [round(a[0] + d[0] * allonge, 3), round(a[1] + d[1] * allonge, 3)]
                for o in lg.get("ouvertures", []):
                    if o.get("mur") == m["id"]:
                        o["position"] = round(o["position"] + allonge, 3)
            else:
                m["fin"] = [round(b[0] + d[0] * allonge, 3), round(b[1] + d[1] * allonge, 3)]
            raccords.append({"mur": m["id"], "bout": bout, "vers": vers, "allonge_m": round(allonge, 3)})
    return lg, raccords


def fermer_les_fentes(logement: dict, journal=None) -> tuple[dict, dict]:
    """Le logement prêt à construire : les fentes de son enveloppe refermées par le raccord des bouts de murs voisins.
    Rend aussi le bilan {"fentes_avant": [...], "raccords": [...], "fentes_apres": [...]} ; les fentes qui restent (ouverture
    sur une partie non construite, mur manquant) sont à montrer à la personne, jamais bouchées en silence."""
    from moteur.controle_maquette import fentes_vers_dehors
    from moteur.geometrie import calculer_briques
    from moteur.logement import Logement

    def fentes(lg: dict) -> list[dict]:
        return fentes_vers_dehors(calculer_briques(Logement.model_validate(lg)))

    avant = fentes(logement)
    bilan = {"version": VERSION, "fentes_avant": avant, "raccords": [], "fentes_apres": avant}
    if avant:
        essai, raccords = raccorder(logement, pres_de=[f["zone_m"] for f in avant])
        apres = fentes(essai) if raccords else avant
        if raccords and sum(f["longueur_m"] for f in apres) < sum(f["longueur_m"] for f in avant):
            logement, bilan["raccords"], bilan["fentes_apres"] = essai, raccords, apres
    if journal:
        journal(f"Enveloppe du logement : {len(avant)} fente(s) trouvée(s), {len(bilan['raccords'])} bout(s) de mur raccordé(s), "
                f"{len(bilan['fentes_apres'])} fente(s) restante(s)"
                + "".join(f" ; reste {f['longueur_m']} m vers {f['zone_m'][:2]}" for f in bilan["fentes_apres"]))
    return logement, bilan
