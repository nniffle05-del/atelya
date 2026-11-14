# CLAUDE.md : Atelya (à lire en entier avant toute action)

Ce fichier est lu automatiquement par Claude Code à chaque démarrage, avec TOUTE la mémoire du projet (section 10). Il remplace la mémoire du projet
claude.ai « Modélisation immobilière » quand on travaille directement sur le PC ou le Mac.
**État au 3 novembre 2026.** Le journal complet (chaque étape, chaque chiffre, chaque décision) est
recopié mot pour mot dans `docs/projet/` (voir la fin de ce fichier). En cas de doute, lire le fichier
détaillé correspondant avant d'agir.

---

## 1. Qui, quoi, pourquoi

- **NT** (GitHub `nniffle05-del`) = associé 2. Il construit le moteur 3D **Atelya**. Il n'est **pas
  informaticien**.
- **Associé 1** (GitHub `gabysmon2005`) = plateforme interne, site, dashboard. Il travaille dans **son
  propre projet Claude**, séparé. **Ne jamais toucher à sa partie** (son code, son site, son dépôt), même
  pour « aider ». Si un jour il faut adapter son site : accord de l'associé, puis son dépôt ajouté
  exprès, puis branche relue. C'est l'écran de vérification d'Atelya qui s'adapte au site, pas l'inverse.
- **Atelya** = le LOGICIEL COMPLET (nom décidé par NT le 24/10/2026), une seule offre client. Briques :
  lecteur de plans (le U-Net entraîné, « le coloriage »), traducteur coloriage → `logement.json`, échelle,
  doutes, écran de vérification, 3D + rendu Blender, plan 2D propre ; plus tard brique photos,
  bibliothèques de matières et de meubles.
- **Objectif** : un logiciel AUTONOME, sans LLM dedans, qui lit un plan d'appartement et modélise le
  logement dans Blender. Claude = copilote de développement, jamais un composant du logiciel. Le client
  dépose juste son plan (+ 5-6 photos de pièces, max 10) → lecture AUTOMATIQUE → vérification humaine
  ~2 min → 3D. NT veut une lecture PERFORMANTE AVANT les premiers clients.
  **Changement du 08/11/2026** : au lancement, la LECTURE est faite par Claude via l'API ; l'autonomie complète (sans LLM)
  reste le but à terme (voir § 5 et `docs/projet/memoire/plan-lancement-lecture-claude.md`).
- **But commun (NT, 01/11/2026)** : tout optimiser globalement pour rendre Atelya très performant et
  **vendable**, une vraie solution sur le marché. Juger chaque étape sur les **vrais plans**, pas
  seulement sur les plans fabriqués. Toujours choisir ce qui sert le plus ce but.
- Décisions de fond (22/10/2026) : le **plan coté fait foi**, les photos servent de contrôle et
  d'habillage (pas de photogrammétrie) ; **Blender d'abord**, Unreal plus tard ; format intermédiaire JSON
  avec statut mesuré / estimé / ajouté. NT travaillera **en France** : ne pas biaiser le moteur vers les
  plans suisses.
- **PRODUIT (recadrage NT du 10/11/2026, PRIME sur tout le reste)** : le cœur d'Atelya est le TEMPS RÉEL : une
  CINÉMATIQUE pour le client et une VISITE LIBRE du logement. AUCUNE photo fixe à produire : le client a déjà ses
  photos (elles servent seulement à Atelya pour reconnaître sols, meubles, couleurs). Moteur visé : Unreal Engine 5
  (Lumen, Sequencer) ; Blender = atelier automatique qui construit et exporte. Ne plus investir dans ce qui ne sert
  qu'aux images fixes Cycles. (Avant, 01/11 : « photos fixes d'annonce → Blender Cycles » — ABANDONNÉ.) Visite web
  séparée REPORTÉE « bien plus tard » : ne pas la reproposer.

## 2. Règles de NT (toutes obligatoires)

1. **Français**, simple. NT n'est pas informaticien : expliquer **chaque terme technique** en une phrase
   avec un exemple tiré des appartements, et toujours dire **POURQUOI** on fait une étape avant le comment.
2. **Une étape à la fois**, et **attendre sa validation** avant de passer à la suivante. Distinguer les
   faits (vérifiés) des hypothèses.
3. **AUCUNE installation sans accord écrit de NT** (logiciel, bibliothèque Python, `uv add`, `pip`,
   `winget`, pilote, extension, modèle téléchargé…). Donner la liste exacte, la taille et la licence, puis
   attendre son « oui ». Pas non plus de création de dépôt ou de dossiers importants sans accord.
4. **Copier / lancer du code venu de l'extérieur** sur le Mac exige un accord écrit (« vas-y »). Un clic
   sur une carte ne suffit pas, il faut un message écrit.
5. **Entraînements longs** : surveiller **toutes les 30 min** (lire les journaux : perte, « nan », lots
   sautés, IoU anciens/photos, `code=1`, `Traceback`) et **arrêter/corriger tôt** si ça dérive, au lieu
   d'attendre la fin. (Cause : l'essai 7 a dérivé à la 50e minute et a tourné 2 h pour rien.) Ne pas
   déranger NT si tout va bien. Rappeler à NT la page en direct (`en_direct.py`) avant chaque long calcul.
6. **Plantage** (calcul, mesure, script) : **reprendre la main IMMÉDIATEMENT et corriger, sans attendre
   que NT le demande** (accord permanent pour corriger puis relancer l'étape plantée), dans le respect des
   autres règles (pas d'installation sans accord ; Mac = « vas-y » écrit). Les scripts `.ps1` doivent
   **s'arrêter au premier code ≠ 0** avec une ligne claire « PLANTÉ … ». Ne jamais se fier au silence
   d'une veille : vérifier soi-même.
7. **Méthode d'essai** : d'abord plusieurs **petits essais de 20-30 min** pour comparer les réglages,
   puis UN seul long essai. La durée se fixe en minutes (`--minutes`), pas en pas.
8. **Règle de mise en service d'un modèle** : le modèle en service reste tant qu'un nouveau ne fait pas
   **mieux sans recul** : ≤ 0,5 point de recul sur les bancs anciens et photos, **0 erreur d'échelle
   > 3 %**, pas plus d'erreurs silencieuses graves (A1). Sinon on le garde « en réserve ».
9. **Note honnête /100** à chaque fin d'étape : séparer « prêt client », « plans fabriqués » et « vrais
   plans » ; dire ce qui tire la note vers le bas et ce qui la ferait monter. Ne pas enjoliver.
10. **Fin d'étape** : proposer d'ouvrir une **nouvelle conversation** pour l'étape suivante (voir § 8 pour
    la liste complète de fin d'étape).
11. **Feuille de route** : chaque élément fini (12 cas, A1-A6, P1-P8, R1-R5) doit être marqué « fait » sur
    la Feuille de route, visible par NT.
12. **Carte de l'associé** : la tenir à jour à chaque fin d'étape (même lien). **Ne plus ajouter d'entrée
    à `suivi.json`** (dépôt `suivi-moteur`, règle caduque depuis le 02/11/2026).
13. **Sauvegarde** après chaque étape : le code sur GitHub (`nniffle05-del/atelya`), les modèles `.pt`
    sauvegardés aussi (voir § 6).
14. **Gros calculs = sur le PC** (RTX 2070) : bancs de notation, coloriages, entraînements. Le code léger
    peut s'écrire ailleurs.
15. **Les 13 vrais plans français = EXAMEN UNIQUEMENT. Ne JAMAIS entraîner dessus**, ni s'en servir pour
    régler un seuil à la main. Plus tard, ~50 vrais plans de plus (corrigés brouillon par Claude + validés
    par NT à l'écran de vérification) pourront servir à l'entraînement ; les 13 restent l'examen.
16. **Test sur 10-20 vrais plans** : NT dit « on le fera le moment venu ». Ne pas insister.
17. **Données personnelles** : retirer adresses et noms des plans (RGPD). Aucune donnée privée (e-mail,
    chemins perso) dans ce qui est partagé avec l'associé.
18. **Fil « Lire les plans sans cotes »** arrêté par NT le 24/10 : ne pas le reprendre sans son accord
    (travail gardé dans `moteur-sans-cotes/travail-interrompu.diff` du dossier partagé). Les étapes
    6-10 et 6-11 ont depuis repris l'idée avec son accord.
19. Ameublement : le type de pièce n'impose pas les meubles (maisons atypiques). Le type est une
    proposition, modifiable à l'écran de vérification.
20. Rendu : lumière fidèle à la réalité (moment flatteur oui, soleil inventé non).
21. **Réglages PAR DÉFAUT** (NT, 10/11/2026) : « si à chaque fois tu dois passer par une correction, ce n'est pas correct ».
    Une correction faite à la main une fois (option, réglage, retouche d'un logement) devient le comportement par défaut
    d'Atelya, ou un chantier pour l'automatiser ; le bon résultat doit sortir SEUL de la chaîne, sans option à ajouter.

## 3. Licences (vendre Atelya exige des licences commerciales)

- **INTERDITS** : CubiCasa5k, CVC-FP, RPLAN (recherche seulement ; NT pense que l'entraînement n'est pas
  commercial → on lui a conseillé de demander l'accord des auteurs), **Ultralytics YOLO (AGPL)**,
  **PyMuPDF (AGPL)**, AlbumentationsX (AGPL), 3D-FRONT / Structured3D / ZInD (non commerciaux), poids
  CC BY-NC (Raster2Seq, MASt3R…), Hunyuan3D-2 (exclut l'UE). **Aspiration d'annonces REFUSÉE.**
- **OK** : Swiss Dwellings (CC BY 4.0), DINOv2 (Apache 2.0, code réécrit dans `oeil.py`, seuls les poids
  téléchargés), PyTorch (BSD), OpenCV, RapidOCR + onnxruntime (Apache/MIT), pydantic, Pillow, Kornia
  (Apache), SAM 2 (Apache), pypdfium2 (Apache/BSD) ou pdfplumber (MIT) pour les PDF, ezdxf (MIT),
  IfcOpenShell (LGPL), matières/meubles CC0 (ambientCG, Poly Haven), polices libres (`moteur/polices/`).
- **À faire vérifier** : ResPlan (CC BY 4.0 mais annonces aspirées → avis juridique).
- **Meubles 3D (lus le 08/11/2026, envoyés par NT)** : ABO, Amazon Berkeley Objects = OK (CC BY 4.0, texte de la licence lu,
  aucune clause ajoutée ; ~7 900 meubles réels en glTF avec textures PBR 4K ; 154 Go en tout ; créditer « Amazon.com », ne pas
  utiliser les marques ; préférer la source officielle au réenvoi `codepawl/abo-glb`, qui ne cite pas sa source). Sand3D =
  code Apache 2.0, objets CC BY 4.0 ; le lot `sand3d-objaverse` garde la licence d'origine de chaque objet (`source_license`,
  `attribution`) : filtrer objet par objet et lire la section Licence avant tout téléchargement. Téléchargement = accord NT.
- **OWLv2 (Google, détecteur d'objets « on lui dit quoi chercher »), lu le 10/11/2026** : OK commercial. README officiel
  `scenic/projects/owl_vit` § License : « Both the code and the model checkpoints are licensed under the Apache 2.0 license » ;
  fichier LICENSE de scenic lu en entier = Apache 2.0 standard (+ BSD pour `projects/must3r/utils/colmap_lib`, non utilisé).
  Fiche Hugging Face `google/owlv2-base-patch16-ensemble` : apache-2.0 (« intended use : research » = souhait, pas une clause).
  Entraîné sur COCO/LVIS/Objects365/VG/WebLI : même règle que DINOv2 et SAM 2 (c'est la licence des POIDS qui compte).
  Tailles : base B/16 `model.safetensors` 619,92 Mo ; large L/14 1 750,52 Mo ; + `vocab.json` 1,06 Mo, `merges.txt` 0,52 Mo.
  Route sans installation : code réécrit dans Atelya (comme `oeil.py`), poids lus à la main (safetensors), pas de `transformers`.
  Téléchargement = accord écrit NT.
- **MoGe-2 (Microsoft, profondeur en mètres d'une seule photo), lu le 14/11/2026** : OK commercial. Fichier LICENSE du dépôt lu en entier = MIT
  (+ Apache 2.0 pour la partie DINOv2) ; poids `Ruicheng/moge-2-vitb-normal` MIT, 419 Mo, téléchargés avec l'accord écrit de NT dans
  `..\atelya\modeles-externes\moge-2-vitb-normal`. Réécrit dans `moteur/moge.py`, aucune installation. Sert aux essais « caméras des photos
  calées seules » (pas encore en service).
- **UNREAL ENGINE 5 — CLUF lu EN ENTIER le 10/11/2026** (PDF de la page officielle fourni par NT, 44 p., rangé dans
  `..\atelya\licences\unreal-engine-eula-2026-11-10.pdf` ; sites d'Epic bloqués aux robots). Utilisable commercialement :
  (a) CINÉMATIQUE = « rendered video files » = Non-Engine Product (§4.a.i) : AUCUNE redevance, à quiconque ; (b) VISITE
  interactive vendue et diffusée au public (fichier ou streaming : « make its functionality available on a network » =
  Distribute) = très probablement « Royalty Product » (§4.b) : 5 % du revenu directement généré, mais RIEN sur le 1er million $
  de chaque produit (addendum §4(b)(ii)) ni sur un trimestre < 10 000 $ ; formulaire unrealengine.com/release AVANT diffusion
  payante ; (c) postes (« seats ») pour le reste SAUF exception indie : société + groupe < 1 000 000 $ de revenu brut sur 12 mois,
  levées de fonds COMPRISES (§6.b.i) ; prix des postes absent du CLUF ; (d) INTERDIT de mêler au produit Unreal du code ou contenu
  GPL, LGPL (sauf lien dynamique), CC BY-SA (§6.c) : Blender (GPL) reste un OUTIL à part, ses exports sont à nous ; ABO CC BY 4.0 et
  CC0 OK ; IfcOpenShell (LGPL) seulement en lien dynamique ; (e) mentions obligatoires au générique si le produit en a (§7.a) ;
  (f) pas de location d'Unreal lui-même (§6.e) ; contrat avec Epic Games Commerce GmbH, droit de New York, renonciation aux actions
  de groupe (opt-out possible 30 jours après acceptation). ZONES GRISES à faire confirmer (Epic ou juriste) : chaque visite = un
  produit distinct ? visite payée par l'agence puis montrée gratuitement aux acheteurs = revenu « direct » (§4.a.ii) ?
- **OUTILS DE DÉVELOPPEMENT pour Unreal (accord écrit NT « Oui je suis d'accord », 11/11/2026), jamais dans le produit** :
  Node.js 26.13.0 LTS PORTABLE (MIT ; zip nodejs.org, SHA256 vérifié ; `D:\Atelya-Unreal\outils\node`, 112 Mo, sans droits
  administrateur ni changement de Windows) ; MCP `@runreal/unreal-mcp` 0.1.4 (MIT, fichier LICENSE lu ; 97 modules npm, tous
  MIT / MIT-0 / ISC / BSD, 21 Mo, `D:\Atelya-Unreal\outils\mcp-unreal`), déclaré dans `.mcp.json` du dépôt (non suivi par Git) ;
  il pilote l'éditeur Unreal OUVERT via la « Remote Execution » Python (127.0.0.1 seulement, réglée dans le projet).
- Toute nouvelle bibliothèque ou donnée : **lire sa licence** (le fichier, pas un résumé) avant de la
  proposer à NT. Détail : `docs/projet/memoire/audit-technologique-2026-10-31.md`.

## 4. Machines et chemins

### PC Windows 11 portable (la station de calcul)
- i7-8750H 6 cœurs, 16 Go, **RTX 2070 8 Go** (pilote 555.97, CUDA 12.5). Utilisateur Windows `nniff`.
  GPU à **86 °C en charge** : surélever le PC.
- **Dossier de travail historique : `D:\Modélisation immobilière\atelya`** (pas un dépôt Git, à NE PAS
  écraser) : projet uv avec `.venv` (Python 3.13.17 dans `atelya\.pythons`, torch 2.14.1+cu126,
  torchvision 0.29.1, numpy, pillow, opencv-python-headless 5.0.0.93, rapidocr 3.10.0, onnxruntime 1.31.1,
  pydantic 2.14.1, pytest 9.2.0 (installé le 03/11/2026 avec l'accord de NT), pdfplumber 0.11.10 + pdfminer.six + pypdfium2 5.14.0 + cryptography (A2, accord NT 03/11/2026)), `UV_CACHE_DIR` / `UV_PYTHON_INSTALL_DIR` → `atelya\.cache-uv` /
  `.pythons`. Contient : `donnees\` (9,7 Go de plans fabriqués, régénérables, dont `jeu-10000` et son cache
  `cache-atelya-768px`), `resultats-essai-*\` (modèles et bilans), `code-6-13` … `code-6-19`, `code-a1`,
  `code-a3`, `code-a3b` (copies du moteur posées à chaque étape), `depot-*`, `vrais-plans\`
  (`lot-2026-10-31` = les 13 plans d'examen + coloriages), `modeles-externes\` (poids DINOv2 vits14 et
  vitb14), `banc-*` (bancs et caches), `analyse-a3b\`, `en_direct.py`, scripts `.ps1`.
- Blender 5.2.2 (04/11/2026, archive, sans droits administrateur) : `atelya\blender-5.2.2\blender.exe`, variable utilisateur BLENDER. Rendu : CUDA (OptiX échoue avec le pilote 555.97).
- Dossiers de travail que NT peut supprimer (déjà sauvegardés) : `sauvegarde-pc-2026-11-02`,
  `modeles-a-envoyer`, `modeles-pour-github-2026-11-02`.
- Souvent sur le **partage iPhone** (172.20.10.x) → ne voit pas le Mac. Le PC peut se mettre en **veille**
  et couper un calcul : désactiver la veille avant un long calcul.
- **Le dépôt Git cloné** (depuis le passage à VS Code) : `D:\Modélisation immobilière\atelya-code`, à côté
  de l'ancien dossier. Depuis lui, l'ancien dossier se rejoint par le chemin relatif `..\atelya\` (sans
  accent, donc sans le piège ci-dessous).

### Mac M4 16 Go (Blender)
- Blender 5.2.2 (Python 3.13 intégré, serveur MCP « Blender » local actif), uv, Git (nniffle05-del), Xcode
  CLI. **Pas** d'identifiants GitHub en ligne de commande, ni `gh`, ni Node.js.
- Dépôt `~/Documents/reconstruction-3d/moteur-3d` (branche `main`, Python 3.13 via uv ; pydantic, OpenCV 5,
  RapidOCR + onnxruntime). `main` du Mac = **20ce703** (A3), 314 tests.
- Pour mettre le code du Mac sur GitHub : `git bundle create ~/Desktop/atelya.bundle --all` puis
  pousser le bundle (le Mac ne peut pas pousser lui-même).
- Claude Code sur le Mac : **plus tard**, pour les étapes photos / habillage / Blender.

### Pièges connus (à respecter)
- **Chemins avec accent** (« Modélisation immobilière ») : `cv2.imread`/`cv2.imwrite` ne lisent/n'écrivent RIEN et ne signale rien
  dans un chemin absolu accentué ; un `.ps1` UTF-8 sans BOM sous PowerShell 5.1 lit mal le chemin en dur.
  → **toujours des chemins RELATIFS** (`..\donnees\…`), vérifier que le fichier existe, arrêter sinon.
  Depuis le 03/11/2026 (branche `correctif-chemins-accents`), le moteur et les tests passent par
  `moteur/images.py` (`lire_image` / `ecrire_image`, octets lus par Python puis décodés par OpenCV) : plus
  de piège là. Tout nouveau code doit les utiliser au lieu de `cv2.imread` / `cv2.imwrite`. Les anciens
  scripts du PC (`..\atelya\`, `pc/`) ne sont pas corrigés : chemins relatifs toujours.
- `--processus 6` à l'entraînement → `WinError 1455` (fichier d'échange) : `--processus 1` pour charger un
  nouveau jeu (cache ensuite).
- `OMP_NUM_THREADS=1` pour le générateur multi-processus.
- `torch.hub` (télécharger puis exécuter du code d'internet) est refusé par le filtre de sécurité : code
  réécrit localement, poids seuls téléchargés (`torch.load(weights_only=True)`).
- Remote Control (ancienne méthode) : ne peut ni tuer de processus ni supprimer de fichiers ni changer la
  veille ; le 1er lancement échoue souvent.

## 5. État d'Atelya au 3 novembre 2026 (soir, fin de l'étape A2)

**Notes honnêtes** : **~64/100 « prêt client »** ; ~93/100 sur plans fabriqués ; ~45-48/100 sur vrais plans
(aucun vrai PDF testé : les 13 vrais plans sont des JPG).
Ce qui tire vers le bas : les vrais plans (styles jamais vus, murs gris clair, traits fins, sols hachurés,
murs en biais), les erreurs silencieuses, les plans sans cotes ni surfaces.

**Lecteur en service** :
- **Essai 5** pour les plans à murs droits : PC `resultats-essai-5\atelya-essai-4.pt` (le fichier garde le
  nom de l'essai 4). Sauvegardé dans la release GitHub `modeles-2026-11-02`.
- **Essai 7b** (U-Net essai 5 + œil DINOv2 ViT-S/14 figé, `oeil.py`) pris par **aiguillage** quand sa
  lecture trouve **≥ 1,5 m de murs en biais/arrondis** (`moteur/aiguillage.py`, `SEUIL_LIBRES_M`) :
  PC `resultats-essai-7b\atelya-essai-7.pt` (+ `-dernier`), sauvegardé sur la branche `sauvegarde-modeles`.
- **Traducteur** coloriage → logement : `moteur/coloriage.py` 0.4.1 (murs droits, en biais, arrondis).
- **Échelle** : `moteur/echelle_plan.py` 0.7.0 (cotes, barre d'échelle, surfaces écrites, garde-fous
  « coloriage douteux », accord optique 8 %, cotes fiables, sens unique confirmé, lecture par morceaux).
- **Doutes** : `moteur/doutes.py` (A1 : relecture sous 4 angles, contrôles de bon sens, refus ;
  DOUTE_ELEMENT 0,25, ORPHELINE_MIN 0,35 m²).
- **PDF** (A2) : `moteur/lecture_pdf.py` 0.3.0 (tri vectorielle / scannée / piégée / vide, choix de la page,
  image 300 dpi recadrée sur le dessin, textes exacts à la place de l'OCR, échelle écrite « 1/50 ») ;
  `echelle_plan.py` 0.9.1 (`textes=`, `px_par_pt=` ; « 1/50 » seul → vérification). PDF de test :
  `moteur/generateur/plan_pdf.py`. Banc PC : `pc/a2/banc-a2.ps1` + `pc/a2/analyser_a2.py`.

**Chiffres clés** (murs justes %, bancs PC, aiguillage A3) : plans fabriqués (1 066 niveaux) ~90,7 ;
photos sans cotes ~75,9 ; photos réalistes avec cotes ~78,3 ; réalistes sans cotes ~71,6 ; plans en biais
68,7 → 73,8 ; photos de biais 52,1 → 59,4 ; **0 erreur d'échelle > 3 %** ; erreurs silencieuses graves
306 sur les six bancs. Échelle lue sur ~94 % des plans fabriqués.
**PDF** (banc A2, 2 132 PDF fabriqués depuis les 1 066 niveaux de test) : **0 erreur d'échelle > 3 %** ; vectoriels :
échelle lue 97,1 % (mêmes plans en image 94,7), murs justes 94,1 (90,7), plans parfaits 62,3 (53,3) ; piégés
96,6 % lus, réduits 98,2, tournés 96,4, dossiers 3 pages 98,6, scannés 92,7. Mêmes images, textes PDF contre
OCR : 97,1 contre 96,4 % lus (le gain vient surtout de l'image nette recadrée ; les textes = vitesse, ~0,25 s
contre ~16 s par plan). Images : aucun recul (1 066 niveaux relus, 0 échelle changée).

**Étapes faites** (commits du Mac ; détails dans `docs/projet/memoire/`) :
1-4 format `logement.json`, géométrie → Blender, saisie de plan, lecture auto, habillage + rendus Cycles ;
5a-5d correcteur, banc, fabrique, salissure/nettoyage, plans suisses ; 6 générateur de plans synthétiques
(10 199 plans) ; essais 1 à 7b ; 6-5 traducteur ; 6-6 redressement des photos de biais ; 6-7 petites
pièces ; 6-8 échelle sur les cotes ; 6-9 essai 3 + duo ; 6-10 barre d'échelle ; 6-11 surfaces écrites ;
6-12 barre coupée ; 6-13 échelle fine ; 6-14 photos de biais sans cotes ; 6-15 essai 4 ; 6-16 photos
réalistes + essai 5 ; 6-17 moins de photos en vérification ; 6-18 écran de vérification ; 6-19 styles du
monde (essai 6e NON mis en service) ; **A1** doutes (877967c) ; **A3** DINOv2 + murs en biais (20ce703) ;
**P1** sauvegarde GitHub ; **P3** plan 2D propre (`moteur/plan_propre.py`, PDF A4/A3 ; sur GitHub, **pas
encore posé sur le Mac**, attend le « vas-y » de NT) ; **A2** lecture des PDF (PC ; fusionnée dans `main` sur GitHub le
04/11/2026, fc43891 ; pas encore posée sur le Mac : accord de NT).

**Étape « vérification réelle » (04-05/11/2026, branche `etape-verification-reelle`, FUSIONNÉE dans `main` le 05/11/2026,
75851c5, 406 tests)** : lecture complète (`moteur/lecture_complete.py`, `outils/atelya/lire_plan.py` → `ecran.html` par plan),
écran de vérification refait (un point à la fois, retouche des murs, recalcul des pièces, reprise du travail), Blender 5.2.2
sur le PC (`..\atelya\blender-5.2.2`, rendu CUDA), 1re 3D d'un vrai plan (fr-006), 3D constructible 4/13 → 11/15, échelle lue
sur 4/15 vrais plans (cotes en cm, surfaces en légende, PDF), traducteur 0.4.3. 2 plans de travail avec accords :
`..\atelya\vrais-plans\travail-2026-11-04` (fr-018 photo, fr-019 PDF anonymisé). Détail :
`docs/projet/memoire/atelya-verification-reelle.md`. Note ~68/100 client, ~93 fabriqués, ~53 vrais plans. Pas encore posée sur
le Mac (accord NT). **Correctif « dehors » (05/11, FUSIONNÉ dans `main` en local, 94dd0fb ; NT doit pousser)** : traducteur 0.4.4, une zone coloriée pièce bordée de murs reste dedans
(fr-004 : chambre de 12 m² avalée par l'extérieur à cause d'un ruban de fond à la place d'une cloison) ; bancs sans recul (05/11 12h35). **Première vraie note sur les 15 vrais plans** (vérités
faites par Claude, `outils/verite/`, `verites/`) : à l'échelle vraie murs trouvés 66 %, placés 62 %, ouvertures 40 %, pièces 54 %,
bon type 69 % ; à l'échelle lue par Atelya : murs 33 %, pièces 17 % (échelle lue 4/15, secours par les portes faux de 26-72 %).
Verrou n° 1 = l'échelle ; puis ~58 murs en trop par plan ; puis les ouvertures.
**Chantier « échelle des vrais plans » (05/11 après-midi, NT « fait tout tout seul », FUSIONNÉ dans `main` en local 7e36adc ; NT doit pousser)** : echelle_plan 0.11.0 + lecture_complete 0.2.0 :
échelle de secours du brouillon dans l'ordre surfaces écrites → cotes non confirmées → portes si « fiables » (`portes_fiables` : régulières,
pleines, ≥ 1,8 × épaisseur des murs ; 0/150 fabriqués signalés, 11/11 vrais plans) → épaisseur des murs (20 cm) → 15 m ; contradiction des
cotes aussi sur photo (fr-010 : plus d'échelle « sûre » fausse de 12 %). 15 vrais plans : 0 erreur silencieuse (1 avant), brouillons de −72…−26 %
à ±18 %, à l'échelle lue murs 33 → 40 %, pièces 17 → 33 %. 406 tests. **4 bancs de non-recul SANS AUCUN RECUL** (`banc-echelle2.ps1`, 05/11 17h13 : images et PDF et biais strictement identiques, photos 2 échelles bougées < 0,2 %). Détail :
`docs/projet/memoire/atelya-echelle-vrais-plans.md`.
**Chantier « murs en trop » (05/11 soir, FUSIONNÉ dans `main` en local le 05/11 20h20 ; NT doit pousser)** : traducteur 0.4.5 = plafond d'épaisseur 70 cm
(murs droits et libres ; sols hachurés / dessins à la main coloriés « mur » donnaient des arcs de 1 à 4 m d'épaisseur), arcs écartés
comptés dans l'aiguillage e5/e7b (sinon fr-010 et fr-015 changeaient de modèle). A/B : images 1 034 → 947 murs en trop, biais 844 → 681,
rien d'autre ne bouge ; 15 vrais plans : murs en trop 828 → 634, pièces identiques. 407 tests. **4 bancs de non-recul SANS RECUL** (images en trop
1 079 → 994, PDF 3 154 → 3 113, photos =, biais 921 → 745 et murs justes 75,2 → 75,5 ; 0 échelle changée, 0 nouvelle erreur > 3 %).
Détail : `docs/projet/memoire/atelya-murs-en-trop.md`.
**Décision NT (05/11 soir)** : étape suivante = **lot 2 du générateur** (styles vus sur les vrais plans) ; **aucune aspiration de sites**
(règle réaffirmée). **NT a obtenu 105 VRAIS PLANS** (05/11 soir) → nouvelle conversation : accords + RGPD, ~25 à l'examen (40 juges au total,
jamais touchés) / ~80 à l'entraînement, vérités des 80 (Claude + validation NT à l'écran), catalogue de styles pour le lot 2, puis essai 8
(e5 + DINOv2 + fabriqués + 80 vrais plans), jugé sur les 40 d'examen. Plan détaillé dans `atelya-murs-en-trop.md` (fin).

**Lot 2 du générateur (07/11/2026, branche `etape-vrais-plans-105`)** : générateur 0.1.6, option `--lot2`, module `moteur/generateur/lot2.py`, 20 traits du catalogue, exemples composés `{ident}-ensemble/` (plusieurs niveaux, deux logements). Sans `--lot2` : témoin identique (137 fichiers). Relecture adverse : aucun masque faux. 627 tests. Aucun jeu fabriqué, aucun modèle entraîné : aucune note ne change. Détail : `docs/projet/etapes/lot2-conception.md`. **Lecteur d'échelle 0.13.0 (lecture_cotes 0.3), 08/11/2026, accord de NT (« tout ce que tu peux faire sans Fable »)** : défaut des cotes en cm trouvé par le lot 2 corrigé à sa cause (cotes coupées par d'autres traits, face du mur, halo, dimensions écrites deux fois, marques larges, alerte des cotes presque d'accord). 1 816 plans mesurés : échelles fausses sans alerte 92 → 0 pour 1 plan juste de plus en vérification ; relecture adverse sans nouvelle erreur ; 4 bancs SANS RECUL (biais : 1 ancienne erreur en moins). 657 tests. Jeux du lot 2 fabriqués (`..\atelya\donnees\lot2-a`, `-monde`, `-biais`, `-photos` pour l'entraînement, `lot2-test` jamais appris ; 6 994 exemples). Détail : fin de `atelya-echelle-vrais-plans.md`.

**Plusieurs niveaux sur une image (08/11/2026)** : échelle 0.14.0 (images à plusieurs blocs repérées : 43/48 du lot 2, 8/9 vrais plans d'entraînement, 0 faux repérage sur ~4 000 niveaux ; surfaces lues sur tous les blocs ; lot2-test 1 → 0 échelle fausse, fr-025 → à vérifier) ; doutes 0.2.0 : doute fort `plusieurs_niveaux` en tête de l'écran de vérification, niveaux non lus entourés en orange, décision jamais « lu ». La 3D ne lit toujours qu'UN niveau (chantier à part, à proposer à NT). Banc des styles du lot 2 avec e5 (`banc-lot2-e5`) : murs justes 59,6 %, pièces 75,7 %, parfaits 28,9 % (point de départ de l'essai 8). Essai 8 : option `-Lot2` prête. 668 tests.

**CHANGEMENT DE PLAN (décision NT, 08/11/2026) — lire `docs/projet/memoire/plan-lancement-lecture-claude.md`** :
au LANCEMENT, c'est **Claude, par l'API** (clé API, pas l'abonnement) qui lit les plans ; Atelya fait tout le reste (écran de
vérification, géométrie, Blender, habillage, photos/matières, meubles, soleil, caméra, Unreal, plan 2D). Claude rend sa lecture en
**pixels** (murs, ouvertures, pièces, textes lus avec leur position, ses doutes) ; **notre code calcule l'échelle** avec les
garde-fous d'`echelle_plan` (jamais Claude). Le lecteur entraîné (e5 / e7b, aiguillage, traducteur) reste en **secours et second
avis**. Atelya lira seul à terme. Les chantiers d'entraînement (lot 2, essai 8, 105 vrais plans, ci-dessous) passent **au second
plan : ne pas les reprendre sans l'accord de NT**. Coût / exactitude de Claude : testés dans un autre fil (branche
`origin/claude/project-thread-qtyplp`) ; ne rien dépenser ici, jamais de clé API dans le dépôt ni dans le fil.

**ÉTAPE EN COURS (08/11/2026) : brancher l'écran de vérification sur la lecture de Claude** (branche dédiée
`etape-ecran-lecture-claude`) : format de la lecture en pixels → traducteur vers `logement.json` + `verification.json` → doutes →
essai sans clé API sur les vérités des 15 vrais plans + copies abîmées exprès → puis NT chronomètre la correction, puis 3D. Plan
**validé par NT le 08/11**, avec l'échelle à « deux clés » : Claude donne chaque cote (valeur + bouts du trait en pixels) et sa
propre échelle, notre code recalcule ; accord à 3 % → « sûre », sinon doute fort. `main` = 33e58de (fusion locale, NT doit pousser).
Fait : sous-étape 1 (format, `moteur/lecture_claude.py` 0.1.0) et sous-étape 2 (traducteur, `moteur/traduire_claude.py` 0.1.0,
recalage `moteur/recalage_murs.py`, outil `outils/lecture_claude/traduire_fiche.py` preparer / traduire → ecran.html) et
sous-étape 3 (doutes propres à la lecture de Claude, `moteur/doutes_claude.py` 0.1.0 : textes introuvables, cotes contre le dessin,
surfaces contre les pièces ; traducteur 0.2.0). Suite : sous-étape 4 (essai sans clé API sur les vérités + copies abîmées).
Détail : `plan-lancement-lecture-claude.md`.
**NT 08/11 : API testée À LA FIN ; priorité = Atelya performant partout, en commençant par Blender** (entrée : vérités Fable
fr-021…041 prises comme lecture de Claude, `outils/lecture_claude/fiche_depuis_verite.py`). Étapes Blender proposées : B1 maquette
sans défaut (FAITE le 08/11 : 20/20 vrais plans construits, 15/20 sans aucun trou, plus de fuites ni de carrés noirs ;
`moteur/controle_maquette.py`) → B2 rendu photo d'annonce → B3 soleil réel → B4 meubles (ABO retenu, réalisme d'abord) → B5
caméra / cinématique + comparatif.
**B2 « maquette 3D réaliste », TEMPS 1 FAIT (08-09/11/2026, branche `etape-ecran-lecture-claude`, 726aaac, 741 tests)** : B2-1 plinthes
+ encadrements + appuis ; plinthes, portes de placard et SOL décidés PIÈCE PAR PIÈCE (décision NT : jamais une règle fixe partout ;
champs `plinthes`, `placard`, `sol` (+ `teinte`) de chaque pièce, statut ajoute = supposé / estime = vu sur photo / mesure = choisi à
l'écran ; listes dans la fiche de chaque pièce à l'écran de vérification ; `habillage.completer_finitions`) ; B2-2 portes de placard ;
B2-3 vraies matières CC0 (bibliothèque `..\atelya\bibliotheque\matieres`, 29 matières dont 19 sols au catalogue `moteur/matieres.py`,
photos rangées dans le .blend ; fin des lignes au sol) ; teinte d'un sol d'après une photo du client (`moteur/teinte_photo.py`, mur
blanc = étalon) ; B2-4 lumière du jour (ciel physique, portails, plafonniers éteints, exposition et balance des blancs « de
photographe », 512 passes). Habillage 0.7. Note ~71/100 client. Meubles ABO officiels en téléchargement (`..\atelya\bibliotheque\
meubles-abo`, outil `outils/bibliotheque/telecharger_meubles.py`, REPRENABLE ; depuis le 09/11 il tourne dans SA PROPRE FENÊTRE Windows, indépendante des conversations, lancée par
`outils/bibliotheque/lancer_telechargement_meubles.ps1` (double-clic pour le relancer ; journal `meubles-abo\journal.txt`)).
**ÉTAPE SUIVANTE (accord NT 09/11) : B2 TEMPS 2 = app-001** (`..\atelya\photos-clients\app-001\`, plan sans cotes + 12 photos) :
lire le plan à la main comme une vérité (échelle : 124 m² au total, portes ~80 cm, HSP 3 m ; ne PAS construire palier, escalier,
ascenseur), 3D par Atelya, puis chaque pièce prend le sol (motif + teinte) de SA photo, comparaison côte à côte avec l'annonce.
Détail complet : fin de `docs/projet/memoire/plan-lancement-lecture-claude.md`.
**Temps 2, avancement (09/11)** : étape 1 vérité d'app-001 VALIDÉE par NT (`verites/app-001/` ; RÈGLE NT : ne jamais inventer
limite, porte ou cloison absente du plan, un espace ouvert = UNE pièce) ; étape 2 3D faite (HSP « HSP 3m » lue, `lecture_cotes`) ;
défaut des angles saillants corrigé (traducteur de la lecture de Claude 0.2.1 : bouts de murs coupés sur la face du voisin ; 21 plans :
bouche-trous 48,4 → 20,9 m², trous 11 → 10) ; étape 3 sols : ZONES DE SOL dans une pièce (sans mur ni trait), échelle du motif, carrelages dessinés par Atelya (cubes, petits carreaux), parquets satinés, TEINTE RÉGLÉE AU RENDU automatique (`regler_teintes.py`), CORNICHES pièce par pièce (aucune / simple / moulure, aussi à l'écran) ; vérité des sols d'app-001 faite à la main (`verites/app-001/sols.json`) → la BRIQUE PHOTOS d'Atelya sera notée contre elle. Demandes NT en attente : plusieurs ÉCLAIRAGES dans la maquette Blender (une scène par éclairage, changés DANS Blender), puis brique photos. **Étape 4 FAITE (09/11, NT : « on est sur la bonne voie »)** : caméras au même endroit que les photos (`moteur/camera_photo.py`,
calage sur des arêtes relevées à la main ; relevé `verites/app-001/cameras-photos.json` : 11/12 photos calées, la 09 = montage de
gros plans, non calable) ; rendus depuis ces caméras dans une COPIE de la maquette (`outils/habillage/caler_photos.py`,
`moteur/blender/poser_cameras_photos.py`) ; planches `..\atelya\b2\app-001\etape4\`. Constats : forme des pièces juste ; fenêtres
trop petites, pan coupé du coin repas presque droit en vrai, mur de la porte de la courette plus long, plafond cuisine 2,80 ;
parquet trop foncé / rouge dans ces vues ; lames droites (et non point de Hongrie / carreaux) autour de l'îlot et dans l'entrée ;
lumière trop dure (voilages, ciel doux sur les photos) ; murs de couleur absents. **ÉCLAIRAGES FAITS (09/11)** : une scène Blender par
éclairage (1 Jour ensoleillé, 2 Jour voilé, 3 Fin de journée, 4 Soirée lampes allumées, 5 Nuit ; `moteur/eclairages.py`,
`moteur/blender/poser_eclairages.py`, posées par `construire`) ; app-001 : `..\atelya\b2\app-001\eclairages\`. Suite (ordre NT) :
brique photos (Atelya reconnaît seul les sols sur les photos, notée contre `verites/app-001/sols.json`).

**« PAS DU SOL » + MEUBLES PAR OWLv2 (10/11/2026, EN SERVICE, branche `etape-ecran-lecture-claude`)** : OWLv2 (Google, Apache 2.0,
réécrit dans `moteur/owlv2.py`, poids `..\atelya\modeles-externes\owlv2-base`) repère sur les vraies photos lits, canapés, rangements… ;
`moteur/pas_du_sol.py` les rend « douteux » avant le vote du sol (défaut de `sols_photos.py`, `--sans-pas-du-sol` = ancien) ;
`moteur/reperer_meubles.reperer_depuis_releve` + `outils/habillage/reperer_meubles_photos.py` posent les meubles trouvés (remplace le
repérage DINOv2). Literie des lits (couette, oreillers, plaid) dans le format et dans Blender. Non-recul (examens DÉJÀ VUS) : sols
app-001 81,5 → 83,6 %, app-002 79,2 → 87,9 % ; meubles app-001 16/34 → 25/34, app-002 10/30 → 22/30 (lits 0/2 → 2/2 sur les deux).
Contrôle fabriqué à vrais lits : sols 70,3 → 84,1 %. Premier plan vidéo avant/après (`moteur/blender/video_trajet.py`, `outils/habillage/video_piece.py`, 256 échantillons par défaut) : `..\atelya\b2\app-002\video\avant-apres.mp4`. Note ~73/100 client. Vraie note = un NOUVEAU logement avec photos (NT). Détail : fin de
`plan-lancement-lecture-claude.md`. Chantier suivant proposé : « tout ce qui n'est ni mur ni sol » (sur mesure, sanitaires…),
jugé en vidéo ; NT : la CINÉMATIQUE avant la visite Unreal (`produit-livre-client.md`).

**ATELYA → UNREAL, LE PAQUET (11/11/2026)** : `outils/unreal/exporter_pour_unreal.py <dossier 3d> <sortie> [--verifier]` = forme glTF (`moteur/blender/exporter_gltf.py` : placage UV « monde » calculé, verre lisible, brillances cuites) + fiche de scène `scene-atelya.json` (`moteur/export_unreal.py`) + photos des matières. Vérifié sur app-002 : maquette relue depuis le glTF = originale (séjour 1,86/255). Perdu : motifs dessinés (point de Hongrie, carreaux de ciment). **Unreal Engine 5.8.4 INSTALLÉ le 11/11/2026** dans `D:\Epic Games\UE_5.8` (5.9 = Preview, écartée ; pièges d'installation du lanceur dans la mémoire). **Studio Unreal** `D:\Atelya-Unreal\AtelyaStudio`
(SM6, Lumen ray tracing matériel) ; cinématique en une commande `outils/unreal/cinematique_unreal.py` ; **comparatif mesuré** (même plan,
chambre app-002) : Cycles ~29 s/image, EEVEE 2,0, **Unreal ~0,33**, écart à Cycles EEVEE 26,3 / Unreal 15,1 (/255) → Unreal retenu.
MCP de développement `unreal` (runreal) déclaré, utilisable à la prochaine conversation (éditeur ouvert). Détail : fin de `produit-livre-client.md`.
**FILM DU LOGEMENT (11/11/2026), étape 1 FAITE : exposition automatique dans Unreal** (`moteur/photographe.py` : règle de Blender
mesurée sur de petits essais du film + masque des murs, pente apprise, contrôle du film ; PELLICULE = courbe d'Unreal réglée comme
AgX, fin du sol trop foncé ; préchauffe calculée, fin du mur sombre de l'image 1 ; 5 éclairages dont plafonniers). Contre Cycles
(contrôle seulement) : voilé 12,0/255, soirée 10,6, nuit 7,8, ensoleillé 38,7, fin de journée 48,9. Étapes suivantes (ordre NT) :
2 soleil réel « Jour ensoleillé » (sol noir dehors, fin de journée trop orangée), 3 réalisateur automatique (film 60-90 s Full HD de
tout app-002), 4 motifs dessinés cuits. Une étape à la fois, validation NT.
**LUMIÈRE RÉALISTE (11/11/2026 soir, NT préfère la lumière de Cycles ; « optimisé CINÉMATIQUE »)** : ciel d'Unreal ×3,3 (part du ciel
mesurée contre Blender), clarté visée = celle des images Blender (`photographe.CLARTE_UNREAL`), couleurs de la pellicule réglées sur
un nuancier AgX (`moteur/pellicule_unreal.py`), sol extérieur 20 km. Séjour au soleil, écart à Cycles : path tracer 24,1 → 6,7/255,
Lumen 29,8 → 13,0. Film : LUMEN « intérieur » (`lumen_max`, défaut) = aussi calme que Cycles, ~0,2-0,4 s/image ; path tracer = option
« qualité maximale » (grain, heures). Débruiteur temporel NFOR écarté (sillages). Éditeur + rendu ensemble = plantage GPU : éditeur
fermé pendant les rendus. Soleil encore PROVISOIRE (pas de nord sur app-002) : règle proposée à NT (orientation à l'écran de
vérification, sinon « Jour voilé »), en attente. Détail : fin de `produit-livre-client.md`.
**SOLEIL RÉEL + RÉALISATEUR (11/11/2026)** : `moteur/soleil.py` (NOAA ; app-002 façade sud d'après NT, lieu/date supposés,
`outils/atelya/soleil_reel.py`) ; `moteur/realisateur.py` choisit SEUL pièces, ordre, points de vue et travellings ;
`outils/unreal/film_unreal.py` = film complet en une commande (app-002 : 8 plans de 6 s, Lumen Full HD 0,52 s/image).
**PREMIER FILM D'ATELYA SEUL (12/11/2026, 0 h 50)** : `..\atelya\b2\app-002\unreal\film\film.mp4` (28 s, 5 plans : séjour ×2,
cuisine, chambres ×2 ; 41 min de calcul). Corrigés à la source cette nuit : portes fermées (réalisateur), plafonnier allumé dans une
pièce sans fenêtre, pièces vides et sans fenêtre non filmées (`rien_a_montrer`), exposition bornée, DALLES de l'immeuble au-dessus des
plafonds et sous les sols (`geometrie.dalles_de_l_immeuble`, catégorie « dalle » : plus de fuites de lumière). Apprentissage par les
AVIS de NT : `outils/atelya/noter_film.py` → `moteur/realisateur_appris.json`. À faire : sanitaires et meubles de cuisine (salles d'eau
vides), reconstruire app-002 avec ses dalles, la visite libre plus tard.

**ÉVOLUTION DE LA CINÉMATIQUE (12/11/2026, plan VALIDÉ par NT)** : briques `moteur/cinema/` (réglages, navigation, parcours,
planificateur, trajectoire, regard, caméra, contrôle, montage). FAITES : 0 découpage (film identique), 1 CONTRÔLEUR (`controle.py`,
`outils/atelya/controler_vol.py`, note /100 avant tournage), 2 collisions EN HAUTEUR (meubles accrochés, suspensions), 3
PLANIFICATEUR (défaut de `promeneur.vol` : cœurs des pièces, panoramiques, conclusion, 4 ordres notés). app-002 : 32 → 58/100,
murs 12,6 → 6,8 s, 46 s ; app-001 31 → 72/100. Film `..\atelya\b2\app-002\unreal\film\planifie-v3.mp4`. NT : UNE SEULE PRISE
(fondus refusés), demi-tours vifs. SUIVANT : 4 lumière et fenêtres (nouvelle conversation). Écartés : NavMesh, netteté variable,
spline à la main, meubles inventés par règles (meubles = ceux du client). NT veut qu'on lui dise CHAQUE FOIS qu'une demande semble
contre-productive. Note cinématique ~62/100. Détail : fin de `produit-livre-client.md`.
**ÉTAPE 4 LUMIÈRE, 1er temps (12/11/2026)** : `outils/unreal/mesurer_lumiere.py` (fenêtres, sombre, sauts ; aussi à la fin de chaque
balade) ; masque des murs JUSTE (comptait les meubles devant les murs) + canal « dehors » ; exposition en marchant plus vive (essais
/0,25 s, médiane 1,5 s, 2 crans/s) ; exposition locale ÉCARTÉE (NT : « tu as retiré la lumière ?! ») et visée du jour
ensoleillé 0,90 → 1,0 (éclat du v3). app-002 même vol : murs trop clairs 18 → 2 % du film, sauts durables 6 → 2, chambre plus
grillée. Ciel photographié CC0 posé sur l'image (sans effet sur la lumière ; presque blanc à l'exposition du film). Soirée du 12/11
(NT : « autodidacte, tous tes points ») : relief = déjà plus que Cycles (ombres de contact laissées coupées) ; sorties de pièces
face au mur d'un couloir étroit : 2 essais sans gain net (écartés) ; voilé / fin de journée / soirée / nuit sains ; portes grises =
vraie lumière (path tracer). Film du soir `..\atelya\b2\app-002\unreal\film\film-12-11-soir.mp4` (+ `-avant-apres`). Reste : la
vraie vue (photos du client), sorties de pièces, cuisine et salles d'eau vides. Film
`..\atelya\b2\app-002\unreal\film\lumiere-etape4.mp4`.

**ÉTAPE 5 : LA VRAIE VUE (12-13/11/2026)** : `moteur/vue_dehors.py` + `outils/unreal/vue_dehors_photos.py`, film avec
`balade_unreal.py --photos verites/<logement>/cameras-photos.json` (moments de jour). Une toile par côté de l'immeuble (immeubles d'en
face, 35 m par défaut) + la rue à leurs pieds, peintes d'après les photos calées (meilleure photo par point, murs / meubles / balcons
écartés, prolongée en flou ailleurs), couleurs comme sur la photo (pellicule d'Unreal à l'envers) ; dans Unreal, objet translucide
sans éclairage (murs inchangés, mesuré), vitre claire, ciel photographié coupé avec la vue. BALCONS dans le format (`Balcon`) et
construits dans Unreal (`poser_balcons`) ; app-002 : deux balcons du plan. app-002 : dehors presque blanc 89 → 21 %, couleur ×10.
NT veut la distance la plus juste ; à faire : distance des immeubles mesurée seule, caméras des photos calées seules, balcons dans
Blender et lus sur le plan. app-001 : voilages, pas de vue. Détail : fin de `produit-livre-client.md`.

**ÉTAPE 6 : DISTANCE des immeubles d'en face mesurée seule (13/11/2026)** : `moteur/distance_dehors.py` (les étages d'en face, 3 m,
retrouvés en faisant glisser la vue d'un étage ; mesure retenue seulement si deux endroits séparés d'une même photo s'accordent),
branché par défaut dans `vue_dehors_photos` (côté non mesuré = 35 m). app-002 : ouest 34,2 m mesuré (main ~29), sud NON mesuré
(piège du demi-étage chambre 14, immeubles anciens trop petits) ; app-001 non mesuré (voilages) ; « accord des photos » écarté (les
photos voient des immeubles différents). SUITE (NT « creuse ») : second avis d'une AUTRE photo qui voit le même endroit de la rue → sud mesuré : immeuble proche 24 m, lointains 44 m ; décor qui SUIT LA RUE (une toile par distance, pan en biais entre les deux ; la marche franche faisait une bande blanche). VIDE SOUS LA VUE (les photos ne voient pas le pied des immeubles) : mesuré image par image (`moteur/cinema/vide_dehors.py`) ; le REGARD du film évite par défaut les directions qui le cadrent, sauf quand il montre une pièce (app-002 : 21,5 → 20,4 s, au pire 6,3 → 5,3 %, gain modeste) ; refusés par NT : étages recopiés, caméra loin des fenêtres, relance du client. Détail : fin de `produit-livre-client.md`.

**CAMÉRAS DES PHOTOS CALÉES SEULES (13-14/11/2026, branche `etape-cameras-seules`, NON fusionnée, rien de branché)** : but = retrouver seul d'où
chaque photo du client est prise (aujourd'hui relevé à la main, `verites/<logement>/cameras-photos.json`). `main` = f0a49c8 (poussé).
Voie « traits de la photo contre murs de la 3D » ÉCARTÉE (3/11, instable). DÉCISION NT 14/11 : pas de Claude pour cette tâche (« c'est Atelya
qui doit apprendre »), outils libres permis. MoGe-2 (Microsoft, MIT) réécrit dans `moteur/moge.py` : d'une photo, chaque point en mètres
(0,2 s) ; hauteurs et largeurs justes, profondeurs ~20 % trop longues (zoom cru trop serré ; `relire` impose un zoom). Pose sur le plan
(prototype `pc/essais-cameras-seules/moge2.py`) : 3-4 photos sur 22 bien posées du premier coup, bonne place dans les 8 premières 9/22 ;
verrou = pièces qui se ressemblent. SUITE (accord NT, nouvelle conversation) : 1 reconnaître portes et fenêtres sur la photo, 2 placer toutes
les photos d'un logement ensemble, 3 zoom par GeoCalib (téléchargement = accord NT) si besoin. Brique ~35/100. Détail : fin de `produit-livre-client.md`.
**Point 1 FAIT (14/11 soir), sans gain sur la pose** : fenêtres reconnues sur les photos par le relief (baies, fenêtres nues, portes ouvertes) et par l'aspect (œil DINOv2 + couche apprise, appris sur un logement / noté sur l'autre ; voit aussi derrière les rideaux) ; portes mal reconnues. Pose des 22 photos : toujours 2-3 bien placées (ambiguïté, pièces jumelles à même fenêtre, profondeur de MoGe-2 trop longue de 10-30 %). Prototypes `pc/essais-cameras-seules/moge4…7.py`, sorties `..\atelya\b2\cameras-seules\`. SUITE : point 2 (photos ensemble), puis zoom fiable.
**Point 2 FAIT (14/11 nuit) : photos placées ENSEMBLE** (type de pièce d'après les meubles OWLv2, photos très ressemblantes = même pièce, chaque pièce principale montrée, pas deux photos au même endroit, fenêtres comptées globalement) : bonne pièce 10 → 16 sur 22, à peu près placées (< 1 m, < 15°) 6 → 9, bien placées 3. Restent : la place dans la pièce (zoom → point 3, GeoCalib, accord NT), chambres jumelles échangées sur app-001, cuisines / entrées / salles d'eau. Prototypes `moge8.py`, `moge9.py`. Brique ~42/100.

**Chantier mis en pause (06-08/11/2026, branche `etape-vrais-plans-105`) : les 105 vrais plans** (`docs/projet/etapes/reprise-105-plans.md`).

**Restes d'A2** (non prioritaires) :
pose sur le Mac (+ `pdfplumber`/`pypdfium2` dans `pyproject.toml`, ce qui les installe sur le Mac : accord NT),
option A2-7 (marques des cotes lues dans les traits du PDF : défaut ancien de ~0,5 % quand deux cotes se
touchent de part et d'autre d'une cloison fine), essai sur de VRAIS PDF dès qu'on en aura.

**Pistes ouvertes** : défaut du générateur repéré en A2
(`rendu._Dessin.contour_des_murs` : contour décalé sur les plans « agence » penchés, à corriger avant un futur
entraînement) ; recalibrer `ORPHELINE_MIN` vers 0,15-0,2 m² (hausse des erreurs silencieuses depuis
A1) ; réduire les murs « en trop » du traducteur sur les plans droits ; brancher l'écran de vérification
sur les vraies lectures (préparateur `verification.json`) ; escaliers ; styles US/UK ; photos clients ;
bibliothèques matières/meubles ; comparatif de rendu ; soleil réel.

**Les 12 cas particuliers** (Feuille de route) : 1 sans cotes, 2 meubles/équipements, 3 murs en biais,
4 ouvertures particulières/balcons, 5 placards/gaines, 6 PDF/multi-logements, 7 maisons/duplex, 8 combles,
9 main levée, 10 poteaux, 11 arrondis, 12 mezzanines. Objectif NT : à terme performant sur CHAQUE ligne.

## 6. Où se trouve chaque chose

- **Ce dépôt** `nniffle05-del/atelya` (privé) : code du moteur (`moteur/`), tests (`tests/`, 37 fichiers),
  outils (`outils/atelya/` entraînement et coloriage, `outils/saisie-plan/`, `outils/verification-plan/`),
  `pc/` = sauvegarde des scripts et copies du PC (`pc/a3/` : `oeil.py`, `entrainer_essai7b.py`,
  `en_direct.py`, scripts de mesure), `pc/MODELES.txt` = SHA256 des modèles, `docs/projet/` = journal.
  `README.md` = mode d'emploi des commandes. `lancer_tests.py` = lance les tests sans pytest.
- **Modèles** : release GitHub `modeles-2026-11-02` (essais 2, 3, 4, 5, 6e, 6e-dernier) ; branche
  orpheline `sauvegarde-modeles` (essai 7b, `.pt` coupés en morceaux de 40 Mo, LISEZMOI pour les recoller).
- **Projet claude.ai « Modélisation immobilière »** : il reste en place (mémoire, Feuille de route, carte,
  fils). Son dossier partagé contient les livrables de chaque étape (plans, diffs, bilans).
- **Pages (claude.ai, privées à NT)** :
  - Feuille de route (12 cas, A1-A6, P1-P8, R1-R5) : https://claude.ai/artifact/SHUQoK6FVydYuJN2xk8UP7
  - Carte d'Atelya pour l'associé : https://claude.ai/artifact/SHUy3ye6UPhqojRfCPzS6n
  - Audit techno global : https://claude.ai/artifact/WGSFGjdDD2qfD8SFHTfVzS
  - Ce qu'on peut ajouter à Atelya : https://claude.ai/artifact/MToWqm1wXF2JptDt9s41PX
  - Analyse de 5 dépôts : https://claude.ai/artifact/SLY5nbE3ELTycrkJQmE8vX
  - Catalogue des styles de plans FR/US/UK : https://claude.ai/artifact/XgfA55ptzti5UdRXkiEuS8
  - Guide des plans français : https://claude.ai/artifact/9fWqMwWYaXX9YQc67BGkNy
  - Sources de vrais plans : https://claude.ai/artifact/HBjgQUKk6JBeHdp7KJLmoL
  - Analyse lecture des plans : https://claude.ai/artifact/8h5aQyKBZqMW4pKtYVj1RC
  - Audit initial et architecture : https://claude.ai/artifact/3LffV1yEj28nrqSm2toYqa
  - Récap simple : https://claude.ai/artifact/Aq3wDm7VWikvXyTB6PoW5F
  - Fiche étape 3 : https://claude.ai/artifact/MHfapB2bmSdv2xjD1hP5nj
- **Dépôt `nniffle05-del/suivi-moteur`** : ancien suivi pour l'associé (`suivi.json`). Plus d'ajouts. Les
  PR #3 à #21 y sont ouvertes, chacune posée sur la précédente : NT doit les fusionner dans l'ordre.

## 7. Travailler sur le PC avec Claude Code

- Ouvrir le dossier du dépôt cloné dans VS Code. Le Python du PC (avec PyTorch et la carte graphique) est
  celui de l'ancien dossier : `"D:\Modélisation immobilière\atelya\.venv\Scripts\python.exe"`.
  Ne pas créer un autre environnement sans l'accord de NT (ce serait une installation de ~8 Go).
- Lancer les tests : `<python> -m pytest -q` (367 OK + 6 Blender sautés au 03/11/2026, fin A2). `lancer_tests.py` = ancien secours sans pytest.
  Les tests Blender sont sautés sur le PC.
- Données, modèles et bancs restent dans `D:\Modélisation immobilière\atelya\` ; y accéder par des
  **chemins relatifs** (`..\atelya\donnees\…`, `..\atelya\resultats-essai-5\…`) quand un outil écrit
  des images.
- Page en direct pendant un calcul : `<python> en_direct.py` (depuis `pc/a3/` ou la copie à la racine de
  l'ancien dossier) ouvre `direct\index.html`, rafraîchie toutes les 2 s, bandeau rouge si plantage.
- Git : travailler sur une **branche** par étape, commits clairs en français, pousser sur GitHub ;
  fusionner dans `main` seulement avec l'accord de NT. Ne jamais pousser de données lourdes (`donnees/`,
  `sorties/`, `.venv`).
- Avant de lancer un long calcul : désactiver la veille, prévenir NT de la durée, programmer la
  surveillance toutes les 30 min (règle 5).

## 8. À faire à chaque fin d'étape

1. Tests verts (nombre de tests donné à NT), commit + push sur GitHub (sauvegarde).
2. Si un modèle change : sauvegarde du `.pt` (release ou branche `sauvegarde-modeles`) + SHA256.
3. Note honnête /100 (prêt client / fabriqués / vrais plans).
4. Feuille de route et carte de l'associé : Claude Code local ne peut pas modifier ces pages claude.ai →
   **demander à NT de le faire faire dans le projet claude.ai** (en donnant le texte exact à reporter),
   ou le faire depuis ce projet si on y a accès.
5. Mettre à jour la section 5 de ce fichier (état d'Atelya) et le journal `docs/projet/`.
6. Pour le Mac (tant qu'il n'a pas Claude Code) : préparer un paquet (`.patch`/`.mbox`) que NT télécharge,
   puis l'appliquer après son « vas-y » écrit.
7. Proposer une nouvelle conversation pour l'étape suivante.

## 9. Journal détaillé (`docs/projet/`)

- `docs/projet/memoire/` : la mémoire complète du projet claude.ai au 03/11/2026, recopiée telle quelle
  (`MEMORY.md` = l'index ; un fichier par sujet : règles, machines, chaque étape, licences, produit…).
- `docs/projet/etapes/` : les plans d'étape (`*-plan.md`), le détail de l'étape A3
  (`memoire-a3-detail-2026-11-02.md`), les résultats 6-15, le rapport qualité du générateur, les
  README des étapes 1 à 5c, la fiche de pose et le prompt pour le site de l'associé.
- Ces fichiers datent du 03/11/2026 : les chemins `/mnt/project-files/…` y désignent le dossier partagé du
  projet claude.ai, et `RC` = session Remote Control (ancienne méthode). Les chiffres et règles y sont
  à jour ; l'état d'Atelya fait foi en section 5 ci-dessus.

## 10. Mémoire à la demande (allégée le 06/11/2026, décision de NT)

**Pourquoi** : charger toute la mémoire coûtait ~157 000 tokens à chaque agent et à chaque démarrage, soit ~70 % de ce qu'il relit à chaque tour, pour un travail qui n'en utilise presque rien. NT a dit « oui » le 06/11/2026 : ce budget sert mieux à la qualité (réflexion maximale, double tracé). **Rien n'est supprimé.** À la fin du chantier des 105 vrais plans, **proposer à NT de remettre la mémoire complète** : le texte d'origine est dans `docs/projet/memoire/SECTION-10-COMPLETE.txt`.

**Règle** : avant de toucher un sujet ci-dessous, LIRE son fichier dans `docs/projet/memoire/` : ne pas deviner, ne pas reposer à NT une question dont la réponse y est. `MEMORY.md` est l'index général. Les chiffres et règles de ce CLAUDE.md suffisent pour le reste.

| Sujet | Fichier(s) |
|---|---|
| Vrais plans, accords, lots, coupe, vérités, coût des agents | `vrais-plans-francais.md` |
| Écran de vérification, lecture complète, 3D d'un vrai plan, vérités (outils) | `atelya-verification-reelle.md`, `ecran-verification.md` |
| Échelle | `atelya-echelle-vrais-plans.md`, `atelya-echelle-cotes.md`, `atelya-echelle-fine.md`, `atelya-barre-echelle.md`, `atelya-barre-coupee.md`, `atelya-surfaces.md` |
| Traducteur, murs en trop, petites pièces | `atelya-murs-en-trop.md`, `atelya-petites-pieces.md`, `atelya-modele.md` |
| Entraînements et modèles | `atelya-modele.md`, `atelya-essai-3.md`, `atelya-essai-4.md`, `atelya-photos-realistes.md`, `atelya-styles-monde.md`, `atelya-dinov2-biais-a3.md`, `../etapes/memoire-a3-detail-2026-11-02.md` |
| Surveillance des calculs, PC | `surveiller-entrainements.md`, `gros-calculs-sur-pc.md`, `calculs-sur-pc.md`, `environnement-poste-nt.md`, `passage-vscode.md` |
| Générateur | `generateur-dataset.md`, `atelya-styles-monde.md`, `../etapes/catalogue-styles-lot2.md` |
| Photos de biais, redressement | `atelya-redressement.md`, `atelya-biais-sans-cotes.md`, `atelya-verification.md` |
| Doutes, PDF, plan 2D | `atelya-doutes-a1.md`, `atelya-pdf-a2.md`, `plan-2d-propre-p7.md` |
| Licences, technologies | `audit-technologique-2026-10-31.md` |
| **Lecture des plans par Claude au lancement (décision 08/11/2026)**, écran branché sur la lecture de Claude | `plan-lancement-lecture-claude.md` (+ `lecture-par-api-claude.md` sur la branche `origin/claude/project-thread-qtyplp` : coûts, conditions) |
| Produit, objectifs, décisions | `objectif-global-nt.md`, `produit-livre-client.md`, `projet-reconstruction-3d-decisions.md`, `sujets-produit-non-traites.md` |
| Sauvegarde, feuille de route, carte, associé | `sauvegarde-atelya.md`, `feuille-de-route-a-jour.md`, `carte-atelya-associe.md`, `suivi-moteur-associe.md` |
| Façon de parler à NT, note /100 | `preference-explications-simples.md`, `preference-note-realiste.md` |

Règle inchangée : tout ce que tu apprends d'important (décision de NT, règle, chiffre, piège, état d'une étape) s'écrit dans le fichier de `docs/projet/memoire/` qui couvre le sujet (ou un nouveau, ajouté à ce tableau et à `MEMORY.md`), dans le même tour, puis se pousse sur GitHub avec le reste.
