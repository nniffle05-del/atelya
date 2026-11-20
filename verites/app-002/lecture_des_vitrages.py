r"""APP-002 : LE DESSIN DES FENÊTRES LU PAR CLAUDE, à la place du service payant (F2, 20/11/2026).

Lu dans la conversation, fenêtre par fenêtre, sur les images agrandies et graduées de ..\atelya\lectures-photos\app-002\
envoi-vitrages (outils/lecture_photos/preparer_vitrages.py). Format : moteur/vitrages.py. Chaque vantail coulissant est dit à
part. Fiche écrite par : outils/lecture_photos/ecrire_vitrages.py app-002 ; à REGARDER avec « preparer_vitrages.py controle ».

Baies coulissantes sans petits bois ; balcons à garde-corps (lisse et verre) devant le séjour et les chambres.

Relu le 20/11/2026 (F2 pièce 3, format 0.2) : le TOUR de chaque menuiserie (`cadre`) et, quand on la voit, la ligne du SOL
sous la baie (`sol`) : les baies du séjour et des chambres sont posées sur une marche d'une quinzaine de centimètres. Le
troisième vantail de la baie de la salle à manger est dit (il compte dans le dessin), avec un cache qui le couvre.
"""
VITRAGES = {
    # photo-02 : la baie du séjour vue de l'entrée par une porte, petite, brûlée par le jour ; la fenêtre de la cuisine : un filet
    "photo-02": [{"baie": "O8", "vue": "non"}, {"baie": "O1", "vue": "non"}],
    "photo-03": [
        # la baie de la salle à manger, trois vantaux. Celui de gauche montre le bout du balcon (volet, échelle, outils) : il est
        # dit pour le dessin de la fenêtre, et caché en entier (pas le dehors).
        # Sous le muret plein du balcon (y ≥ 391) : le muret et le sol du balcon, pas le dehors.
        # (corrigé au contrôle en image : le vantail de gauche commence à x = 668, après son montant à poignée, et non à 690)
        {"baie": "O9", "coins": [[668, 282], [762, 266.5], [762, 463.5], [668, 443]],
         "caches": [[[660, 255], [768, 255], [768, 470], [660, 470]]],
         "cadre": [[652, 274.5], [1163, 172], [1163, 558], [652, 445.5]]},
        {"baie": "O9", "coins": [[773.5, 264.5], [909.5, 242], [909.5, 495.5], [773.5, 466]], "caches": [[600, 391, 1206, 660]]},
        {"baie": "O9", "coins": [[929, 234], [1154.5, 193.5], [1154.5, 548.5], [929, 500]], "caches": [[600, 391, 1206, 660]]},
        {"baie": "O14", "vue": "non"},  # un filet au bord d'un mur
    ],
    "photo-04": [
        # la baie du séjour vue de biais ; le vantail de gauche sort du cadre (coins estimés hors de la photo). Le vantail de
        # droite est derrière une toile (moustiquaire ou store) : pas le dehors, pas dit. Fenêtre coupée : pas de « cadre ».
        {"baie": "O8", "coins": [[0, 145], [202, 227.5], [202, 561.5], [0, 640]], "caches": [[0, 478, 33, 660]]},
    ],
    "photo-05": [
        {"baie": "O8", "coins": [[454.5, 281], [546, 287], [546, 453], [454.5, 457]], "caches": [[529, 385, 700, 480]],  # chaises, table
         "cadre": [[446.5, 272.5], [632, 291], [632, 457.5], [446.5, 465]], "sol": [480, 481]},
        {"baie": "O8", "coins": [[550, 291], [623, 295.5], [623, 450], [550, 453]], "caches": [[529, 385, 700, 480]]},
        {"baie": "O9", "vue": "non"},  # le chant d'un vantail ouvert
    ],
    # photo-07 : là où le plan met ces fenêtres, la photo montre un mur et un coin d'écran
    "photo-07": [{"baie": "O8", "vue": "non"}, {"baie": "O10", "vue": "non"}],
    "photo-08": [  # la fenêtre de la cuisine, deux vantaux ; le robinet devant le vantail de gauche, une plante au bord du droit
        {"baie": "O1", "coins": [[226, 246.5], [345.5, 261], [345.5, 413.5], [226, 416.5]], "caches": [[316, 385, 356, 420]],
         "cadre": [[206, 228.5], [457, 263], [457, 420.5], [206, 432]]},
        {"baie": "O1", "coins": [[353.5, 265], [444.5, 273.5], [444.5, 409.5], [353.5, 411.5]], "caches": [[436, 378, 450, 412]]},
    ],
    "photo-10": [  # la chambre 1 : la télévision, la commode et le lit cachent le bas et la droite de la baie
        {"baie": "O15", "coins": [[292, 252], [419, 261], [419, 507], [292, 511.5]], "caches": [[363, 311, 542, 424], [329, 418, 600, 600]],
         "cadre": [[277, 238], [541, 258], [541, 514], [277, 523]], "sol": [300, 546]},
        {"baie": "O15", "coins": [[426.5, 265.5], [534.5, 266.5], [534.5, 503], [426.5, 506.5]],
         "caches": [[363, 311, 542, 424], [329, 418, 600, 600]]},
    ],
    "photo-14": [  # la chambre 2 : le tabouret et le bureau devant le vantail de droite
        {"baie": "O16", "coins": [[725.5, 264], [827.5, 254.5], [827.5, 494], [725.5, 483]],
         "cadre": [[718, 251], [985, 222], [985, 515.5], [718, 490]], "sol": [1000, 540]},
        {"baie": "O16", "coins": [[845, 251], [976, 236], [976, 509], [845, 495.5]], "caches": [[927, 468, 980, 515], [963, 438, 1060, 520]]},
    ],
    "photo-15": [
        {"baie": "O16", "coins": [[265, 209], [407.5, 213], [407.5, 490], [265, 503]],
         "cadre": [[258, 192], [541, 230], [541, 474], [258, 508]]},  # le bas est caché par le lit : pas de « sol »
        {"baie": "O16", "coins": [[422, 230.5], [528.5, 243.5], [528.5, 467], [422, 478.5]], "caches": [[520, 447, 580, 472]]},  # le tabouret
    ],
}
