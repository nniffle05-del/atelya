r"""APP-004 (logement jamais vu, examen de A à Z) : la LECTURE DU PLAN par Claude, à la place de l'appel payant à l'API.

Lecture REFAITE DE ZÉRO le 15/11/2026 dans la conversation de l'examen (le brouillon du 16/11 du journal, mis de côté, n'a pas
été ouvert avant ; il sera comparé après). Faite sur le PLAN SEUL (aucune photo regardée), sur l'image exacte qu'on enverrait
(1206 × 693 px, envoi.png), lue à l'œil sur trois agrandissements × 4 quadrillés tous les 10 px. Tout est en PIXELS de cette
image ; aucun mètre n'est calculé ici (seule l'échelle PROPOSÉE est donnée, comme le demande le format).

    ..\atelya\.venv\Scripts\python.exe verites\app-004\lecture_du_plan.py ..\atelya\lectures-claude\app-004-fiche.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------- les murs : axe (x0, y0, x1, y1), épaisseur
MURS = {
    # le pourtour
    "m_haut": ((305.5, 138.5, 900.4, 138.5), 17.0),
    "m_gauche": ((305.5, 138.5, 305.5, 404.0), 16.5),
    "m_droit": ((900.4, 138.5, 900.4, 562.4), 16.75),
    "m_bas_chambre": ((609.0, 562.4, 900.4, 562.4), 16.25),
    "m_gauche_chambre": ((609.0, 341.25, 609.0, 562.4), 17.0),
    "m_bas_entree": ((422.5, 365.5, 609.0, 365.5), 16.0),
    "m_biais_1": ((422.5, 365.5, 378.0, 379.5), 15.0),
    "m_biais_2": ((378.0, 379.5, 341.5, 404.0), 14.0),
    "m_bas_sdb": ((341.5, 404.0, 305.5, 404.0), 16.75),
    # les cloisons
    "m_cuisine_sdb": ((305.5, 260.5, 506.0, 260.5), 6.0),
    "m_sdb_entree": ((506.0, 260.5, 506.0, 365.5), 6.0),
    "m_sejour_chambre": ((609.0, 344.6, 900.4, 344.6), 6.75),
    # les pleins dessinés dans les pièces
    "m_retour_haut": ((609.0, 138.5, 609.0, 178.0), 17.5),  # bout de mur qui descend du mur du haut, entre entrée et séjour
    "m_poteau": ((609.0, 243.0, 609.0, 282.0), 17.5),  # plein isolé, dans l'alignement du précédent
    "m_plein_cuisine": ((428.0, 138.5, 428.0, 178.0), 21.0),  # plein contre le mur du haut de la cuisine
    "m_plein_cuisine_2": ((438.5, 152.75, 454.5, 152.75), 11.5),  # son redan, à droite
    "m_saillie_sejour": ((710.5, 152.75, 794.5, 152.75), 11.5),  # surépaisseur du mur du haut du séjour
}

# ---------------------------------------------------------------- les ouvertures : type, bords, mur
OUVERTURES = {
    "o_entree": ("porte", (526.0, 365.5, 587.0, 365.5), "m_bas_entree"),
    "o_sdb": ("porte", (506.0, 295.0, 506.0, 350.0), "m_sdb_entree"),
    "o_chambre": ("porte", (628.0, 344.6, 683.0, 344.6), "m_sejour_chambre"),
    "f_cuisine": ("fenetre", (305.5, 178.5, 305.5, 243.0), "m_gauche"),
    "f_sdb": ("fenetre", (305.5, 301.5, 305.5, 366.0), "m_gauche"),
    "f_sejour": ("fenetre", (900.4, 200.5, 900.4, 282.0), "m_droit"),
    "f_chambre": ("fenetre", (900.4, 403.5, 900.4, 490.0), "m_droit"),
}

# ---------------------------------------------------------------- les pièces : nom écrit, type, point, contour intérieur
PIECES = {
    "p_cuisine": ("Cuisine", "cuisine", (370.0, 235.0),
                  [(313.5, 147.0), (508.0, 147.0), (508.0, 257.5), (313.5, 257.5)]),
    "p_entree": ("Entrée", "entree", (555.0, 225.0),
                 [(508.0, 147.0), (609.0, 147.0), (609.0, 357.5), (509.0, 357.5), (509.0, 257.5), (508.0, 257.5)]),
    "p_sejour": ("Séjour", "sejour", (760.0, 290.0),
                 [(609.0, 147.0), (892.0, 147.0), (892.0, 341.25), (609.0, 341.25)]),
    "p_sdb": ("Salle de bains / WC", "salle_d_eau", (400.0, 300.0),
              [(313.5, 263.5), (503.0, 263.5), (503.0, 357.5), (420.5, 357.5), (376.0, 371.75), (339.25, 395.75),
               (313.5, 395.75)]),
    "p_chambre": ("Chambre", "chambre", (760.0, 510.0),
                  [(617.5, 348.0), (892.0, 348.0), (892.0, 554.25), (617.5, 554.25)]),
}

# ---------------------------------------------------------------- les surfaces écrites : texte, valeur, cadre, pièce
SURFACES = [
    ("3,36 m²", 3.36, (363.0, 214.0, 410.0, 229.0), "p_cuisine"),
    ("4,05 m²", 4.05, (532.0, 265.0, 580.0, 280.0), "p_entree"),
    ("4,19 m²", 4.19, (387.0, 318.0, 435.0, 333.0), "p_sdb"),
    ("11,21 m²", 11.21, (737.0, 243.0, 792.0, 258.0), "p_sejour"),
    ("11,85 m²", 11.85, (733.0, 456.0, 788.0, 471.0), "p_chambre"),
    ("34,66 m²", 34.66, (268.0, 31.0, 324.0, 46.0), None),  # « …totale : 34,66 m² », en haut à gauche (début du texte coupé)
]

DOUTES = [
    ("La cuisine est écrite 3,36 m², mais la zone dessinée jusqu'au bout de la cloison est plus grande (environ 1 m² de plus). "
     "Aucun trait ne sépare la cuisine de l'entrée : où s'arrête la cuisine ? (limite posée au bout de la cloison)",
     "fort", (313.0, 147.0, 610.0, 258.0), "p_cuisine"),
    ("Aucun trait ne sépare l'entrée du séjour : limite posée sur la ligne des deux pleins (celui qui descend du mur du haut et "
     "celui qui est isolé).", "faible", (598.0, 147.0, 620.0, 342.0), "p_entree"),
    ("Plein isolé entre l'entrée et le séjour : poteau ou bout de cloison ? Un filigrane passe dessus. Lu comme un poteau plein.",
     "faible", (598.0, 240.0, 620.0, 285.0), "m_poteau"),
    ("Plein contre le mur du haut de la cuisine (gaine, conduit ?) : lu comme un plein de toute la hauteur.",
     "faible", (415.0, 145.0, 457.0, 181.0), "m_plein_cuisine"),
    ("Mur du haut du séjour plus épais sur une partie (conduit, cheminée ?) : lu comme un plein de toute la hauteur.",
     "faible", (708.0, 145.0, 797.0, 161.0), "m_saillie_sejour"),
    ("Mur en biais de la salle de bains : dessiné en deux pans d'inclinaisons différentes, positions approchées.",
     "faible", (335.0, 355.0, 428.0, 414.0), "m_biais_2"),
    ("Le plan ne dit pas si les quatre baies sont des fenêtres ou des portes-fenêtres : toutes lues comme des fenêtres.",
     "faible", None, None),
    ("Aucune hauteur sous plafond écrite sur le plan.", "faible", None, None),
]


def fiche() -> dict:
    return {
        "schema": "lecture-claude/0.1",
        "image": {"nom": "envoi.png", "largeur": 1206, "hauteur": 693},
        "murs": [{"id": i, "axe": list(a), "epaisseur_px": e} for i, (a, e) in MURS.items()],
        "ouvertures": [{"id": i, "type": t, "bords": list(b), "mur": m} for i, (t, b, m) in OUVERTURES.items()],
        "pieces": [{"id": i, "nom": n, "type": t, "point": list(p), "contour": [list(q) for q in c]}
                   for i, (n, t, p, c) in PIECES.items()],
        "cotes": [],
        "surfaces": [{"texte": t, "valeur_m2": v, "cadre": list(c), "piece": p} for t, v, c, p in SURFACES],
        "textes": [],
        "echelle_proposee": {"px_par_m": 69.2, "source": "surfaces",
                             "explication": "Aucune cote ni barre d'échelle. La chambre (rectangle net, 11,85 m² écrits) et la "
                                            "salle de bains (4,19 m²) donnent la même échelle, à 0,1 px par mètre près."},
        "niveau_lu": None,
        "autres_niveaux": [],
        "doutes": [{"raison": r, "gravite": g, "cadre": list(c) if c else None, "element": e} for r, g, c, e in DOUTES],
    }


if __name__ == "__main__":
    sortie = Path(sys.argv[1])
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(fiche(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"fiche écrite : {sortie}", flush=True)
