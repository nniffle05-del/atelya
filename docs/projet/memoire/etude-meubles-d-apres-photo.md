# Étude : fabriquer chaque meuble en 3D d'après sa photo (« voie B »), état au 16/11/2026

**Pourquoi cette étude.** NT, le 16/11/2026 : « j'aimerais que chaque meuble, chaque plinthe, chaque mur, chaque rideau soit
exactement le même que sur la photo ». Les meubles d'Atelya sont choisis dans un catalogue (7 641 modèles ABO) : ils ressemblent,
ils ne sont jamais « le même ». La seule voie vers « ce canapé-là » est de FABRIQUER le meuble d'après sa photo (un programme
qui transforme la photo d'un objet en objet 3D). NT a dit « Oui » à l'étude (licences, machine, prix), **sans rien télécharger**.

**Statut : ÉTUDE SEULEMENT. Rien téléchargé, aucun compte créé, aucune image envoyée, aucune dépense.** Tout essai demande
l'accord écrit de NT (règles 3 et 4 de CLAUDE.md), et la relecture EN ENTIER, par la session qui proposera l'essai, de la licence
de l'option retenue (règle des licences : le fichier, pas un résumé).

**Qui a lu quoi.** La recherche a été faite par un agent de recherche (Claude, 152 lectures de pages, ~19 min). Dans son
rapport, [V] = il a ouvert et lu lui-même le fichier de licence, la page de prix ou les conditions ; [NV] = source secondaire ou
page non ouverte. La session principale a ensuite RELU elle-même, le 16/11/2026 :
- TRELLIS.2, fichier LICENSE du dépôt : texte MIT standard, lu mot à mot (« Copyright (c) Microsoft Corporation ») ;
- nvdiffrast, LICENSE.txt : « The Work and any derivative works thereof only may be used or intended for use non-commercially »,
  non commercial = « for research or evaluation purposes only and not for any direct or indirect monetary gain » ;
- Stability AI Community License (5/7/2024) : gratuit en commercial tant qu'on ne dépasse pas « USD $1,000,000 in annual
  revenue », « You must register with Stability AI », « You own any outputs generated from the Models » ; pas de clause de territoire ;
- SAM License (Meta, 19/11/2025) : seulement un RÉSUMÉ (licence mondiale, gratuite, usage / copie / modification / distribution ;
  interdits : militaire, nucléaire, espionnage, armes ; redistribution sous la même licence ; indemnisation de Meta ; droit de
  Californie ; Meta peut modifier les termes). **Texte intégral NON relu mot à mot : à faire avant tout usage.**

## En bref

- Les deux meilleurs modèles ouverts demandent 24 à 32 Go de mémoire de carte graphique : **pas la RTX 2070 (8 Go)**. Il faut donc
  un service payant à l'objet (0,02 à 0,35 $ par meuble) ou une carte louée à l'heure (~0,01 $ par meuble).
- Le piège est rarement la licence des poids (souvent MIT) : c'est celle des outils d'export (nvdiffrast de NVIDIA : non commercial).
- Pour 10 à 30 meubles par logement : de 0,2 à 10 $ par logement selon l'option.

## 1. Liste classée (adéquation à notre cas d'abord)

### 1. SAM 3D Objects (Meta, 19/11/2025)
Le seul fait pour notre cas : il reçoit la photo ENTIÈRE et le masque du meuble, vise les « real-world scenarios with occlusion
and clutter », et rend forme, texture, et place / taille dans la scène.
- Licence [V] (code et poids, « SAM License ») : « You are granted a non-exclusive, worldwide, non-transferable and royalty-free
  limited license […] to use, reproduce, distribute, copy, create derivative works of, and make modifications to the SAM
  Materials. » Aucune clause non commerciale ni territoriale. Interdits : « military or warfare purposes, nuclear industries or
  applications, espionage ». Redistribution sous la même licence.
  https://github.com/facebookresearch/sam-3d-objects/blob/main/LICENSE
- Dépendances [V pour la liste] : pytorch3d, kaolin 0.17, gsplat, MoGe ; pas de nvdiffrast dans l'installation. Leurs licences : non relues [NV].
- Poids : sur demande (nom légal, date de naissance, société) [V] https://huggingface.co/facebook/sam-3d-objects
- Matériel [V] : « A NVIDIA GPU with at least 32 Gb of VRAM », Linux. Impossible sur 8 Go.
- Coût : 0,02 $ par objet chez fal.ai [V] https://fal.ai/models/fal-ai/sam-3/3d-objects ; ou carte 48 Go louée 0,59 $/h [V]
  https://www.runpod.io/pricing, soit environ 0,01 $ par meuble (calcul de l'agent).
- Sortie [V, lu dans le code] : gaussiennes + maillage GLB, couleurs par sommet par défaut, texture 1024 en option, pas de PBR.
- Faiblesses : détail limité ; « Heavily occluded subjects produce less accurate geometry » (guide fal [V]) ; une seule photo par
  meuble (la version à plusieurs photos, « Scene-SAM3D », juillet 2026, n'a pas encore publié son code [V]).

### 2. TRELLIS.2 (Microsoft, déc. 2025) : la meilleure qualité ouverte, avec matières (PBR)
- Licence [V, relue] : « This model and code are released under the MIT License. » https://github.com/microsoft/TRELLIS.2
- Pièges [V] : l'export GLB officiel appelle nvdiffrast (non commercial, relu) ; le détourage par défaut `briaai/RMBG-2.0`
  (« Commercial use is subject to a commercial agreement with BRIA » ; remplaçable par notre masque, à confirmer) ; œil DINOv3
  obligatoire, sous « DINOv3 License » de Meta (mêmes termes que SAM, pas de clause non commerciale).
- Voie propre [V] : ComfyUI l'intègre depuis août 2026, « no compiled CUDA extensions […] and no non-commercial dependencies »
  (https://blog.comfy.org/p/trellis2-and-pixal3d-are-now-native). ComfyUI est GPL-3 [V] : un OUTIL à part, comme Blender.
- Matériel : « at least 24GB », Linux [V] ; 3 s à 60 s par objet sur une très grosse carte [V]. Poids compressés chez Comfy-Org [V] ;
  « 6 à 8 Go suffisent » = blogs [NV], non prouvé.
- Coût : fal.ai 0,25 / 0,30 / 0,35 $ selon la finesse [V] https://fal.ai/models/fal-ai/trellis-2 ; carte 24 Go louée 0,89 $/h [V].
- Sortie [V] : GLB PBR (couleur, rugosité, métal), 1 000 000 de faces par défaut, à alléger pour Unreal.
- Faiblesses : une seule image, rien pour les parties cachées, « small holes » possibles.
- Variante Pixal3D (Tencent ARC, mai 2026 ; plusieurs photos avec caméras connues depuis sept. 2026) : licence MIT sans exclusion [V],
  mais la fiche officielle porte `extra_gated_eu_disallowed: true` [V] https://huggingface.co/TencentARC/Pixal3D → téléchargement
  officiel fermé à l'UE : zone grise, avis juridique avant tout essai.

### 3. TRELLIS v1 (Microsoft) : le moins cher, accepte plusieurs photos
- Licence [V] : « TRELLIS models and the majority of the code are licensed under the MIT License » ; mais l'export GLB passe par
  nvdiffrast et par un rendu dérivé d'Inria (« free for non-commercial, research and evaluation use »). Étape à réécrire, ou service.
  https://github.com/microsoft/TRELLIS
- Matériel : « at least 16GB », Linux [V] ; installeur Windows communautaire en demi-précision « great for GPUs with 8GB vram »
  [V pour la page, non garanti].
- Coût : 0,02 $ chez fal.ai [V] https://fal.ai/models/fal-ai/trellis
- Sortie : GLB, texture 1024, couleur seule. Plusieurs photos : « tuning-free… may not give the best results » [V].

### 4. SPAR3D / Stable Fast 3D (Stability AI) : les seuls vérifiés sous 8 Go
- Licence [V, relue] (Community License, 5/7/2024) : gratuit en commercial tant qu'on ne dépasse pas 1 000 000 $ de revenu annuel ;
  inscription obligatoire pour un usage commercial ; « You own any outputs ».
  https://github.com/Stability-AI/stable-point-aware-3d/blob/main/LICENSE.md
- Matériel [V] : SF3D « about 6GB VRAM » ; SPAR3D 10,5 Go, « roughly 7GB » en mode économe ; Windows « experimental ».
- Coût : gratuit en local ; service 0,04 $ (SPAR3D), 0,10 $ (SF3D) [V] https://docs.stability.ai/pricing
- Sortie : maillage léger déplié, texture, rugosité et métal globaux.
- Faiblesses : qualité d'il y a deux ans, une image, dos inventé.

### 5. Services payants de référence : Tripo ou Meshy
- Tripo [V] : 0,30 $ le modèle texturé PBR. Plusieurs vues, mais imposées (face obligatoire, puis gauche, dos, droite). Conditions
  du 11/7/2025 (droit de Hong Kong) : « Paid Users generally have all rights […] derive revenue » ; « Company will not use Inputs
  and Outputs as training data » ; interdit de « make the […] Service available to any third party, including end users » sans
  accord écrit. https://developers.tripo3d.ai/en/pricing · https://developers.tripo3d.ai/en/terms
- Meshy [V] : Pro 19 €/mois (1 000 crédits, API comprise) ; 30 crédits le modèle texturé (≈ 0,57 €), 15 en version « lite » ; 1 à 4
  photos libres du même objet. Conditions du 19/9/2026 : « customers on a paid Meshy plan own their Customer Output » ; mais Meshy
  peut utiliser entrées et sorties « to train, validate, test, or improve Services » (retrait par e-mail) ; sorties effacées après
  3 jours ; droit de Californie. https://docs.meshy.ai/en/api/pricing · https://www.meshy.ai/terms-of-use
- Ni l'un ni l'autre ne complète les parties cachées ; aucun hébergement en UE annoncé dans ce qui a été lu.

## 2. Exclus

- **Hunyuan3D 2.0, 2.1, Omni, Part** : inchangé, « THIS LICENSE AGREEMENT DOES NOT APPLY IN THE EUROPEAN UNION, UNITED KINGDOM
  AND SOUTH KOREA » [V]. https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1/blob/main/LICENSE
- **Hunyuan3D 2.5 / 3.x** : aucun dépôt de poids chez Tencent [V] ; service en ligne seulement [NV].
- **InstantMesh** : repose sur Zero123++, poids CC BY-NC [V] https://github.com/SUDO-AI-3D/zero123plus
- **PartPacker (NVIDIA)** : non commercial [V]. **Amodal3R** (complète les parties cachées) : S-Lab License 1.0, non commercial [V].
- **Step1X-3D** : Apache 2.0 mais 27 à 29 Go, et l'étage texture reprend du code Hunyuan3D 2.0 [V].
- **Forme sans texture** (MIT [V], hors besoin) : TripoSG (8 Go), Direct3D-S2, Hi3DGen, CraftsMan3D, PartCrafter.
- **MIDI-3D** (scène entière, Apache 2.0) : environ 30 Go avec texture [V]. **TripoSR** : MIT, 6 Go [V], qualité de 2024 : simple repli.
- **Rodin / Hyper3D** : ≈ 0,29 $ le modèle (offre à 120 $/mois), mais se réserve d'utiliser entrées et sorties pour améliorer ses
  services et la recherche, sans retrait trouvé [V] https://hyper3d.ai/legal/terms
- **CSM** : racheté par Google (27/1/2026), site introuvable. **Luma Genie** : arrêté le 1/1/2026 [NV]. **Kaedim** : pas de prix
  public, délai en heures [V]. **Sloyd** : ≈ 0,27 $ le modèle [V], conditions non lues : non classé.
- Pages non ouvertes par l'agent : prix et confidentialité du site Tripo (403), confidentialité Meshy (403), csm.ai.

## 3. Faisabilité pour notre cas

Faisable, mais pas tel quel. Sauf SAM 3D, ces modèles attendent un objet ISOLÉ, vu EN ENTIER. Il faut donc avant : le masque de
chaque meuble (SAM 2, déjà autorisé) ; un recadrage d'au moins 512 points de petit côté (guide fal [V]), ce qu'un meuble au fond
d'une photo d'annonce n'atteint pas toujours ; et, pour un meuble coupé ou caché, soit un modèle qui complète seul (SAM 3D), soit
une retouche d'image avant la 3D, qui invente. Défauts documentés : la lecture sur une seule photo est jugée « insufficient for
real-world scenes » (Scene-SAM3D [V]) ; ombres et lumière de la photo cuites dans la texture ; taille réelle inconnue (Atelya la
connaît par le plan) ; dos inventé ; petits trous ; maillages lourds. Plusieurs photos du même meuble : Meshy et Rodin les prennent
librement, TRELLIS v1 de façon approximative, Pixal3D avec des caméras connues (Atelya les a), Tripo seulement face / gauche / dos / droite.

## 4. Questions que seul un essai tranchera

1. Qualité réelle sur NOS recadrages (meuble de 200 à 500 points, grand angle, à moitié caché) : SAM 3D contre TRELLIS.2 contre
   un service payant, jugée en rendant le meuble depuis la caméra de la photo (le juge de NT : « le même que sur la photo »).
2. La place et la taille rendues par SAM 3D collent-elles au plan ?
3. Un modèle tient-il vraiment sur la RTX 2070, et en combien de temps ?
4. Deux ou trois photos du même meuble : gain ou dégâts ?
5. Textures dans Unreal : ombres de la photo cuites dedans ; couleurs par sommet suffisantes ? Poids pour 10 à 30 meubles par logement.
6. Juridique : le badge « Commercial use » d'un service couvre-t-il un modèle dont l'export officiel est non commercial ? Que fait le
   service des photos envoyées (RGPD : ce sont les photos d'un client) ? Licences SAM et DINOv3 à relire en entier. Pixal3D et l'UE.

## 5. Avis de la session principale (16/11/2026), à faire valider par NT

- Ordre conseillé inchangé : zéro collision (FAIT) → place et taille justes (étape 2) → peintures et couleurs d'après les photos →
  catalogue par ressemblance (voie A, gratuite) → ESSAI de la voie B sur 5 à 10 meubles.
- Pour l'essai, le plus adapté sur le papier est SAM 3D Objects (il accepte un meuble à moitié caché dans une photo entière), par
  une carte louée ou un service à ~0,02 $ l'objet : l'essai entier coûterait moins d'1 $, mais il demande un compte, une dépense et
  l'envoi de photos hors du PC → **accord écrit de NT, photos dont il a les droits, licence relue en entier avant**.
- Repli gratuit et local à comparer dans le même essai : Stable Fast 3D (≈ 6 Go, tient sur la RTX 2070 d'après sa fiche ; licence
  Stability : gratuite sous 1 M$ de revenu, inscription obligatoire pour un usage commercial) → téléchargement = accord écrit de NT.
- À ne PAS faire sans avis juridique : Pixal3D (fermé à l'UE au téléchargement), tout ce qui dépend de nvdiffrast dans le produit.
