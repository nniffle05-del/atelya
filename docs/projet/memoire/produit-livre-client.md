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
