---
name: audit-technologique-2026-10-31
description: Audit techno global du 2026-10-31 (fil « Auditer les technologies du marché face à Atelya ») : conclusions, licences vérifiées, feuille de route proposée
metadata:
  type: project
  modified: 2026-10-31T11:17:46.645Z
---

Rapport (Claude Doc) : https://claude.ai/artifact/WGSFGjdDD2qfD8SFHTfVzS — demandé par NT (cahier des charges « MISSION DE RECHERCHE ET D'AUDIT TECHNOLOGIQUE GLOBAL »), analyse seulement, attendre son accord avant toute modification.

Conclusions : garder toute la chaîne Atelya ; aucun poids pré-entraîné sur plans n'est commercial (tous CubiCasa/Structured3D/3D-FRONT/RPLAN). Proposé : essai 6 = encodeur DINOv2 (Apache 2.0) dans Atelya ; murs biais/arrondis ; écran de vérif 2 min ; banc vrais plans FR le moment venu ; IFC/DXF (IfcOpenShell LGPL, ezdxf MIT) ; meubles par règles + CC0 ; visite glTF+three.js ; vectoriseur appris type Raster2Seq seulement si besoin. Note inchangée ~55/100 client.

Licences vérifiées (fichiers lus) : Raster2Seq code MIT / poids CC BY-NC ; HouseCrafter MIT mais 3D-FRONT « shall not commercialize », 24 Go VRAM ; PlanTo3D et 3d-Floorplans sans licence (+ YOLO AGPL) ; VGGT : seul VGGT-1B-Commercial commercial ; MASt3R CC BY-NC-SA ; Depth Anything 3 code Apache, certains poids NC ; gsplat Apache vs 3DGS Inria NC ; TRELLIS.2 MIT (24 Go) ; Hunyuan3D-2 exclut l'UE ; ZInD academic only ; ResPlan CC BY 4.0 mais annonces aspirées (avis juridique) ; MSD CC BY 4.0.
REA : l'URL donnée (realkeisers/rea) est inaccessible, le vrai = morluto/rea (MIT). Déconseillé.
Concurrent le plus proche : Extruda (lecture auto + revue, DXF/IFC/GLB/.blend, aucune précision publiée).

**Why:** base de décision pour la suite du moteur.
**How to apply:** ne pas refaire la recherche ; partir de ce rapport. Voir [[atelya-modele]], [[atelya-verification]].

2026-10-31 11h35Z : 2e demande NT = analyse de 5 dépôts (3d-Floorplans listé 2 fois = même dépôt). Doc : https://claude.ai/artifact/SLY5nbE3ELTycrkJQmE8vX. Classement : OpenPlan3D (MIT, éditeur 2D/3D, murs courbes, DXF, pas d'export GLB, pas de lecture auto ; rendus IA via OpenAI/Gemini à retirer) > Blender MCP (fork d'ahujasid, 287 outils, outil de dev seulement) > Floor Plan Document Intelligence (murs IoU 0,53, poids SegFormer NVIDIA NC + CubiCasa ; PyMuPDF AGPL) > CubiCasa5K (NC, 2019) > Construct-AI (pas de licence, YOLO AGPL, maisons+toits). Aucun poids/données récupérable.

2026-10-31 ~12h30Z : 3e demande NT (« tout ce qui peut améliorer Atelya, licences commerciales ; si rien, dis-le »). Doc : https://claude.ai/artifact/MToWqm1wXF2JptDt9s41PX. Verdict : rien de magique, des briques libres utiles. Ordre proposé (accord NT à chaque étape) : 1) confiance calibrée + relecture multi-angles + contrôles de bon sens (sans entraînement) ; 2) lecture PDF vectoriels (pypdfium2 Apache/BSD ou pdfplumber MIT ; PAS PyMuPDF AGPL) ; 3) UN réentraînement regroupé : DINOv2 (Apache code+poids) + murs biais/arrondis + générateur enrichi ; 4) écran vérif + boucle corrections (CGU clients) + SAM 2 (Apache, poids compris) ; 5) IFC/DXF, OIDN, CC0 ; 6) docTR, ONNX, photos. Licences lues ce jour : DINOv3 licence Meta maison, commercial OK ; Albumentations MIT gelé / AlbumentationsX AGPL ; Kornia Apache ; Infinigen BSD-3 ; ProcTHOR Apache ; MoGe code MIT (poids non précisés) ; RapidOCR = modèles PaddleOCR. Note inchangée ~55/100 (viser ~70 si étapes 1-4 tiennent, à confirmer par banc vrais plans).
2026-10-31 12h05Z : à la demande de NT, étapes A1-A6 ajoutées dans la Feuille de route des cas particuliers (https://claude.ai/artifact/SHUQoK6FVydYuJN2xk8UP7, section « Améliorations d'Atelya à faire »). A1 (doutes/confiance, sans entraînement) = prochaine proposée après 6-17, attente « go » NT. NT fait déjà tourner l'écran de vérification (fil dédié).

2026-11-04 : 4e demande NT = « worldgen » (GitHub). Dépôt retenu : ZiYang-xie/WorldGen (~2 200 étoiles, code Apache 2.0) : texte ou photo → panorama 360° (FLUX.1-dev) → profondeur (DA-2) → nuage de « gaussiennes » (Gaussian splatting) ou maillage approximatif ; ~10 Go de mémoire graphique en mode économe. Verdict : NE SERT PAS Atelya. Scène INVENTÉE (pas de mesures, pas de murs/portes exploitables, pas un logement réel) ; dépend de FLUX.1-dev (licence non commerciale : modèle interdit en produit payant sans licence BFL ; sorties utilisables) et option ml-sharp (Apple, recherche seulement). Meta « WorldGen » (arXiv 2511.16825, CVPR 2026) = recherche, pas de code commercial. Seule idée gardée : plus tard, fond de fenêtre / extérieur stylisé ou vue 360° d'ambiance, à condition de remplacer FLUX par un modèle commercial.
