r"""APP-004 : LE DESSIN DES FENÊTRES LU PAR CLAUDE, à la place du service payant (F2, 20/11/2026).

Lu dans la conversation, fenêtre par fenêtre, sur les images agrandies et graduées de ..\atelya\lectures-photos\app-004\
envoi-vitrages (outils/lecture_photos/preparer_vitrages.py). Format : moteur/vitrages.py (coins du vitrage, montants, traverses,
caches, vue). Chaque battant est dit à part (les deux battants d'une fenêtre ancienne ne sont pas tout à fait dans le même plan).
Fiche écrite par : outils/lecture_photos/ecrire_vitrages.py app-004 ; à REGARDER avec « preparer_vitrages.py controle ».

Fenêtres hautes à deux battants, trois vitres par battant (deux traverses), garde-corps en fer forgé devant la vitre du bas.

Relu le 20/11/2026 (F2 pièce 3, format 0.2) : le TOUR de chaque menuiserie (`cadre`), la ligne du SOL sous la fenêtre (`sol`)
et le genre du garde-corps. Constat : ces fenêtres ne descendent PAS jusqu'au sol : sous la menuiserie il y a une allège basse
(un panneau plein d'environ 35 cm), ce qui explique le garde-corps. Un côté caché par un rideau est estimé d'après l'autre.

Relu le 23/11/2026 (format 0.3 : le bas et le haut des fenêtres, moteur/hauteur_baies.py) sur les images « -haut » et « -bas »
au contraste renforcé : la ligne du PLAFOND du mur de chaque fenêtre (`plafond` ; ici une petite corniche : son tiers haut) et
celle du SOL (`sol`, relue : n'importe où le long du pied du mur). Contrôlé par pc/verification/sonde_hauteur_baies.py
--images (les lignes redessinées sur la photo) et par le relief de chaque photo (second avis indépendant).
"""
VITRAGES = {
    "photo-01": [
        {"baie": "O6", "coins": [[885, 254.5], [941, 246], [941, 511], [885, 504]],
         "traverses": [[336, 341, 332.5, 337.5], [420.5, 426, 422, 427.5]],
         "caches": [[855, 205, 883, 560]], "garde_corps": [423, 425], "genre_garde_corps": "fer_forge",  # le rideau, à gauche
         "cadre": [[872, 243.5], [1046, 210.5], [1046, 544], [872, 515]], "sol": [860, 559],
         "plafond": [[800, 227], [1200, 113]]},  # bord gauche estimé (rideau)
        {"baie": "O6", "coins": [[961, 239.5], [1030, 229], [1030, 527], [961, 517.5]],
         "traverses": [[330, 335.5, 325.5, 330.5], [423, 429, 425.5, 432]], "garde_corps": [426, 429]},
    ],
    # photo-04 : la fenêtre est loin et la marque de l'agence (un grand cercle) passe en travers de ses vitres
    "photo-04": [{"baie": "O6", "vue": "non"}],
    "photo-05": [  # la cuisine : fenêtre sur allège, deux battants sans traverse ; une hotte cache le haut du battant de droite
        {"baie": "O4", "coins": [[144, 232.5], [221.5, 242], [221.5, 436.5], [144, 438]],
         "cadre": [[127, 211.5], [324, 243], [324, 446.5], [127, 455.5]],  # bord droit estimé (hotte)
         "plafond": [[80, 127], [275, 163]]},  # le pied du mur est caché par les meubles de cuisine
        {"baie": "O4", "coins": [[247, 248.5], [310, 256.5], [310, 433], [247, 435]], "caches": [[277, 160, 325, 303]]},
    ],
    "photo-07": [
        {"baie": "O6", "coins": [[138, 236], [223, 248], [223, 553.5], [138, 561.5]],
         "traverses": [[341.5, 347, 345.5, 350.5], [450.5, 457.5, 448, 453.5]],
         "caches": [[95, 190, 138, 660]], "garde_corps": [455, 451], "genre_garde_corps": "fer_forge",  # le rideau, à gauche
         "cadre": [[121.5, 218], [328, 252], [328, 551], [121.5, 577]], "sol": [[140, 643], [345, 594]],
         "plafond": [[25, 127], [325, 201]]},  # bord gauche estimé (rideau)
        {"baie": "O6", "coins": [[245.5, 254], [314.5, 264.5], [314.5, 539], [245.5, 549]],
         "traverses": [[350, 356, 352.5, 358.5], [444.5, 450.5, 443.5, 449]], "garde_corps": [448, 446]},
    ],
    # photo-08 : à l'endroit où le plan met cette fenêtre, la photo montre un mur (et la marque de l'agence)
    "photo-08": [{"baie": "O5", "vue": "non"}],
    "photo-09": [
        {"baie": "O7", "coins": [[788, 274], [845, 270], [845, 533.5], [788, 527]],
         "traverses": [[357, 363, 356, 362], [443, 450, 444.5, 451.5]], "garde_corps": [449, 450], "genre_garde_corps": "fer_forge",
         "cadre": [[776, 262], [947.5, 247], [947.5, 559], [776, 536.5]], "plafond": [[650, 231], [1125, 158]]},  # bord droit estimé (rideau) ; sol caché par le lit
        # le battant de droite : son bord droit est derrière le rideau (estimé)
        {"baie": "O7", "coins": [[863.5, 268.5], [933, 263], [933, 544], [863.5, 536.5]],
         "traverses": [[355.5, 360, 353, 358.5], [445.5, 452, 446.5, 453]],
         "caches": [[[931, 200], [1010, 200], [1010, 600], [919, 600]]], "garde_corps": [451, 452]},
    ],
    "photo-10": [
        {"baie": "O7", "coins": [[174, 247], [248.5, 259], [248.5, 539], [174, 549]],
         "traverses": [[344, 350, 348, 353], [443, 448, 442, 447.5]], "garde_corps": [446, 444], "genre_garde_corps": "fer_forge",
         "cadre": [[160, 230], [339, 264], [339, 533], [160, 563.5]], "sol": [185, 618], "plafond": [[0, 128], [375, 237]]},  # bord droit estimé (rideau)
        {"baie": "O7", "coins": [[269.5, 264.5], [328, 274], [328, 524.5], [269.5, 533]],
         "traverses": [[349.5, 354.5, 353, 358], [441.5, 447, 440, 446]],
         "caches": [[327, 225, 400, 560]], "garde_corps": [444, 442]},  # le rideau, à droite
    ],
    # photo-11 : la salle de bains : vitrage DÉPOLI (on ne voit qu'une clarté et l'ombre du garde-corps)
    "photo-11": [{"baie": "O5", "vue": "lueur", "cadre": [[283, 204], [503, 229], [503, 582], [283, 596]],
                  "sol": [[400, 668], [500, 655]], "plafond": [[240, 127], [510, 165]]}],
    "photo-12": [
        {"baie": "O7", "coins": [[946.5, 249], [1021.5, 247.5], [1021.5, 547.5], [947, 536]],
         "traverses": [[345, 350.5, 345, 350.5], [445, 451, 446, 452]], "garde_corps": [450, 452], "genre_garde_corps": "fer_forge",
         "cadre": [[932, 235.5], [1160.5, 208], [1160.5, 584], [932, 547]], "plafond": [[825, 238], [1200, 132]]},  # bord droit estimé (rideau) ; sol caché par le lit
        {"baie": "O7", "coins": [[1045.5, 241.5], [1142, 228.5], [1142, 565], [1045.5, 554]],
         "traverses": [[339.5, 345, 337, 343], [448, 454, 451, 457]],
         "caches": [[[1147, 190], [1206, 190], [1206, 600], [1127, 600]]], "garde_corps": [453, 456]},  # le rideau, à droite
    ],
}
