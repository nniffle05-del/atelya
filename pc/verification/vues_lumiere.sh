#!/usr/bin/env bash
# POINT 2 (18/11/2026) : les mêmes vues « photo | film » des trois logements, tournées avec un essai de lumière ou de réglage,
# sur les maquettes DÉJÀ importées dans Unreal (rien n'est reconstruit ni réimporté), puis jugées (outils/unreal/juger_lumiere.py).
#
#     bash pc/verification/vues_lumiere.sh <nom de l'essai> [options du film…]
#     ex. bash pc/verification/vues_lumiere.sh ancien-ciel --reglage ciel_couvert=uni
#         VUES_001="photo-04" VUES_002="photo-01" VUES_004="photo-08" bash pc/verification/vues_lumiere.sh exact --moteur path_tracer
#
# Les vues sont tournées avec le DÉCOR du film entier (vraie vue par les fenêtres, balcons, vitre claire, ciel) ;
# SANS_DECOR=1 : comme avant le 18/11/2026 (pour comparer aux anciens essais).
# Sorties : ..\atelya\b2\lumiere-film\<essai>\app-00x\ (vues) et ..\atelya\b2\lumiere-film\<essai>\juge\ (chiffres, planches).
# Éditeur Unreal FERMÉ. S'arrête au premier plantage.
set -u
cd "$(dirname "$0")/../.."
PY=../atelya/.venv/Scripts/python.exe
ESSAI="$1"; shift
SORTIE=../atelya/b2/lumiere-film/$ESSAI
B=../atelya/b2/film-contre-photos
J3=../atelya/lectures-photos/parquet-sur-mesure/juges-3/images
C3=../atelya/lectures-photos/parquet-sur-mesure/chaine-3
VUES_001="${VUES_001-photo-01 photo-04 photo-07 photo-08 photo-10}"
VUES_002="${VUES_002-photo-01 photo-05 photo-07 photo-14}"  # photo-09 (cuisine) : appareil du film dans un meuble, écartée
VUES_004="${VUES_004-photo-02 photo-08 photo-09 photo-10}"

filmer() {  # <logement> <dossier 3d> <nom Unreal> <fiche des caméras> <paquet> <photos> [options]
  local cas="$1" d3="$2" nom="$3" fiche="$4" paquet="$5" photos="$6"; shift 6
  [ -z "$photos" ] && return 0
  local log="$C3/$cas/c/logement-meuble.json"
  # app-001 : logement refait le 19/11/2026 avec les voilages des deux chambres (lecture des photos corrigée)
  # (puis refait le 20/11/2026, étape F1 : fenêtre du coin repas élargie d'après les photos, maquette app-001-v6-3d / parquet001g)
  # (puis le 23/11/2026, rideaux étape b : chaque pan à la largeur vue sur les photos, tiré ou ouvert, rideau repoussé devant
  # son voilage : maquettes app-001-v8-3d / parquet001i et app-004-v8-3d / parquet004j, logements « rideaux-largeur » ;
  # 23/11/2026, étape c : la tringle vue sur les photos, maquettes app-001-v10-3d / parquet001k et app-004-v10-3d /
  # parquet004l, logements « tringle »)
  [ "$cas" = app-001 ] && log=../atelya/lectures-photos/tringle/app-001/logement-meuble.json
  # app-004 : refait de même le 19/11/2026 (rideaux de la collection calculée, couleur vue sur la photo ; puis un seul pan par
  # fenêtre, du côté vu sur les photos : maquettes app-001-v5-3d / parquet001f et app-004-v4-3d / parquet004e)
  # (puis le 20/11/2026, F2 pièce 3 : fenêtres construites d'après leur dessin lu sur les photos — partie pleine, vantaux, petits
  # bois, garde-corps : maquettes app-004-v5-3d / parquet004f et app-002-v3-3d / parquet002d, logements « dessin-fenetres »)
  # (puis le 21/11/2026 : ferronnerie des garde-corps recopiée des photos, maquette app-004-v7-3d / parquet004h, logement
  # « ferronnerie »)
  [ "$cas" = app-004 ] && log=../atelya/lectures-photos/tringle/app-004/logement-meuble.json
  [ "$cas" = app-002 ] && log=../atelya/lectures-photos/dessin-fenetres/app-002/logement-meuble.json
  local decor="--logement $log"
  [ -n "${SANS_DECOR-}" ] && decor=""
  # shellcheck disable=SC2086
  $PY outils/unreal/vues_photos_unreal.py "$d3" "$nom" "$fiche" "$SORTIE/$cas" --photos $photos --paquet "$paquet" --sans-import $decor "$@" \
    || { echo "PLANTÉ : vues de $cas (essai $ESSAI)"; exit 1; }
}

filmer app-001 $B/app-001-v10-3d parquet001k verites/app-001/cameras-photos.json $B/app-001-v10/paquet "$VUES_001" "$@"
filmer app-002 $B/app-002-v3-3d parquet002d verites/app-002/cameras-photos.json $B/app-002-v3/paquet "$VUES_002" "$@"
filmer app-004 $B/app-004-v10-3d parquet004l ../atelya/b2/app-004/chaine-v2/cameras-photos-seul.json $B/app-004-v10/paquet "$VUES_004" "$@"

VUES=""
for cas in app-001 app-002 app-004; do
  ls "$SORTIE/$cas"/vue-*.png >/dev/null 2>&1 && VUES="$VUES $cas=$SORTIE/$cas"
done
# shellcheck disable=SC2086
$PY outils/unreal/juger_lumiere.py "$SORTIE/juge" $VUES --sans app-002:photo-09 --titre "ESSAI $ESSAI : $*" || { echo "PLANTÉ : juge de la lumière (essai $ESSAI)"; exit 1; }
