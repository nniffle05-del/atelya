# Modèles de l'étape A3 (essai 7b), 3 novembre 2026

Sauvegarde des modèles entraînés sur le PC (la création d'une « release » GitHub n'était pas possible depuis la session).
Chaque modèle est coupé en morceaux de 40 Mo. Pour le reconstituer :

- Mac / Linux : `cat atelya-essai-7.pt.part* > atelya-essai-7.pt`
- Windows (PowerShell) : `cmd /c copy /b atelya-essai-7.pt.part00+atelya-essai-7.pt.part01 atelya-essai-7.pt`

Puis vérifier l'empreinte (SHA256.txt) :
- atelya-essai-7.pt : 50f0038553f6da02231474ac68b8ccdec06245e499b11ff7b7373d9b8f61209b (modèle gardé, en service sur les plans en biais)
- atelya-essai-7-dernier.pt : 205fa43e513ed52774b330b9861373f37dd0c221f54aae8c62c02610576dcc5b

Les poids DINOv2 ne sont pas inclus : ils viennent de Meta (Apache 2.0), voir pc/a3/ sur la branche de code.
`analyses/` : bancs de mesure et réglage de l'aiguillage (moteur/aiguillage.py).
