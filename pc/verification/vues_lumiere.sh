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
  local decor="--logement $C3/$cas/c/logement-meuble.json"
  [ -n "${SANS_DECOR-}" ] && decor=""
  # shellcheck disable=SC2086
  $PY outils/unreal/vues_photos_unreal.py "$d3" "$nom" "$fiche" "$SORTIE/$cas" --photos $photos --paquet "$paquet" --sans-import $decor "$@" \
    || { echo "PLANTÉ : vues de $cas (essai $ESSAI)"; exit 1; }
}

filmer app-001 $B/app-001-v2-3d parquet001c verites/app-001/cameras-photos.json $B/app-001-v2/paquet "$VUES_001" "$@"
filmer app-002 $J3/app-002-apres-3d parquet002c verites/app-002/cameras-photos.json $B/app-002-v2/paquet "$VUES_002" "$@"
filmer app-004 $J3/app-004-apres-3d parquet004c ../atelya/b2/app-004/chaine-v2/cameras-photos-seul.json $B/app-004-v2/paquet "$VUES_004" "$@"

VUES=""
for cas in app-001 app-002 app-004; do
  ls "$SORTIE/$cas"/vue-*.png >/dev/null 2>&1 && VUES="$VUES $cas=$SORTIE/$cas"
done
# shellcheck disable=SC2086
$PY outils/unreal/juger_lumiere.py "$SORTIE/juge" $VUES --sans app-002:photo-09 --titre "ESSAI $ESSAI : $*" || { echo "PLANTÉ : juge de la lumière (essai $ESSAI)"; exit 1; }
