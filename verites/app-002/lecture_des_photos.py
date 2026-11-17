r"""APP-002 : LES PHOTOS LUES PAR CLAUDE, à la place du service payant (essai du 16/11/2026, accord de NT).

Lues dans la conversation, une par une, sur les photos numérotées de ..\atelya\lectures-photos\app-002\envoi
(outils/lecture_photos/preparer_photos.py), SANS ouvrir le relevé des meubles fait à la main (verites/app-002/meubles.json) :
c'est lui qui juge cette lecture. Format des notes : moteur/lecture_photos.fiche_depuis_notes.
Fiche écrite par : outils/lecture_photos/ecrire_lecture.py app-002
"""
NOTES = {
    "photo-01": {"objets": "1 table rectangulaire, plateau bois, pieds métal ; 2 chaise brun ; 3 rangement buffet, bois clair {entier} ; 4 chaise brun ; "
                           "5 chaise brun ; 6 canape blanc cassé ; 7 chaise brun ; 8 chaise brun ; 9 radiateur ; 10 bureau blanc ; 11 porte ; "
                           "12 suspension plafonnier à vasque, pendu court ; 13 chaise brun ; 14 bibliotheque pin, étroite ; 15 tableau ; "
                           "16 autre écran d'ordinateur ; 17 applique",
                 "sol": "lames", "manquants": "applique 483,240,527,275 ; canape 1145,375,1206,492 gris"},
    "photo-02": {"objets": "1 porte porte d'entrée, bois foncé ; 2 miroir octogonal ; 3 placard portes blanches ; 4 = 3 ; 5 porte blanche ; "
                           "6 rangement buffet, bois clair, vu par l'ouverture ; 7 suspension plafonnier ; "
                           "8 meuble_cuisine_bas bois, vu par la porte",
                 "sol": "lames"},
    "photo-03": {"objets": "1 table rectangulaire, plateau bois ; 2 chaise brun ; 3 chaise brun ; 4 chaise brun ; 5 chaise brun ; 6 bureau blanc ; "
                           "7 rangement buffet, bois clair ; 8 chaise brun ; 9 suspension plafonnier à vasque ; 10 tableau ; "
                           "11 autre écran d'ordinateur ; 12 bibliotheque pin ; 13 miroir cadre bois ; 14 canape blanc cassé",
                 "sol": "lames", "manquants": "porte_fenetre 655,185,1165,555 baie coulissante ; chaise 780,400,882,470 brun"},
    "photo-04": {"objets": "1 table rectangulaire, plateau bois ; 2 bureau blanc ; 3 porte_fenetre baie coulissante ; 4 chaise brun ; "
                           "5 chaise brun ; 6 chaise brun ; 7 chaise brun ; 8 chaise brun ; 9 chaise brun ; 10 suspension plafonnier à vasque ; "
                           "11 rangement buffet, bois clair ; 12 tableau ; 13 radiateur ; 14 autre écran d'ordinateur ; 15 chaise brun ; "
                           "16 applique",
                 "sol": "lames",
                 "manquants": "applique 708,290,752,318 ; porte 826,288,967,520 ; porte_fenetre 0,140,205,640 baie coulissante ; "
                              "fauteuil 0,480,32,705 rotin"},
    "photo-05": {"objets": "1 porte_fenetre baie coulissante ; 2 table rectangulaire, plateau bois ; 3 rangement buffet, bois clair ; "
                           "4 chaise brun ; 5 commode ancienne, marqueterie, bois foncé ; 6 chaise brun ; 7 chaise brun ; 8 chaise brun ; "
                           "9 faux ; 10 suspension plafonnier à vasque ; 11 autre tabouret pliant en bois ; 12 chaise brun ; "
                           "13 meuble_cuisine_bas bois, vu par l'ouverture ; 14 tableau ; 15 autre écran d'ordinateur ; 16 applique ; "
                           "17 autre cadres photo posés sur le buffet",
                 "sol": "lames",
                 "manquants": "applique 738,285,772,310 ; fenetre 448,272,632,462 ; bureau 1065,430,1206,690 blanc ; porte 1018,235,1068,492"},
    "photo-07": {"objets": "1 canape gris anthracite ; 2 meuble_tv blanc ; 3 canape blanc cassé ; 4 television ; 5 bibliotheque pin ; "
                           "6 rangement buffet, bois clair ; 7 chaise brun ; 8 bureau blanc, vu de bout ; 9 autre boîte blanche ; "
                           "10 autre tabouret pliant en bois",
                 "sol": "lames", "manquants": "applique 918,195,975,250 ; applique 290,288,328,308 ; porte 380,285,415,400"},
    "photo-08": {"objets": "1 electromenager réfrigérateur inox ; 2 porte blanche ; 3 colonne_cuisine bois ; 4 hotte blanche ; "
                           "5 electromenager four encastré ; 6 = 3 ; 7 meuble_cuisine_bas tiroirs, bois {d=g3} ; "
                           "8 electromenager micro-ondes encastré ; 9 meuble_cuisine_bas sous l'évier, bois {g=d10 d=g15} ; 10 meuble_cuisine_bas bois ; "
                           "11 faux ; 12 plafonnier rampe de spots ; 13 = 3 ; 14 electromenager plaque de cuisson ; 15 = 7 ; 16 = 3 ; 17 evier",
                 "sol": "carreaux", "manquants": "fenetre 205,235,465,420"},
    "photo-09": {"objets": "1 meuble_cuisine_bas linéaire avec évier, bois {g=cadre d=g2} ; 2 meuble_cuisine_bas tiroirs sous la plaque, bois ; 3 evier ; "
                           "4 electromenager réfrigérateur inox ; 5 = 1 ; 6 colonne_cuisine bois ; "
                           "7 porte porte d'entrée, dans le couloir ; 8 meuble_cuisine_bas petit meuble à droite, bois ; "
                           "9 electromenager fours encastrés ; 10 plafonnier rampe de spots ; 11 = 6 ; "
                           "12 electromenager plaque de cuisson ; 13 = 6 ; 14 = 2",
                 "sol": "carreaux", "manquants": "hotte 395,65,775,215 blanche"},
    "photo-10": {"objets": "1 commode blanche, trois tiroirs ; 2 miroir posé au sol, cadre blanc ; 3 lit une place, blanc ; "
                           "4 meuble_tv blanc, bas ; 5 bibliotheque colonne blanche, étroite ; 6 suspension globe blanc ; 7 television",
                 "sol": "lames",
                 "manquants": "porte_fenetre 270,235,545,520 ; radiateur 565,405,612,445 ; caisson 540,425,872,700 panneau blanc à mi-hauteur"},
    "photo-14": {"objets": "1 lit double, blanc ; 2 porte_fenetre ; 3 autre boîte de rangement en tissu ; 4 suspension globe blanc ; "
                           "5 autre clavier sur pied ; 6 chaise noire ; 7 faux ; 8 radiateur",
                 "sol": "lames"},
    "photo-15": {"objets": "1 lit double, blanc ; 2 porte_fenetre ; 3 = 2 ; 4 suspension globe blanc ; 5 autre clavier sur pied ; "
                           "6 radiateur ; 7 faux ; 8 chaise noire",
                 "sol": "lames"},
}
