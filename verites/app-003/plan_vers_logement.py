"""app-003 (EXAMEN jamais vu, reçu de NT le 14/11/2026) : le plan relevé à la main (par Claude, sur le plan de l'annonce) →
verites/app-003/logement.json. Le plan n'a NI cotes NI surface : l'échelle est estimée d'après les portes (portes simples
~30 px = 0,80 m ; portes doubles ~52 px = 1,43 m), soit 2,75 cm par pixel du plan (1206 × 627 px). La hauteur sous plafond
n'est pas écrite : 3,10 m (immeuble ancien ; à recaler si NT donne la vraie). Faces INTÉRIEURES des pièces relevées en
pixels du plan (x vers la droite, y vers le bas), puis mises en mètres (y vers le haut).
Relevé PARTIEL, suffisant pour caler les photos : pièces + ouvertures ; un petit mur est créé par ouverture (pas tous les murs).
Règle de NT : rien d'inventé (aucune porte ni cloison absente du plan).

    ..\\atelya\\.venv\\Scripts\\python.exe verites\\app-003\\plan_vers_logement.py
"""
import json
from pathlib import Path

E, X0, Y0, HSP = 0.0275, 200, 620, 3.10


def m(x, y):
    return [round((x - X0) * E, 3), round((Y0 - y) * E, 3)]


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


PIECES = [  # id, nom du plan, contour en pixels
    ("sejour_1", "Séjour", rect(375, 48, 596, 253)),
    ("sejour_2", "Salle à manger", [(741, 174), (963, 174), (963, 190), (995, 190), (995, 312), (965, 312), (965, 326), (741, 326)]),
    ("cuisine_1", "Cuisine", [(804, 48), (963, 48), (963, 168), (741, 168), (741, 94), (804, 94)]),
    ("salle_d_eau_1", "SDE", rect(741, 48, 804, 94)),
    ("chambre_1", "Chambre (haut, bureau bleu)", [(611, 48), (733, 48), (733, 179), (695, 179), (695, 140), (611, 140)]),
    ("wc_1", "WC", rect(604, 146, 689, 180)),
    ("entree_1", "Entrée", rect(607, 184, 733, 282)),
    ("degagement_1", "Couloir", [(550, 256), (597, 256), (597, 455), (637, 460), (637, 489), (376, 489), (376, 440), (428, 440), (428, 448), (550, 448)]),
    ("chambre_2", "Chambre (milieu, enfants)", rect(375, 270, 514, 432)),
    ("placard_1", "Placard", [(520, 270), (545, 270), (545, 443), (428, 443), (428, 434), (520, 434)]),
    ("chambre_3", "Chambre (gauche, d'angle)", rect(212, 424, 365, 608)),
    ("salle_d_eau_2", "SDB", rect(377, 491, 454, 611)),
    ("chambre_4", "Chambre (bas, droite)", [(461, 491), (585, 491), (585, 530), (595, 530), (595, 611), (490, 611), (490, 603), (461, 603)]),
    ("wc_2", "WC", rect(604, 493, 638, 528)),
]
PF, FEN, PORTE = ("porte_fenetre", 0.0, 2.6), ("fenetre", 0.9, 1.5), ("porte", 0.0, 2.1)
OUVERTURES = [  # sens (v = mur vertical sur le plan, h = horizontal), axe du mur, début, fin (pixels), (type, allège, hauteur), note
    ("v", 370, 68, 120, PF, "séjour, côté rue (ouest)"), ("v", 370, 175, 233, PF, "séjour, côté rue (ouest)"),
    ("h", 45, 628, 666, FEN, "chambre du haut (bureau)"),
    ("v", 966, 88, 153, PF, "cuisine"),
    ("v", 997, 208, 298, ("fenetre", 0.6, 2.0), "salle à manger (radiateur dessous)"),
    ("v", 370, 325, 378, PF, "chambre du milieu"),
    ("h", 421, 255, 315, PF, "chambre de gauche"), ("v", 207, 432, 480, PF, "chambre de gauche"),
    ("v", 598, 545, 596, PF, "chambre du bas à droite (type supposé)"),
    ("h", 614, 412, 451, ("fenetre", 1.2, 1.0), "salle de bains"),
    ("v", 601, 188, 239, PORTE, "séjour / entrée (double)"), ("v", 737, 224, 277, PORTE, "entrée / salle à manger (double)"),
    ("h", 182, 650, 689, PORTE, "WC / entrée"), ("h", 182, 698, 733, PORTE, "chambre du haut / entrée"),
    ("v", 737, 72, 92, PORTE, "chambre du haut / SDE"),
    ("h", 171, 799, 906, ("porte", 0.0, 2.4), "cuisine / salle à manger (grande ouverture sans porte)"),
    ("v", 601, 256, 281, PORTE, "entrée / couloir"), ("h", 253, 555, 597, PORTE, "séjour / couloir"),
    ("h", 285, 628, 698, PORTE, "porte palière (entrée)"),
    ("h", 437, 388, 418, PORTE, "chambre du milieu / couloir"), ("v", 370, 452, 482, PORTE, "chambre de gauche / couloir"),
    ("h", 489, 390, 418, PORTE, "salle de bains / couloir"), ("h", 489, 520, 550, PORTE, "chambre du bas à droite / couloir"),
    ("h", 491, 606, 636, PORTE, "WC / couloir (mur en biais sur le plan, mis droit)"),
]

if __name__ == "__main__":
    murs, ouvertures = [], []
    for i, (sens, axe, a, b, (genre, allege, hauteur), note) in enumerate(OUVERTURES, 1):
        d, f = ((axe, a - 11), (axe, b + 11)) if sens == "v" else ((a - 11, axe), (b + 11, axe))
        murs.append({"id": f"M{i}", "debut": m(*d), "fin": m(*f), "epaisseur": 0.2, "statut": "estime", "source": "verite_claude"})
        ouvertures.append({"id": f"O{i}", "type": genre, "mur": f"M{i}", "position": round(11 * E, 3), "largeur": round((b - a) * E, 3),
                           "hauteur": hauteur, "allege": allege, "statut": "estime", "source": "verite_claude", "note": note})
    logement = {"schema": "logement/0.1", "projet_id": "app-003", "unites": "m", "hauteur_sous_plafond": HSP,
                "note": "Relevé à la main sur le plan de l'annonce (sans cotes) ; échelle estimée d'après les portes ; relevé partiel (un mur par ouverture).",
                "murs": murs, "ouvertures": ouvertures,
                "pieces": [{"id": i, "nom": n, "contour": [m(*p) for p in c], "statut": "estime", "source": "verite_claude"} for i, n, c in PIECES]}
    sortie = Path(__file__).resolve().parent / "logement.json"
    sortie.write_text(json.dumps(logement, ensure_ascii=False, indent=1), encoding="utf-8")
    aire = lambda c: abs(sum(c[k][0] * c[(k + 1) % len(c)][1] - c[(k + 1) % len(c)][0] * c[k][1] for k in range(len(c)))) / 2
    tot = 0
    for p in logement["pieces"]:
        tot += aire(p["contour"]); print(f"{p['id']:16s} {p['nom']:28s} {aire(p['contour']):5.1f} m²")
    print(f"total {tot:.1f} m² | {len(ouvertures)} ouvertures | écrit : {sortie.name}")
