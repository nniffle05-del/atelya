# CLAUDE.md : Atelya (à lire en entier avant toute action)

Ce fichier est lu automatiquement par Claude Code à chaque démarrage. Il remplace la mémoire du projet
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
- **But commun (NT, 01/11/2026)** : tout optimiser globalement pour rendre Atelya très performant et
  **vendable**, une vraie solution sur le marché. Juger chaque étape sur les **vrais plans**, pas
  seulement sur les plans fabriqués. Toujours choisir ce qui sert le plus ce but.
- Décisions de fond (22/10/2026) : le **plan coté fait foi**, les photos servent de contrôle et
  d'habillage (pas de photogrammétrie) ; **Blender d'abord**, Unreal plus tard ; format intermédiaire JSON
  avec statut mesuré / estimé / ajouté. NT travaillera **en France** : ne pas biaiser le moteur vers les
  plans suisses.
- Produit livré (01/11/2026) : cinématique + visite libre → Unreal (une seule scène, plus tard) ; photos
  fixes d'annonce → Blender Cycles ; démos EEVEE en attendant. Visite web séparée REPORTÉE « bien plus
  tard » : ne pas la reproposer. Comparatif Cycles / EEVEE / Unreal prévu avant de choisir.

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
- Toute nouvelle bibliothèque ou donnée : **lire sa licence** (le fichier, pas un résumé) avant de la
  proposer à NT. Détail : `docs/projet/memoire/audit-technologique-2026-10-31.md`.

## 4. Machines et chemins

### PC Windows 11 portable (la station de calcul)
- i7-8750H 6 cœurs, 16 Go, **RTX 2070 8 Go** (pilote 555.97, CUDA 12.5). Utilisateur Windows `nniff`.
  GPU à **86 °C en charge** : surélever le PC.
- **Dossier de travail historique : `D:\Modélisation immobilière\atelya`** (pas un dépôt Git, à NE PAS
  écraser) : projet uv avec `.venv` (Python 3.13.17 dans `atelya\.pythons`, torch 2.14.1+cu126,
  torchvision 0.29.1, numpy, pillow, opencv-python-headless 5.0.0.93, rapidocr 3.10.0, onnxruntime 1.31.1,
  pydantic 2.14.1 ; **pas de pytest**), `UV_CACHE_DIR` / `UV_PYTHON_INSTALL_DIR` → `atelya\.cache-uv` /
  `.pythons`. Contient : `donnees\` (9,7 Go de plans fabriqués, régénérables, dont `jeu-10000` et son cache
  `cache-atelya-768px`), `resultats-essai-*\` (modèles et bilans), `code-6-13` … `code-6-19`, `code-a1`,
  `code-a3`, `code-a3b` (copies du moteur posées à chaque étape), `depot-*`, `vrais-plans\`
  (`lot-2026-10-31` = les 13 plans d'examen + coloriages), `modeles-externes\` (poids DINOv2 vits14 et
  vitb14), `banc-*` (bancs et caches), `analyse-a3b\`, `en_direct.py`, scripts `.ps1`.
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
- **Chemins avec accent** (« Modélisation immobilière ») : `cv2.imwrite` n'écrit RIEN et ne signale rien
  dans un chemin absolu accentué ; un `.ps1` UTF-8 sans BOM sous PowerShell 5.1 lit mal le chemin en dur.
  → **toujours des chemins RELATIFS** (`..\donnees\…`), vérifier que le fichier existe, arrêter sinon.
- `--processus 6` à l'entraînement → `WinError 1455` (fichier d'échange) : `--processus 1` pour charger un
  nouveau jeu (cache ensuite).
- `OMP_NUM_THREADS=1` pour le générateur multi-processus.
- `torch.hub` (télécharger puis exécuter du code d'internet) est refusé par le filtre de sécurité : code
  réécrit localement, poids seuls téléchargés (`torch.load(weights_only=True)`).
- Remote Control (ancienne méthode) : ne peut ni tuer de processus ni supprimer de fichiers ni changer la
  veille ; le 1er lancement échoue souvent.

## 5. État d'Atelya au 3 novembre 2026

**Notes honnêtes** : **~62/100 « prêt client »** ; ~92/100 sur plans fabriqués ; ~45-48/100 sur vrais plans.
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

**Chiffres clés** (murs justes %, bancs PC, aiguillage A3) : plans fabriqués (1 066 niveaux) ~90,7 ;
photos sans cotes ~75,9 ; photos réalistes avec cotes ~78,3 ; réalistes sans cotes ~71,6 ; plans en biais
68,7 → 73,8 ; photos de biais 52,1 → 59,4 ; **0 erreur d'échelle > 3 %** ; erreurs silencieuses graves
306 sur les six bancs. Échelle lue sur ~94 % des plans fabriqués.

**Étapes faites** (commits du Mac ; détails dans `docs/projet/memoire/`) :
1-4 format `logement.json`, géométrie → Blender, saisie de plan, lecture auto, habillage + rendus Cycles ;
5a-5d correcteur, banc, fabrique, salissure/nettoyage, plans suisses ; 6 générateur de plans synthétiques
(10 199 plans) ; essais 1 à 7b ; 6-5 traducteur ; 6-6 redressement des photos de biais ; 6-7 petites
pièces ; 6-8 échelle sur les cotes ; 6-9 essai 3 + duo ; 6-10 barre d'échelle ; 6-11 surfaces écrites ;
6-12 barre coupée ; 6-13 échelle fine ; 6-14 photos de biais sans cotes ; 6-15 essai 4 ; 6-16 photos
réalistes + essai 5 ; 6-17 moins de photos en vérification ; 6-18 écran de vérification ; 6-19 styles du
monde (essai 6e NON mis en service) ; **A1** doutes (877967c) ; **A3** DINOv2 + murs en biais (20ce703) ;
**P1** sauvegarde GitHub ; **P3** plan 2D propre (`moteur/plan_propre.py`, PDF A4/A3 ; sur GitHub, **pas
encore posé sur le Mac**, attend le « vas-y » de NT).

**Prochaine étape : A2, lecture des PDF** (pilote du travail avec Claude Code sur le PC). Les plans en PDF
vectoriel contiennent déjà les traits et les textes exacts : les lire directement (pypdfium2 ou
pdfplumber, **pas PyMuPDF** qui est AGPL) au lieu de les photographier. Installation = accord de NT.

**Pistes ouvertes** : recalibrer `ORPHELINE_MIN` vers 0,15-0,2 m² (hausse des erreurs silencieuses depuis
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
- Lancer les tests : `<python> lancer_tests.py` (le PC n'a pas pytest ; installer pytest = accord NT).
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
