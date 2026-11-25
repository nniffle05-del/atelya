#!/usr/bin/env bash
# LES JUGES DU PARQUET, D'UN TRAIT (18/11/2026) : à lancer depuis la racine du dépôt, dans Git Bash.
#   bash pc/verification/juger_parquets.sh <dossier AVANT (chaîne)> <dossier APRÈS (chaîne)> <sortie>
# 1. planches « la photo | avant | après » des trois logements (maquettes meublées, rendues depuis la place des photos) ;
# 2. la COULEUR des sols avant et après (mesurer_couleur_sols.py) ;
# 3. la maquette d'APRÈS sans meubles, rendue depuis la place de toutes les photos (sols_nus.py) ;
# 4. le SENS des lames photo contre maquette (comparer_sens_photo_rendu.py) ;
# 5. le PARQUET photo contre maquette (comparer_parquet_photo_rendu.py).
# S'arrête au premier plantage avec une ligne « PLANTÉ … ».
set -u
AVANT="$1"; APRES="$2"; S="$3"
PY=../atelya/.venv/Scripts/python.exe
mkdir -p "$S"
etape() { nom="$1"; shift; echo "== $nom"; "$@" || { echo "PLANTÉ à l'étape « $nom » (code $?)"; exit 1; }; }
etape "planches" $PY pc/verification/planches_avant_apres.py "$AVANT" "$APRES" "$S/images" \
  app-001:photo-05,photo-07,photo-08,photo-11 app-002:photo-01,photo-03,photo-07,photo-14 app-004:photo-02,photo-07,photo-08 \
  --titres "hier (parquet du catalogue)" "aujourd'hui (parquet sur mesure)"
for quand in avant apres; do
  R="$S/images/planches"
  etape "couleur $quand" $PY pc/verification/mesurer_couleur_sols.py "$S/couleur-$quand" \
    app-001=$R/app-001-$quand/vues/rendus app-002=$R/app-002-$quand/vues/rendus app-004=$R/app-004-$quand/vues/rendus --titre "couleur des sols, $quand"
done
etape "sols nus" $PY pc/verification/sols_nus.py "$APRES" "$S/sols-nus" --version c
N="$S/sols-nus/planches"
R="app-001=$N/app-001/vues/rendus app-002=$N/app-002/vues/rendus app-004=$N/app-004/vues/rendus"
etape "sens" $PY pc/verification/comparer_sens_photo_rendu.py $R > "$S/sens.txt" 2>&1; tail -1 "$S/sens.txt"
etape "parquet" $PY pc/verification/comparer_parquet_photo_rendu.py "$S/juge-parquet" $R > "$S/parquet.txt" 2>&1; tail -1 "$S/parquet.txt"
echo "FINI"
