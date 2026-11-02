# Sauvegarde du PC (2026-11-02)

Copie du dossier `D:\Modélisation immobilière\atelya` du PC de calcul (RTX 2070),
qui n'avait aucun historique. Ce dossier ne remplace pas le moteur (racine du dépôt) :
c'est l'état du PC tel qu'il était le 2 novembre 2026.

- Racine : scripts d'entraînement (`entrainer.py` = base, `entrainer_essai6.py` = le plus récent),
  coloriage (`colorier*.py`), scripts PowerShell des essais, `pyproject.toml` + `uv.lock`.
- `code-6-13` … `code-6-19`, `depot-6-19` : copies du moteur posées sur le PC à chaque étape.
- `vrais-plans/` : les 13 vrais plans français (`lot-2026-10-31`, plans d'EXAMEN, ne pas entraîner
  dessus) et les coloriages d'Atelya pour chaque essai.
- `resultats-*` : bilans, historiques et planches des essais (sans les modèles).
- `MODELES.txt` : liste des modèles `.pt` avec leur empreinte SHA256. Les modèles eux-mêmes sont
  dans les « Releases » du dépôt (trop gros pour le code).

Non sauvegardé (refaisable) : `donnees/` (9,7 Go de plans fabriqués), `.venv`, `.cache-uv`, `.pythons`.
