#!/usr/bin/env bash
# RIDEAUX, 2e TEMPS, ÉTAPE (b) (23/11/2026) : les rideaux à leur largeur, jugés QUAND LA CAMÉRA BOUGE. Trois plans de 6 s tournés
# depuis la place d'une photo (la caméra avance de 40 cm et tourne de 60°), montés hier | aujourd'hui.
#
#     bash pc/verification/mouvement_largeur_pans.sh
#
# « Hier » : app-004 = les plans du 21/11 (ferronnerie, niveau parquet004h), déjà tournés ; app-001 = le niveau parquet001g
# (20/11, pans de 45 cm), tourné ici. « Aujourd'hui » : parquet004j et parquet001i (film_largeur_pans.sh, à lancer avant).
# Sorties : ..\atelya\b2\lumiere-film\rideaux-largeur\mouvement\*-avant-apres.mp4. Éditeur Unreal FERMÉ. ~30 min.
# S'arrête au premier plantage.
set -u
cd "$(dirname "$0")/../.."
PY=../atelya/.venv/Scripts/python.exe
export PYTHONIOENCODING=utf-8
B=../atelya/b2/film-contre-photos
L=../atelya/lectures-photos
S=../atelya/b2/lumiere-film/rideaux-largeur/mouvement
HIER=../atelya/b2/lumiere-film/ferronnerie/mouvement
F4=../atelya/b2/app-004/chaine-v2/cameras-photos-seul.json
F1=verites/app-001/cameras-photos.json
mkdir -p "$S"

plan() {  # <paquet> <nom Unreal> <fiche> <photo> <logement> <dossier de sortie>
  [ -f "$6/image-0100.png" ] && { echo "déjà tourné : $6"; return 0; }
  $PY pc/verification/panoramique_lumiere.py "$1" "$2" "$3" "$4" "$6" --logement "$5" \
    || { echo "PLANTÉ : plan $2 $4"; exit 1; }
}

monter() {  # <sortie.mp4> <dossier hier> <dossier aujourd'hui>
  $PY pc/verification/film_cote_a_cote.py "$1" "hier=$2" "aujourd'hui (rideaux a leur largeur)=$3" \
    || { echo "PLANTÉ : montage $1"; exit 1; }
}

plan $B/app-004-v8/paquet parquet004j $F4 photo-12 $L/rideaux-largeur/app-004/logement-meuble.json "$S/app-004-photo-12"
monter "$S/app-004-photo-12-avant-apres.mp4" "$HIER/apres-photo-12" "$S/app-004-photo-12"
plan $B/app-004-v8/paquet parquet004j $F4 photo-01 $L/rideaux-largeur/app-004/logement-meuble.json "$S/app-004-photo-01"
monter "$S/app-004-photo-01-avant-apres.mp4" "$HIER/apres-photo-01" "$S/app-004-photo-01"
plan $B/app-001-v6/paquet parquet001g $F1 photo-08 $L/fenetres-f1/chaine/app-001/c/logement-meuble.json "$S/app-001-photo-08-hier"
plan $B/app-001-v8/paquet parquet001i $F1 photo-08 $L/rideaux-largeur/app-001/logement-meuble.json "$S/app-001-photo-08"
monter "$S/app-001-photo-08-avant-apres.mp4" "$S/app-001-photo-08-hier" "$S/app-001-photo-08"
echo "FAIT : $S"
