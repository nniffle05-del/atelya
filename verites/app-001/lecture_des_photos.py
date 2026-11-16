r"""APP-001 : LES PHOTOS LUES PAR CLAUDE, à la place du service payant (essai du 16/11/2026, accord de NT).

Lues dans la conversation, une par une, sur les photos numérotées de ..\atelya\lectures-photos\app-001\envoi
(outils/lecture_photos/preparer_photos.py). RÉSERVE : avant cette lecture, la liste des SORTES du relevé à la main
(verites/app-001/meubles.json : « 4 tabourets hauts, 2 îlots, 1 étagère à cases, 1 horloge, 1 lit superposé… ») était passée
à l'écran ; les places, elles, n'ont pas été regardées. La lecture d'app-001 est donc un peu flattée ; celle d'app-002 ne l'est pas.
Format des notes : moteur/lecture_photos.fiche_depuis_notes. Fiche écrite par : outils/lecture_photos/ecrire_lecture.py app-001
"""
NOTES = {
    "photo-01": {"objets": "1 rideaux voilages blancs ; 2 canape gris clair ; 3 table_basse ovale, bois ; 4 suspension grande, noire, filaire ; "
                           "5 porte blanche ; 6 fauteuil jaune ; 7 television ; 8 meuble_tv blanc ; 9 bibliotheque bois, haute ; "
                           "10 miroir verrière, cadre noir ; 11 rangement buffet bois et blanc, dans la salle à manger ; "
                           "12 table blanche, dans la salle à manger ; 13 etagere_cubes blanc ; 14 rideaux ceux de la salle à manger ; "
                           "15 chaise grise ; 16 chaise grise ; 17 suspension petite, noire ; 18 rangement petit meuble, bois",
                 "sol": "point_de_hongrie", "manquants": "fauteuil 0,520,350,804 jaune ; caisson 228,10,605,575 volume bleu"},
    "photo-02": {"objets": "1 rideaux voilages blancs ; 2 tapis rond, crème ; 3 canape gris clair ; 4 fauteuil jaune ; 5 ilot bar blanc ; "
                           "6 suspension grande, noire, filaire ; 7 tabouret_haut jaune ; 8 suspension cage noire ; 9 fauteuil jaune ; "
                           "10 porte blanche ; 11 etagere_cubes blanc ; 12 table_basse ovale, bois ; 13 lampadaire trépied doré ; "
                           "14 bibliotheque bois, haute ; 15 fauteuil jaune ; 16 television ; 17 rangement buffet bois et blanc ; "
                           "18 miroir verrière, cadre noir ; 19 chaise grise ; 20 chaise grise ; 21 suspension petite, noire ; "
                           "22 rangement buffet de l'entrée, bois",
                 "sol": "point_de_hongrie + lames",
                 "manquants": "horloge 435,312,475,378 ; fenetre 250,215,310,390 ; caisson 495,193,725,500 volume bleu ; "
                              "table 728,405,800,470 blanche"},
    "photo-03": {"objets": "1 canape gris clair ; 2 suspension grande, noire, filaire ; 3 table_basse ovale, bois ; 4 rideaux voilages blancs ; "
                           "5 tableau grand, bleu ; 6 rideaux voilages blancs ; 7 meuble_tv blanc ; 8 television ; "
                           "9 table_d_appoint ronde, blanche ; 10 bibliotheque bois, haute ; 11 fauteuil jaune ; "
                           "12 lampadaire trépied doré ; 13 chaise grise, dans la salle à manger ; 14 rangement petit meuble, bois",
                 "sol": "point_de_hongrie", "manquants": "fauteuil 705,570,1206,804 jaune ; caisson 0,0,190,570 volume bleu"},
    "photo-04": {"objets": "1 rideaux voilages blancs ; 2 bibliotheque grand meuble mural à cases, bois et blanc ; 3 table blanche, pied central ; "
                           "4 chaise grise ; 5 rangement buffet blanc et bois ; 6 chaise grise ; 7 chaise grise ; "
                           "8 rangement buffet bois et blanc ; 9 chaise grise ; 10 suspension noire, filaire ; 11 = 3",
                 "sol": "point_de_hongrie"},
    "photo-05": {"objets": "1 ilot bar gris, plan blanc ; 2 tabouret_haut jaune ; 3 colonne_cuisine grise ; 4 colonne_cuisine grise ; "
                           "5 tabouret_haut jaune ; 6 tabouret_haut jaune ; 7 tabouret_haut jaune ; 8 = 3 ; 9 etagere_cubes blanc ; 10 = 1 ; "
                           "11 = 3 ; 12 meuble_cuisine_haut gris ; 13 fenetre ; 14 = 12 ; 15 electromenager four encastré ; "
                           "16 suspension cage noire ; 17 suspension cage noire ; 18 suspension cage noire ; 19 = 12 ; 20 = 12 ; 21 = 12 ; "
                           "22 = 12 ; 23 electromenager plaque de cuisson ; 24 meuble_cuisine_bas gris, linéaire du fond",
                 "sol": "lames + carreaux", "manquants": "fenetre 735,95,860,345"},
    "photo-06": {"objets": "1 colonne_cuisine grise ; 2 ilot bar gris, plan blanc ; 3 tabouret_haut jaune ; 4 tabouret_haut jaune ; 5 = 1 ; "
                           "6 etagere_cubes blanc ; 7 tabouret_haut jaune ; 8 meuble_cuisine_bas gris ; 9 meuble_cuisine_haut gris ; 10 = 9 ; "
                           "11 = 9 ; 12 = 8 ; 13 = 2 ; 14 = 9 ; 15 = 9 ; 16 suspension cage noire ; 17 suspension cage noire ; 18 = 9 ; "
                           "19 fenetre ; 20 = 19 ; 21 = 9 ; 22 = 8 ; 23 = 9 ; 24 autre petit électroménager posé ; 25 = 9 ; 26 = 2 ; "
                           "27 electromenager plaque de cuisson",
                 "sol": "carreaux + lames", "manquants": "fenetre 640,150,790,360 ; tabouret_haut 850,400,940,600 jaune"},
    "photo-07": {"objets": "1 etagere_cubes blanc ; 2 porte blanche ; 3 rangement buffet bois et blanc ; 4 banc noir, à chaussures ; "
                           "5 colonne_cuisine grise, vue par l'ouverture ; 6 fenetre ; 7 fenetre",
                 "sol": "lames",
                 "manquants": "horloge 838,110,1075,308 grande, noire et dorée ; applique 588,170,618,210 ; applique 765,238,783,262"},
    "photo-08": {"objets": "1 lit double, beige ; 2 rideaux beige ; 3 placard dressing toute hauteur ; 4 table_de_chevet noire ; "
                           "5 rideaux beige ; 6 = 3 ; 7 lampadaire ; 8 fauteuil noir ; 9 radiateur",
                 "sol": "lames", "manquants": "applique 243,312,300,395 ; applique 490,338,530,385"},
    "photo-10": {"objets": "1 chaise_de_bureau blanche ; 2 tapis gris, étoiles ; 3 bureau bois clair ; 4 rideaux mauve ; "
                           "5 chaise_de_bureau blanche ; 6 = 11 ; 7 rideaux mauve ; 8 commode colonne à tiroirs, blanche ; "
                           "9 etagere_cubes blanc, bacs en tissu ; 10 bureau bois ; 11 placard armoire blanche à deux portes ; "
                           "12 autre panneau de liège ; 13 suspension boule en papier ; 14 radiateur ; 15 autre tablette sur pied ; "
                           "16 lampe fine, blanche",
                 "sol": "lames", "manquants": "bibliotheque 0,385,30,680 blanche ; placard 1015,0,1206,470 armoire bois"},
    "photo-11": {"objets": "1 tapis gris, étoiles ; 2 placard armoire bois, portes miroir ; 3 = 2 ; 4 = 2 ; 5 chaise_de_bureau blanche ; 6 = 2 ; "
                           "7 faux reflet ; 8 suspension boule en papier ; 9 chaise_de_bureau blanche ; 10 bureau bois ; 11 = 12 ; "
                           "12 porte blanche ; 13 faux reflet ; 14 faux reflet ; 15 tableau ; 16 autre boîte posée sur l'armoire ; 17 tableau ; "
                           "18 tableau ; 19 faux reflet ; 20 = 10 ; 21 faux reflet ; 22 faux reflet ; 23 autre livres ; 24 autre livres ; "
                           "25 autre coussin",
                 "sol": "lames", "manquants": "lit_superpose 730,300,1206,640 bois"},
    "photo-12": {"objets": "1 rangement meuble vasque blanc, à tiroirs ; 2 baignoire ; 3 miroir forme galet, cadre blanc ; "
                           "4 autre pommeau de douche sur la baignoire ; 5 faux filigrane ; 6 miroir ; 7 autre niche murale ; "
                           "8 faux filigrane ; 9 lavabo ; 10 lavabo ; 11 faux reflet",
                 "sol": "carreaux", "manquants": "suspension 808,55,848,125 ampoule nue ; fenetre 0,0,150,300"},
}
