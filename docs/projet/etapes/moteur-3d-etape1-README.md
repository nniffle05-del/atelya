# moteur-3d

Moteur de reconstruction 3D immobilière : plan + photos, puis modèle JSON, puis scène Blender.

## Organisation

- `moteur/logement.py` : le format JSON d'un logement (version 0.1) et ses règles de vérification.
- `exemples/cas-test-00/logement.json` : le cas test n°0, un T2 de synthèse de 42 m² (dimensions de référence exactes).
- `tests/` : les tests automatiques.

## Commandes utiles

```
uv run pytest        # lance tous les tests
```

## Conventions

- Longueurs en mètres ; repère vu de dessus : x vers l'est, y vers le nord, origine au coin intérieur sud-ouest.
- Un mur est décrit par son axe (la ligne en son milieu) et son épaisseur.
- Chaque élément porte un `statut` : `mesure`, `estime` ou `ajoute`, et une `source`.
