#!/usr/bin/env bash
# RIDEAUX, 2e TEMPS, ÉTAPE (b) (22/11/2026) : les maquettes d'app-004 et d'app-001 REFAITES avec la largeur de chaque pan vue sur
# les photos, puis regardées dans le film depuis la place des photos (pc/verification/vues_rideaux.sh).
#
#     bash pc/verification/film_largeur_pans.sh [app-004] [app-001]
#
# Entrée : les logements refaits par la chaîne (..\atelya\lectures-photos\rideaux-largeur\chaine\<logement>\c\).
# Sorties : maquettes ..\atelya\b2\film-contre-photos\app-004-v8-3d (niveau Unreal parquet004j) et app-001-v8-3d (parquet001i) ;
# vues ..\atelya\b2\lumiere-film\rideaux-largeur\<logement>\. Éditeur Unreal FERMÉ. ~1 h 30. S'arrête au premier plantage.
set -u
cd "$(dirname "$0")/../.."
PY=../atelya/.venv/Scripts/python.exe
export PYTHONIOENCODING=utf-8
L=../atelya/lectures-photos/rideaux-largeur
B=../atelya/b2/film-contre-photos
CAS="${*:-app-004 app-001}"

refaire() {  # <logement> <dossier 3d> <nom Unreal> "<photos>"
  local cas="$1" d3="$2" nom="$3" photos="$4"
  mkdir -p "$L/$cas"
  cp "$L/chaine/$cas/c/logement-meuble.json" "$L/$cas/logement-meuble.json" || { echo "PLANTÉ : logement de $cas introuvable"; exit 1; }
  [ -f "$L/chaine/$cas/c/vitrages.json" ] && cp "$L/chaine/$cas/c/vitrages.json" "$L/$cas/vitrages.json"
  if [ ! -f "$d3/maquette.blend" ]; then
    $PY -m moteur.construire "$L/$cas/logement-meuble.json" "$d3" --sans-images > "$L/$cas/construire.log" 2>&1 \
      || { echo "PLANTÉ : maquette de $cas (voir $L/$cas/construire.log)"; exit 1; }
  fi
  [ -f "$d3/maquette.blend" ] || { echo "PLANTÉ : pas de maquette pour $cas"; exit 1; }
  echo "maquette de $cas prête : $d3"
  bash pc/verification/vues_rideaux.sh rideaux-largeur "$cas" "$d3" "$nom" "$L/$cas/logement-meuble.json" "$photos" > "$L/$cas/vues.log" 2>&1 \
    || { echo "PLANTÉ : vues de $cas (voir $L/$cas/vues.log)"; tail -5 "$L/$cas/vues.log"; exit 1; }
  echo "vues de $cas prêtes"
}

for cas in $CAS; do
  case "$cas" in
    # parquet004i : import resté bloqué 4 h 30 le 22/11 (Unreal tournait à vide) ; relancé sous un nom neuf
    app-004) refaire app-004 $B/app-004-v8-3d parquet004j "photo-01 photo-02 photo-07 photo-08 photo-09 photo-10 photo-12" ;;
    # app-001-v7-3d / parquet001h : premier tournage, le voilage traversait les rideaux tirés par endroits (points clairs) ;
    # refait le 23/11 avec le rideau repoussé devant son voilage (moteur/blender/tissus.py)
    app-001) refaire app-001 $B/app-001-v8-3d parquet001i "photo-08 photo-10" ;;
    *) echo "PLANTÉ : logement inconnu : $cas"; exit 1 ;;
  esac
done
echo "FAIT : ../atelya/b2/lumiere-film/rideaux-largeur"
