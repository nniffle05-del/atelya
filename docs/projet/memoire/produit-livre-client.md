---
name: produit-livre-client
description: Produit fini livré au client = 2 parties (cinématique caméra + visite libre) ; quel outil pour chacune (conseil du 2026-11-01)
metadata:
  type: project
---
NT (2026-11-01 23h30Z) : le produit envoyé au client se scinde en deux : 1) une CINÉMATIQUE (caméra qui parcourt les pièces, très beau rendu) ; 2) une partie où le client SE DÉPLACE lui-même.
Conseil RÉVISÉ (même soir : Cycles ~1-3 min/image sur 2070 → 30-90 h par minute de vidéo) : visite libre ET cinématique → Unreal (une seule scène, caméra sur trajet calculé depuis le plan, vidéo en minutes-1 h, Movie Render Queue) ; photos fixes d'annonce → Blender Cycles ; fabrication maquette → Atelya + Blender puis export auto vers Unreal. En attendant Unreal : démos vidéo avec EEVEE (Blender).
Unreal : pas plus beau en image fixe ; plus-value = direct (heure, matières), interactions, VR, vidéos rapides.
**Why:** cadre la sortie finale d'Atelya.
**How to apply:** ne pas reproposer la visite web séparément (NT l'a reportée) ; voir [[objectif-global-nt]].
2026-11-01 23h33Z NT : « on fera un COMPARATIF de tout pour vraiment savoir » → test Cycles / EEVEE / Unreal sur un même logement avant de choisir. Estimation donnée : RTX 5090 ~6-7× la 2070 → 1 min de vidéo Cycles ~5-15 h (3-8 h avec débruiteur) ; 5090 ~2 500-3 000 € ; location GPU ~1 €/h pour tester avant d'acheter.
Protocole de comparatif prévu (à intégrer au plan global, quand la lecture des plans sera stabilisée ou plus tôt si NT veut ; faisable sur le PC) : même logement sorti d'Atelya, même trajet caméra 10 s (300 images, séjour, fenêtre au soleil + zone sombre) ; 4 rendus Cycles max / Cycles optimisé+débruiteur / EEVEE / Unreal ; mesurer temps par image, mémoire, qualité côte à côte ; extrapoler à 1 min et à une carte haut de gamme.
Mouvements caméra (proposé 2026-11-01 23h35Z, pas encore validé ni codé ; aujourd'hui seulement 2 images fixes auto) : ordre de visite d'agent depuis le graphe pièces/portes ; plans courts par pièce avec coupures/fondus (caméra 1,60 m, coin opposé à la fenêtre, avancée/panoramique 6-10 s, carte des espaces libres) ; durée selon taille (T2 ~1 min, T4 ~2 min) ; même trajet pour Blender/Unreal/comparatif ; plus tard trajet continu « drone » + options client (heure, meublé/vide).
Compléments : points de vue notés auto (surface vue, lumière, verticales droites), ouverture « maison de poupée », fichier trajet commun = aussi points de téléportation de la visite libre, options titres/logo/musique ; brique « réalisateur automatique » (règles, pas d'entraînement) placée juste après le comparatif dans le plan global.
Soleil réel (proposé 2026-11-01 23h37Z) : adresse/ville au dépôt (latitude) + orientation (flèche nord lue par Atelya ; sinon boussole dans le formulaire de dépôt ; plus tard cadastre public) → position du soleil par formule astronomique (hors ligne), soleil Blender/Unreal. V1 sans ombres des immeubles voisins ni étage ; plus tard hauteurs IGN (BD TOPO). À décider avec NT : lumière réelle à heure choisie vs heure la plus flatteuse par pièce.
État code : habillage.py pose un soleil FIXE (ouest-sud-ouest, 50° de haut), provisoire. Vrais plans : fr-003 et fr-017 ont une rose des vents, fr-012 « SUD-OUEST », fr-014 « 3ème étage ». Conseil donné : lumière fidèle à la réalité (moment flatteur oui, soleil inventé non).
2026-11-01 23h45Z : à la demande de NT, section « Rendu et produit livré au client » ajoutée à la Feuille de route (étapes R1 comparatif, R2 réalisateur caméra, R3 soleil réel, R4 visite Unreal ; colonne État).
R5 vue par les fenêtres : PAR DÉFAUT tout auto IGN (adresse+étage+orientation → volumes BD TOPO + ciel + monuments modélisés, rendu « maquette » + flou) ; option : vue remarquable détectée → proposer au client une photo de la vue. Pas de Google 3D/Street View. V2 : vraies façades par photos de rue libres (Panoramax, Mapillary CC BY-SA) projetées sur volumes IGN.
**RECADRAGE NT (10/11/2026)** : « tu perds l'objectif de vue » → le produit, c'est le LOGEMENT ENTIER EN 3D, visité en cinématique
(caméra qui se déplace proprement, bonnes lumières) puis visite libre sur Unreal ; les photos d'annonce ne sont qu'un sous-produit.
Conséquences : (1) ne jamais juger une brique sur une seule image fixe : juger en mouvement, sous tous les angles, de près, sous
chaque éclairage ; (2) les photos du client servent à MESURER (dimensions, découpage, couleur, type de matière), jamais de texture
projetée (ombres et reflets figés, faces cachées fausses, étirement) ; (3) vraie géométrie + vraies matières PBR partout, objets
assez légers pour le temps réel (ABO = textures 4K → versions allégées pour Unreal) ; (4) sur mesure : mesuré sur photos calées,
construit module par module, habillé de vraies matières, jugé en vidéo tournante côte à côte avec les photos.
**ORDRE NT (10/11/2026)** : « avant de se projeter sur la visite, il faut d'abord penser CINÉMATIQUE ». Priorité = le film du
logement rendu par Blender (caméra qui parcourt proprement, bonnes lumières) ; visite libre Unreal PLUS TARD. Critère de jugement
d'une brique = un court plan vidéo en mouvement (pas de scintillement d'une image à l'autre, géométrie juste sur tout le trajet,
sols et meubles crédibles au passage, lumière cohérente entre pièces). L'allègement des objets pour le temps réel (textures 4K
d'ABO) n'est PAS prioritaire tant qu'on fait la cinématique.
**NT (10/11/2026)** : trouver le meilleur milieu entre beau rendu 4K et visite fluide, toujours réaliste, et TOUT fait par Atelya
(aucune retouche à la main). Piste proposée (non essayée) : une maquette de référence pleine qualité (film 4K Cycles) ; Atelya en
dérive SEUL une version allégée (textures réduites selon la taille de l'objet à l'écran, objets simplifiés au loin, lumière
précalculée « cuite ») ; réglages choisis sur mesures (temps, fluidité, réalisme) au comparatif R1 Cycles/EEVEE/Unreal.
**RECADRAGE NT n° 2 (10/11/2026, soir) : PAS DE PHOTOS FIXES.** « Le cœur de mon projet c'est le temps réel : une cinématique pour le
client et la possibilité de visiter le logement ; à aucun moment il a besoin de photo fixe, ils ont déjà des photos. » → Les photos du
client = SOURCE pour Atelya (sols, meubles, couleurs), jamais un livrable. Moteur visé : UNREAL ENGINE 5 (temps réel, Lumen, Sequencer
pour la cinématique, visite libre) ; Blender = atelier automatique (construire, exporter glTF/FBX/USD). Arrêter d'investir dans le
rendu fixe Cycles (512 échantillons, réglage « photographe », heures de rendu). Le réalisateur automatique se pense pour Unreal.
Proposé à NT : (1) lire la LICENCE d'Unreal (texte officiel Epic) + taille d'installation + capacités du PC, accord écrit avant toute
installation ; (2) passage automatique Atelya → Unreal ; (3) essai app-002 (cinématique + visite) contre la vidéo Blender.
ERREUR À NE PLUS FAIRE : ramener la discussion aux photos d'annonce (deux recadrages le même jour).
**CINÉMATIQUE : Blender ou Unreal ? (10/11/2026, NT « réfléchis concrètement »).** MESURÉ sur le PC (RTX 2070), chambre d'app-002,
1280 × 720 : Cycles 256 échantillons ~27 s/image (le plus réaliste, marbrures légères) ; EEVEE (Blender 5.2, réglages de base,
raytracing activé) 1,7 s/image après 30 s de préparation, rendu « maquette » (murs brûlés, pas d'ombres douces, lumière plate,
vitre granuleuse) — image `scratchpad eevee-48.png`. Projection film 90 s Full HD (2 700 images) : Cycles ~45 h (invendable), EEVEE
2-3 h (réalisme insuffisant), Unreal 5 Lumen + Movie Render Queue 1-4 h (HYPOTHÈSE, non mesuré). RECOMMANDATION donnée à NT :
UNREAL 5 pour la cinématique (réalisme proche de Cycles à des temps vendables, MÊME scène pour film et visite libre, Sequencer
pour le réalisateur automatique, vidéo sans redevance) ; Blender = atelier qui construit et exporte. À confirmer par le comparatif
mesuré (même plan 10 s : Cycles / EEVEE / Unreal) après installation d'Unreal (accord écrit NT, compte Epic de NT).

**ATELYA → UNREAL : LE PAQUET (11/11/2026, NT « oui » pour l'export ; Unreal pas encore installé).** NT a résumé, confirmé :
Blender = ATELIER (murs, sols, plafonds, menuiseries, sur-mesure, linge, meubles ABO posés) ; Unreal = STUDIO (lumière, ombres,
matières natives, caméra, cinématique, puis visite). Une commande : `python outils/unreal/exporter_pour_unreal.py <dossier 3d>
<sortie> [--verifier]` → `maquette.gltf` (+ .bin, textures/), `scene-atelya.json` (fiche de scène, `moteur/export_unreal.py`
schéma scene-unreal/0.1 : matières avec photos, taille réelle, teinte RÉGLÉE au rendu, rotation, brillance ; lumières (soleil,
plafonniers W, fenêtres) ; 5 éclairages + équivalent Unreal ; meubles (nœud glTF `Meuble_<id>`) ; vues ; crédits ABO
« Amazon.com » CC BY 4.0 + matières CC0 ; liste « pertes »), `matieres/` (photos CC0 utilisées). app-002 : 45 s, 192 Mo.
Défauts trouvés et CORRIGÉS à l'export (`moteur/blender/exporter_gltf.py`) : (1) photos des sols/murs plaquées « par position »
→ parties SANS repères (texCoord -1) : carte UV `atelya_monde` calculée comme Blender au rendu ; (2) verre « transparent +
reflet » → parti VIDE donc opaque, pièces NOIRES : verre alpha 0,06 (le verre « transmission » essayé bloquait le soleil au rendu,
plus de taches de soleil) ; (3) brillance « satinée » (calcul) perdue → parquet miroir : images de brillance CUITES déjà réglées.
VÉRIFICATION « toutes choses égales » (`moteur/blender/verifier_gltf.py` + `outils/unreal/comparer_export.py` : même lumière,
mêmes caméras, maquette remplacée par le glTF relu) : séjour écart moyen 1,86/255 (0,31 % de pixels nettement changés, surtout
la vue dehors par la fenêtre), dessus 0,33/255 (0,02 %). Avant corrections : séjour 167/255 (noir). Planches
`..\atelya\b2\app-002\unreal\verification\`. PERDU encore : motifs DESSINÉS (point de Hongrie, carreaux de ciment) → partent en
photo de base (à cuire en image répétable, chantier à part) ; lampes/ciel/caméras/exposition (refaits dans Unreal, par choix).
Repère Unreal (cm, axes) à vérifier au premier import. Suite : installation UE 5.9 par NT (chez lui), import + comparatif mesuré.
Installation (11/11/2026) : dans le lanceur Epic, UE 5.9 est marqué « Preview » (version d'essai). Conseil donné à NT : prendre la
DERNIÈRE VERSION SANS « Preview » (stable), D:\Epic Games, sans symboles de débogage ni Android/iOS/Linux ; NT envoie la taille avant
d'installer. Passer à 5.9 quand elle sera finale (les projets s'ouvrent dans une version plus récente, pas l'inverse).
**UNREAL ENGINE 5.8.4 INSTALLÉ (11/11/2026, accord écrit NT « Oui », compte Epic de NT)** : `D:\Epic Games\UE_5.8` (29,5 Go ;
Build.version 5.8.4, CL 58902052 ; sans symboles de débogage ni Android/iOS/Linux). Éditeur `Engine\Binaries\Win64\UnrealEditor.exe`
et `UnrealEditor-Cmd.exe` (sans écran, pour l'automatisation) ; greffons Python (PythonScriptPlugin) et Interchange (import glTF)
présents. Installés d'office par le lanceur avec le moteur : Fab UE Plugin et Quixel Bridge (Epic, même CLUF) : non utilisés.
PIÈGES rencontrés : (1) un clic « Installer » dans le lanceur ouvert normalement déclenche une préparation du dossier en
administrateur puis un REDÉMARRAGE du lanceur qui PERD l'installation (2 fois) → ouvrir le lanceur « Exécuter en tant
qu'administrateur » ; le chemin proposé par défaut est C:\Program Files\Epic Games (à changer) ; (2) blocage à 62 % sans écriture
pendant ~25 min → Pause puis Reprendre dans Téléchargements a relancé ; vérification finale ~45 min. LauncherInstalled.dat
(ProgramData) restait vide : se fier à l'écran « Installés » ou à Engine\Build\Build.version.
**STUDIO UNREAL (11/11/2026, NT « fait tout »)** : projet `D:\Atelya-Unreal\AtelyaStudio` (chemin SANS accent ; créé par
`outils/unreal/creer_projet.py` : Lumen, ombres virtuelles, DX12, pas d'éclairage statique, exposition fixe, Remote Execution
Python locale). Pilotage SANS écran par le Python intégré d'Unreal (`UnrealEditor-Cmd.exe -run=pythonscript -script="… args"` ;
les messages `LogPython` sont dans `Saved\Logs\AtelyaStudio.log`, pas sur la sortie). Import du paquet app-002 :
`moteur/unreal/importer_maquette.py` (Interchange `import_scene`) : 562 acteurs dont 469 formes en 54 s ; REPÈRE VÉRIFIÉ :
Unreal X = 100 x, Y = −100 y, Z = 100 z (meuble reperage_1 (3,445 ; 4,668) → (344,5 ; −466,8) cm) ; lacet = −cap.
Plan : `moteur/unreal/preparer_cinematique.py` (ciel couvert = dôme émissif « is sky » + Sky Light temps réel ; ciel physique =
Sky Atmosphere + soleil de la fiche ; vitres sans ombre ; Post Process exposition manuelle, Lumen qualité 2 ; caméra de cinéma
POSÉE dans le niveau puis « possédée » par la séquence (le modèle d'une caméra « spawnable » est inaccessible en Python) ;
Movie Render Queue : PNG, 8 sous-images, 64 images de chauffe). Rendu en ligne de commande : `UnrealEditor.exe projet carte -game
-LevelSequence=… -MoviePipelineConfig=… -RenderOffscreen`. Commande unique : `outils/unreal/cinematique_unreal.py`.
**COMPARATIF MESURÉ CYCLES / EEVEE / UNREAL (11/11/2026, chambre d'app-002, trajet `trajet-chambre.json`, 96 images 1280×720,
« 2 Jour voilé », RTX 2070)** : Cycles 256 éch. ~29 s/image (46 min) ; EEVEE 2,0 s/image (3 min 40) ; UNREAL 5.8 Lumen ray tracing
matériel ~0,33 s/image (31 s de rendu, ~1 min avec le chargement ; compilation des effets la 1re fois seulement, quelques minutes).
Écart moyen à Cycles (/255, 20 images) : EEVEE 26,3 ; UNREAL 15,1 (max 30 sur l'image 1 : mur gauche trop sombre au départ ;
sol un peu plus foncé). Vidéo + planche : `D:\Atelya-Unreal\Paquets\rendus\comparatif-cycles-eevee-unreal.mp4/.jpg`
(`outils/unreal/comparer_moteurs.py`). CONCLUSION : Unreal ≈ 90 fois plus rapide que Cycles et plus proche de Cycles qu'EEVEE →
recommandation Unreal confirmée par la mesure. PIÈGES : (1) Git Bash change « /Game/… » en « C:/Program Files/Git/Game/… » (passer
par Python/subprocess ou MSYS_NO_PATHCONV=1) ; (2) projet créé à la main = SM5 par défaut → le ray tracing est IGNORÉ sans erreur
(« Skipped NVAPI RT queries since the feature level is below SM6 ») : `+D3D12TargetedShaderFormats=PCD3D_SM6` ; (3) Lumen logiciel =
traînées en éventail sur les murs d'une pièce éclairée par une fenêtre → ray tracing matériel ; (4) exposition : calée sur la
référence Cycles (`--reference`, +2,26 crans pour le ciel couvert) ; pour un logement SANS référence, il faudra une règle
automatique (clarté des murs, comme le « photographe » de Blender) : CHANTIER SUIVANT.
**FILM DU LOGEMENT, ÉTAPE 1 : EXPOSITION AUTOMATIQUE DANS UNREAL (11/11/2026, demande NT : « sans référence Cycles », règle 21)** :
FAIT pour les 5 éclairages. (1) LE PHOTOGRAPHE (`moteur/photographe.py`) : même règle et mêmes chiffres que Blender
(`rendre.reglage_de_photographe` : médiane des murs et plafonds = `clarte_murs` de l'éclairage, balance des blancs `balance`), mais
mesurée sur de PETITS ESSAIS DU FILM LUI-MÊME (réglage MRQ « Essai » : 320×180, une image sur 8, PNG + passe « M_MasqueBlancs » =
murs et plafonds marqués en custom stencil, `r.CustomDepth=3`, liste `surfaces_blanches` de la fiche de scène) ; la courbe des tons
est remontée à l'envers ; essais refaits avec la pente apprise (`prochaine_exposition`) jusqu'à ±0,15 cran (2 à 4 essais de
~30 s) ; écart régulier essai → film compté d'office (`ESSAI_VERS_FILM` −0,18) ; CONTRÔLE du film sur ses vraies images, une
reprise au plus. ÉCHEC NOTÉ : l'essai « sans courbe des tons » en EXR (valeurs physiques) ne suit PAS le film dans Unreal (valeurs
plafonnées à 100, lumière indirecte écrêtée par Lumen à 10 APRÈS exposition, `r.Lumen.ScreenProbeGather.MaxRayIntensity`) : au soleil
le film sortait 1,5 cran trop clair et la « constante » exposition → clarté variait de 4,5 à 7,5 crans selon la scène. (2) LA
PELLICULE : la courbe d'usine d'Unreal écrase les sombres (parquet à 0,01 → 5/255 au lieu de 18 dans AgX : le SOL TROP FONCÉ) ;
5 réglages (pente 0,514, pied 0,65, épaule 0,545, coupures 0 et 0,0642) imitent AgX de Blender 5.2 à 1,1/255 près sur les gris
(14/255 d'usine) ; formule d'Unreal recopiée dans `courbe_unreal` (TonemapCommon.ush) et vérifiée. (3) MUR SOMBRE DE L'IMAGE 1 :
`render_warm_up_frames` n'était pas activé → les 64 images de chauffe n'étaient pas calculées (Lumen pas « installé ») ; corrigé.
(4) 5 ÉCLAIRAGES dans Unreal (`preparer_cinematique.py`) : soleil à la hauteur et direction de chaque ambiance, 110 000 lux hors
atmosphère (mesuré dans le ciel de Blender : 138,6 W/m² face au soleil à 50°, ~94 700 lux au sol ; 1 W = 683 lm, 1 unité de ciel =
683 nits), plafonniers en Rect Light (W × 683 lumens) le soir et la nuit. PIÈGE : `unreal.Color` est rangé bleu-vert-rouge → lampes
BLEUES ; passer par `set_light_color(unreal.LinearColor(r=, g=, b=))`. (5) RÉSULTAT (chambre d'app-002, 96 images, jugé contre des
images Cycles de CONTRÔLE jamais utilisées pour régler, `outils/unreal/juger_eclairages.py`) : écart moyen /255 voilé 12,0 (15,1 avant,
quand l'exposition était CALÉE sur Cycles), soirée 10,6, nuit 7,8, ensoleillé 38,7, fin de journée 48,9 ; ~3 min par éclairage
(dont ~1 min de rendu du film, 0,5-0,65 s/image chargement compris). Planches `..\atelya\b2\app-002\unreal\eclairages\`
(`planche-image48.jpg`, `juge-unreal-photographe.jpg/.json`), films `D:\Atelya-Unreal\Paquets\rendus\app002\<éclairage>\plan.mp4`.
RESTE pour l'ÉTAPE 2 (soleil) : dehors, le sol de la planète d'Unreal sort NOIR dans les fenêtres (Blender : sol gris vu par la
caméra) ; fin de journée nettement plus orangée que Blender (atmosphère d'Unreal à 7°) ; ensoleillé et fin de journée ~0,7-1 cran
plus sombres que Cycles hors murs. Commande : `outils/unreal/cinematique_unreal.py <paquet> <nom> <trajet> --eclairages tous`.
**LUMIÈRE RÉALISTE DANS UNREAL (11/11/2026 soir, NT : « je préfère nettement la lumière de Blender/Cycles », « fais tout et donne-moi
un rendu », « optimisé pour la CINÉMATIQUE, pas la photo », « bon mélange résultat / légèreté »)**. Scène d'essai : séjour d'app-002
au soleil (vue sejour_1, repère Cycles `..\atelya\b2\app-002\unreal\lumiere\cycles\`), zones fixes mesurées + planches.
(1) CAUSES de l'écart avec Cycles, MESURÉES : (a) la lumière du CIEL d'Unreal (Sky Light capturant l'atmosphère) éclaire ~3 fois trop
peu par rapport au soleil : part du ciel dans la lumière d'un mur 26 % (Unreal) contre 59 % (Blender, cohérent avec un vrai ciel bleu),
canapé 53 % contre 79 % (rendus avec / sans le ciel, exposition fixe) → `FORCE_CIEL_PHYSIQUE = 3,3` (médiane de 7 zones), ciel couvert
inchangé ; (b) le photographe de BLENDER expose de jour PLUS CLAIR que sa visée (essai granuleux 16 rayons sans débruiteur) : murs
réels soleil 0,91 au lieu de 0,55, voilé 0,54 au lieu de 0,47, fin de journée 1,30 au lieu de 0,50 ; soirée / nuit justes. C'est ce
style « photo d'annonce » que NT préfère → `photographe.CLARTE_UNREAL` (0,90 / 0,55 / 1,30 / 0,45 / 0,35) ; (c) couleurs : modèle
complet des couleurs de la pellicule d'Unreal recopié des shaders (`moteur/pellicule_unreal.py`), nuancier de 163 couleurs passé dans
AgX (`tests/donnees/nuancier_agx_blender52.json`) → `PELLICULE_COULEURS` (expand_gamut 0, blue_correction 1, saturation 1,04) :
8,6 → 5,7/255, gris inchangés. ÉCARTÉS (mesurés sans effet) : garde-fou du path tracer (max path intensity), ombres par rayons.
Résultat séjour : écart moyen à Cycles Path Tracer 24,1 → 6,7/255, Lumen 29,8 → 13,4 (réglages « intérieur » `lumen_max` : pas de
short range AO, cache plus fin, accumulation 32 images : 13,0). Le soleil sur l'embrasure de la porte-fenêtre O10 n'est PAS une fuite
(vérifié au rayon près dans Blender : embrasure de droite au soleil, celle de gauche en lumière renvoyée).
(2) CINÉMATIQUE (trajet chambre, 96 images 720p, critère « film ») : Lumen 0,17 s/image, scintillement 1,74 (= Cycles 1,75, bruit de
fond d'une caméra qui bouge) ; path tracer 16 rayons 2,55 s/image, 2,66 (grain qui grouille), 32 rayons 5,1 s, 2,52 ; débruiteur
TEMPOREL NFOR (`r.PathTracing.TemporalDenoiser`) : 0,18 mais SILLAGES FANTÔMES sur les objets → écarté. CHOIX : LUMEN « intérieur »
(`lumen_max`, défaut de `cinematique_unreal.py`) pour le film ; path tracer en option « qualité maximale » (calcul de nuit).
Outils : `outils/unreal/juger_film.py` (scintillement, écart, temps pour 90 s), `outils/unreal/monter_film.py` (plans + fondus).
(3) DEHORS : sol gris 20 km à 6 m sous le logement (`DEHORS_*`, logement supposé au 2e étage, statut « ajouté ») : plus de sol noir dans
les fenêtres ; avec 2 km, trait sombre à l'horizon. (4) ÉDITEUR OUVERT : la chaîne prépare alors la scène DANS l'éditeur
(`outils/unreal/editeur_python.js`, Remote Execution 127.0.0.1) car il verrouille les fichiers (erreur Windows 32) ; mais éditeur +
rendu = carte graphique pleine (7,7/8 Go, 86 °C) → PLANTAGE GPU (« device reset ») vu à 21h44 : pour les rendus lourds, ÉDITEUR FERMÉ.
MCP runreal : adresse rendue réglable (`UE_PYTHON_BIND=127.0.0.1` dans `.mcp.json` ; `dist/index.js` modifié, original
`index.js.origine`, dans `D:\Atelya-Unreal\outils\mcp-unreal`) ; relancer le MCP (/mcp → unreal → Reconnect) pour qu'il le prenne.
(5) PIÈGES : pilote NVIDIA 555.97 plante à la compilation de Lumen « hit lighting » (`r.Lumen.HardwareRayTracing.LightingMode 2`) →
une mise à jour du pilote (accord NT) le débloquerait (et OptiX dans Blender) ; passe du path tracer nommée « PathTracer » ; débruiteur
du path tracer : greffon OpenImageDenoise activé (fourni avec Unreal, Intel, Apache 2.0, lu). (6) SOLEIL : direction PROVISOIRE
(habillage.SOLEIL_AZIMUT 200°) ; app-002 n'a PAS de flèche du nord (NT). Proposé à NT (en attente) : orientation donnée en un geste à
l'écran de vérification, sinon « Jour voilé » par défaut (règle 20) ; lieu = ville / code postal ; date et heure au choix. Idée gardée :
ciels photographiés HDRI Poly Haven (CC0) — téléchargement = accord NT. Outil de lumière de Karim Yasser (CG Foundry) écarté
(réglage manuel, trucage de la lumière : contraire aux règles 20 et 21).
**SOLEIL RÉEL (11/11/2026, NT : « on m'a dit que le soleil venait du sud », pour simuler)** : `moteur/soleil.py` (formules NOAA,
vérifiées : Paris midi solstice 64,6°, équinoxe 41°) : azimut / hauteur d'après orientation (nord_deg sur le plan), lieu (latitude,
longitude ; ville, jamais l'adresse), date et heure légale (heure d'été France) ; moments : « Jour ensoleillé » 15 h, « Fin de
journée » soleil à 7°, « Soirée » -3°. `outils/atelya/soleil_reel.py <scene-atelya.json> --nord 0 --source …` les inscrit dans la
fiche (bloc « soleil » avec statuts : orientation « estime », lieu centre de la France et 21 avril « ajoute »). App-002 : façade des
baies séjour + chambres (bas du plan) = SUD (lecture de Claude, à confirmer par NT) → 15 h : azimut 209°, 52° ; 19 h 58 : 280°, 7°.
**RÉALISATEUR AUTOMATIQUE (11/11/2026, NT : « il faut qu'Atelya sache faire un plan cinéma tout seul »)** : `moteur/realisateur.py`
d'après logement.json (murs + épaisseur, ouvertures, pièces, meubles) : pièces dans l'ordre d'une visite (entrée, séjour, cuisine,
chambres, salles d'eau ; pas placards / WC / dégagements ; 2 plans si > 28 m²) ; points de vue candidats tous les 0,25 m (≥ 0,45 m
des murs, 0,3 m en pièce étroite, ≥ 0,3 m des meubles), 180 rayons 2D (portes = passages, fenêtres = lumière, meubles hauts cachent),
note = part de la pièce vue + fenêtre dans le champ (4-35 %) + meubles + profondeur − mur proche ; mouvement : travelling avant
0,5-1 m (finit sur le point choisi) avec ±6° de panoramique, sinon latéral, sinon panoramique (malus 0,6) ; 18 mm, 1,5 m, −5°, 6 s.
App-002 : 8 plans (entrée, séjour ×2, cuisine, chambres ×2, salles d'eau ×2), tous en travelling, ~95 s de calcul ; vue de dessus
`realisateur.dessiner` (plans.png). Commande : `outils/unreal/film_unreal.py <paquet> <nom> <logement.json> --eclairage jour_soleil`
(réalisateur → rendu plan par plan, photographe PIÈCE PAR PIÈCE → montage avec fondus 0,5 s ; film.json, plans.json, plans.png).
Full HD mesuré : Lumen 0,52 s/image (film de 90 s ≈ 19 min), path tracer 16 rayons 4,2 s (≈ 2 h 30).
**PREMIER FILM D'ATELYA SEUL (nuit du 11 au 12/11/2026) — défauts trouvés et corrigés À LA SOURCE** : (1) le réalisateur croyait les
PORTES intérieures ouvertes (il visait le séjour « à travers ») alors qu'elles sont FERMÉES dans la maquette → `PORTES_FERMEES` (une
porte cache la vue) ; (2) pièce SANS FENÊTRE filmée de jour (entrée, salles d'eau d'app-002) = noire, le photographe partait à +22
crans → le plan dit `lumiere_du_jour` (`Scene2D.a_une_fenetre`) et le film ALLUME LE PLAFONNIER de cette pièce (`lampes_pieces` du
réglage, comme un photographe d'immobilier) ; exposition d'Unreal bornée à [-16 ; -3] (`photographe.EXPOSITION_UNREAL_BORNES`) ;
(3) FUITES DE LUMIÈRE (NT : « qu'Atelya empêche ces petites fuites dans les maquettes ») : plafonds et sols sans épaisseur posés pile
sur le haut des murs → Lumen voyait le ciel aux jonctions (bande bleutée au plafond, trait de soleil sur une porte). CORRECTION À LA
SOURCE : `geometrie.dalles_de_l_immeuble` = une dalle de 30 cm au-dessus de chaque plafond et sous chaque sol, débordant de 20 cm
sur les murs (catégorie « dalle », collection Blender « Dalles », cachée dans la vue de dessus) : toute nouvelle maquette est
étanche ; pour les maquettes déjà exportées (app-002), la fiche donne les mêmes dalles (`export_unreal.dalles`) et Unreal les pose
(`preparer_cinematique.poser_dalles`). Vérifié sur l'entrée : plus de bande ni de trait. (4) APPRENTISSAGE PAR LES AVIS DE NT (« il
doit l'apprendre tout seul », voie choisie par NT) : `realisateur.savoir_faire()` (réglages de départ + appris), `realisateur.AVIS`
(bien, trop_pres, ennuyeux, trop_rapide, pas_assez_de_lumiere, contre_jour, piece_mal_montree, trop_haut, trop_plongeant, deforme…),
chaque avis corrige un peu (pas bornés, `BORNES`) ; gardé dans `moteur/realisateur_appris.json` (+ historique) ; commande
`outils/atelya/noter_film.py <dossier du film> "3:trop_pres,ennuyeux" "tous:bien"`.
**LA BALADE (12/11/2026, NT : « au lieu de couper pièce par pièce, une vraie caméra qui se balade, qui ose, va au bout de la pièce,
se retourne »)** : `moteur/promeneur.py` = UNE prise continue. (1) carte praticable (grille 5 cm : murs, fenêtres, meubles, battants
ouverts = obstacles ; marge 20 cm pour passer une porte de 60 cm, coût plus fort près des obstacles pour marcher au milieu) ; (2) portes
ouvertes COMME UN AGENT : seulement entre pièces visitées ou de circulation, battant à 90° vers l'intérieur de la pièce (jamais dans le
couloir) ; placards, WC, pièces vides et porte palière fermés (`portes_ouvertes`, `porte_palliere`) ; (3) parcours : départ près de la
porte palière, puis par pièce (ordre de visite) son meilleur point de vue (réalisateur) et son FOND (le plus loin de l'entrée dans la
pièce, à ≥ 0,6 m des obstacles), plus court chemin (Dijkstra), lissé ; allure 0,45 m/s dans la pièce montrée, 0,8 m/s dans les
passages ; arrêt 1,8 s au point de vue, demi-tour 3,2 s au fond ; (4) REGARD vers la profondeur (rayons 2D ; ±50° autour de la marche ;
demi-tour vers la plus belle profondeur) — premier essai : la caméra fixait des murs à quelques cm ; tête ≤ 35 °/s. Unreal : battants
pivotés sur leurs gonds (`preparer_cinematique.ouvrir_portes`, position d'origine gardée en étiquette, `refermer_portes` à chaque
préparation) ; EXPOSITION EN MARCHANT : clés sur la séquence (« Settings.AutoExposureBias » du Post Process, vérifié : +2,03 cran pour
+2,0) d'après un essai par seconde de film (`photographe.exposition_en_marchant` : moyenne 2 s, ≤ 0,75 cran/s), 2 passes (écart médian
1,37 → 0,18 cran) ; plafonniers des pièces sans fenêtre allumés. Commande : `outils/unreal/balade_unreal.py <paquet> <nom> <logement>`.
App-002 : 58,7 m, 1 min 50.
Balade, réglages du REGARD trouvés en mesurant la profondeur vue (part du film à moins de 1 m d'un mur) : regard vers la profondeur
±50° autour de la marche, ÉLARGI à ±140° quand tout est à moins de 2 m devant (marche vers un angle ou une porte) ; rotation de la
tête bornée dans les deux sens du temps (elle ANTICIPE les virages) ; fond de pièce à ≥ 0,6 m des obstacles (1 m excluait tout le coin
repas). App-002 : 8 % → 6,5 % du film à moins de 1 m d'un mur (le reste : franchir des portes de 60 cm), profondeur médiane vue 3 m.
**LA CAMÉRA VOLANTE (12/11/2026, NT : « 1 min 50 trop long ; la caméra qui marche, on ressent les secousses ; il faudrait qu'elle
vole »)** : `promeneur.vol` (défaut de `balade_unreal.py --mode vol`) : ordre de visite le plus court (plus proche pièce par le chemin,
Dijkstra complet) ; fond seulement si pièce > 20 m² ; courbe = chemin rééchantillonné 10 cm, lissages gaussiens (0,7 m) sans
toucher d'obstacle ; DEMI-TOURS (culs-de-sac) détectés à la pointe exacte, chaque morceau lissé à part et rejoint exactement, vitesse
abaissée à 20 % sur ±1,2 m APRÈS le lissage (sinon effacée) ; allure 0,9 m/s, 0,5 m/s devant un point de vue (1,4 m), courbure ≤
0,6 m/s² ; hauteur 1,6 m, tangage -7° ; REGARD PAR PROGRAMMATION DYNAMIQUE (72 directions, une clé / 4 images ; note = profondeur +
vers l'avant + vers le cadrage de la pièce où l'on est + vers la profondeur aux demi-tours − mur < 0,9 m ; rotation ≤ 30 °/s, chaque
degré coûte) puis lissage 0,5 s. Lisser des caps après coup « moyennait » deux bonnes directions à travers un mur (13-28 % du film
face à un mur) → DP : 4,4 %, profondeur médiane vue 4,5 m. App-002 : 43,6 m, 1 min 13.
**LE BEAU TRAVELLING (12/11/2026, NT : « mouvements saccadés ; des fois il avance en arrière ; j'aimerais un beau travelling »)** :
causes trouvées et corrigées dans `promeneur.vol` : (1) RECUL aux impasses → boucle de demi-tour quand elle tient (`_boucle_demi_tour`,
rayons 0,4-1,5 m, amorcée jusqu'à 5 m avant) ; sinon ARRÊT complet en vol stationnaire 1,6 s, pivot à 60 °/s (30 °/s en vol), freinage
en racine sur 1 m ; regard ≤ 40° de la direction du mouvement (pénalité forte au-delà) → recul 0 % ; (2) CROCHETS de trajectoire :
garder le point d'origine près d'un obstacle faisait des zigzags → DOSAGE progressif lissé entre chemin sûr et courbe lisse, puis
finition temporelle 0,2 s ; courbure mesurée aussi à ±0,2 m (freinage avant un virage sec) → accélération max 1,5 m/s² (p95 1,0 ;
avant pics 5-6) ; dégagement ≥ 0,14 m (> 10 cm du plan de coupe d'Unreal) ; (3) passages déjà empruntés pénalisés (`VOL_DEJA_VU_*`,
un circuit plutôt qu'un aller-retour quand il existe) ; (4) FLOU DE MOUVEMENT : `motion_blur_amount` 0 → 0,5 (obturateur 180°,
accumulé par les 8 sous-images de Movie Render Queue) : sans lui tout panoramique à 24 i/s paraît saccadé. App-002 : 40,7 m, 1 min 09.
**SURVOL DES MEUBLES ET HAUTEUR VARIABLE (12/11/2026, NT : « pourquoi tu ne contournes pas les objets en élevant la caméra ? »)** :
`Carte(..., hauteur_camera)` : en vol, un meuble plus bas que la caméra − 0,5 m se SURVOLE (app-002 : tous ≤ 1 m) ; seuls murs, portes,
meubles hauts bloquent. Hauteur 1,6 m → 1,9 m dans les grands espaces (moyenne des 180 rayons de 1,5 à 3,2 m), ≥ meuble survolé + 0,6 m,
≤ plafond − 0,45 m, lissée ; plongée −7° + 15°/m au-dessus de 1,6 m. Fond d'une pièce = le plus loin du POINT DE VUE (traverser ce
que le point de vue ne montrait pas) ; boucle de demi-tour amorcée à ≤ 1,5 m du bout (au-delà elle coupait l'excursion). App-002 :
29,6 m, 50 s, boucle en goutte d'eau au-dessus de la table du coin repas.

**ÉVOLUTION DE LA CINÉMATIQUE (12/11/2026, cahier des charges de NT « audit → évaluation → plan → validation »).** NT préfère le
SURVOL de 50 s (`..\atelya\b2\app-002\unreal\film\survol.mp4`) au travelling de 1 min 09 : il devient la référence. Audit
présenté et VALIDÉ par NT : ordre 0 découpage → 1 contrôleur qualité (avant rendu + images d'essai) → 2 collisions 3D (le
promeneur ignore l'`altitude` des meubles : un meuble haut de cuisine serait « survolé » donc traversé ; lampes suspendues,
plafond) → 3 planificateur (UN vol continu en moments typés : ouverture, révélation, valorisation, transition, conclusion ;
plusieurs candidats notés par le contrôleur ; BUDGET DE DURÉE ~50-60 s pour app-002) → 4 fenêtres et lumière en mouvement.
Écartés (contre-productifs pour un film immobilier automatique) : NavMesh d'Unreal, netteté variable / changement de point,
spline retouchée à la main. Note cinématique ~55/100.
**Étape 0 FAITE (12/11)** : le vol est découpé en briques `moteur/cinema/` (reglages, navigation, parcours, trajectoire, regard,
camera) ; `moteur/promeneur.py` = chef d'orchestre + balade à pied, anciens noms toujours disponibles. Preuve : empreinte complète
de vol() et balade() sur 4 logements app-002 (8 cas) IDENTIQUE au chiffre près avant / après.
**Étape 1 FAITE (12/11) : le CONTRÔLEUR du vol** (`moteur/cinema/controle.py`, commande `outils/atelya/controler_vol.py`,
appelé avant chaque tournage par `balade_unreal.py` → `controle.json` + note dans le bilan). Sur le plan, en ~2 s, sans rendu :
nez au mur (part du champ à < 1,2 m > 55 % ou centre < 1 m), recul, rotation, à-coups, frôle, TRAVERSE (meubles posés en hauteur
d'après `altitude`, plafond), pièce vue < 3 s, fin sur un mur, budget de durée (10 s par pièce montrée + 10 s : 50 s pour app-002).
Vérifié sur les VRAIES IMAGES du survol de 50 s : 6 « nez au mur » sur 7 sont des murs plein écran (8, 30, 34, 40, 42, 49 s ; 43,8 s
limite), 8 images « rien à signaler » toutes correctes ; les 2 secousses (15 et 21 s : 0,85 → 0,05 → 0,77 m/s en < 1 s) sont
réelles. Survol : 30/100 au contrôleur (11 s face à des murs sur 50 s). Les corrections viendront avec le planificateur.
**Étape 2 FAITE (12/11) : collisions EN HAUTEUR** (`moteur/cinema/navigation.py` : `etendue`, `bloque_le_vol`, `au_dessus_du_vol` ;
`camera.hauteurs_du_vol`). Un meuble accroché à hauteur de caméra (meuble haut de cuisine 1,40 → 2,10 m) est un obstacle (avant :
pris pour un meuble bas et « survolé », donc traversé) ; on passe SOUS un objet suspendu assez haut (suspension, bas ≥ 1,90 m) en
descendant à 30 cm sous lui, image par image ; les meubles bas se survolent toujours. App-002 (aucun meuble en hauteur) : empreinte
8/8 identique. 855 tests.
**Décision NT (12/11/2026) sur les meubles** : « il faudra les mêmes meubles que le client ». Pas d'ameublement automatique
« par règles » (idée tirée de l'outil Floorcraft, écartée) : les meubles viennent des PHOTOS du client (repérage OWLv2, bibliothèque
ABO). Floorcraft (floorcraft.chirostudio.xyz, outil web fermé, sans licence, dessin du plan à la main) = concurrent à surveiller,
rien à reprendre ; idée retenue pour plus tard : un plan d'OUVERTURE « maison de poupée » (maquette en coupe vue d'en haut).
**Décision NT (12/11/2026) : UNE SEULE PRISE** (pas de fondus). Comparé sur les mêmes images : version 2 du vol planifié (48 s, une
seule prise) contre version « fondus » (31 s, couloirs remplacés par des fondus de 0,6 s, `moteur/cinema/montage.py`,
`outils/unreal/monter_fondus.py`) : NT préfère la PREMIÈRE. Le monteur reste disponible (outil), pas par défaut. Suite : réduire
les passages de murs DANS la prise continue (couloirs, sorties de pièces, panoramiques).
**Étape 3 FAITE (12/11/2026, soir) : le PLANIFICATEUR** (`moteur/cinema/planificateur.py`, défaut de `promeneur.vol`, ancien vol
= `planificateur=False`). Chaque pièce montrée par son CŒUR (endroit dégagé ≥ 0,9 × min(dégagement max, 1,4 m), le plus près
d'une porte ; 2 cœurs au-delà de 20 m²), plus beau cadrage recalculé DEPUIS le cœur ; pièce en cul-de-sac = arrêt doux +
PANORAMIQUE (70 °/s, 0,4 s sur le cadrage, on repart à mi-virage de sortie) ; CONCLUSION au cœur de la dernière pièce sur son
cadrage ; tous les ordres de visite estimés, 4 construits et notés par le contrôleur, le meilleur gardé (`candidats`). Regard :
anticipe 1,2 m de chemin (jamais au-delà d'un arrêt), évite un obstacle au centre de l'image (même règle que le contrôleur) ;
vitesse bornée pour que le regard suive les virages ; couloirs à 1,2 m/s et regard 45 °/s (pièces inchangées).
Avis NT intégrés : demi-tours plus rapides et plus fluides ; UNE SEULE PRISE (version « fondus » comparée et refusée).
Résultats (contrôleur, plan) : app-002 32 → 58,1/100, murs 12,6 → 6,8 s, 49,5 → 46 s, fin réussie, 0 hoquet ; app-001 (jamais
réglé dessus) 31 → 72,3/100. Films : `..\atelya\b2\app-002\unreal\film\planifie-v3.mp4` (+ v1, v2, fondus-v2, aperçus 960).
Reste : sorties de pièces et couloir étroit (8-14, 24-30, 36-40 s de la v3), cuisine/salles d'eau vides. Note cinématique ~62/100.
Étape suivante : 4 LUMIÈRE ET FENÊTRES (mesurer d'abord les fenêtres brûlées sur les images, puis corriger), dans une NOUVELLE
conversation. Pistes notées : ouverture « maison de poupée », meubles de cuisine et sanitaires (meubles = ceux du client).
**Étape 4, premier temps FAIT (12/11/2026, après-midi) : LUMIÈRE DU FILM MESURÉE puis corrigée à la source.** Outil
`outils/unreal/mesurer_lumiere.py` (+ brique `moteur/cinema/lumiere.py`, lancée aussi à la fin de chaque `balade_unreal.py` →
`lumiere.json`, `lumiere.png`) : chaque image qui a un masque d'essai (une toutes les 0,25 s), rangée dans la pièce de la caméra ;
fenêtres (part du dehors en blanc pur / presque blanc, couleur, détail), intérieur (bouché < 20/255, sombre < 50/255), murs (écart à
la clarté visée, part du film trop clair / trop sombre de > 0,5 cran, plus forte variation DURABLE en 1 s : médiane glissante 1 s,
une embrasure frôlée 0,5 s est vraiment plus sombre et ne compte pas), écart entre pièces ; comparaison `--avant`.
MASQUE À DEUX CANAUX (`preparer_cinematique._materiau_masque`) : rouge = murs et plafonds (photographe), vert = DEHORS vu par une
fenêtre (sol du dehors marqué stencil 2, ou ciel = profondeur > 10 km). DÉFAUT ANCIEN TROUVÉ : le marquage d'Unreal (custom depth /
stencil) ne dessine que les objets marqués entre eux → le masque des murs comptait les MEUBLES et SOLS posés devant les murs (le
photographe croyait les murs plus sombres et éclaircissait tout le film : murs du v3 −0,32 cran trop clairs en médiane). Corrigé :
pixel marqué seulement si profondeur marquée = profondeur de l'image (1 % + 2 cm). PIÈGE : sortie d'une texture de scène = 4
composantes, la comparer à une couleur à 3 composantes ne compile pas (« select_internal is ambiguous » → matériau par défaut, sans
erreur fatale) : prendre la 1re composante. Le journal montre aussi 72 « missing usage flag Nanite » : sans effet (recompilé au
chargement), et « verre translucide sur maillage Nanite » : les vitres restent transparentes (vérifié sur les masques).
MESURE DU FILM v3 (185 images) : fenêtres LAITEUSES 88 images sur 89 (96 % du dehors presque blanc, couleur 0) ; zones sombres
quasi nulles (0,7 % ; seul pic = parquet rouge foncé de la chambre 1, une matière) ; murs trop clairs 29 % du film ; 6 sauts
durables, les deux pires en passant une porte (couloir sans fenêtre → chambre au soleil : +1,1 cran pendant 3 s, l'exposition en
retard). CORRECTIONS : (1) masque juste (ci-dessus) ; (2) EXPOSITION EN MARCHANT (`photographe.exposition_en_marchant`) : essais
toutes les 0,25 s (`ESSAI_PAS_IMAGES` 6), médiane glissante 1,5 s, moyenne 0,75 s, jusqu'à 2 crans/s (le changement se fait pendant
le passage de la porte) — réglages choisis par SIMULATION hors ligne sur les murs mesurés du v3 (exposition voulue = exposition
utilisée + écart des murs) : murs à > 0,5 cran 34 % → 5 % ; (3) EXPOSITION LOCALE d'Unreal (`photographe.exposition_locale`,
contraste des hautes lumières 0,5, PIVOT = clarté visée des murs, log2(0,9/0,18) = 2,32 crans) : essai 47 images, pivot au gris
moyen = murs assombris de 0,7 cran (rejeté), pivot sur les murs = murs intacts, dehors blanc 99 → 55 %. FILM APRÈS (même vol, mêmes
images, `..\atelya\b2\app-002\unreal\film\lumiere-etape4.mp4`, côte à côte `lumiere-avant-apres.mp4/.jpg`) : dehors blanc pur 4,3 →
0,01 %, presque blanc 96 → 12 %, vues laiteuses 88 → 6 images ; murs trop clairs 29 → 0 %, trop sombres 4,9 → 3,2 % ; écart médian
−0,32 → −0,16 ; sauts durables 6 → 2 (2,26 → 1,36 cran, aux deux portes du couloir) ; écart entre pièces 0,81 → 0,39 ; sombre =.
Moins bien : étendue des clartés de l'intérieur 3,46 → 3,06 crans (image un peu plus douce). LIMITE : la vue reste grise et SANS
COULEUR (0,004) : il n'y a RIEN dehors (ciel vu à l'horizontale = brume, sol gris 20 km). Aucun réglage de caméra n'y remédiera ;
question posée à NT (ciel/rue photographiés CC0 Poly Haven = téléchargement à accorder, ou vue tirée des photos du client plus
tard, ou garder des fenêtres claires). Pas encore branché : `cinematique_unreal.py` / `film_unreal.py` (plans séparés) gardent
l'ancienne exposition (sans exposition locale). `balade_unreal.py` : options `--suffixe=-xx` (garder un film précédent) et
`--reprendre` (plantage après le rendu : contrôle, vidéo, mesure seulement). Plantage corrigé : contrôle du film à 185 images Full
HD = 1,8 Go → le photographe mesure une image du film à la taille de son masque.
**Étape 4, DÉCISION NT (12/11/2026, soir) : « tu as retiré la lumière ?! » puis « fais ce qu'il y a de mieux visuellement ».** Le film
ci-dessus (avec exposition locale, `lumiere-essai-expo-locale.mp4`) était plus terne : fenêtres 242 → 227/255, murs 199 → 195. Choix
retenu : EXPOSITION LOCALE ÉCARTÉE par défaut (`photographe.EXPOSITION_LOCALE_HAUTES_LUMIERES = 1`, sans vue réelle dehors elle ne
montre rien de plus et retire l'éclat ; réglage gardé pour le jour où une vraie vue sera posée) et clarté visée du JOUR ENSOLEILLÉ
0,90 → 1,0 (`CLARTE_UNREAL`) pour retrouver l'éclat du v3 que NT avait validé (il venait en partie du masque faux, murs réels du v3
à 1,12). Gardés : masque juste, exposition en marchant vive. FILM DE RÉFÉRENCE `..\atelya\b2\app-002\unreal\film\lumiere-etape4.mp4`
(côte à côte avec le v3 : `lumiere-avant-apres.mp4/.jpg`) ; mêmes 185 images, visée 1,0 pour les deux : murs trop clairs 18,4 → 2,2 %
du film, trop sombres 5,4 → 3,8 %, écart médian −0,17 → −0,01 cran, sauts durables 6 → 2 (2,26 → 1,39 cran, aux deux portes du couloir),
écart entre pièces 0,81 → 0,36 ; fenêtres presque blanches 96 → 86 %, vues laiteuses 88 → 77, blanc pur 4,3 → 7,3 % ; intérieur
197 → 193/255, fenêtres 242 → 239 (à l'œil : même éclat, plus de chambre grillée à 42 s). Le vrai remède des fenêtres = une vue
dehors (photo de rue / ciel CC0 = téléchargement à accorder par NT, ou vue tirée des photos du client).
**Étape 4, CIEL PHOTOGRAPHIÉ (12/11/2026, soir, accord écrit de NT pour le téléchargement)** : `..\atelya\bibliotheque\ciels\`
`kloofendal_48d_partly_cloudy_puresky_4k.hdr` (Poly Haven, Greg Zaal + Jarod Guest, CC0 lue, 20,7 Mo, LISEZMOI.txt ; copié sans accent
dans `D:\Atelya-Unreal\Paquets\ciels\`). Un CIEL SEUL, pas une rue (une rue inventée ne serait pas la vue du logement : risque de
tromper l'acheteur ; dit à NT). `moteur/cinema/ciels.py` (catalogue par éclairage : jour ensoleillé seulement ; colonne du soleil de
la photo 0,595, hauteur 47,9°) ; `preparer_cinematique.poser_ciel_photo` : posé SUR L'IMAGE (réglage d'image avant la courbe des tons),
pas dans la scène : seuls les pixels de ciel (profondeur > 10 km) sont remplacés, la photo lue dans la direction du regard, tournée
pour que son soleil tombe sur le vrai. ESSAIS : (1) sphère de 15 km dans la scène = murs −1,2 cran malgré toutes les protections
(ombre, captures, Lumen, rayons) → écartée ; (2) photo × exposition d'Unreal (nœud EyeAdaptation) = ciel NOIR → écarté ; (3) RETENU :
clarté du VRAI ciel calculé à ce pixel × détail et couleur de la photo autour de sa moyenne locale (photo floue, niveau 6) : murs
identiques au millième (0,1802 / 0,1802), nuages visibles à exposition basse (`..\atelya\b2\app-002\unreal\film\ciel-photo-expo-basse.jpg`).
PIÈGES : Unreal 5.8 importe un .hdr toujours en CUBE (import « Interchange », le réglage LoadHdrAsLongLatCubemap=0 de
Config/DefaultEditor.ini est ignoré) → le matériau inverse le dépliage d'Unreal (TextureCompressorModule.cpp, LookupLongLatDouble :
u = (1 + atan2(x, −z)/π)/2, v = acos(y)/π) ; OpenCV du PC ne sait pas écrire d'EXR. LIMITE MESURÉE à l'exposition du film (planche
`ciel-photo-essais.jpg`) : le ciel est ~2,9 crans au-dessus des murs → presque blanc, nuages à peine visibles (dehors presque blanc
97 → 99 %) ; avec exposition locale 0,7 / 0,5 : 63 / 46 %, murs −0,03 cran seulement (visée 1,0), nuages devinés. Gardé par défaut
(sans effet sur la lumière) ; exposition locale laissée à NT. Le gros du dehors vu par les fenêtres reste le SOL GRIS (logement
supposé au 2e étage) : la vraie vue ne viendra que des photos du client.
**Étape 4, SOIRÉE DU 12/11/2026 (NT : « je te laisse autodidacte jusqu'à la fin, tous tes points, et ce soir une cinématique »).**
(1) RELIEF (coins et dessous des meubles jugés trop clairs) : ombres de contact de Lumen (`r.Lumen.ScreenProbeGather.ShortRangeAO`,
réglage « ombres_contact » de la préparation, défaut coupé) mesurées contre l'image Cycles du séjour (clarté égalisée) : écart 10,3 →
10,5/255, contraste des ombres (médiane − 10 % les plus sombres) Unreal 3,70 → 3,74 crans contre Cycles 3,30 : Unreal a DÉJÀ plus de
relief que Cycles ; hypothèse fausse, laissé coupé. L'impression « plate » vient du style lumineux voulu (murs presque blancs).
(2) CAMÉRA QUI FRÔLE LES MURS aux sorties de pièces (app-002 25-27 s, 38-40 s) : cause vue sur les images = la porte donne sur un
COULOIR ÉTROIT (~1 m), la caméra arrive face au mur d'en face (le regard reste à < 40° de la marche). Essai A, portes franchies DROIT
(`navigation.redresser_aux_portes`, `planificateur.PORTES_DROITES`) : app-002 nez au mur 6,8 → 7,0 s, app-001 note 74,2 → 65,3 :
ÉCARTÉ (franchir droit fait fixer le mur d'en face encore plus). Essai B, regard libre jusqu'à 75° près des portes et dans les couloirs
(`regard.REGARD_MAX_PORTE_DEG`) : app-001 74,2 → 76,6 (nez au mur 6,2 → 5,6 s) mais app-002 6,8 → 7,0 s : gain mitigé, laissé sans
effet (= 40°), à reprendre sur d'autres logements. Vol d'app-002 vérifié identique au v3.
(3) AUTRES MOMENTS (photographe en marchant, 2 passes, images d'essai, vol v3) : jour voilé, fin de journée, soirée, nuit : murs à la
visée (écart médian +0,01 à +0,07 cran), murs trop clairs 0-3 % / trop sombres 2-4 % du film, sauts durables 1-2 (≤ 1,4 cran),
part sombre 0,6-3,8 %, bouchée ≤ 0,8 % ; coucher de soleil dans la fenêtre le soir, nuit bleu sombre. Rien à corriger.
(4) PORTES OUVERTES GRIS-BLEU : même image en Lumen et au path tracer (calcul exact, 128 rayons) : porte aussi grise (un peu plus
sombre) au path tracer ; matière blanche (0,88) dans le glTF. C'est la vraie lumière (face peu éclairée), pas un défaut.
**Décision NT (12/11/2026, fin de soirée)** : après la planche `..\atelya\b2\app-002\unreal\film\fenetres-3-versions.jpg` (3 moments
× actuel / exposition locale 0,5 / 0,3, pleine qualité) : même « ciel bien visible », on ne voit presque pas le ciel (à hauteur d'yeux,
une fenêtre montre surtout l'horizon et ce qui est en dessous, ici le sol gris). NT garde la version ACTUELLE (sans exposition locale).
CHANTIER À VENIR : la vraie vue par les fenêtres tirée des PHOTOS DU CLIENT (jamais une rue inventée).
**Étape 5 (12-13/11/2026) : la VRAIE VUE par les fenêtres, tirée des photos du client.** Photos regardées : app-002 = 8 photos sur 15
montrent le dehors (immeubles haussmanniens, arbres, garde-corps) ; app-001 = voilages partout, vue jamais visible (garder les fenêtres
claires ; plus tard poser les voilages du client). Proposé : A « posée sur l'image » ou B « vrai objet dehors » ; NT : « optimiser la 2 ».
`moteur/vue_dehors.py` : une TOILE verticale par côté de l'immeuble (fenêtres regroupées par direction du dehors), à DISTANCE_M = 35 m
(app-002 mesuré à la main par la hauteur des étages : ~20 m l'immeuble le plus proche, ~55 m les plus lointains côté sud, ~29 m côté
ouest ; à 21 m les photos se mêlaient mal), de -40 m à +26 m, coupées au coin de rue. Chaque point de la toile prend la couleur de la
MEILLEURE photo qui le voit par une fenêtre (caméras de `verites/app-002/cameras-photos.json` ; masque = ouverture projetée faces
intérieure ET extérieure, sans les pixels où un MUR plein est entre l'appareil et la fenêtre, sans les montants de la vraie fenêtre,
sans les MEUBLES devant (OWLv2, rectangles gardés en cache), sans la marque de l'annonce, rétréci de 4 px + 2 × l'écart du calage ;
fenêtre que l'appareil a dans le dos écartée) ; pas de moyenne (doublait les immeubles), couture 25 cm ; là où aucune photo ne voit :
vraie vue PROLONGÉE EN FLOU (push-pull ; avant : trous transparents = « collage », avis NT). COULEUR : le dehors s'affiche COMME SUR
LA PHOTO (teinte du mur neutralisée), la pellicule d'Unreal prise à l'envers couleurs comprises (`couleur_avant_pellicule`, exacte à
< 1/255 ; la courbe seule désaturait tout ce qui est plus clair que les murs) ; image stockée / FORCE_TOILE (10). Règle « murs »
(mur de la photo = mur du film) essayée puis écartée : délavait. Unreal (`preparer_cinematique.poser_vues_dehors`) : plan 100 cm mis à
l'échelle, matériau TRANSLUCIDE SANS ÉCLAIRAGE, image lue d'après la position dans le monde, × exposition inverse (clarté affichée
indépendante de l'exposition) ; hors de tout calcul de lumière (ombre, Lumen, champs de distance, rayons, captures). ÉTALONNAGE en
bandes grises : affiché = demandé à 2-5/255 de 0,1 à 8. PIÈGES : (1) l'exposition locale (gardée dans un vieux réglage d'essai)
écrasait les clairs ; (2) le CIEL PHOTOGRAPHIÉ posé sur l'image remplace tout ce qui a la profondeur du ciel, donc passait par-dessus
la vue translucide et lui volait ses couleurs (arbres gris) : coupé quand la vue est posée ; (3) le SOL GRIS du dehors cachait le bas
de la toile (caméra à 1,60 m qui plonge) : invisible à la caméra mais toujours dans la lumière indirecte (`poser_dehors(invisible)`) ;
(4) verre importé = surface blanche à 94 % transparente : remplacé par une VITRE CLAIRE (base noire, 6 % de reflet,
`verre_clair`) quand la vue est posée (sans effet mesurable sans vue). Outil `outils/unreal/vue_dehors_photos.py` ; film :
`balade_unreal.py --photos verites/<logement>/cameras-photos.json` (moments de jour seulement : jour_soleil, jour_voile).
MESURES (même vol que `film-12-11-soir`, jour ensoleillé, 185 images) : dehors presque blanc 89 → 21 %, blanc pur 7,6 → 0,01 %, vues
laiteuses 79 → 16 images, couleur 0,004 → 0,038, détail 0,6 → 3,2 crans ; MURS inchangés (écart médian −0,012 → −0,015, trop clairs /
sombres =, sauts =) ; images fixes avec / sans : hors de la vue 0,1 à 0,5/255. Depuis la place de la photo 15 : même clarté médiane
et même couleur que l'annonce. Films `..\atelya\b2\app-002\unreal\film\vraie-vue-essai2.mp4` (+ `-avant-apres.mp4/.jpg`, essai 1 =
collage `vraie-vue-essai1.mp4`, `vraie-vue-essai2-4-moments.jpg`). RESTE : bas des fenêtres flou et grisâtre (la caméra du film,
plus haute et plus près des vitres, plonge vers la rue qu'aucune photo ne montre) ; parallaxe juste seulement pour le lointain
(garde-corps peint sur la toile) ; distance par défaut, pas encore mesurée seule ; calage des caméras des photos fait à la main
(chantier « caler les photos automatiquement » pour un nouveau client). NT : on demandera au client de vraies photos de la vue, mais
il faut s'entraîner avec ce qu'on a.
**Étape 5, suite (13/11/2026) : NT « le décor à une distance plus juste » (le bas) puis « fais-le » (les balcons).** (1) RUE : la
toile des immeubles d'en face part du niveau de la rue (Z_BAS_M = -6, logement supposé au 2e étage) ; la rue = décor HORIZONTAL au
niveau de la rue, de notre façade jusqu'aux immeubles d'en face (`vue_dehors.rues`), gris neutre uni (clarté du bas de la vraie vue) :
les photos ne voient pas la chaussée. Rue « physique » (sol d'Unreal visible) essayée : blanche au soleil, écartée. (2) BALCONS : le
format accepte `balcons` (`moteur/logement.Balcon` : contour, garde-corps {cotes, hauteur, genre verre/barreaudage/plein}, joues,
dalle ; contrôle : pas dans une pièce, > 0,5 m²). app-002 : deux balcons relevés sur le plan (balcon_1 séjour 4,65 × 1,58 m, plan
460 × 145 ; balcon_2 chambres 8,32 × 1,55 m, plan 840 × 150, joue côté séjour), statut mesure, dans `verites/app-002/logement.json`
et `..\atelya\b2\app-002\video\apres\logement.json`. Unreal : `preparer_cinematique.poser_balcons` (dalle gris clair, lisses et
montants laqués blancs tous les 1,4 m, verre dépoli 35 %, joues ; vrais objets : ombres et lumière renvoyée ; 33 objets pour app-002),
passés par `balade_unreal` (toujours, pas seulement avec --photos). Décor : `vue_dehors.touche_un_balcon` retire des photos ce qui
est la DALLE ou un mur de côté (sinon le carrelage du balcon partait sur la rue) ; un garde-corps en verre ou à barreaux laisse voir
le dehors (tout retirer vidait la vue du séjour, essai du 13/11). LIMITES : balcons construits dans Unreal seulement (pas encore dans
la maquette Blender ni lus sur un plan par Atelya : relevés à la main pour app-002) ; contour rectangulaire.
Comparaison avec l'annonce depuis la place des photos 03, 14, 15 (`..\atelya\b2\app-002\unreal\film\balcons-zoom-v3.jpg`) : verre
des garde-corps trop laiteux (35 % -> 12 %, base gris foncé : on voit la rue à travers, comme sur la photo 15), lisse haute 5 -> 10 cm,
balcon du SÉJOUR = MURET PLEIN (photo 03 ; erreur de relevé corrigée, `genre: plein`, construit en muret). Film final
`vraie-vue-balcons2.mp4` (+ `-avant-apres`) : dehors presque blanc 89 -> 26 %, couleur 0,004 -> 0,051, détail 0,6 -> 3,7 crans, murs
inchangés (trop clairs / sombres =, écart médian -0,012 -> -0,029). NT : « j'aime beaucoup ». Qui fait quoi (question de NT) : Atelya
construit, peint le décor et tourne seul ; relevés à la main par Claude pour app-002 : balcons, caméras des photos, distance 35 m.
**Étape 6 (13/11/2026) : la DISTANCE des immeubles d'en face mesurée SEULE sur les photos (accord NT « Oui » aux deux façons).**
`moteur/distance_dehors.py` 0.1.0, branché dans `outils/unreal/vue_dehors_photos.py` (donc dans `balade_unreal --photos`) : sans
`--distance`, chaque côté prend sa distance mesurée, sinon garde `vue_dehors.DISTANCE_M` (35 m) ; `--distance` impose l'ancien
comportement. Sorties : `distances-dehors.json` (détail par côté et par photo) et `distances-etages.jpg` (étages trouvés dessinés :
vert retenu, orange écarté). FAÇON 1 « les étages d'en face » (retenue) : étage = 3 m (HAUTEUR_ETAGE_M) ; pour chaque distance
essayée (8-120 m), la caméra calée dit de combien de pixels descendre d'un étage ; on corrèle les TRAITS HORIZONTAUX de la vue avec
eux-mêmes un étage plus bas (et deux étages quand la fenêtre en montre assez), bande de 120 px par bande (une photo voit souvent un
immeuble proche à droite et des lointains à gauche). Pièges trouvés en route : (1) le motif « haut + bas de fenêtre » fait prendre un
demi-étage pour un étage (distance doublée) → corrélation de l'image décalée plutôt que spectre du profil ; (2) les traits de NOTRE
façade (barre d'appui 0,8-1,2 m d'une porte-fenêtre, lisse des garde-corps, haut du muret) se retrouvaient entre eux → retirés
(+ 8 px) et les lignes continues sur toute une bande ôtées ; (3) la barre d'appui d'une fenêtre était cherchée sur le plan de TOUTES
les fenêtres du côté (vidait le haut de la vue de la chambre 15) → seulement dans la largeur de l'ouverture ; (4) avec trop peu de
partie commune (< 35 % de la bande), faux immeubles à 9-14 m ; (5) une lamelle de fenêtre au bord d'une photo ne mesure rien
(largeur ≥ 50 px). PRUDENCE : une mesure n'est RETENUE que si la même photo donne la même distance (±10 %) dans deux bandes qui ne
se recouvrent pas ; côté = moyenne en 1/D des retenues, bornée 12-80 m. FAÇON 2 « accord des photos » (essayée, ÉCARTÉE) : sur
app-002 aucune distance où les photos s'accordent (corrélations ≤ 0,1-0,2) : elles voient presque toujours des immeubles différents
(chambre 14 l'immeuble proche, 15 les lointains, 10 la télé devant), et le calage à 3-10 px près brouille le détail.
RÉSULTATS app-002 (mesures à la main : ouest ~29 m, sud ~20 m le proche / ~55 m les lointains) : OUEST 34,2 m MESURÉ (cuisine,
4 bandes 33,4-35,3 m ; contrôle à l'œil : traits sur les étages ; écart à la main surtout l'étage supposé à 3 m, immeuble moderne
~2,8 m → ~32 m) ; SUD NON MESURÉ → 35 m (chambre 14 : 47-48 m = demi-étages d'un immeuble à ~20 m qui alterne balcons et fenêtres,
non confirmé ; chambre 15 : immeubles anciens trop petits et irréguliers ; couloir : faux 9 m écarté ; chambre 10 : 44 et 93 m qui
se contredisent). app-001 (voilages) : non mesuré partout (une bande isolée à 20 m derrière un voilage, écartée). Plans fabriqués
(façade dessinée à distance connue) : 15, 20, 30, 45, 60 m retrouvés à < 1 %. 5 s de calcul par logement. AVANT / APRÈS : ouest
35 → 34,2 m, sud inchangé : les immeubles glissent ~2 % plus vite à l'ouest, invisible ; film non refait (identique à
`vraie-vue-balcons2.mp4`). Images : `..\atelya\b2\app-002\unreal\distance-dehors\` (`etape6-etages-comptes.jpg`). LIMITES : une
toile plate par côté (ne peut pas être à 20 m ET 55 m) ; étage supposé 3 m (±10 %) ; il faut ≥ 1,5 étage net et régulier dans une
fenêtre ; dépend du calage des photos (fait à la main pour app-002). Pistes : demander au client une photo de la vue prise près de
la vitre (plusieurs étages nets) ; une toile par fenêtre ou par pièce à sa propre distance ; caméra calée seule (en réserve).
**Étape 6, suite (13/11/2026, NT « creuse si ça permet d'améliorer ») : SECOND AVIS d'une autre photo + décor EN MARCHES.**
(1) `distance_dehors.second_avis` : une mesure seule dans sa photo est confirmée si une AUTRE photo, prise sur les pixels qui voient
le MÊME endroit de la rue (empreinte u0..u1 × z0..z1 de la bande, sur le décor à la distance mesurée), retrouve les étages à 10 %
près (distances essayées 0,55-1,8 × D, partie commune ≥ 15 % admise car l'endroit est déjà désigné). Largeur minimale de bande
50 → 30 px (le séjour 03 ne voit qu'une lamelle de l'immeuble proche). app-002 SUD désormais MESURÉ en deux « marches » : immeuble
proche 23,8 m (séjour 03, confirmé par la chambre 14 à 24,8-25,8 m ; à la main ~20 m), lointains 44,4 m (chambre 10, confirmé par
la 15 à 44,4 m ; à la main ~55 m) ; le faux 47 m de la 14 et le faux 9 m du couloir ne sont confirmés par personne. Ouest 34,2 m
inchangé ; app-001 toujours non mesuré. (2) `vue_dehors.facades(…, marches)` : un côté à ≥ 2 marches = une toile par distance
(« facade-sud-1/-2 », champ « cote », bouts « bout0/bout1 »), coupées à mi-chemin entre deux endroits mesurés ; JOINT entre deux
marches (genre « joint », façade de côté de l'immeuble qui avance, peint par les photos ou de la couleur de la marche proche) ;
coin de rue seulement entre les bouts qui se font face ; une rue par marche ; `composer(…, ecrans)` + `caches_par_les_marches` :
une photo ne peint pas sur une marche lointaine ce qui est derrière une marche proche. Pourquoi des marches : un décor unique à
la moyenne (31 m) ne gagnait rien (simulation sur la balade du film, Full HD, vérité = mesures à la main : immeuble proche décalé
de 9 px en médiane / 113 px pour 10 % des images à 35 m, 7 / 91 à 31 m, 3 / 40 en marches 24/44 ; lointains 27 / 45, 36 / 60,
12 / 20).
CORRECTION du même jour : la marche franche (JOINT perpendiculaire) n'était vue par AUCUNE photo → peinte unie → BANDE BLANCHE
verticale au milieu de la vue du séjour dans le film (`vol-jour_soleil-marches`, 18 s). Remplacée par un décor qui SUIT LA RUE :
chaque endroit mesuré garde sa distance sur toute sa largeur (toile droite), et entre deux endroits mesurés une toile EN BIAIS
les relie (« facade-sud-2 », champ `biais`, sa rue = rectangle jusqu'au plus loin) ; les photos voient ce pan et le peignent
(app-002 : 38 % du pan peint par les 4 photos du sud). Écrans : toutes les autres toiles du même côté.
2e CORRECTION (film `vol-jour_soleil-biais`, chambres 21-46 s) : coin BLEUTÉ au bord en diagonale en bas des fenêtres = le pied
des toiles (hauteur de rue, jamais vu par les photos prises d'un étage) prolongé du verre bleuté des garde-corps, contre la rue
grise. `vue_dehors.fondre_le_bas` : sous la dernière ligne vue de chaque colonne, la toile passe à la couleur de la rue en 1,5 m
(FONDU_BAS_M) ; UNE couleur de rue par côté (moyenne des pieds des toiles vues, pondérée par leur part vue).
3e CORRECTION (film `vol-jour_soleil-rue`) : RECTANGLES GRIS verticaux dans la vue (séjour 18 s, chambre 46 s) : une colonne
étroite vue seulement en haut (montant, meuble) commençait le fondu vers la rue trop haut. La ligne vue la plus basse est prise
sur 6 m de large (maximum glissant puis adouci, LARGEUR_BAS_M). Film final : `vol-jour_soleil-rue2`.
RÉSULTAT (13/11/2026) : film `..\atelya\b2\app-002\unreal\film\distance-mesuree.mp4` (même vol que `vraie-vue-balcons2`, 46 s,
17,5 min de calcul) + `distance-mesuree-avant-apres.mp4` ; images `..\atelya\b2\app-002\unreal\distance-dehors\`
(`decor-vu-de-dessus.png`, `avant-apres-zoom.jpg`). Images fixes : écart moyen 0,24/255 (médiane), murs et lumière inchangés
(dehors presque blanc 26 → 27 %) ; le gain est dans le MOUVEMENT (simulation ci-dessus : immeuble proche ~3× moins décalé, lointains
~2×). Plus de bande blanche, de coin bleuté ni de rectangle gris. 887 tests verts (sans celui d'Edge, qui échoue sans navigateur).
Reste : pâles bandes verticales entre deux photos (déjà là avant), objets intérieurs (appliques) peints sur le décor ouest (déjà là
avant, calage des photos 04/05), étage supposé 3 m.
