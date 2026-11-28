#!/usr/bin/env bash
# L'APPAREIL DANS UN MEUBLE, point 1, TOURNAGE DE CONFIRMATION (28/11/2026 : lit tête au bon mur, colonne plus en double, une seule suspension au séjour, appareil de la photo 05 repris sur la fenêtre lue et les éléments de cuisine) : les côtés ouverts entre pièces (ATELYA_COTES_OUVERTS=1). Seul app-004 change
# (cuisine ouverte sur l'entrée) : le photographe de la photo 05 est cherché aussi dans l'entrée, le regard passe le côté
# ouvert. Le logement refait par la chaîne avec ces appareils (pc/essais-place-appareils/chaine.py ouverts --cas app-004 :
# ..\atelya\b2\place-appareils\chaine\ouverts\app-004\c\) est rangé dans ..\atelya\lectures-photos\cotes-ouverts\app-004\,
# sa maquette reconstruite (app-004-v18-3d), importée dans Unreal sous un nom NOUVEAU (parquet004t), puis filmée depuis la
# place des deux photos de cuisine et de deux témoins.
#
#     powershell -File pc\verification\lancer_detache.ps1 pc/verification/film_cotes_ouverts_3.sh ..\atelya\b2\lumiere-film\cotes-ouverts-3\tournage.log
#
# « Avant » : ..\atelya\b2\lumiere-film\sol-au-calage\apres\app-004 (maquette v15 : photos 05, 06, 13) et
# ..\atelya\b2\lumiere-film\place-appareils\lus\app-004 (maquette v13 : photo 07, le séjour) ; premier tournage (lit tourné,
# colonne en double) : ..\atelya\b2\lumiere-film\cotes-ouverts\apres\app-004.
# Sorties : ..\atelya\b2\lumiere-film\cotes-ouverts-3\apres\app-004\vue-<photo>.png.
# Éditeur Unreal FERMÉ ; NE RIEN LANCER DE LOURD pendant le tournage. S'arrête au premier plantage ; reprend où il en était.
set -u
cd "$(dirname "$0")/../.."
PY=../atelya/.venv/Scripts/python.exe
export PYTHONIOENCODING=utf-8
export ATELYA_COTES_OUVERTS=1
B=../atelya/b2/film-contre-photos
S=../atelya/b2/lumiere-film/cotes-ouverts-3
L=../atelya/lectures-photos
C=../atelya/b2/place-appareils/chaine/ouverts/app-004/c
ICI=$L/cotes-ouverts-3/app-004
PHOTOS="photo-05 photo-06 photo-13 photo-07"
mkdir -p "$S" "$ICI"

a_faire=""
for p in $PHOTOS; do [ -f "$S/apres/app-004/vue-$p.png" ] || a_faire="$a_faire $p"; done
[ -z "$a_faire" ] && { echo "déjà tourné : app-004"; echo "code=0"; exit 0; }
for f in logement-meuble.json vitrages.json cameras-photos-affinees.json; do
  cp "$C/$f" "$ICI/$f" || { echo "PLANTÉ : $f d'app-004 introuvable dans $C"; exit 1; }
done
D3=$B/app-004-v18-3d
if [ ! -f "$D3/maquette.blend" ]; then
  $PY -m moteur.construire "$ICI/logement-meuble.json" "$D3" --sans-images > "$ICI/construire.log" 2>&1 \
    || { echo "PLANTÉ : maquette d'app-004 (voir $ICI/construire.log)"; exit 1; }
fi
[ -f "$D3/maquette.blend" ] || { echo "PLANTÉ : pas de maquette pour app-004"; exit 1; }
echo "maquette d'app-004 prête : $D3 ($(date +%H:%M))"
# shellcheck disable=SC2086
FICHE_PHOTOS="$ICI/cameras-photos-affinees.json" bash pc/verification/vues_rideaux.sh cotes-ouverts-3/apres app-004 "$D3" parquet004t \
  "$ICI/logement-meuble.json" "$a_faire" > "$ICI/vues.log" 2>&1 \
  || { echo "PLANTÉ : vues d'app-004 (voir $ICI/vues.log)"; tail -5 "$ICI/vues.log"; exit 1; }
echo "vues d'app-004 prêtes ($(date +%H:%M))"
echo "code=0"
