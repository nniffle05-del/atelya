r"""APP-004 : LES PHOTOS LUES PAR CLAUDE, à la place du service payant (essai du 16/11/2026, accord de NT).

Lues dans la conversation, une par une, sur les photos numérotées de ..\atelya\lectures-photos\app-004\envoi
(outils/lecture_photos/preparer_photos.py), SANS regarder la maquette. Format des notes : moteur/lecture_photos.fiche_depuis_notes.
Fiche écrite par : outils/lecture_photos/ecrire_lecture.py app-004
"""
NOTES = {
    "photo-01": {"objets": "1 canape bleu ; 2 table ronde, bois ; 3 porte_fenetre ; 4 chaise ; 5 chaise ; 6 cheminee ; 7 suspension rotin ; "
                           "8 autre foyer carrelé de la cheminée ; 9 rideaux ; 10 meuble_tv banc bas, bois clair ; 11 television",
                 "sol": "lames"},
    "photo-02": {"objets": "1 canape bleu ; 2 suspension rotin ; 3 table ronde, bois ; 4 passe_plat ; 5 chaise ; 6 porte ; 7 chaise ; 8 porte ; "
                           "9 autre foyer carrelé de la cheminée ; 10 faux",
                 "sol": "lames",
                 "manquants": "radiateur 0,600,215,790 ; etagere_murale 0,190,235,570 ; cheminee 1085,490,1206,792"},
    "photo-03": {"objets": "1 rideaux ; 2 meuble_tv banc bas, bois clair ; 3 television ; 4 cheminee ; 5 suspension rotin ; "
                           "6 autre foyer carrelé de la cheminée ; 7 passe_plat ; 8 table ronde, bois ; 9 chaise ; 10 chaise ; "
                           "11 colonne_cuisine vue à travers le passe-plat ; 12 = 11 ; 13 = 5",
                 "sol": "lames", "manquants": "canape 0,660,250,803 bleu"},
    "photo-04": {"objets": "1 cheminee ; 2 canape bleu ; 3 lit ; 4 autre foyer carrelé de la cheminée ; 5 chaise ; 6 porte_fenetre ; "
                           "7 suspension rotin ; 8 suspension dans la chambre ; 9 rideaux ; 10 meuble_tv banc bas, bois clair ; "
                           "11 television ; 12 table_de_chevet ; 13 lampe",
                 "sol": "lames"},
    "photo-05": {"objets": "1 meuble_cuisine_haut blanc ; 2 colonne_cuisine grand placard en bois, deux portes ; 3 meuble_cuisine_bas plan de travail bois ; "
                           "4 meuble_cuisine_bas blanc {g=coin d=coin} ; 5 tapis chevrons, gris ; 6 fenetre sur allège ; 7 = 2 ; 8 autre ; 9 = 6 ; "
                           "10 = 4 ; 11 meuble_cuisine_bas blanc, sous l'évier, le long du mur de droite ; 12 applique ; 13 meuble_cuisine_haut blanc ; 14 = 4 ; 15 faux ; 16 faux ; 17 faux",
                 "sol": "carreaux",
                 # sous la fenêtre : les meubles bas blancs, d'un mur à l'autre ; mur de droite : le meuble de l'évier, de l'angle
                 # jusqu'au pilier blanc ; passé le pilier, le grand placard en bois à deux portes (une largeur et demie), puis le
                 # mur nu. Le banc (3) et son meuble haut, encore plus à droite, sont dans l'entrée : pas dits.
                 "rangees": "vers6 : coin bas*(4) coin ; droite6 : angle bas*(11) coin ; droite6+1 : coin colonnex1.5(2) cadre"},
    "photo-06": {"objets": "1 meuble_cuisine_bas blanc ; 2 electromenager four encastré ; 3 passe_plat ; 4 evier ; 5 colonne_cuisine blanc ; "
                           "6 meuble_cuisine_haut blanc ; 7 rangement meuble bas blanc à deux portes, sous le passe-plat ; "
                           "8 suspension noire ; 9 suspension rotin, celle du séjour vue à travers le passe-plat"},
    "photo-07": {"objets": "1 placard armoire blanche à portes coulissantes, dans la chambre ; 2 canape bleu ; 3 suspension rotin ; "
                           "4 cheminee ; 5 chaise ; 6 rideaux ; 7 etagere_murale niche à étagères",
                 "sol": "lames", "manquants": "porte_fenetre 135,225,335,575"},
    "photo-08": {"objets": "1 canape bleu ; 2 cheminee ; 3 suspension rotin ; 4 table ronde, bois ; 5 chaise ; "
                           "6 autre foyer carrelé de la cheminée ; 7 passe_plat ; 8 chaise ; 9 porte ; 10 faux",
                 "sol": "lames", "manquants": "porte 385,240,440,560"},
    "photo-09": {"objets": "1 lit ; 2 porte_fenetre ; 3 rideaux ; 4 suspension ; 5 rangement meuble bas blanc {entier pied} ; "
                           "6 chaise celle du séjour, vue par la porte ; 7 lampe",
                 "sol": "point_de_hongrie", "manquants": "radiateur 615,490,665,570"},
    "photo-10": {"objets": "1 placard grande armoire blanche, portes coulissantes et tiroirs ; 2 lit ; 3 rangement meuble bas blanc {g=cadre} ; "
                           "4 rideaux gris ; 5 suspension ; 6 table_de_chevet blanche ; 7 lampe rotin ; 8 table_de_chevet",
                 "sol": "point_de_hongrie", "manquants": "porte_fenetre 155,230,330,545"},
    "photo-11": {"objets": "1 autre paroi vitrée de la baignoire ; 2 baignoire ; 3 wc ; 4 = 3 ; 5 autre pommeau de douche",
                 "sol": "carreaux", "manquants": "porte_fenetre 285,205,500,600 vitrage dépoli, garde-corps ; radiateur 225,175,270,700 sèche-serviettes"},
    "photo-12": {"objets": "1 lit ; 2 rideaux ; 3 table ronde, celle du séjour ; 4 porte_fenetre ; 5 suspension ; "
                           "6 chaise celle du séjour ; 7 rangement meuble bas blanc {entier pied} ; 8 faux",
                 "sol": "point_de_hongrie", "manquants": "radiateur 750,490,805,570"},
    "photo-13": {"objets": "1 lit ; 2 rideaux ; 3 etagere_murale niche à étagères encastrée ; "
                           "4 placard armoire blanche à deux portes et tiroirs ; 5 table_de_chevet ; 6 suspension ; 7 table_de_chevet",
                 "sol": "point_de_hongrie"},
}
