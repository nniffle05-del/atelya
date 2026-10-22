# moteur-3d

Moteur de reconstruction 3D immobilière : plan + photos, puis modèle JSON, puis scène Blender.

## Organisation

- `moteur/logement.py` : le format JSON d'un logement (version 0.1) et ses règles de vérification.
- `exemples/cas-test-00/logement.json` : le cas test n°0, un T2 de synthèse de 42 m² (dimensions de référence exactes).
- `moteur/geometrie.py` : transforme le logement en « briques » (morceaux de murs, allèges, linteaux, sols, plafonds, seuils). Aucun besoin de Blender.
- `moteur/blender/poser_briques.py` : script lu par Blender, qui pose les briques et enregistre la maquette.
- `moteur/blender/mesurer.py` : script lu par Blender, qui mesure la maquette (pour les tests).
- `moteur/construire.py` : la commande unique, du logement.json à la maquette .blend.
- `tests/` : les tests automatiques (`test_blender.py` lance vraiment Blender, sans écran).

## Commandes utiles

```
uv run pytest        # lance tous les tests
uv run python -m moteur.construire exemples/cas-test-00/logement.json sorties/cas-test-00
                     # construit sorties/cas-test-00/maquette.blend
```

Les maquettes produites vont dans `sorties/`, qui n'est pas suivi par Git (on peut toujours les reconstruire).
Blender est cherché dans `/Applications/Blender.app` ; sinon, indiquer son chemin dans la variable `BLENDER`.

## Conventions

- Longueurs en mètres ; repère vu de dessus : x vers l'est, y vers le nord, origine au coin intérieur sud-ouest.
- Un mur est décrit par son axe (la ligne en son milieu) et son épaisseur.
- Aux angles, le premier mur de la liste est rallongé et le second raccourci, pour que l'angle soit fermé sans chevauchement. Version 0.1 : angles droits seulement, deux murs au plus par angle.
- Chaque élément porte un `statut` : `mesure`, `estime` ou `ajoute`, et une `source`.
