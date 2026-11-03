# Pose sur le Mac (seulement après le « vas-y » de NT et la fin de l'étape 6-17)

Uniquement des AJOUTS, aucun fichier existant modifié :
- `verification-plan/`  →  `moteur-3d/outils/verification-plan/`
- `tests-mac/test_ecran_verification.py`  →  `moteur-3d/tests/test_ecran_verification.py`
- `scripts/` reste dans le cloud (fabrication de l'exemple, parcours navigateur).

Puis `uv run pytest` (le nouveau test relit le logement corrigé avec moteur/logement.py)
et `node --test outils/verification-plan/tests/verif.test.js` si Node.js est présent (sinon, déjà passé dans le cloud : 21/21).
