# Photos du client rangées par pièce : ce qu'Atelya attend de la plateforme

Fiche du 15/11/2026, pour la plateforme interne (dépôt des plans et des photos). Atelya ne touche pas à la plateforme :
il lit seulement le petit fichier décrit ici.

## Pourquoi

Atelya se sert des photos du client pour retrouver le sol et les meubles de chaque pièce. Pour cela il doit savoir quelle
pièce chaque photo montre. Seul, il n'en est sûr que pour une photo sur deux environ. Si le client le dit au dépôt,
presque toutes les photos deviennent utilisables (mesuré sur trois logements : 23 photos utilisées sur 45 quand Atelya
devine, 43 quand la pièce est donnée).

## Ce que le client fait

Pour chaque photo, il choisit **une pièce du plan**.

- Le mieux : il clique sur la pièce dans le plan, ou la choisit dans la liste des pièces du logement. Cette liste vient
  d'Atelya, une fois le plan lu : dans `logement.json`, chaque pièce a un identifiant (`id`, par exemple `chambre_2`) et
  un nom à afficher (`nom`). Il faut donc que le plan soit lu avant le rangement des photos.
- À défaut : il donne seulement la sorte de pièce (`chambre`, `cuisine`…). Cela suffit quand le logement n'a qu'une pièce
  de cette sorte. Avec deux chambres qui se ressemblent, Atelya ne peut pas savoir laquelle : la photo reste de côté.
- Une photo que le client ne sait pas ranger : on ne met rien, Atelya essaie seul.

## Le fichier attendu

Un fichier `pieces-des-photos.json`, rangé dans le même dossier que les photos :

```json
{
  "pieces": {
    "photo-01.jpg": "sejour_1",
    "photo-02.jpg": "chambre_2",
    "photo-03.jpg": "cuisine"
  },
  "confirmees": ["photo-02.jpg"]
}
```

- `pieces` : pour chaque photo (nom du fichier, avec ou sans extension), l'identifiant de la pièce, ou sa sorte. Sortes
  connues : `sejour` (séjour, salon, salle à manger), `cuisine`, `chambre`, `bureau`, `salle_d_eau`, `wc`, `entree`,
  `degagement` (couloir), `placard`, `buanderie`.
- `confirmees` (facultatif) : les photos dont la pièce a été confirmée à l'écran de vérification (voir plus bas).

## Ce qu'Atelya répond

Dans sa fiche des photos (`cameras-photos-seul.json`) :

- `cameras` : les photos utilisées, avec la pièce et l'endroit d'où chacune est prise ;
- `a_verifier` : les photos pour lesquelles Atelya doute de la pièce donnée, avec la raison en clair (par exemple « les
  meubles vus sur la photo ne vont pas avec cette pièce »). Elles ne sont pas utilisées tant que la pièce n'est pas
  confirmée à l'écran de vérification ; une fois confirmée, le nom de la photo va dans `confirmees` et Atelya ne doute plus ;
- `incertaines` : les photos sans pièce donnée dont Atelya n'est pas sûr (laissées de côté).

## Limites connues

- Une erreur entre deux pièces de même sorte (la chambre 1 donnée pour la chambre 2) ne peut pas être repérée par Atelya.
- Une erreur vers une pièce d'une autre sorte est repérée environ quatre fois sur cinq.
