# Étape A3 sur le PC (œil DINOv2 + murs en biais)

Scripts lancés sur le PC (RTX 2070) pendant l'étape A3, 2 et 3 novembre 2026.

- `oeil.py` : UNetOeil, le U-Net de l'essai 5 plus DINOv2 ViT-S/14 figé (code DINOv2 réécrit ici, seuls les poids
  officiels de Meta sont téléchargés, licence Apache 2.0 : `LICENSE-DINOv2.txt`).
- `entrainer_essai7b.py` + `essai-7b.ps1` : essai 7b (lr 5e-5, garde « retour en arrière »), modèle gardé
  `resultats-essai-7b/atelya-essai-7.pt` (release GitHub `modeles-2026-11-03`).
- `mesure-a3b.ps1`, `controle-a3b.ps1` : mesure complète et banc de contrôle modèle / traducteur.
- `en_direct.py` : page qui montre Atelya travailler en temps réel (bandeau rouge si une étape plante).

Verdict (3/11) : essai 5 sur les plans droits, essai 7b sur les plans à murs en biais ou arrondis
(`moteur/aiguillage.py`, traducteur 0.4.1).
