# Photos du client rangées par pièce : ce qu'Atelya attend de la plateforme

Fiche du 15/11/2026, pour la plateforme interne (dépôt des plans et des photos). Atelya ne touche pas à la plateforme :
il lit seulement le petit fichier décrit ici.

## Pourquoi

Atelya se sert des photos du client pour retrouver le sol et les meubles de chaque pièce. Pour cela il doit savoir quelle
pièce chaque photo montre. Seul, il n'en est sûr que pour une photo sur deux environ (23 photos sur 45 sur trois
logements). Si le client nomme la pièce au dépôt, on passe à 30 ; les photos restantes sont réglées ensuite à l'écran de
vérification d'Atelya (44 sur 45).

## Ce que le client fait : nommer la pièce de chaque photo

Pour chaque photo, il choisit la sorte de pièce dans une liste : `sejour` (séjour, salon, salle à manger), `cuisine`,
`chambre`, `bureau`, `salle_d_eau`, `wc`, `entree`, `degagement` (couloir), `placard`, `buanderie`.

- C'est tout ce qui est demandé au client. Il n'a pas à dire de quelle chambre il s'agit.
- Une photo qu'il ne sait pas ranger : on ne met rien, Atelya essaie seul.
- En option, si la plateforme connaît déjà les pièces du plan lu par Atelya (dans `logement.json`, chaque pièce a un
  identifiant `id`, par exemple `chambre_2`, et un nom à afficher `nom`), le client peut choisir directement la pièce :
  il y aura alors moins de questions à la vérification.

## Le fichier attendu

Un fichier `pieces-des-photos.json`, rangé dans le même dossier que les photos :

```json
{
  "pieces": {
    "photo-01.jpg": "sejour",
    "photo-02.jpg": "chambre",
    "photo-03.jpg": "cuisine"
  }
}
```

`pieces` : pour chaque photo (nom du fichier, avec ou sans extension), la sorte de pièce, ou l'identifiant d'une pièce
du plan.

## La suite se passe dans Atelya

Quand Atelya ne sait pas où ranger une photo (deux chambres qui se ressemblent, une photo qui ne colle pas à la pièce
nommée), son écran de vérification pose la question « d'où est prise cette photo ? » et la personne qui vérifie pointe
l'endroit sur le plan. La plateforme n'a rien à faire pour cela. Atelya complète lui-même le fichier avec ces réponses
(`endroits`, `confirmees`).

## Limites connues

- Une erreur du client vers une pièce d'une autre sorte (une chambre rangée en « cuisine ») est repérée par Atelya environ
  quatre fois sur cinq, et envoyée à la vérification.
