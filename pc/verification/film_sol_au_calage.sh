#!/usr/bin/env bash
# LE SOL PRIS POUR UN LIT, 2e TEMPS (26/11/2026) : le vrai sol du relief pris AUSSI par le calage des photos et par l'affinage des
# appareils (ATELYA_SOL_JUSTE_AU_CALAGE=1). Seul app-004 change dans le film (ses appareils sont calés par Atelya ; ceux d'app-001
# et d'app-002 sont relevés à la main) : sa maquette REFAITE avec les nouveaux appareils, importée sous un nom NOUVEAU, puis
# regardée depuis la place des photos dont l'appareil a bougé (cuisine photo 06, chambre photos 13 et 09) et de deux témoins.
#
#     powershell -File pc\verification\lancer_detache.ps1 pc/verification/film_sol_au_calage.sh ..\atelya\b2\lumiere-film\sol-au-calage\tournage.log
#     (ou : bash pc/verification/film_sol_au_calage.sh [avant apres])
#
# avant   la vue de la cuisine (photo 06) jamais tournée sur la maquette de la veille (app-004-v14-3d / parquet004p), depuis
#         l'appareil de la veille, sans réimport ; les autres « avant » existent : ..\atelya\b2\lumiere-film\sol-des-photos\apres\app-004
#         (photos 09, 10, 13).
# apres   le logement refait par la chaîne avec les appareils du nouveau calage (pc/essais-place-appareils/chaine.py sol-partout :
#         ..\atelya\b2\place-appareils\chaine\sol-partout\app-004\c\) est rangé dans ..\atelya\lectures-photos\sol-au-calage\app-004\,
#         sa maquette reconstruite (app-004-v15-3d), importée dans Unreal (parquet004q), puis filmée.
# Sorties : ..\atelya\b2\lumiere-film\sol-au-calage\{avant,apres}\app-004\vue-<photo>.png.
# Éditeur Unreal FERMÉ ; NE RIEN LANCER DE LOURD pendant le tournage. S'arrête au premier plantage ; reprend où il en était.
set -u
cd "$(dirname "$0")/../.."
PY=../atelya/.venv/Scripts/python.exe
export PYTHONIOENCODING=utf-8
export ATELYA_SOL_JUSTE_AU_CALAGE=1
B=../atelya/b2/film-contre-photos
S=../atelya/b2/lumiere-film/sol-au-calage
L=../atelya/lectures-photos
C=../atelya/b2/place-appareils/chaine/sol-partout/app-004/c
ICI=$L/sol-au-calage/app-004
PHOTOS="photo-06 photo-13 photo-09 photo-10 photo-05"
CAS="${*:-avant apres}"
mkdir -p "$S" "$ICI"

for cas in $CAS; do
  case "$cas" in
    avant)
      for p in photo-06 photo-05; do
        [ -f "$S/avant/app-004/vue-$p.png" ] && continue
        $PY outils/unreal/vues_photos_unreal.py $B/app-004-v14-3d parquet004p $L/place-appareils/app-004/cameras-photos-affinees.json "$S/avant/app-004" \
          --photos $p --paquet $B/app-004-v14/paquet --sans-import --logement $L/sol-des-photos/app-004/logement-meuble.json \
          || { echo "PLANTÉ : vue « avant » d'app-004 ($p)"; exit 1; }
      done
      echo "vues « avant » prêtes ($(date +%H:%M))" ;;
    apres)
      a_faire=""
      for p in $PHOTOS; do [ -f "$S/apres/app-004/vue-$p.png" ] || a_faire="$a_faire $p"; done
      [ -z "$a_faire" ] && { echo "déjà tourné : app-004"; continue; }
      for f in logement-meuble.json vitrages.json cameras-photos-affinees.json; do
        cp "$C/$f" "$ICI/$f" || { echo "PLANTÉ : $f d'app-004 introuvable dans $C"; exit 1; }
      done
      D3=$B/app-004-v15-3d
      if [ ! -f "$D3/maquette.blend" ]; then
        $PY -m moteur.construire "$ICI/logement-meuble.json" "$D3" --sans-images > "$ICI/construire.log" 2>&1 \
          || { echo "PLANTÉ : maquette d'app-004 (voir $ICI/construire.log)"; exit 1; }
      fi
      [ -f "$D3/maquette.blend" ] || { echo "PLANTÉ : pas de maquette pour app-004"; exit 1; }
      echo "maquette d'app-004 prête : $D3 ($(date +%H:%M))"
      # shellcheck disable=SC2086
      FICHE_PHOTOS="$ICI/cameras-photos-affinees.json" bash pc/verification/vues_rideaux.sh sol-au-calage/apres app-004 "$D3" parquet004q \
        "$ICI/logement-meuble.json" "$a_faire" > "$ICI/vues.log" 2>&1 \
        || { echo "PLANTÉ : vues d'app-004 (voir $ICI/vues.log)"; tail -5 "$ICI/vues.log"; exit 1; }
      echo "vues d'app-004 prêtes ($(date +%H:%M))" ;;
    *) echo "PLANTÉ : cas inconnu : $cas"; exit 1 ;;
  esac
done
echo "code=0"
