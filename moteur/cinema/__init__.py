"""La CINÉMATIQUE d'Atelya, brique par brique (12/11/2026, étape 0 du plan validé par NT : séparer les rôles sans rien changer).

Chaque brique a UN métier, et se teste seule :

    reglages      tous les réglages du vol (vitesses, hauteurs, regard…), au même endroit : ce qu'on ajustera d'après les avis
    navigation    OÙ la caméra peut passer : la grille du logement, les portes ouvertes, le plus court chemin
    parcours      CE QU'ON VA MONTRER et dans quel ordre : points de vue des pièces, fonds des grandes pièces (le futur planificateur)
    trajectoire   la COURBE lisse et l'ALLURE : lissage, demi-tours en boucle, vitesse, positions image par image
    regard        OÙ REGARDE la caméra : la profondeur vue, le regard choisi sur tout le vol d'un seul calcul
    camera        la caméra elle-même : hauteur (survol des meubles bas), plongée, clés du trajet pour Unreal

Le chef d'orchestre reste moteur/promeneur.vol() ; le rendu reste dans moteur/unreal et outils/unreal ; le contrôle viendra à
l'étape 1 (moteur/cinema/controle.py).
"""
