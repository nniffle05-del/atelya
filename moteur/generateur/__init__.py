"""Le générateur de jeux de données : des milliers de plans inventés, avec leur vérité terrain exacte.

Chaque module fait une chose :

- `reglages.py`      : les réglages (distributions des types, surfaces, épaisseurs…), modifiables par JSON ;
- `logements.py`     : invente la géométrie d'un logement (studio à T5, duplex, formes variées) ;
- `annotations.py`   : la vérité terrain vectorielle, en mètres, indépendante de tout dessin ;
- `rendu.py`         : dessine l'image du plan ET ses masques, dans le même repère pixel ;
- `mobilier.py`      : les symboles de meubles dessinés dans les pièces (variante « avec mobilier ») ;
- `variantes.py`     : les styles graphiques et les imperfections de numérisation ;
- `modele3d.py`      : le modèle 3D (GLB, OBJ, briques Blender) construit depuis la même géométrie ;
- `validateur.py`    : les contrôles, règles explicites et réglables ;
- `doublons.py`      : doublons exacts et plans trop semblables ;
- `exportateur.py`   : la fabrication d'un exemple complet, le manifeste, la répartition train/validation/test ;
- `statistiques.py`  : les statistiques d'un jeu généré ;
- `controle_qualite.py` : planches d'aperçu et page de contrôle visuel ;
- `__main__.py`      : la ligne de commande (`python -m moteur.generateur`).

La fabrique existante (moteur/fabrique.py) n'est pas modifiée : elle sert au banc
de lecture, qui doit redonner exactement les mêmes plans qu'avant.
"""

VERSION_GENERATEUR = "0.1.1"
