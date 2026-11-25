#!/usr/bin/env bash
# RIDEAUX, 2e TEMPS, ÉTAPE (c) (23/11/2026) : la tringle à sa couleur et à sa hauteur, jugée QUAND LA CAMÉRA BOUGE. Deux plans de
# 6 s tournés depuis la place d'une photo (la caméra avance de 40 cm et tourne de 60°), montés hier | aujourd'hui.
#
#     bash pc/verification/mouvement_tringle.sh
#
# « Hier » : les plans du 23/11 au matin (étape b, niveaux parquet004j et parquet001i), déjà tournés.
# « Aujourd'hui » : parquet004l et parquet001k (film_tringle.sh, à lancer avant).
# Sorties : ..\atelya\b2\lumiere-film\tringle\mouvement\*-avant-apres.mp4. Éditeur Unreal FERMÉ ; rien de lourd à côté. ~25 min.
# S'arrête au premier plantage.
set -u
cd "$(dirname "$0")/../.."
PY=../atelya/.venv/Scripts/python.exe
export PYTHONIOENCODING=utf-8
B=../atelya/b2/film-contre-photos
L=../atelya/lectures-photos/tringle
S=../atelya/b2/lumiere-film/tringle/mouvement
HIER=../atelya/b2/lumiere-film/rideaux-largeur/mouvement
F4=../atelya/b2/app-004/chaine-v2/cameras-photos-seul.json
F1=verites/app-001/cameras-photos.json
mkdir -p "$S"

plan() {  # <paquet> <nom Unreal> <fiche> <photo> <logement> <dossier de sortie>
  [ -f "$6/image-0100.png" ] && { echo "déjà tourné : $6"; return 0; }
  $PY pc/verification/panoramique_lumiere.py "$1" "$2" "$3" "$4" "$6" --logement "$5" \
    || { echo "PLANTÉ : plan $2 $4"; exit 1; }
}

monter() {  # <sortie.mp4> <dossier hier> <dossier aujourd'hui>
  $PY pc/verification/film_cote_a_cote.py "$1" "hier=$2" "aujourd'hui (la tringle vue sur la photo)=$3" \
    || { echo "PLANTÉ : montage $1"; exit 1; }
}

plan $B/app-004-v10/paquet parquet004l $F4 photo-12 $L/app-004/logement-meuble.json "$S/app-004-photo-12"
monter "$S/app-004-photo-12-avant-apres.mp4" "$HIER/app-004-photo-12" "$S/app-004-photo-12"
plan $B/app-001-v10/paquet parquet001k $F1 photo-08 $L/app-001/logement-meuble.json "$S/app-001-photo-08"
monter "$S/app-001-photo-08-avant-apres.mp4" "$HIER/app-001-photo-08" "$S/app-001-photo-08"
echo "FAIT : $S"
