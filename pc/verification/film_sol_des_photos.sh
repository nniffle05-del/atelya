#!/usr/bin/env bash
# LE SOL PRIS POUR UN LIT (25/11/2026) : les trois maquettes REFAITES avec le vrai sol et le vrai plafond du relief des photos
# (moteur.caler_photos.sol_et_plafond), passées dans le film et regardées depuis la place des photos des pièces qui changent.
#
#     bash pc/verification/film_sol_des_photos.sh [avant app-004 app-002 app-001]
#
# avant    les deux vues « avant » qui n'avaient jamais été tournées (séjour d'app-001 photo 03, chambre d'app-004 photo 13),
#          sur les maquettes de la veille, sans réimport ; les autres « avant » existent déjà :
#          app-001 photo 01 : ..\atelya\b2\lumiere-film\hauteur-baies\app-001 ; app-002 photos 14, 15 : …\fenetres-dessin\app-002 ;
#          app-004 photos 09, 10 : …\place-appareils\lus\app-004.
# app-00x  le logement refait par la chaîne (..\atelya\b2\sol-des-photos\chaine\apres\<logement>\c\, pc/verification/ab_sol_des_photos.sh)
#          est rangé dans ..\atelya\lectures-photos\sol-des-photos\<logement>\, sa maquette reconstruite, importée dans Unreal sous
#          un nom NOUVEAU (app-001-v12-3d / parquet001m, app-002-v4-3d / parquet002e, app-004-v14-3d / parquet004p), puis filmée.
# Sorties : ..\atelya\b2\lumiere-film\sol-des-photos\{avant,apres}\<logement>\vue-<photo>.png.
# Éditeur Unreal FERMÉ ; NE RIEN LANCER DE LOURD pendant le tournage ; veille : pc/verification/veille_tournage.sh. S'arrête au premier plantage.
set -u
cd "$(dirname "$0")/../.."
PY=../atelya/.venv/Scripts/python.exe
export PYTHONIOENCODING=utf-8
B=../atelya/b2/film-contre-photos
S=../atelya/b2/lumiere-film/sol-des-photos
L=../atelya/lectures-photos
C=../atelya/b2/sol-des-photos/chaine/apres
AFFINEES=$L/place-appareils/app-004/cameras-photos-affinees.json
CAS="${*:-avant app-004 app-002 app-001}"
mkdir -p "$S"

refaire() {  # <logement> <dossier 3d> <nom Unreal nouveau> "<photos>" [fiche]
  local cas="$1" d3="$2" nom="$3" photos="$4" fiche="${5-}" a_faire=""
  for p in $photos; do [ -f "$S/apres/$cas/vue-$p.png" ] || a_faire="$a_faire $p"; done
  [ -z "$a_faire" ] && { echo "déjà tourné : $cas"; return 0; }
  mkdir -p "$L/sol-des-photos/$cas"
  cp "$C/$cas/c/logement-meuble.json" "$L/sol-des-photos/$cas/logement-meuble.json" || { echo "PLANTÉ : logement de $cas introuvable"; exit 1; }
  [ -f "$C/$cas/c/vitrages.json" ] && cp "$C/$cas/c/vitrages.json" "$L/sol-des-photos/$cas/vitrages.json"
  if [ ! -f "$d3/maquette.blend" ]; then
    $PY -m moteur.construire "$L/sol-des-photos/$cas/logement-meuble.json" "$d3" --sans-images > "$L/sol-des-photos/$cas/construire.log" 2>&1 \
      || { echo "PLANTÉ : maquette de $cas (voir $L/sol-des-photos/$cas/construire.log)"; exit 1; }
  fi
  [ -f "$d3/maquette.blend" ] || { echo "PLANTÉ : pas de maquette pour $cas"; exit 1; }
  echo "maquette de $cas prête : $d3 ($(date +%H:%M))"
  # shellcheck disable=SC2086
  FICHE_PHOTOS="$fiche" bash pc/verification/vues_rideaux.sh sol-des-photos/apres "$cas" "$d3" "$nom" "$L/sol-des-photos/$cas/logement-meuble.json" "$a_faire" \
    > "$L/sol-des-photos/$cas/vues.log" 2>&1 || { echo "PLANTÉ : vues de $cas (voir $L/sol-des-photos/$cas/vues.log)"; tail -5 "$L/sol-des-photos/$cas/vues.log"; exit 1; }
  echo "vues de $cas prêtes ($(date +%H:%M))"
}

for cas in $CAS; do
  case "$cas" in
    avant)
      [ -f "$S/avant/app-001/vue-photo-03.png" ] || $PY outils/unreal/vues_photos_unreal.py $B/app-001-v11-3d parquet001l verites/app-001/cameras-photos.json "$S/avant/app-001" \
        --photos photo-03 --paquet $B/app-001-v11/paquet --sans-import --logement $L/hauteur-baies/app-001/logement-meuble.json || { echo "PLANTÉ : vue « avant » d'app-001"; exit 1; }
      [ -f "$S/avant/app-004/vue-photo-13.png" ] || $PY outils/unreal/vues_photos_unreal.py $B/app-004-v13-3d parquet004o "$AFFINEES" "$S/avant/app-004" \
        --photos photo-13 --paquet $B/app-004-v13/paquet --sans-import --logement $L/place-appareils/app-004/logement-meuble.json || { echo "PLANTÉ : vue « avant » d'app-004"; exit 1; }
      echo "vues « avant » prêtes ($(date +%H:%M))" ;;
    app-004) refaire app-004 $B/app-004-v14-3d parquet004p "photo-09 photo-13 photo-10" "$AFFINEES" ;;
    app-002) refaire app-002 $B/app-002-v4-3d parquet002e "photo-14 photo-15" ;;
    app-001) refaire app-001 $B/app-001-v12-3d parquet001m "photo-01 photo-03" ;;
    *) echo "PLANTÉ : cas inconnu : $cas"; exit 1 ;;
  esac
done
echo "code=0"
