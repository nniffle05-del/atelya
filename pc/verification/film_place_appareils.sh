#!/usr/bin/env bash
# LA PLACE DES APPAREILS DES PHOTOS (24/11/2026) : le film regardé depuis la place des photos, avec les appareils d'Atelya
# AVANT (le calage sans affinage) et APRÈS (appareils affinés dans l'image).
#
#     bash pc/verification/film_place_appareils.sh [app-004 app-004-seul app-002 app-001]
#
# app-004       la maquette REFAITE avec les nouveaux appareils (meubles posés depuis eux), importée sous un nom nouveau, puis
#               filmée depuis les appareils affinés avec les lignes lues des fenêtres (la configuration du lancement : Claude lit
#               les photos). « Avant » = les vues du 23/11 (..\atelya\b2\lumiere-film\hauteur-baies\app-004, maquette v11).
# app-004-seul  la même maquette, filmée depuis les appareils affinés par Atelya SEUL (sans les lignes lues) ;
# app-002, app-001 : les maquettes d'hier, inchangées (construites avec les appareils relevés à la main), filmées depuis les
#               appareils d'Atelya avant (« service ») et après (« defaut » : Atelya seul) : jamais filmées ainsi jusqu'ici.
# Entrées : le banc officiel de la chaîne (..\atelya\lectures-photos\place-appareils\chaine\app-004\c\) et les fiches du banc
# des appareils au format de service (..\atelya\b2\place-appareils\fiches\, pc/essais-place-appareils/chaine.py).
# Sorties : ..\atelya\b2\lumiere-film\place-appareils\<variante>\<logement>\vue-<photo>.png.
# Éditeur Unreal FERMÉ ; NE RIEN LANCER DE LOURD pendant le tournage. 10 à 20 min par vue. S'arrête au premier plantage.
set -u
cd "$(dirname "$0")/../.."
PY=../atelya/.venv/Scripts/python.exe
export PYTHONIOENCODING=utf-8
B=../atelya/b2/film-contre-photos
F=../atelya/b2/place-appareils/fiches
S=../atelya/b2/lumiere-film/place-appareils
L=../atelya/lectures-photos
C4=$L/place-appareils/chaine/app-004/c
CAS="${*:-app-004 app-004-seul app-002 app-001}"
mkdir -p "$S" "$L/place-appareils/app-004"

filmer() {  # <variante> <logement> <dossier 3d> <nom Unreal> <paquet> <logement meublé> <fiche> "<photos>"
  local v="$1" cas="$2" d3="$3" nom="$4" paquet="$5" log="$6" fiche="$7" photos="$8" a_faire=""
  for p in $photos; do [ -f "$S/$v/$cas/vue-$p.png" ] || a_faire="$a_faire $p"; done
  [ -z "$a_faire" ] && { echo "déjà tourné : $v $cas"; return 0; }
  [ -f "$fiche" ] || { echo "PLANTÉ : fiche introuvable : $fiche"; exit 1; }
  # shellcheck disable=SC2086
  $PY outils/unreal/vues_photos_unreal.py "$d3" "$nom" "$fiche" "$S/$v/$cas" --photos $a_faire --paquet "$paquet" --sans-import --logement "$log" \
    || { echo "PLANTÉ : vues de $cas ($v)"; exit 1; }
  echo "vues prêtes : $v $cas ($a_faire)"
}

for cas in $CAS; do
  case "$cas" in
    app-004)
      D3=$B/app-004-v12-3d
      cp "$C4/logement-meuble.json" "$L/place-appareils/app-004/logement-meuble.json" || { echo "PLANTÉ : logement d'app-004 introuvable"; exit 1; }
      cp "$C4/vitrages.json" "$L/place-appareils/app-004/vitrages.json"
      cp "$C4/cameras-photos-affinees.json" "$L/place-appareils/app-004/cameras-photos-affinees.json" || { echo "PLANTÉ : fiche affinée d'app-004 introuvable"; exit 1; }
      if [ ! -f "$D3/maquette.blend" ]; then
        $PY -m moteur.construire "$L/place-appareils/app-004/logement-meuble.json" "$D3" --sans-images > "$L/place-appareils/app-004/construire.log" 2>&1 \
          || { echo "PLANTÉ : maquette d'app-004 (voir $L/place-appareils/app-004/construire.log)"; exit 1; }
      fi
      [ -f "$D3/maquette.blend" ] || { echo "PLANTÉ : pas de maquette pour app-004"; exit 1; }
      echo "maquette d'app-004 prête : $D3"
      if [ ! -f "$S/lus/app-004/vue-photo-11.png" ]; then
        FICHE_PHOTOS="$L/place-appareils/app-004/cameras-photos-affinees.json" bash pc/verification/vues_rideaux.sh place-appareils/lus app-004 \
          "$D3" parquet004n "$L/place-appareils/app-004/logement-meuble.json" "photo-09 photo-10 photo-12 photo-01 photo-07 photo-11" \
          > "$L/place-appareils/app-004/vues.log" 2>&1 || { echo "PLANTÉ : vues d'app-004 (voir $L/place-appareils/app-004/vues.log)"; tail -5 "$L/place-appareils/app-004/vues.log"; exit 1; }
      fi
      echo "vues d'app-004 prêtes" ;;
    app-004-seul)
      filmer seul app-004 $B/app-004-v12-3d parquet004n $B/app-004-v12/paquet "$L/place-appareils/app-004/logement-meuble.json" \
        ../atelya/b2/app-004/chaine-v3/cameras-photos-seul.json "photo-09 photo-10" ;;
    app-002)
      for v in service defaut; do
        filmer $v app-002 $B/app-002-v3-3d parquet002d $B/app-002-v3/paquet $L/dessin-fenetres/app-002/logement-meuble.json "$F/app-002-$v.json" "photo-01 photo-14"
      done ;;
    app-001)
      for v in service defaut; do
        filmer $v app-001 $B/app-001-v11-3d parquet001l $B/app-001-v11/paquet $L/hauteur-baies/app-001/logement-meuble.json "$F/app-001-$v.json" "photo-06 photo-10"
      done ;;
    *) echo "PLANTÉ : cas inconnu : $cas"; exit 1 ;;
  esac
done
echo "code=0"
