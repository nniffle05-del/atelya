"""Tous les réglages de la caméra d'Atelya au même endroit (valeurs réglées à l'œil et sur les films d'app-002, 12/11/2026)."""

# le temps
IPS = 24  # images par seconde
CLE_IMAGES = 4  # une décision de regard toutes les 4 images

# la grille où la caméra peut passer
PAS_M = 0.05
MARGE_M = 0.20  # on passe une porte de 60 cm (comme un opérateur) ; ailleurs, on préfère le milieu des passages (CONFORT_M)
CIRCULATION = {"entree", "degagement", "couloir", "hall"}
CONFORT_M = 0.6  # au-delà de cette distance des obstacles, plus de surcoût : on passe au milieu des passages
BATTANT_EP = 0.05  # épaisseur d'un battant de porte ouvert
SURVOL_MARGE_M = 0.5  # on survole un meuble si l'on passe au moins 50 cm au-dessus
SOUS_OBJET_M = 0.3  # on passe SOUS un objet suspendu (suspension, étagère haute) avec au moins 30 cm de jeu
FOND_DISTANCE_M = 0.6  # le fond d'une pièce est pris à au moins ça des murs et des meubles

# le regard (12/11/2026, premier essai : la caméra fixait parfois un mur à quelques centimètres) : vers là où l'on voit LOIN, à au
# plus REGARD_LIBERTE_DEG de la direction du mouvement ; au fond d'une pièce, vers la plus belle profondeur (on révèle la pièce)
REGARD_LIBERTE_DEG = 50.0
REGARD_LIBERTE_LARGE_DEG = 140.0  # quand tout est proche devant (on va vers un angle ou une porte)
PROFONDEUR_MIN_M = 2.0
REGARD_CHAMP_DEG = 30.0  # demi-largeur du cône où l'on mesure la profondeur d'une direction
REGARD_RAPPEL = 0.025  # pénalité (m de profondeur par degré) pour s'écarter de la direction du mouvement

# LA CAMÉRA VOLANTE (12/11/2026, NT : « 1 min 50 c'est trop long ; la caméra qui marche, ce n'est pas ouf, on ressent les
# secousses ; il faudrait que la caméra vole »). Comme un drone de cinéma : une courbe continue très lissée, accélérations
# douces, rotation fluide et anticipée. Plus court : l'ordre de visite le plus court, le fond de pièce seulement dans les grandes.
VOL_HAUTEUR_M = 1.6
VOL_HAUTEUR_MAX_M = 1.9  # dans les grands espaces ouverts
VOL_SOUS_PLAFOND_M = 0.45  # jamais plus près du plafond
VOL_PLONGEE_PAR_M = 15.0  # degrés de plongée en plus par mètre au-dessus de 1,6 m
VOL_TANGAGE_DEG = -7.0
VOL_VITESSE = 0.9  # m/s en croisière
VOL_VITESSE_VUE = 0.6  # m/s en passant devant ce qu'on montre (un léger ralenti, pas un freinage)
VOL_RAYON_VUE_M = 1.4  # on ralentit et on tourne la caméra vers le cadrage à moins de ça du point de vue
VOL_DEPART_ARRIVEE_M = 1.5  # accélération au départ, décélération à l'arrivée
VOL_LISSAGE_M = 0.7  # lissage de la trajectoire (écart type, en mètres)
VOL_LISSAGE_CAP_S = 0.8  # lissage de la rotation (écart type, en secondes)
VOL_ROTATION_MAX = 28.0  # °/s
VOL_FINITION_S = 0.2
VOL_PIVOT_S = 1.6  # arrêt en vol stationnaire au bout d'une impasse (la caméra y pivote, plus vite qu'en vol)
VOL_ROTATION_PIVOT = 60.0  # °/s à l'arrêt (en vol : VOL_ROTATION_MAX)
VOL_REGARD_MAX_DEG = 40.0  # le regard reste à moins de ça de la direction du mouvement (la caméra ne recule jamais)
VOL_MUR_MIN_M = 0.9  # jamais le nez sur un mur plus près que ça (sauf en franchissant une porte)
VOL_FOND_M2 = 20.0  # au-delà, la pièce a aussi son « fond » (on va au bout ; on en ressort par un autre chemin si possible)
VOL_DEJA_VU_M = 0.7  # autour d'un passage déjà emprunté…
VOL_DEJA_VU_COUT = 3.0  # … chaque pas coûte en plus ça (on préfère un autre chemin jusqu'à ~4 fois plus long)
VOL_ACCEL_LATERALE = 0.6  # m/s² : dans un virage serré (ou un demi-tour au bout d'un cul-de-sac), on ralentit en douceur
VOL_BOUCLE_RAYONS = (1.5, 1.2, 0.9, 0.75, 0.6, 0.5, 0.4)  # m : la plus grande boucle qui tient (autour d'une table…)
VOL_BOUCLE_RECUL_M = 1.5  # on amorce la boucle jusqu'à ça avant le bout de l'impasse ; au-delà, arrêt et pivot
