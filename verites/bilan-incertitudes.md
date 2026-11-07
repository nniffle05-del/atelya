# Bilan des incertitudes des vérités

20 plans relus sur 103, 24 tracés. Généré par `pc/verites/bilan_incertitudes.py` : à relancer, ne pas corriger à la main.

Plans classés du moins sûr au plus sûr (confiance = note que le traceur se donne, pas une mesure).

## Plans

- **Tracé (mur, épaisseur, équipement)** : 52 doutes notés
- **Passages ouverts (murs virtuels)** : 44 doutes notés
- **Échelle** : 32 doutes notés
- **Fenêtre ou porte-fenêtre** : 29 doutes notés
- **Porte d'entrée ou porte supposée** : 23 doutes notés
- **Nom ou type de pièce deviné** : 16 doutes notés
- **Extérieur ou dépendance (pas une pièce)** : 15 doutes notés
- **Niveaux multiples** : 1 doutes notés

### fr-026 : confiance 65, relu, ok

- **Fenêtre ou porte-fenêtre** : Terrasse et loggia = extérieurs (murs tracés, pas de pièce) ; 3 portes-fenêtres sur les flèches vers l'extérieur
- **Passages ouverts (murs virtuels)** : Salon/séjour ouverts : mur virtuel 2 px + porte 2,9 m
- **Porte d'entrée ou porte supposée** : Porte d'entrée = flèche du bas du hall (hypothèse) ; gaines hachurées tracées en blocs de mur ; petite case du hall nommée « Gaine (hall) » typée placard
- **Tracé (mur, épaisseur, équipement)** : Bloc gauche tourné ~50° : angles à ±4 px ; salle de bains non rectangulaire / Placards et WC numérotés Pl. 1-4, W.c. 1-2
- **Échelle** : Plan d'agence en traits fins 2-3 px, portes non dessinées : flèches seulement, portes posées ~45 px centrées sur chaque flèche ; échelle approximative

### fr-035 : confiance 65, relu, ok

- **Fenêtre ou porte-fenêtre** : Balcon : pas de pièce, traits fins tracés ; les deux baies du séjour y donnent (porte_fenetre), les 3 autres sont des fenêtres
- **Passages ouverts (murs virtuels)** : Passage sans porte Dégagements → Entrée : mur x=447 interrompu entre y 542 et 625 (deux blocs hachurés de part et d'autre, trait fin de seuil) noté « porte » de toute la largeur / Entrée / Séjour-Cuisine sans trait entre (582,541) et (582,657) : mur virtuel 2 px + porte de toute la largeur / Cloison hachurée y=533 (447-582, 16 px) avec passage sans porte 482-528 traversé d'un trait fin ; retour hachuré (573, 440-533) ; blocs hachurés (215-248 × 457-473 ; 447-480 × 625-641) tracés comme murs épais (gaines ou piliers ?)
- **Tracé (mur, épaisseur, équipement)** : Portes du WC (252-280) et de la salle d'eau (347-382) : coulissantes (deux traits décalés)
- **Échelle** : Échelle posée à la main (65 px/m) : les portes sont dessinées trop étroites (même dessinateur que fr-034) ; verite.json porte echelle_inconnue=true

### fr-033 : confiance 70, relu, ok

- **Fenêtre ou porte-fenêtre** : Murs extérieurs = bande grise 9-10 px ; tronçons à double trait fin = fenêtres (5 en haut, 3 à gauche, 3 à droite ; aucune sur le mur bas ni à droite du Salon)
- **Nom ou type de pièce deviné** : Réduit sans nom à droite du Wc (porte depuis le Wc) nommé « Placard (wc) », pourrait faire partie du Wc / Cellier ~2 m² typé placard ; zone entre les deux blocs = cour (extérieur)
- **Passages ouverts (murs virtuels)** : Entrée ouverte des deux côtés entre y 322 et 412 : traits virtuels + portes vers les deux dégagements / Chambre 3 en L avec un renfoncement ouvert (le mur y 231 s'arrête à x 252) ; sa porte sur le Dégagement + une porte vers la Salle à manger / Placard 2 : aucun trait vers le renfoncement (vérifié au pixel) -> front virtuel + porte ; petit Placard : porte sur la Chambre 2
- **Porte d'entrée ou porte supposée** : Quatre portes doubles/larges : Salle à manger/Entrée (361-425), porte d'entrée du logement (362-424, mur bas de l'entrée), Chambre 4 (528-592), Salon/Dégagement 2 (529-592, battant droit rabattu sur le mur du Wc)
- **Tracé (mur, épaisseur, équipement)** : Quatre portes dessinées (arc + battant) sans trou dans le trait du mur (petit placard, renfoncement, cellier, double Salon) gardées comme portes
- **Échelle** : Échelle inconnue, exclue de la note ; grand logement (~18 m de large) si les portes font 0,83 m / Battants dessinés en trait épais comme les murs (barres de ~31 px + arc pointillé) : non tracés comme murs

### fr-034 : confiance 70, relu, ok

- **Extérieur ou dépendance (pas une pièce)** : Terrasse n°1, Terrasse n°2, Parties communes : pas de pièce, murs tracés ; cellier 1,4 m² classé placard
- **Fenêtre ou porte-fenêtre** : Les 5 baies cyan donnent sur les terrasses : classées porte_fenetre ; certaines sont peut-être de simples fenêtres
- **Passages ouverts (murs virtuels)** : Séjour et Cuisine forment une zone ouverte : mur virtuel 2 px posé à y=452 (prolongement du mur haut des parties communes) + porte de toute la largeur ; vraie limite non dessinée
- **Porte d'entrée ou porte supposée** : Aucune porte dessinée pour Chambre n°1 (sauf vers sa salle d'eau) ni Chambre n°2 (sauf vers sa salle d'eau) : aucune porte inventée ; rectangles pointillés (placards ou gaines ?) laissés dans les pièces
- **Échelle** : Plan schématique pas à l'échelle : chaque pièce s'écarte de l'échelle moyenne (chambres ~70 px/m, salle d'eau 2,8 et WC ~80, cellier 1,4 m² dessiné à ~100), terrasses 46/40 m² dessinées bien trop petites / Portes dessinées ~40 px (0,5 m à cette échelle) : trop étroites par construction du dessin

### fr-040 : confiance 70, relu, ok

- **Fenêtre ou porte-fenêtre** : Symbole de fenêtre sur la cloison haute de la salle d'eau (mur intérieur) : tracé fenetre (second jour), à confirmer / Fenêtres prises d'un bord extérieur des carrés à l'autre (x 399-507 et 398-472)
- **Passages ouverts (murs virtuels)** : Entrée ouverte sur le séjour : mur virtuel 2 px à y 456 (x 115-283) avec porte
- **Tracé (mur, épaisseur, équipement)** : Photo de plan imprimé en léger trapèze : murs haut et droit tracés obliques sur l'encre / Une seule pièce « Coin cuisine Salon Sejour » (sejour) ; « Salle d'eau + Wc » en une zone (salle_d_eau)
- **Échelle** : Surfaces incohérentes avec le dessin : séjour seul → 104,5 px/m (−8,4 %), salle d'eau 126 (+10,4 %), entrée 176 (+54,6 % : 1,26 m² écrit pour une zone dessinée ~3 m²) ; 114,13 retenu (total 23,74 m² juste) ; porte d'entrée 88 px = 0,76 m, porte de salle d'eau 55 px = 0,48 m : dessin pas à l'échelle

### fr-042 : confiance 70, pas encore relu

- **Extérieur ou dépendance (pas une pièce)** : Terrasse 1 (+0.20) et escalier extérieur du haut : pas des pièces ; garde-corps (double trait fin) non tracés, seuls les murs pleins le sont.
- **Fenêtre ou porte-fenêtre** : Grande porte-fenêtre du séjour (y 1100-1278) déclarée en une seule baie (partie fixe + double vantail).
- **Nom ou type de pièce deviné** : Zones hachurées étiquetées « soffite » = circulation : nommées « Dégagement » (petit hall des 3 chambres + couloir) et « Entrée » (vestibule, hall, zone devant le séjour), noms absents du plan. / SDB : zone « F » hachurée (lavabo) comprise dans la SDB ; triangle noir de l'angle nord-est tracé en mur en biais (582,692)→(608,740), petite poche fermée sans nom dans l'angle ; Sde : carré rayonnant = receveur de douche, paroi fine non tracée. / Petite cellule de ventilation x 475-517 × y 922-940 : poche fermée sans nom.
- **Passages ouverts (murs virtuels)** : Entrée / Séjour-cuisine sans cloison (trait de limite ≈3 px en y≈1029) : mur virtuel 2 px + porte de toute la largeur (4,35 m).
- **Tracé (mur, épaisseur, équipement)** : Porte de Chambre 1 : arc dans l'angle (402,717), posée sur la cloison y=717 (depuis le petit hall) plutôt que sur x=405 (depuis le couloir) ; même ambiguïté pour la porte couloir→vestibule (y=837). / WC : porte dans un mur épais (deux traits y 1004-1010 et 1028-1032, battant dessiné dans l'épaisseur) tracé en un seul mur de 26 px (axe y 1018) avec porte de 0,63 m vers la cuisine. / Murs figés sur les valeurs recalées par l'outil (affiner: false) pour poser à la main le mur épais du WC.
- **Échelle** : Portes de la SDB, du placard PL 1 (double battant 1,19 m), du placard PL 2 (trait fin) : dessinées sans trou dans la cloison ; barre noire x 540-563 lue comme sèche-serviettes.

### fr-032 : confiance 72, relu, ok

- **Extérieur ou dépendance (pas une pièce)** : Deux poteaux violets tracés murs courts épais ; murs violets du palier tracés, escalier/ascenseur/balcon ignorés
- **Fenêtre ou porte-fenêtre** : Murs extérieurs : blocs violets à fond gris = trumeaux pleins, blancs à double trait fin = fenêtres (sinon une fenêtre chevaucherait la cloison cuisine/chambre) / Mur du bas sur balcon : 565-635 et 762-867 lues fenêtres, 635-697 (double trait décalé) lue porte-fenêtre : le style ne le dit pas / Cellier (2 m², placard) : porte = trou de 39 px (0,53 m) dans le mur violet x 404 entre y 329 et 368, vu au zoom x6 et par le contrôle d'encre ; trou à double trait du mur bas lu fenêtre
- **Nom ou type de pièce deviné** : Trois réduits sans nom typés placard : Gaine (wc), Gaine (salle d'eau) (bande à diagonale fermée par le trait fin x 915, sans quoi la salle d'eau fait +9 %), Gaine (cuisine) (0,59 m² = 559-638 seulement) / Placard 1 = boîte haute avec battant (porte 730-797) ; boîte basse à diagonale nommée « Placard (bas) » sans porte ; étiquettes peut-être inversées
- **Passages ouverts (murs virtuels)** : Wc sans trait vers la Salle d'eau : virtuel 2 px + porte / Placard chambre 1 : front trait fin -> virtuel + porte ; Placard 2 : côté entrée coupé 732-813 sans battant -> porte
- **Porte d'entrée ou porte supposée** : Porte cuisine/entrée à deux vantaux inégaux (1,18 m) ; porte d'entrée sur le mur gauche (0,83 m)
- **Tracé (mur, épaisseur, équipement)** : Mur de droite en biais (axe x 983 en haut, 933 en bas), violet + bande grise = un mur de 26 px / Épaisseurs lues sur les profils de gris (bord externe des traits sombres) : violets 14-16 px, cloisons 8-9 px
- **Échelle** : Chambre 1 (11 m², placard compris chez l'auteur), Entrée (8,79) et Placard 1 (0,57) hors du calcul d'échelle

### fr-025 : confiance 75, relu, ok

- **Extérieur ou dépendance (pas une pièce)** : 3 niveaux sur l'image (rez de chaussée en haut, rez de jardin au milieu, 1er étage en bas) : maison / triplex, tout tracé, noms suffixés « (étage) » pour l'escalier.
- **Fenêtre ou porte-fenêtre** : Toutes les baies vitrées (bandes cyan) notées « fenetre » : certaines (séjour du rez de jardin, chambre du RDC) sont peut-être des portes-fenêtres.
- **Passages ouverts (murs virtuels)** : Rez de jardin : cuisine et séjour ouverts l'un sur l'autre : mur virtuel 2 px à x≈394 + porte de toute la largeur (1,20 m). / Escaliers (rez de jardin et étage) ouverts : zone « escalier » fermée par des murs virtuels 2 px + une porte sur le côté ouvert (1,59 m côté séjour, 0,70 m côté dégagement) ; choix du côté ouvert = hypothèse. Règle du lot gardée : zone « escalier » comme fr-007, fr-010 et fr-017 du premier lot.
- **Porte d'entrée ou porte supposée** : Aucune porte d'entrée dessinée sur les 3 niveaux ; le segment plein du mur haut du RDC (x 384-453) est gardé comme mur (pilier plein vérifié). / 1er étage : chambre 2 sans porte vers le dégagement (murs y≈1153 et x≈762 pleins, vérifié sans trou d'encre), desservie seulement par le dressing 1 lui-même fermé : oubli du dessinateur, aucune porte inventée.
- **Tracé (mur, épaisseur, équipement)** : Recalage automatique désactivé (affiner: false) : murs gris cernés de noir, le recalage accrochait un cerne ; axes et épaisseurs saisis sur l'encre, contrôlés (controler ne signale que le cerne du mur 24 « encre 3 px » et le trait d'escalier du mur 28). / Le rectangle fin dans la cuisine (x 300-390, y 526-550) est un meuble, pas un mur. / Types : Dressing et Dressing 1 → placard ; Wc → wc ; les deux Salle d'Eau → salle_d_eau.
- **Échelle** : Les trois niveaux ne sont pas dessinés à la même échelle : par les surfaces écrites, RDC ≈ 69,5 px/m, rez de jardin ≈ 71,5 (séjour +6 %), 1er étage ≈ 64-65 (chambre 2 −12 %, dégagement −6 %) ; l'échelle unique 68,6 est fausse de ±5 % selon le niveau → ce plan ne peut pas juger l'échelle à 3 % près (tolérer ±5 % ou l'exclure de la note « 0 erreur d'échelle > 3 % »). / Surfaces écrites incohérentes avec le dessin : Dressing 3,95 m² écrit pour ~2,3 dessinés (−23 % en px/m), Dressing 1 1,65 pour ~2,8 (+34 %), Wc 1,0 pour ~1,6 (+16 %) ; chambre 2 dessinée plus petite que chambre 1 alors qu'elle est écrite plus grande : défaut du plan, pas du tracé. / Battants de porte dessinés comme des barres pleines NON tracés : sas de la salle d'eau RDC (y≈131, x 640-687), battant chambre 1 (x≈658, y 1110-1153), battant dressing 1 (x≈861, y 1084-1124), battants Wc et salle d'eau 1.

### fr-039 : confiance 75, relu, ok, **échelle douteuse**

- **Extérieur ou dépendance (pas une pièce)** : Terrasse 11,91 m² (x 25-178, y 680-1270, à gauche) : extérieur, pas de pièce ; sa limite est un trait fin gris, non tracé comme mur.
- **Fenêtre ou porte-fenêtre** : Baies du mur gauche sur la terrasse dessinées en deux panneaux accolés (750-819 + 823-891 ; 1008-1077 + 1080-1149) : une porte_fenetre chacune, de toute la largeur.
- **Nom ou type de pièce deviné** : « WC / Buanderie » 1,84 m² (cuvette + lave-linge) : type wc.
- **Passages ouverts (murs virtuels)** : Cuisine ouverte dans le séjour (plan de travail en L en bas à droite) : une seule pièce « Séjour / Cuisine », type sejour. / Tache plus claire sur le mur haut entre x 422 et 457 (rien de visible au zoom) : pas d'ouverture tracée.
- **Porte d'entrée ou porte supposée** : Pas de porte d'entrée dessinée : aucune porte inventée. L'ouverture du mur haut (x 517-584, y 670, rectangle blanc à cadre fin, même dessin que les fenêtres du mur droit) est la seule porte d'entrée possible ; elle reste tracée « fenetre » comme elle est dessinée.
- **Tracé (mur, épaisseur, équipement)** : Mur entre la salle de bains et le Placard 3 avec un décroché à y ≈ 1106 : encre à x 708-716 (axe 712, 9 px) de y 1016 à 1106, puis x 713-723 (axe 718, 11 px) de y 1106 à 1238 ; tracé en deux segments. Le liseré de la baignoire (x 701-708) et le blanc 709-712 ne sont pas du mur. / Hauteur sous plafond non écrite : 2,5 m par défaut.
- **Échelle** : ÉCHELLE INCONNUE, DESSIN PAS À L'ÉCHELLE : la barre 0-5 m mesure 310-313 px (62,0-62,6 px/m) ; portes (43-45 px = 0,70 m), baignoire (110 px = 1,76 m), plan de travail (0,64 m) et meubles sont à cette échelle (celle du logiciel de rendu). Mais à 62,6 px/m les pièces feraient ~100 m² habitables au lieu des 63,64 m² écrits (+55 %), et les surfaces écrites mesurées pièce par pièce donnent 70 (chambre 1), 73 (chambre 2, WC, dégagement), 82 (séjour) et 87 px/m (salle de bains) autour de l'ajustement global 77,96 : murs tracés trop grands, et pas uniformément. Choix : inconnue = true (échelle d'Atelya non notée sur ce plan) avec px_par_m = 77,96 pour que la vérité ait la surface habitable légale ; un lecteur qui prendrait la barre (62,6) ferait 20 % d'écart sans être en faute, un lecteur qui prendrait les surfaces aussi. / Trois placards (gris, « Placard ») sans porte dessinée : zones fermées nommées Placard 1 (haut, entre WC et chambre 1), Placard 2 (côté séjour), Placard 3 (entre salle de bains et chambre 2) ; leurs surfaces ne sont pas dans le tableau (63,64 m² = somme des 6 pièces).
- *Vu par le relecteur (moyenne)* : Mur bas salle de bains / placard 3 [701, 1106, 701, 1238, 22] posé sur le bord droit de la BAIGNOIRE, pas sur l'encre : aux zooms ×8 (revue\z-jog-sdb-placard3.png, z-bas-sdb-placard3.png) la baignoire s'arrête à x ≈ 706, puis blanc, puis le mur gris sombre occupe x 713-724 (11 px) de y 1106 à 1230 ; au-dessus de y 1106 le mur est à x 708-717 (le segment haut, affiné à 712, est juste). Le « coffrage de 22 px » n'existe pas : c'est le liseré de la baignoire + l'écart + le vrai mur. Conséquence : la salle de bains est amputée de ~23 px à droite et la zone Placard 3 englobe le vrai mur. (controler a été trompé par le liseré de la baignoire : « encre 8 px décalée de -4,5 ».)
- *Vu par le relecteur (moyenne)* : Échelle 77,96 px/m (surfaces écrites) contredite par trois indices indépendants et concordants : barre 0-5 m = x 121→434 = 313 px → 62,6 px/m (revue\z-barre.png) ; portes 43-45 px = 0,69-0,72 m à 62,6 mais 0,55-0,58 m à 78 (impossible) ; baignoire 110 px (y 1118-1228) = 1,76 m à 62,6 contre 1,41 m à 78. De plus les surfaces écrites donnent chacune une échelle différente mesurée sur le dessin : chambre 1 (214×240 px int.) 68, chambre 2 70, dégagement 72, WC 75, séjour 84, salle de bains 89 px/m : écarts de ±13 %, bien au-delà des 6 % tolérés. Le rendu d'agence n'est pas à l'échelle des surfaces annoncées ; juger Atelya sur 77,96 pénaliserait de 20 % une lecture correcte de la barre.

### fr-021 : confiance 78, relu, ok

- **Fenêtre ou porte-fenêtre** : Deux vérandas fermées (murs vitrés tout autour) tracées comme pièces de type sejour, selon la convention « véranda fermée ». / Paroi fine entre Véranda 2 et Entrée (x 469) : porte à un battant (y 790-832) puis panneau vitré fixe (y 850-878) tracé comme fenêtre bien qu'intérieur. / Mur extérieur gauche de Véranda 2 : vitrages séparés par des meneaux de 4-7 px (y 968-971, 1051-1057) tracés comme quatre fenêtres. / affiner=false : axes et épaisseurs mesurés directement sur l'encre (balayage des lignes et colonnes) ; l'affinage automatique amincissait le mur droit de Chambre 2 à cause de sa fenêtre.
- **Nom ou type de pièce deviné** : Pièce 2 (sans nom) : zone grise sans étiquette entre la cuisine et la pièce « Pièce » ; type chambre proposé. Pièce 3 et Pièce 5 (étiquette « Pièce ») : type chambre proposé ; Pièce 1 et Pièce 4 (étiquette « Pièce », 0,6 m de profondeur) : placards. / Entrée 3 = couloir (x 528-580, y 469-779) étiqueté « Entrée » par ligne de rappel (boîte « Entrée » à (720-770, 640-665), point d'ancrage à (553,657) au milieu du couloir, même procédé que pour le vestibule) ; il dessert Pièce 2, Pièce 3, Chambre 2, Salle de bains et Pièce 4 (fonctionnellement un dégagement) ; nom écrit et type entree respectés.
- **Passages ouverts (murs virtuels)** : Passage sans battant Cuisine → Entrée 2 (flèche dessinée, 35 px) tracé comme porte sur le mur épais. / Passage sans battant Cuisine → Véranda (x 571-627) tracé comme porte ; sa voisine (495-563) est une fenêtre. / Placard de Chambre 1 (Pièce 1) : ouvert sur la chambre par un simple trait fin → mur virtuel 2 px + porte de toute la largeur. / Mur gauche de la cuisine : ouverture y 361-400 sans symbole (le sol beige traverse l'épaisseur du mur et déborde en petite alcôve vers l'extérieur, x 328-345, y 365-395 ; trait fin à x≈345 sur y 383-400 : alcôve ou porte de service sans battant), comptée dans la fenêtre 361-447 ; seul y 400-447 porte le symbole blanc de fenêtre. / Passages ouverts sans porte : Entrée 3 (couloir) → Entrée (x 532-578, y 779) ; Entrée → Séjour (x 549-609, y 900) ; Séjour → Pièce 5 (x 628, y 1094-1192) : murs virtuels 2 px + porte de toute la largeur.
- **Porte d'entrée ou porte supposée** : Entrée 2 = petit vestibule en haut à droite (étiquette « Entrée » reliée par un trait) ; sa porte d'entrée (bas, vers l'extérieur) et sa porte vers Chambre 1 (ligne y=318) sont posées sur des murs virtuels de 2 px : aucun mur n'est dessiné sur ces deux lignes. / Porte Entrée → extérieur (x 636-674, y 904) et porte d'entrée d'Entrée 2 : portes vers l'extérieur tracées comme « porte ».
- **Tracé (mur, épaisseur, équipement)** : Bloc de mur épais à droite du séjour (x 583-640, y 1007-1061) tracé comme mur ; sa petite niche blanche (x 583-601, y 1019-1048, symbole arrondi) laissée dans le mur. / Deux carrés noirs dans Véranda 2 (x≈352, y 890 et 1050) = poteaux, tracés comme mini-murs de 9 px. / Mur de gauche de la cuisine légèrement incliné (l'image est tournée d'environ 0,8°) : tracé en un segment de (344,262) à (350,784). / Encoche rose du vestibule dans son mur de droite (x 814-838, y 336-352) ignorée : mur tracé continu.
- **Échelle** : Aucune cote, surface ni barre d'échelle : échelle posée sur les portes à un battant (≈ 40 px = 0,83 m → 48 px/m) ; l'échelle ne compte pas.
- *Vu par le relecteur (moyenne)* : Pièce « Dégagement » (type degagement, point 553,700 ; couloir x 528-580, y 469-779) : le plan l'étiquette « Entrée » par une ligne de rappel, boîte « Entrée » à (720-770, 640-665), point d'ancrage à (553,657) au milieu du couloir (zoom revue\r-sdb-leader.png) ; même procédé que pour le vestibule (boîte à (865-915, 340-370), point à (792,355)). Le nom écrit et le type ne sont pas respectés.

### fr-024 : confiance 80, relu, ok

- **Extérieur ou dépendance (pas une pièce)** : Balcon (haut) et Balcon 2 (bas) : pas de pièce, garde-corps épais tracés comme murs ; mur bas du Balcon 2 coupé par le bord de l'image.
- **Niveaux multiples** : Mention « 2ème étage » : un seul niveau dessiné.
- **Passages ouverts (murs virtuels)** : Les trois ouvertures sur les balcons sont classées porte-fenêtre par convention mais dessinées comme des fenêtres. / Ouverture Cuisine → Balcon corrigée à 893-1043 (lue au zoom ×4 ; saisie précédente 911-1033).
- **Porte d'entrée ou porte supposée** : Porte à droite du salon = porte d'entrée prise comme porte dans le mur extérieur.
- **Tracé (mur, épaisseur, équipement)** : Photo d'un plan légèrement en perspective (murs penchés ~3 %) : axes obliques, murs gris clair à contour noir, affiner=false.
- **Échelle** : Les 7 surfaces écrites ne s'accordent pas avec le dessin : à 72,6 px/m Chambre 2 +2,6 %, Chambre 3 +7,6 %, Salon −3,5 %, mais Cuisine −17 %, Chambre 1 −12 %, Salle de bain +22 %, Wc +51 % (WC dessiné 2,7 × 1,5 m pour 1,34 m² écrit) : plan de vente schématique ; échelle posée sur les trois grandes pièces (67 % de la surface). / Barre grise isolée dans le salon (x≈879, y 505-570) tracée comme petit mur (poteau ou refend inconnu). / Vantaux de portes dessinés en barres épaisses : non tracés.

### fr-030 : confiance 80, relu, ok

- **Extérieur ou dépendance (pas une pièce)** : Réduit sous le WC compté dans la cuisine ; zone sous le hall (x 305-443) = extérieur (palier)
- **Nom ou type de pièce deviné** : « Arrière bureau » typé bureau ; « Salle d'eau / WC » une seule zone salle_d_eau
- **Passages ouverts (murs virtuels)** : Salle à manger / Hall d'entrée / Salon = un seul espace ouvert : deux traits virtuels (x 262 et x 451, y 261-363) + portes de toute la largeur / Dégagt 2 ouvert sur le Hall (y 141, x 338-379) : trait virtuel + porte (vérifié au zoom : pas de trait)
- **Porte d'entrée ou porte supposée** : Aucune porte intérieure dessinée : seule l'entrée (arc) est une ouverture, aucune porte inventée
- **Tracé (mur, épaisseur, équipement)** : affiner désactivé : murs gris cernés de noir
- **Échelle** : Échelle inconnue, posée sur la porte d'entrée (35 px = 0,83 m)

### fr-037 : confiance 80, relu, ok

- **Extérieur ou dépendance (pas une pièce)** : Séch. (séchoir) et Balcon : extérieurs, pas de pièce, contours tracés (3 et 9 px) ; porte cuisine → séchoir x≈899, y 110-155
- **Passages ouverts (murs virtuels)** : Passage sans porte Entrée → Dégt (mur x≈762 interrompu de y 445 à 502) noté « porte » de toute la largeur / Parties communes tracées sans pièce : cage d'escalier (marches non tracées), palier, ASC, Gs (ouverture 1012-1049 notée porte), bloc hachuré 960-1005 × 587-622 et vide-ordures V.O (contours) ; façade droite non dessinée entre y 107-395 et 415-472
- **Tracé (mur, épaisseur, équipement)** : Mur gauche en deux bandes noires séparées d'un filet blanc tracé comme un seul mur de 23 px
- **Échelle** : Vieux plan scanné : dimensions écrites un peu contradictoires (63-68 px/m selon la pièce) ; les 12,46 et 11,32 m² des chambres incluent sans doute les placards PL. (zones placard à part, portes pliantes en V notées « porte » bien que le trait du placard soit continu) ; « Rangt 2,28 » non localisé / Portes des chambres, bains et WC dessinées étroites (40-43 px ≈ 0,66 m), battants en barres épaisses ; porte d'entrée (x≈877, y 402-452) dessinée fermée dans le plan du mur

### fr-038 : confiance 80, relu, ok

- **Fenêtre ou porte-fenêtre** : Terrasse (à gauche, x 48-91, y 96-431) : extérieur, pas de pièce ; sa limite est un trait fin (x 48) qui tourne à y 431 et rejoint le mur en biais jusqu'en (86, 455), non tracé comme mur. Seules les deux baies hautes du mur gauche (y 130-206 et 290-372) donnent sur la terrasse ; la baie basse (y 487-568) est en dehors. / Baies à deux vantaux (arcs de battants) : 3 sur le mur gauche, 4 sur le mur droit (chambres 2 et 3). Cinq portent un rectangle extérieur : la baie basse gauche (x 73-91, 18 px, y 483-574) et les 4 de droite (x 1121-1149, 29 px) ; les deux baies hautes gauches, sur la terrasse, n'en ont pas. Dans ce logiciel une fenêtre se dessine en trait bleu entre carrés et un symbole à battants est une porte : les 7 baies sont classées porte_fenetre, le rectangle extérieur lu comme un balconnet. Si NT y voit des fenêtres à appui, passer en « fenetre » les 5 baies à rectangle (les 4 de droite ET la basse gauche), jamais l'une sans les autres. / Petit segment gris épais sur le mur haut de la Chambre 2 (x 1007-1037, y 93-97) : peut-être une fenêtre dessinée autrement, non tracée.
- **Nom ou type de pièce deviné** : Petit sas sans nom entre le Wc et l'entrée (x 732-782, y 236-291, cloison fine à y 236 avec porte) : nommé « Sas WC », type degagement.
- **Passages ouverts (murs virtuels)** : Cuisine ouverte sur le séjour : limite = trait fin (x 370 de y 96 à 150, biais jusqu'à (340,180), puis x 340 jusqu'à y 291) + trou entre x 340 et 397 à y 291 ; murs virtuels de 2 px avec « porte » sur toute la largeur. / Entrée ouverte sur le séjour : mur virtuel x 367 de y 291 à 402 (dans l'axe du mur du Dressing 2) avec « porte » sur toute la hauteur. / Façade haute : segments bleus entre les petits carrés = fenêtres (6, dont une très petite de 21 px au-dessus du Wc) ; ouvertures tracées de centre à centre des carrés.
- **Porte d'entrée ou porte supposée** : Zone x 507-787, y 402-598 (sous le couloir d'entrée, entre les deux dressings) : sans mur bas, atteinte par la double porte d'entrée → palier d'immeuble (parties communes), pas de pièce. / Passage de 25 px (~0,6 m) sans porte dessinée entre l'entrée et le dégagement (x 870, y 305-330) : noté « porte ».
- **Tracé (mur, épaisseur, équipement)** : Trois rectangles croisés (x 200-255/y 97-125, x 732-782/y 100-128, x 955-1010/y 570-598) = gaines ou radiateurs, pas des murs ; rectangle noir dans le Wc (x 771-782, y 152-236) = équipement, pas un mur. / Deux petits refends de 30 px dans le Dressing 2 (y 570, x 367-397 et 480-507) = aménagement de placard, non tracés. / Hauteur sous plafond non écrite : 2,5 m par défaut.
- **Échelle** : Échelle inconnue : aucune cote, aucune surface, pas de barre ; px_par_m = 39,2 posé sur la médiane des vraies portes intérieures (32,5 px = 0,83 m) ; l'appartement en sort très grand (~26 × 13 m) : à confirmer. / Fourchette d'échelle 39-50 px/m : à 39,2 la double porte d'entrée (592-672 = 80 px) ferait 2,04 m et les baies à deux vantaux (76-82 px) 1,9-2,1 m ; à 43-50 px/m la double porte ferait 1,6-1,85 m et les fenêtres de façade (56-61 px) 1,1-1,4 m, mais les portes intérieures 0,65-0,75 m. Le dessin n'est pas strictement cohérent : aucune des deux valeurs n'est sûre.
- *Vu par le relecteur (moyenne)* : Classe incohérente des baies à deux vantaux : les 4 baies du mur droit (1121, y 122-182 / 260-320 / 376-435 / 511-572) sont « fenetre » alors que la baie basse du mur gauche (91, y 487-568) est « porte_fenetre » avec EXACTEMENT le même symbole (deux vantaux + arcs + rectangle extérieur : 29 px à droite, 18 px à gauche, trait long (73,484)-(75,576) signalé par controler). Or cette baie basse n'est PAS sur la terrasse : le trait fin de la terrasse redescend de x 50 à y 433 puis rejoint le mur à (91, 453) (revue\z-gauche-bas.png). Dans ce logiciel les fenêtres sont des traits bleus entre carrés (façade haute) ; un symbole à battants est une porte, et le rectangle extérieur ressemble à un balconnet.

### fr-041 : confiance 80, relu, ok

- **Fenêtre ou porte-fenêtre** : Baie du séjour « VR Marche » : porte_fenetre ; baies VR des chambres : fenetre
- **Nom ou type de pièce deviné** : Buanderie ~5 m² : type buanderie ; douche à l'italienne = zone de la Sde
- **Passages ouverts (murs virtuels)** : Séjour ouvert sur le dégagement : mur virtuel x 272 (y 154-225) avec porte ; la porte de la chambre 3 donne sur le dégagement / Entrée délimitée seulement par un rectangle pointillé : mur virtuel y 170 (x 425-501) + 2 raccords de 2 px, porte sur toute la largeur
- **Tracé (mur, épaisseur, équipement)** : Bande en haut à gauche (x 55-255, y 40-72) : 4 caissons croisés entre façade et mur de cuisine = hors logement, pas de pièce ; trait haut, séparations et bout droit tracés en murs fins / 2 gaines techniques (carrés mi-noirs, cuisine et WC/douche) et boîte « N » de la buanderie : contours en murs fins, intérieur hors pièce / Placards à portes coulissantes (flèches ↔) : Placard 2 vers le dégagement, Placards 3 et 4 vers les chambres 2 et 1, porte de la largeur du caisson (le contrôle les signale « mur plein d'encre » : normal) ; Placard 1 sans flèche : pas de porte / Cercles PMR, lits, appareils (LL, CU, LV, R, lavabos, cuvette, TV) et cotes : non tracés
- **Échelle** : Image de 754 px pour ~12 m (54 px/m) : ±2 px sur les axes ; affiner=false (l'affinage accrochait le cadre des fenêtres et les triangles noirs des gaines), axes posés à la main d'après zooms ×4-×6

### fr-046 : confiance 80, pas encore relu

- **Extérieur ou dépendance (pas une pièce)** : Masses noires pleines (gaine technique x 485-610 × y 245-500, poteau carré x 325-390 × y 625-685, poteaux x 632-650 × y 620-685 et x 747-795 × y 590-625) tracées par des bandes courtes et épaisses qui se chevauchent (d'où 35 murs).
- **Fenêtre ou porte-fenêtre** : Fenêtres en traits doubles fins ; celles sur le balcon (séjour y=1033, chambre 2 y=1095) en porte_fenetre ; mur séjour/balcon de 6 px seulement.
- **Passages ouverts (murs virtuels)** : Séjour-Salon / Dégagement sans cloison (y≈634, x 390-632, entre le poteau carré et le poteau de la porte de Chambre 2) : mur virtuel 2 px + porte de 2,5 m. / Dressing : ouverture sans battant sur le mur de Chambre 1 (y≈376, x 837-905) déclarée en porte.
- **Porte d'entrée ou porte supposée** : Balcon (14 m²) : extérieur, pas de pièce, murs pleins tracés, coupé par le bord de l'image ; palier à gauche (x < 325) extérieur, porte d'entrée = trou y 517-607 sur x≈329.
- **Tracé (mur, épaisseur, équipement)** : Salle de bains-wc : seule porte possible = trait fin sur le mur Chambre 1 / SDB (x≈617, y 120-190) → suite depuis Chambre 1, sans battant dessiné. / Salle d'eau-wc : porte = trait fin côté ouest (x≈426, y 415-492) vers le dégagement ; l'encoche x 432-485 × y 302-355 comptée dans la salle d'eau. / Porte de la cuisine sur la ligne y≈400 (x 345-420) entre deux bouts de mur : un mur de 8 px posé sur cette ligne pour la porter.
- **Échelle** : Pas de cote : échelle par 6 surfaces ; Salle d'eau-wc (3,3 écrit, dessinée ~2,7) et Dressing (4,7 écrit, dessiné ~5,9) écartés du calcul.

### fr-036 : confiance 82, relu, ok

- **Extérieur ou dépendance (pas une pièce)** : Murs droit et bas retracés d'une face à l'autre (bande en chaîne + bande blanche + trait de limite / double trait de la terrasse) : 635-677 (0,32 m) et 872-919 (0,36 m) ; faces intérieures sûres, faces extérieures moins (la bande blanche pourrait être un nez de dalle), sans effet sur les pièces. / Terrasse : pas de pièce ; bord haut absorbé dans le mur bas ; bords et traits de limite de lot tracés comme murs fins ; cercle Ø150, rectangle 80x130, « 120x220 », kitchenette : non tracés / non utilisés.
- **Passages ouverts (murs virtuels)** : Studio : entrée séparée du séjour par un pointillé (encre y 382-386) → mur virtuel 2 px à y 384,5 + « porte » de 1,20 m (passage ouvert).
- **Tracé (mur, épaisseur, équipement)** : Mur haut corrigé 64-94 (trait de limite 64-69 + face intérieure 89-93 sur toute la largeur) ; mur gauche 70-99 inchangé. / Boîte à zigzag x 260-299 × y 362-449 (0,30 × 0,63 m, chauffe-eau ou gaine) : côté gauche (prolonge la cloison SDB, même trait) et pied du bas tracés en L (0,65 + 0,28 m) ; côté droit (même trait de 3 px, boîte fermée) non tracé. Le relecteur y voit un contour d'appareil : 0,9 m de mur douteux, à trancher par NT. / Placard « pl » (x 262-326 × y 90-176, 0,45 × 0,65 m) tracé comme zone placard avec ses deux cloisons de 5 px, sans porte (aucune dessinée). / Bande pointillée x 602-635 contre le mur droit de la SDB/WC gardée en mur de 33 px (gaine/coffrage probable, peut-être simple habillage) ; le contrôle y voit un trou de y 94 à 129.
- *Vu par le relecteur (moyenne)* : Mur haut tracé 65-82 (17 px, axe 73,5) : l'encre montre deux faces, le trait épais de limite de lot à y 64-69 ET une face intérieure à y 89-94 présente sur toute la largeur (profils à x=245, 330, 400, 560 ; revue/zoom-n). Le mur fait donc 64-94 (30 px = 0,23 m, comme le mur gauche 70-99) ; la SDB/WC et l'ENTREE commencent 11 px (8 cm) trop haut (+0,2 m² et +0,1 m²).

### fr-027 : confiance 85, relu, ok, **échelle douteuse**

- **Fenêtre ou porte-fenêtre** : Image recadrée en haut : symboles des fenêtres coupés
- **Tracé (mur, épaisseur, équipement)** : Nom de la pièce ouest coupé par le bord : « Salle d'eau + Wc » / Aucune porte entre cuisine et salon-séjour
- **Échelle** : Échelle inconnue posée sur les portes (49 px = 0,83 m) : donne ~14 × 14,6 m, sans doute trop grand (portes dessinées petites)

### fr-029 : confiance 85, relu, ok

- **Fenêtre ou porte-fenêtre** : Fenêtres = cases blanches/bleues qui traversent les murs extérieurs (11 relevées) ; la case blanche hors du mur gauche derrière la tête de lit de la chambre 1 (x 20-35, y 46-216) n'est PAS comptée (ne traverse pas le mur). / Mur extérieur droit en deux parties (x≈930 en haut jusqu'au décroché y≈545-557, puis x≈893 jusqu'en bas) ; petit segment [893-930, y 545, 24 px] pour la face extérieure du décroché ; fenêtre des toilettes dans la façade x≈893 (y 565-611).
- **Nom ou type de pièce deviné** : « Autre » (1,18 m²) : typé placard ; sa limite basse vers le salon est un trait clair (x 562-638) pris pour une porte coulissante.
- **Passages ouverts (murs virtuels)** : Chambres 2 et 3 : baies qui débordent dans le couloir ; portes sur x≈520 (battants dessinés ouverts à plat entre y 297 et 315, ce ne sont pas des murs) ; cloison chambre 2 / chambre 3 dessinée très fine. / Cuisine : trou sans porte dans le mur bas (x 150-235) → noté « porte » (passage ouvert vers le salon).
- **Porte d'entrée ou porte supposée** : Salle de bains 2 (3,00 m²) : seul accès = trou de 60 px (0,67 m) dans le mur de la chambre 1 (x≈415, y 163-223), porte fermée en trait fin, sans arc ; la bande gris clair sous la baie de la chambre 2 (x 520-578, y≈229) est prise pour un mur (cloison basse ou vitrée), pas pour une porte. / Toilettes : aucune porte dessinée (mur x≈780 et mur y≈630 pleins, aucun arc) ; l'accès logique serait par le couloir 2 à x≈780, y≈565-622 : oubli du rendu 3D, aucune porte inventée (zone fermée dans la vérité). / Porte d'entrée : seule porte du mur extérieur bas (x 125-200) ; porte-fenêtre du salon sur le mur droit (y 675-747).
- **Tracé (mur, épaisseur, équipement)** : Plan 3D « vue de dessus » d'agence, murs noirs épais aux bords flous (JPEG) : axes lus à ±3 px, épaisseurs à ±4 px. / Relecture n° 2 du 06/11 (zooms ×4 revue/v3-*.png) : porte des toilettes retirée ; porte couloir 2 → salon recalée x 674-725 ; cloison basse de la SdB 2 (mur 7) ramenée de 13 à 9 px. / Meubles, sanitaires et plan de travail ne sont pas tracés.
- **Échelle** : Aucune cote : échelle par les 11 surfaces écrites, peu cohérentes pour les petites pièces (SdB 1 +20 %, toilettes −16 %, cuisine −10 %, couloir +9 %) ; les quatre grandes pièces sont à ±5 % et portent l'échelle.
- *Vu par le relecteur (moyenne)* : Porte des toilettes INVENTÉE : ["porte", 780, 565, 780, 622] est posée sur un mur plein. Zoom ×2 revue\r3-toilettes.png : le mur x≈780 est noir continu de y 536 à 630, le mur bas y≈630 est noir continu de x 780 à 885 avec un meuble du salon collé dessous, aucun arc ni battant nulle part autour des toilettes (controler : « porte sur un mur plein d'encre »). La convention du lot dit « n'invente aucune porte qui n'est pas dessinée », et le même traceur l'a appliquée strictement à la chambre 2 de fr-025 (laissée sans porte) : incohérent. En vérité d'entraînement, cela apprend au lecteur une porte sur de l'encre pleine ; en notation, Atelya ne pourra jamais la trouver.

### fr-044 : confiance 85, pas encore relu

- **Fenêtre ou porte-fenêtre** : Fenêtres bleu/blanc sans balcon → toutes « fenetre » ; les deux de la salle de bain déclarées séparément.
- **Passages ouverts (murs virtuels)** : Couloir / Dégagement (x≈570, y 272-318) et Hall / Dégagement (y≈321, x 598-668) : passages ouverts → mur virtuel 2 px + porte de toute la largeur.
- **Porte d'entrée ou porte supposée** : Cellule étroite x 575-594 × y 324-445 entre Chambre 1 et le hall : non étiquetée, sans porte dessinée, nommée « Placard » par hypothèse (0,45 × 2,4 m). / Porte d'entrée sur le mur sud du hall (x 612-652), aucun palier dessiné.
- **Tracé (mur, épaisseur, équipement)** : Toutes les portes du plan sont dessinées par leur battant + arc avec la cloison continue dessous (le contrôle les signale toutes, attendu). / Mur ouest en biais tracé en un seul segment (236,63)→(288,473).
- **Échelle** : Pas de cote : échelle par les surfaces ; le Séjour (23,8 m² écrit) est dessiné ~29 m² à l'échelle des autres pièces → surface écrite probablement fausse, écartée ; Hall (4,28) et Dégagement 2 (1,46) trop petits et à -12 %, écartés (le hall ne retrouve 4,3 m² qu'en y comptant la cellule « Placard »). / Chaufferie : pas de surface écrite, type buanderie ; porte lue d'après le battant (x=343, y 276-320).

### fr-047 : confiance 85, pas encore relu

- **Extérieur ou dépendance (pas une pièce)** : Murs gris clair cernés de noir : affiner désactivé ; faces des murs prises sur les contours intérieurs noirs des pièces et sur le cerne extérieur (murs extérieurs 44-54 px ≈ 0,3 m).
- **Fenêtre ou porte-fenêtre** : Terrasse (8,9 m², en haut) : extérieur, contour en trait fin non tracé ; les deux baies du mur nord (x 355-655 et 765-928) donnent dessus → porte_fenetre.
- **Nom ou type de pièce deviné** : Boîte hachurée x 212-325 × y 1160-1226 dans la salle d'eau : gaine technique, cellule fermée sans nom (cloisons de 16 px).
- **Passages ouverts (murs virtuels)** : Porte de la salle d'eau (x≈602, y 1280-1405) : panneau noir 1280-1350 + trou 1350-1405 (coulissante ou battant replié), ouverture déclarée sur les deux.
- **Porte d'entrée ou porte supposée** : Porte d'entrée : trou x 612-733 du mur sud (flèche dessous), arc centré sur (740,1440).
- **Tracé (mur, épaisseur, équipement)** : Placard PL : porte coulissante côté ouest (trait fin x≈735, panneau noir x 755-768) ; ce côté tracé en mur de 38 px portant une porte y 1290-1430. / Nom « Sèjour/cuisine » recopié tel qu'écrit (accent grave).
- **Échelle** : Entrée / Sèjour-cuisine sans cloison (ligne y≈1154, x 611-755) : mur virtuel 2 px + porte de toute la largeur ; la surface écrite de l'Entrée (2,7 m²) ne correspond pas à la zone dessinée (~1,7 m²).

### fr-022 : confiance 88, relu, ok

- **Extérieur ou dépendance (pas une pièce)** : Portes vers le garage (Couloir x 812 ; Bureau x 917) tracées comme « porte ».
- **Fenêtre ou porte-fenêtre** : Garage et son renfoncement (x 815-914, y 193-325) : pas de pièce, murs tracés ; porte de garage, fenêtre et porte extérieure du renfoncement laissées comme trous du mur (pas une pièce). / Véranda (bas gauche) en trait fin sans fenêtres : tracée comme pièce sejour (« véranda fermée »), trait du bas (3 px) comme mur ; ses deux portes depuis la maison comptées intérieures.
- **Nom ou type de pièce deviné** : Placard 2 = petit local sans nom du couloir à double porte (65 px) ; type placard proposé.
- **Passages ouverts (murs virtuels)** : Passages ouverts : Salon ↔ Séjour (x 366, y 58-147), Séjour ↔ Couloir (x 366, y 344-431), Couloir ↔ Cuisine (x 470, y 375-421) → murs virtuels 2 px + porte.
- **Porte d'entrée ou porte supposée** : Placard 1 = rectangle à murs épais sous Chambre 1 sans porte dessinée : sa face du haut déclarée porte ; le second rangement de Chambre 1 (trait fin + deux arcs) pris pour un meuble.
- **Tracé (mur, épaisseur, équipement)** : Bloc hachuré 323-369 × 147-204 (conduit/cheminée) tracé comme mur de 46 px. / « CHEMINEE » (rectangle en trait fin contre le mur gauche) laissé dans le séjour. / Porte de Chambre 2 étroite (30 px ≈ 0,64 m), lue telle quelle.
- **Échelle** : Échelle inconnue (47 px/m posé sur les portes à un battant).

### fr-031 : confiance 88, relu, ok

- **Extérieur ou dépendance (pas une pièce)** : Murs extérieurs creux (double trait) : axe au milieu, épaisseurs 0,21-0,30 m
- **Passages ouverts (murs virtuels)** : Cuisine ouverte sur la salle à manger (cote 2,42, seule la cote rouge passe là) : trait virtuel x 704 + porte de toute la largeur / Pièce aux vasques/WC sans nom : salle_d_eau ; Douche voisine aussi salle_d_eau (passage 0,99 m entre les deux, trait fin de cote dans l'ouverture)
- **Porte d'entrée ou porte supposée** : Baie 2,37 m du mur ouest lue porte-fenêtre ; porte d'entrée supposée = porte à battant du mur ouest (0,90)
- **Tracé (mur, épaisseur, équipement)** : Salon et Salle à manger sans cloison : une seule zone sejour / Placards : fronts en pointillés tracés mur fin + porte de toute la largeur / Portes chambre est (0,71) et salle d'eau (0,73) : positions confirmées par les cotes et les trous du mur

### fr-023 : confiance 90, relu, ok

- **Extérieur ou dépendance (pas une pièce)** : Tous les traits font 3 px : murs extérieurs et cloisons indistinguables.
- **Fenêtre ou porte-fenêtre** : Mur gauche de la cuisine en biais avec fenêtre inclinée (position ±4 px).
- **Passages ouverts (murs virtuels)** : Trois passages ouverts fermés par un mur virtuel 2 px + porte : hall → séjour (y 359), cuisine → séjour (x 408, y 536-608), entrée → séjour (y 608, x 408-481). / Zone en C à droite (x 837-1158) ouverte sur le bord : extérieur probable (balcon/loggia où donnent trois fenêtres), murs tracés, aucune pièce.
- **Porte d'entrée ou porte supposée** : Pièces non nommées, types déduits : WC (72×143 px), Salle d'eau (pièce en L avec fenêtre en haut), Dégagement (hall entre les deux chambres), Entrée (x 408-515, y 608-716, porte d'entrée en bas).
- **Échelle** : Échelle inconnue (84,3 px/m sur la médiane des portes, qui font ~70 px).
