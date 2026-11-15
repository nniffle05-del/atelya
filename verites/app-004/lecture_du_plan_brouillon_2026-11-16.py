r"""app-004 (EXAMEN jamais vu, reçu de NT le 16/11/2026 : plan d'annonce + 13 photos, il en a les droits) : la LECTURE DU PLAN
faite par Claude dans la conversation, À LA PLACE de l'API (décision NT : test de A à Z, « toi à la place de l'API pour
l'instant »). Écrit la fiche lecture-claude/0.1, exactement ce que l'API rendrait : tout en PIXELS de l'image envoyée
(..\atelya\lectures-claude\app-004\envoi.png, 1206 × 693), aucun mètre.

    ..\atelya\.venv\Scripts\python.exe verites\app-004\lecture_du_plan.py ..\atelya\lectures-claude\app-004-fiche.json

Lu sur le PLAN SEUL, sans regarder les photos (elles servent à la suite de la chaîne, pas à la lecture) : ce que le plan ne
dessine pas n'est pas inventé (règle NT). Lecture plus soignée qu'un envoi unique à l'API : faite sur des agrandissements
× 4 avec une grille (coordonnées à ± 1 px, soit ± 1,5 cm) ; à redire dans la note.
"""
import json
import sys
from pathlib import Path

G, D, H, B = 305.4, 900.75, 137.6, 562.25      # axes des murs extérieurs : gauche, droite, haut, bas (de la chambre)
X_CH, Y_CH = 609.1, 344.6                      # axe du mur gauche de la chambre (et du poteau entrée / séjour) ; axe de la cloison séjour / chambre
Y_SDB, X_SDB = 260.25, 506.25                  # cloisons de la salle de bains : cuisine / salle de bains, salle de bains / entrée
Y_ENT = 365.4                                  # axe du mur du bas de l'entrée (porte d'entrée)

MURS = [
    ("M1", (G, H, D, H), 17.0), ("M2", (G, H, G, 404.1), 17.0),
    ("M3", (G, 404.1, 342.0, 404.1), 17.0), ("M4", (342.0, 404.1, 378.75, 380.0), 16.0), ("M5", (378.75, 380.0, 422.25, Y_ENT), 16.0),
    ("M6", (422.25, Y_ENT, X_CH, Y_ENT), 17.0), ("M7", (X_CH, Y_CH, X_CH, B), 17.25), ("M8", (X_CH, B, D, B), 17.0), ("M9", (D, H, D, B), 16.5),
    ("M10", (X_CH, Y_CH, D, Y_CH), 7.0), ("M11", (G, Y_SDB, X_SDB, Y_SDB), 6.5), ("M12", (X_SDB, Y_SDB, X_SDB, Y_ENT), 6.5),
    ("M13", (X_CH, H, X_CH, 178.75), 17.25), ("M14", (X_CH, 243.0, X_CH, 282.0), 17.25),
    ("M15", (427.75, H, 427.75, 178.75), 20.5), ("M16", (446.5, H, 446.5, 159.5), 17.0), ("M17", (710.0, 152.4, 794.5, 152.4), 12.75),
]
OUVERTURES = [
    ("O1", "fenetre", (G, 179.0, G, 243.0), "M2"), ("O2", "fenetre", (G, 301.0, G, 366.0), "M2"),
    ("O3", "fenetre", (D, 201.25, D, 281.25), "M9"), ("O4", "fenetre", (D, 403.0, D, 490.0), "M9"),
    ("O5", "porte", (527.0, Y_ENT, 586.0, Y_ENT), "M6"), ("O6", "porte", (X_SDB, 296.0, X_SDB, 349.0), "M12"), ("O7", "porte", (628.0, Y_CH, 683.0, Y_CH), "M10"),
]
PIECES = [
    ("P1", "Cuisine", "cuisine", (385.0, 235.0),
     [(313.75, 146), (417.5, 146), (417.5, 178.75), (438, 178.75), (438, 159.5), (455, 159.5), (455, 146), (509.5, 146), (509.5, 257), (313.75, 257)]),
    ("P2", "Entrée", "entree", (555.0, 320.0),
     [(509.5, 146), (600.5, 146), (600.5, 178.75), (X_CH, 178.75), (X_CH, 243), (600.5, 243), (600.5, 282), (X_CH, 282), (X_CH, 341.25), (600.5, 341.25),
      (600.5, 357), (509.5, 357)]),
    ("P3", "Salle de bains / WC", "salle_d_eau", (410.0, 300.0),
     [(313.75, 263.5), (503, 263.5), (503, 357), (420.75, 357), (375, 372.5), (339.5, 395.75), (313.75, 395.75)]),
    ("P4", "Séjour", "sejour", (755.0, 290.0),
     [(617.75, 146), (710, 146), (710, 158.75), (794.5, 158.75), (794.5, 146), (892.5, 146), (892.5, 341.25), (X_CH, 341.25), (X_CH, 282), (617.75, 282),
      (617.75, 243), (X_CH, 243), (X_CH, 178.75), (617.75, 178.75)]),
    ("P5", "Chambre", "chambre", (755.0, 500.0), [(617.75, 348), (892.5, 348), (892.5, 553.75), (617.75, 553.75)]),
]
SURFACES = [("3,36 m²", 3.36, (363, 214, 410, 228), "P1"), ("4,05 m²", 4.05, (532, 266, 579, 278), "P2"), ("4,19 m²", 4.19, (388, 318, 435, 331), "P3"),
            ("11,21 m²", 11.21, (737, 244, 792, 257), "P4"), ("11,85 m²", 11.85, (734, 456, 788, 470), "P5")]
TEXTES = [("totale : 34,66 m²", (215, 30, 325, 48), "autre")]
DOUTES = [
    ("Aucun mur dessiné entre la cuisine et l'entrée : limite supposée à l'aplomb de la cloison de la salle de bains (x ≈ 509). La surface écrite de la "
     "cuisine (3,36 m²) est plus petite que la cuisine dessinée (environ 4,4 m²) : environ 1 m² n'est pas compté (placards non dessinés ?).", "fort", (455, 146, 512, 258), "P1"),
    ("Entre l'entrée et le séjour, le plan dessine un bout de mur en haut, un poteau, et deux passages SANS porte (y 179 à 243 et y 282 à 341) : aucune "
     "ouverture posée, les deux pièces communiquent librement ; à vérifier (passage, porte, ou ouverture en hauteur ?).", "fort", (596, 176, 622, 344), None),
    ("Le plan ne distingue pas les fenêtres des portes-fenêtres : les quatre baies sont posées en fenêtres.", "faible", None, None),
    ("Blocs pleins contre le mur du haut (conduits ou cheminée ?) : deux dans la cuisine (M15, M16), un dans le séjour (M17), posés comme des murs.", "faible", (415, 146, 797, 180), None),
    ("Le bas de la salle de bains est en biais, en deux pans (M4, M5).", "faible", (313, 355, 425, 414), "P3"),
    ("Un filigrane de l'agence passe sur l'entrée et le poteau (traits blancs) : contours un peu moins nets à cet endroit.", "faible", (500, 240, 690, 360), None),
    ("Plan de petite taille (1206 px de large) : positions à ± 1 px, soit environ ± 1,5 cm. Aucune cote : l'échelle vient des surfaces écrites.", "faible", None, None),
]

fiche = {
    "schema": "lecture-claude/0.1", "image": {"nom": "envoi.png", "largeur": 1206, "hauteur": 693},
    "murs": [{"id": i, "axe": list(a), "epaisseur_px": e} for i, a, e in MURS],
    "ouvertures": [{"id": i, "type": t, "bords": list(b), "mur": m} for i, t, b, m in OUVERTURES],
    "pieces": [{"id": i, "nom": n, "type": t, "point": list(p), "contour": [list(map(float, c)) for c in k]} for i, n, t, p, k in PIECES],
    "surfaces": [{"texte": t, "valeur_m2": v, "cadre": list(c), "piece": p} for t, v, c, p in SURFACES],
    "textes": [{"texte": t, "cadre": list(c), "genre": g} for t, c, g in TEXTES],
    "echelle_proposee": {"px_par_m": 69.0, "source": "surfaces",
                         "explication": "pas de cote ; surfaces écrites contre les pièces dessinées : chambre 11,85 m² → 69,1 px/m, séjour 11,21 m² → 68,5, "
                                        "salle de bains 4,19 m² → 69,1, entrée 4,05 m² → 68,9 ; la cuisine ne s'accorde pas (voir les doutes) ; "
                                        "contrôle : portes de 53 à 59 px = 0,77 à 0,86 m"},
    "doutes": [{"raison": r, "gravite": g, **({"cadre": list(c)} if c else {}), **({"element": e} if e else {})} for r, g, c, e in DOUTES],
}

if __name__ == "__main__":
    sortie = Path(sys.argv[1])
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(MURS)} murs, {len(OUVERTURES)} ouvertures, {len(PIECES)} pieces : {sortie}")
