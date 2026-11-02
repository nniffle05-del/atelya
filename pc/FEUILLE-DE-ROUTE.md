# Atelya — feuille de route

Objectif : faire d'Atelya une vraie solution de marché. Le client envoie son plan et 5 à 6 photos (10 au plus) ; Atelya rend, automatiquement, le logement en 3D habillé, une cinématique et une visite libre.

Règle de jugement : un progrès compte s'il se voit **sur de vrais plans**, pas seulement dans les notes de contrôle (6d-T1 avait les meilleures notes et le pire rendu réel).

## 0. URGENT — sauvegarde du projet (décision NT, 01/11, à faire juste après les bancs 6e)

Rien n'est sauvegardé ailleurs que sur ce PC (le dossier n'est pas sous git). À protéger en priorité : le code (`code-6-19`, scripts `.py` / `.ps1` à la racine d'`atelya`), les modèles (`resultats-essai-5`, `resultats-essai-6e`…), les vrais plans (`vrais-plans`), cette feuille de route, puis les jeux de données (gros, en partie régénérables par le générateur). Copie hors du PC (disque externe et/ou stockage en ligne) + historique des versions du code.

## 1. Brique « plan » (en cours, prioritaire)

État au 01/11/2026 : essai 6e = premier modèle gardé de la série 6 (contrôle complet : anciens 89,2 %, photos 83,9 %, monde 72,6 % contre 43,9 % pour l'essai 5). Restent faibles sur vrais plans : escaliers, carrelage pris pour autre chose, captures de téléphone, plans très pâles, types de pièces.

1. **Jeu de test réel figé** : 50 à 100 vrais plans variés (agences, scans, photos, PDF, captures), dont une partie jamais apprise. C'est le juge officiel.
2. **Corrigés sur vrais plans** : pré-annotation par Claude (types de pièces lus sur les étiquettes, « ceci n'est pas un escalier »), validation par NT, mélange à l'entraînement.
3. **Lecture du texte des plans** : étiquettes, surfaces, cotes, niveau (« 3ème étage ») → corriger les types, vérifier surfaces et échelle.
4. **Tri à l'entrée** : détecter capture de téléphone / scan de biais / plan pâle, recadrer et redresser ; dire honnêtement « illisible » quand c'est le cas.
5. **Générateur** : carrelages et hachures, escaliers variés, plans pâles, photos de téléphone avec barre d'état.
6. **Mobilier dessiné sur les plans** : apprendre à le repérer (au lieu de l'ignorer) pour placer les meubles.
7. **Flèche du nord** : repérer la rose des vents / la mention d'orientation et lire son angle (sert au soleil, §5).
8. Plus tard : modèle plus grand / entraînement plus long, quand les données réelles seront là.

## 2. Brique « photos » (après la brique plan)

- V1 : le client indique la pièce de chaque photo ; V2 : pièce devinée et croisée avec le plan.
- Extraction automatique : sol, murs, plafond, menuiseries, éléments (cheminée, poutres, verrière, escalier), ambiance.
- Dès maintenant, sans technique : demander aux clients le plan **et** quelques photos des pièces principales, pour constituer la base.

## 3. Bibliothèque de matériaux

- Recherche automatique par « empreinte » dans **notre propre bibliothèque** (pas de recherche Internet à chaque logement) ; ajustement de teinte et d'échelle du motif avec l'échelle du plan.
- Si rien de proche : texture fabriquée depuis la photo (répétable), ou la plus proche marquée « à vérifier ».
- Départ : plusieurs milliers de matériaux à licence commerciale claire (licence notée pour chacun), bien classés ; version légère pour la recherche, HD pour le rendu. Puis enrichissement automatique.
- Remplace les matériaux procéduraux actuels (`moteur/blender/materiaux.py`), choix fait dans `moteur/habillage.py`.

## 4. Banque de meubles 3D

- Détection des meubles sur photos (catégorie, style, couleur, taille), modèle 3D le plus proche, réhabillé avec nos matériaux.
- Placement : mobilier dessiné sur le plan, perspective des photos, règles d'aménagement.
- Trois modes produit : reproduire / vider / remeubler (home staging virtuel). Commencer par vider et remeubler (plus simples).
- Licences commerciales claires ; plus tard catalogues fabricants.

## 5. Lumière du soleil réaliste

Aujourd'hui : soleil **fixe** dans `moteur/habillage.py` (azimut 200°, hauteur 50°) → à remplacer.

1. **Lieu** : adresse → latitude / longitude (Base Adresse Nationale).
2. **Orientation du plan (où est le nord)**, dans cet ordre : flèche du nord sur le plan → contour du bâtiment (cadastre / IGN) recalé sur le plan → question au client → défaut signalé « non vérifié ».
3. **Date et heure** → position exacte du soleil (calcul astronomique) → soleil de la scène dans Blender et dans Unreal (outil de position solaire).
4. Cinématique : choix automatique de la plus belle heure **réelle** ; visite libre : curseur heure / saison.
5. Plus tard : ombres des immeubles voisins (hauteurs BD TOPO IGN) et étage du logement.
6. Règle produit : lumière **fidèle à la réalité** — on choisit le meilleur moment, on n'invente pas de soleil.

## 5 bis. Vue à travers les fenêtres

La vue réelle (ex. tour Eiffel) doit apparaître dans les fenêtres, à la bonne hauteur (étage) et dans la bonne direction (orientation, §5).

Décision NT (01/11) : **voie par défaut = automatique depuis l'adresse (IGN)**, sans rien demander au client.

1. **Automatique depuis l'adresse (par défaut)** : environnement 3D construit à partir des données publiques IGN (bâtiments BD TOPO, LiDAR HD, photos aériennes), vu depuis l'étage du logement. On calcule **un panorama 360° par logement**, à hauteur des fenêtres, qui sert de fond à toutes les fenêtres (et éclaire les reflets). Les volumes IGN sont simples (blocs, toits) : on les habille de façades selon le style du quartier, et les **monuments** repérés dans le champ (tour Eiffel, Sacré-Cœur…) sont remplacés par des modèles 3D détaillés d'une petite bibliothèque dédiée. Option premium : villes 3D photoréalistes (Google Photorealistic 3D Tiles, via Cesium dans Unreal) — conditions d'usage et coût à vérifier.
   Apparence réelle des façades d'en face : Google Photorealistic 3D Tiles (vraies façades texturées, payant, attribution, usage encadré : pas de copie/stockage libre) ; Mapillary (photos de rue ouvertes, licence CC BY-SA, usage commercial avec attribution) pour texturer les façades ; Street View exclu (conditions d'usage). À tester dans le comparatif de rendu et à faire valider juridiquement avant la vente.
2. **Photos du client (bonus si disponible)** : quand une photo montre la vue, elle remplace ou corrige le panorama pour cette fenêtre. Le plus fidèle, mais jamais obligatoire.
3. **Repli** : fond panoramique générique choisi selon le contexte de l'adresse (centre-ville, quartier résidentiel, campagne, mer), flouté légèrement.
4. Règle produit : la vue doit être **vraie** (une vue inventée sur un monument serait trompeuse) ; en cas de doute, fond neutre plutôt que faux.

## 6. Rendu et livrables

Livrable client en deux parties : **cinématique** (caméra qui parcourt les pièces) et **visite libre** (le client se déplace).

- Chaîne existante : `logement.json` → `geometrie.py` + `habillage.py` → `construction.json` → Blender (`poser_briques.py`, `rendre.py`, Cycles) via `moteur.construire`.
- Pressenti : Blender = fabrication de la maquette + images fixes HD ; Unreal = visite libre **et** cinématique (même scène, vidéo en minutes) ; EEVEE pour les premières démos.
- **Comparatif à faire avant de trancher** : même logement, même trajet de 10 s ; Cycles qualité max, Cycles optimisé, EEVEE, Unreal ; temps, mémoire, qualité côte à côte ; extrapolation à 1 min et à une carte haut de gamme.
- Unreal : visite dans le navigateur (Pixel Streaming), réalité virtuelle, changements en direct (matériaux, meubles, heure), interactions ; licence à vérifier le moment venu.

## 7. Réalisateur automatique (mouvements de caméra)

À partir du `logement.json` : ordre de visite par les portes (entrée → séjour → cuisine → chambres → eau), temps dosé selon l'importance des pièces, meilleurs points de vue notés automatiquement (surface vue, fenêtres et lumière, éléments forts, verticales droites, hauteur d'œil), plans types (travelling avant, panoramique, latéral, passage de porte, ouverture « maison de poupée »), trajectoire lissée sans collision, fichier caméra commun Blender / Unreal, mêmes points de vue réutilisés comme points d'intérêt de la visite libre. Options : durée, ambiance, vide / meublé / home staging, titres, logo, musique.

## 8. Sujets pas encore traités (liste du 01/11)

- **Entrées** : plans PDF vectoriels et fichiers d'architecte (DWG/DXF) lus directement (plus précis que l'image) ; plans en plusieurs pages / plusieurs niveaux.
- **Logements sur plusieurs niveaux** : duplex, maisons, escaliers reliant les étages, mezzanines.
- **Hauteurs** : sous plafond, mansardes et combles (indice : écart surface Carrez / au sol sur le plan), poutres, marches.
- **Extérieurs** : balcons, terrasses, loggias, jardins ; façade pour les maisons.
- **Contrôle qualité** : note de confiance automatique par logement, alerte si doute ; écran de correction simple (déplacer un mur, changer un type de pièce) avant le rendu.
- **Premier produit vendable rapide** : plan 2D redessiné propre (coté, surfaces par pièce) — sous-produit direct de la brique plan.
- **Livrables** : formats (MP4, images, lien web), délais promis, cas « plan illisible ».
- **Infrastructure** : où tournent les calculs (PC, serveurs GPU loués), coût et temps par logement, montée en charge.
- **Données et RGPD** : plans, adresses et photos sont des données personnelles ; hébergement en Europe ; **accord du client pour réutiliser ses plans à l'entraînement** (indispensable pour §1) ; floutage des personnes/objets personnels sur les photos.
- **Juridique** : surfaces affichées = indicatives, pas un mesurage Carrez certifié ; licences de tout ce qu'on réutilise.
- **Commercial** : cibles (agences, promoteurs, rénovation, particuliers), prix, offres (images / cinématique / visite), concurrence.

## Ordre conseillé

1. Brique plan fiable sur vrais plans (§1, points 1 et 2 d'abord).
2. Comparatif Blender / EEVEE / Unreal (§6), puis réalisateur automatique (§7) et soleil réaliste (§5).
3. Brique photos + bibliothèque de matériaux (§2, §3).
4. Meubles et home staging (§4).
5. Visite libre Unreal en offre premium.
