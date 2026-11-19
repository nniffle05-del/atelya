#!/usr/bin/env bash
# RIDEAUX, 2e TEMPS (19/11/2026) : une maquette REFAITE (ses rideaux ont changé) passe dans le film, puis on la regarde depuis la
# place des photos qui montrent ses rideaux, à côté de la photo du client.
#
#     bash pc/verification/vues_rideaux.sh <nom de l'essai> <logement> <dossier 3d> <nom Unreal NOUVEAU> <logement-meuble.json> "<photos>"
#     ex. bash pc/verification/vues_rideaux.sh pans app-004 ../atelya/b2/film-contre-photos/app-004-v4-3d parquet004e \
#             ../atelya/lectures-photos/rideaux-pans/chaine/app-004/c/logement-meuble.json "photo-01 photo-07 photo-09"
#
# 1. le paquet pour Unreal est refait à côté de la maquette (<dossier 3d sans « -3d »>/paquet) ;
# 2. la maquette est importée dans Unreal sous le nom donné (un nom NOUVEAU : l'ancien niveau reste pour comparer) ;
# 3. le film tourne une image depuis la place de chaque photo, avec le décor du film entier (vue par les fenêtres, ciel).
# Sorties : ..\atelya\b2\lumiere-film\<essai>\<logement>\ . Éditeur Unreal FERMÉ. ~5 min par vue. S'arrête au premier plantage.
set -u
cd "$(dirname "$0")/../.."
PY=../atelya/.venv/Scripts/python.exe
export PYTHONIOENCODING=utf-8
ESSAI="$1"; CAS="$2"; D3="$3"; NOM="$4"; LOG="$5"; PHOTOS="$6"; shift 6
SORTIE=../atelya/b2/lumiere-film/$ESSAI/$CAS
PAQUET="${D3%-3d}/paquet"
FICHE=verites/$CAS/cameras-photos.json
[ "$CAS" = app-004 ] && FICHE=../atelya/b2/app-004/chaine-v2/cameras-photos-seul.json
for f in "$D3/maquette.blend" "$LOG" "$FICHE"; do
  [ -f "$f" ] || { echo "PLANTÉ : introuvable : $f"; exit 1; }
done
if [ ! -f "$PAQUET/scene-atelya.json" ]; then
  $PY outils/unreal/exporter_pour_unreal.py "$D3" "$PAQUET" || { echo "PLANTÉ : paquet pour Unreal de $CAS"; exit 1; }
fi
IMPORT=""
[ -n "${SANS_IMPORT-}" ] && IMPORT="--sans-import"
# shellcheck disable=SC2086
$PY outils/unreal/vues_photos_unreal.py "$D3" "$NOM" "$FICHE" "$SORTIE" --photos $PHOTOS --paquet "$PAQUET" --logement "$LOG" $IMPORT "$@" \
  || { echo "PLANTÉ : vues de $CAS (essai $ESSAI)"; exit 1; }
echo "FAIT : $SORTIE"
