#!/usr/bin/env bash
# LE BAS ET LE HAUT DES FENÊTRES D'APRÈS LES PHOTOS (23/11/2026) : les maquettes d'app-004 et d'app-001 REFAITES avec leurs
# fenêtres à la hauteur vue sur les photos (moteur/hauteur_baies.py), puis regardées dans le film depuis la place des photos.
#
#     bash pc/verification/film_hauteur_baies.sh [hier] [app-004] [app-001] [mouvement]
#
# « hier » : les vues qui manquaient sur les maquettes de la veille (déjà importées : parquet001k, parquet004l), pour comparer.
# Entrée : les logements refaits par la chaîne (..\atelya\lectures-photos\hauteur-baies\chaine\<logement>\c\).
# Sorties : maquettes ..\atelya\b2\film-contre-photos\app-004-v11-3d (niveau Unreal parquet004m) et app-001-v11-3d
# (parquet001l) ; vues ..\atelya\b2\lumiere-film\hauteur-baies\<logement>\ et …\hauteur-baies-hier\ ; plans en mouvement
# …\hauteur-baies\mouvement\*-avant-apres.mp4. Éditeur Unreal FERMÉ ; NE RIEN LANCER DE LOURD pendant le tournage (22/11 :
# import bloqué 4 h 30, mémoire pleine). 10 à 20 min par vue. S'arrête au premier plantage.
set -u
cd "$(dirname "$0")/../.."
PY=../atelya/.venv/Scripts/python.exe
export PYTHONIOENCODING=utf-8
L=../atelya/lectures-photos/hauteur-baies
B=../atelya/b2/film-contre-photos
S=../atelya/b2/lumiere-film/hauteur-baies
F4=../atelya/b2/app-004/chaine-v2/cameras-photos-seul.json
F1=verites/app-001/cameras-photos.json
CAS="${*:-hier app-004 app-001 mouvement}"
mkdir -p "$L" "$S"

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
  bash pc/verification/vues_rideaux.sh hauteur-baies "$cas" "$d3" "$nom" "$L/$cas/logement-meuble.json" "$photos" > "$L/$cas/vues.log" 2>&1 \
    || { echo "PLANTÉ : vues de $cas (voir $L/$cas/vues.log)"; tail -5 "$L/$cas/vues.log"; exit 1; }
  echo "vues de $cas prêtes"
}

plan() {  # <paquet> <nom Unreal> <fiche> <photo> <logement> <dossier de sortie>
  [ -f "$6/image-0100.png" ] && { echo "déjà tourné : $6"; return 0; }
  $PY pc/verification/panoramique_lumiere.py "$1" "$2" "$3" "$4" "$6" --logement "$5" || { echo "PLANTÉ : plan $2 $4"; exit 1; }
}

monter() {  # <sortie.mp4> <dossier hier> <dossier aujourd'hui>
  $PY pc/verification/film_cote_a_cote.py "$1" "hier=$2" "aujourd'hui (fenêtres à la hauteur des photos)=$3" \
    || { echo "PLANTÉ : montage $1"; exit 1; }
}

for cas in $CAS; do
  case "$cas" in
    hier)  # les vues qui manquaient sur les maquettes de la veille (étape c des rideaux), sans rien réimporter
      VUES_001="photo-01 photo-04 photo-05" VUES_002="" VUES_004="photo-11" bash pc/verification/vues_lumiere.sh hauteur-baies-hier \
        > "$L/vues-hier.log" 2>&1 || { echo "PLANTÉ : vues d'hier (voir $L/vues-hier.log)"; tail -5 "$L/vues-hier.log"; exit 1; }
      echo "vues d'hier prêtes" ;;
    app-004) refaire app-004 $B/app-004-v11-3d parquet004m "photo-01 photo-07 photo-09 photo-10 photo-11 photo-12" ;;
    app-001) refaire app-001 $B/app-001-v11-3d parquet001l "photo-01 photo-04 photo-05 photo-08 photo-10" ;;
    mouvement)  # « hier » : les plans du 23/11 (étape c), déjà tournés
      HIER=../atelya/b2/lumiere-film/tringle/mouvement
      mkdir -p "$S/mouvement"
      plan $B/app-004-v11/paquet parquet004m $F4 photo-12 $L/app-004/logement-meuble.json "$S/mouvement/app-004-photo-12"
      monter "$S/mouvement/app-004-photo-12-avant-apres.mp4" "$HIER/app-004-photo-12" "$S/mouvement/app-004-photo-12"
      plan $B/app-001-v11/paquet parquet001l $F1 photo-08 $L/app-001/logement-meuble.json "$S/mouvement/app-001-photo-08"
      monter "$S/mouvement/app-001-photo-08-avant-apres.mp4" "$HIER/app-001-photo-08" "$S/mouvement/app-001-photo-08" ;;
    *) echo "PLANTÉ : étape inconnue : $cas"; exit 1 ;;
  esac
done
echo "FAIT : $S"
