#!/usr/bin/env bash
# UNE VUE PAR FENÊTRE (18-19/11/2026) : plans EN MOUVEMENT avant / après, depuis la place de photos qui regardent dehors
# (le produit est le film : une vue juste à l'arrêt doit tenir quand la caméra avance et tourne).
#
#     bash pc/verification/mouvement_vue_par_fenetre.sh <dossier de sortie>
#
# « avant » = la toile commune seule (ATELYA_VUE_PAR_FENETRE=0), « après » = une vue par fenêtre (défaut).
# Éditeur Unreal FERMÉ. S'arrête au premier plantage.
set -u
cd "$(dirname "$0")/../.."
PY=../atelya/.venv/Scripts/python.exe
SORTIE="$1"
B=../atelya/b2/film-contre-photos
C3=../atelya/lectures-photos/parquet-sur-mesure/chaine-3

plan() {  # <logement> <nom Unreal> <fiche> <photo> <avant|apres>
  local cas="$1" nom="$2" fiche="$3" photo="$4" quand="$5"
  local drapeau=1; [ "$quand" = "avant" ] && drapeau=0
  local log="$C3/$cas/c/logement-meuble.json" paquet="$B/$cas-v2/paquet"
  if [ "$cas" = app-001 ]; then  # refait le 19/11/2026 avec les voilages des deux chambres
    log=../atelya/lectures-photos/voilages/chaine/app-001/c/logement-meuble.json; paquet="$B/app-001-v3/paquet"
  fi
  ATELYA_VUE_PAR_FENETRE=$drapeau $PY pc/verification/panoramique_lumiere.py "$paquet" "$nom" "$fiche" "$photo" \
    "$SORTIE/$cas-$photo-$quand" --logement "$log" \
    || { echo "PLANTÉ : plan $cas $photo $quand"; exit 1; }
}

monter() {  # <logement> <photo>
  $PY pc/verification/film_cote_a_cote.py "$SORTIE/$1-$2-avant-apres.mp4" \
    "avant (une seule toile)=$SORTIE/$1-$2-avant" "apres (une vue par fenetre)=$SORTIE/$1-$2-apres" \
    || { echo "PLANTÉ : montage $1 $2"; exit 1; }
}

plan app-002 parquet002c verites/app-002/cameras-photos.json photo-14 avant
plan app-002 parquet002c verites/app-002/cameras-photos.json photo-14 apres
monter app-002 photo-14
plan app-001 parquet001d verites/app-001/cameras-photos.json photo-08 avant
plan app-001 parquet001d verites/app-001/cameras-photos.json photo-08 apres
monter app-001 photo-08
plan app-004 parquet004c ../atelya/b2/app-004/chaine-v2/cameras-photos-seul.json photo-09 avant
plan app-004 parquet004c ../atelya/b2/app-004/chaine-v2/cameras-photos-seul.json photo-09 apres
monter app-004 photo-09
echo "FINI : $SORTIE"
