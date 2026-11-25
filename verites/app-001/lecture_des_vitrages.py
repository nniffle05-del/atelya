r"""APP-001 : LA HAUTEUR DES FENÊTRES LUE PAR CLAUDE, à la place du service payant (23/11/2026).

Lu dans la conversation sur les images agrandies de ..\atelya\lectures-photos\app-001\envoi-vitrages (outils/lecture_photos/
preparer_vitrages.py : la fenêtre, et ses images « -haut » et « -bas » au contraste renforcé). Format : moteur/vitrages.py
0.3. Fiche écrite par : outils/lecture_photos/ecrire_vitrages.py app-001 ; contrôlée par pc/verification/
sonde_hauteur_baies.py app-001 --images (les lignes redessinées sur la photo) et par le relief de chaque photo.

Ce logement n'avait pas de lecture des fenêtres (presque toutes sont derrière un voilage). Ici on ne dit que ce qui sert à
mesurer le BAS et le HAUT (moteur/hauteur_baies.py) :
  - cuisine (O5, O6) : fenêtres CLAIRES, dites en « tour seul » (`cadre`, `sol`, `plafond`, sans `coins` ni `vue`) : leur
    dessin (vantaux, garde-corps) et leur vue restent À LIRE ;
  - coin repas (O11) : derrière le voilage on voit l'appui de la fenêtre (son bas) et ses vitres jusqu'au haut du tissu :
    bas lu, haut « au moins » ;
  - séjour (O10) et chambres (O8, O9) : on voit les vitres jusqu'au haut du tissu, pas le bas : haut « au moins », bas caché.
"""
VITRAGES = {
    "photo-01": [{"baie": "O10", "vue": "voilee", "cadre": [[870, 128], [1190, 28], [1190, 520], [870, 500]],
                  "haut_au_moins": True, "bas_cache": True,
                  "sol": [[950, 523], [1025, 534]], "plafond": [[875, 95], [1100, 15]]}],  # sol : le bas du voilage
    "photo-04": [{"baie": "O11", "vue": "voilee", "cadre": [[755, 125], [975, -19], [975, 447], [755, 415]], "haut_au_moins": True,
                  "sol": [[790, 512], [1000, 590]], "plafond": [[705, 115], [845, 5]]}],  # sol : là où le voilage touche le sol
    "photo-05": [{"baie": "O5", "cadre": [[731, 160], [867, 110], [867, 351], [731, 349]],
                  "sol": [[900, 540], [1005, 570]], "plafond": [[740, 123], [975, 27]]}],
    "photo-06": [{"baie": "O5", "cadre": [[645, 165], [783, 142], [783, 355], [645, 358]], "sol": [912, 521],
                  "plafond": [[625, 163], [910, 77]]},
                 {"baie": "O6", "cadre": [[972, 104], [1100, 110], [1100, 352], [972, 351]], "sol": [928, 522],
                  "plafond": [[920, 76], [1060, 78]]}],
    "photo-08": [{"baie": "O8", "vue": "voilee", "cadre": [[752, 122], [855, 109], [855, 480], [752, 470]],
                  "haut_au_moins": True, "bas_cache": True}],
    "photo-10": [{"baie": "O9", "vue": "voilee", "cadre": [[680, 192], [860, 138], [860, 560], [680, 550]],
                  "haut_au_moins": True, "bas_cache": True}],
}
