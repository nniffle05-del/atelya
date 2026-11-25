#!/bin/bash
# LE SOL PRIS POUR UN LIT (25/11/2026) : la chaîne entière des trois logements, AVANT (le sol = la plus grande surface à plat,
# ATELYA_SOL_JUSTE=0) puis APRÈS (le sol = la plus basse), en service (a) et avec la lecture des photos (c).
#   bash pc/verification/ab_sol_des_photos.sh [<dossier de sortie>]     (défaut : ../atelya/b2/sol-des-photos/chaine)
# Puis : pc/verification/comparer_logements.py <sortie>/avant <sortie>/apres  (ce qui a bougé, objet par objet).
cd "$(dirname "$0")/../.." || exit 1
PY=../atelya/.venv/Scripts/python.exe
SORTIE=${1:-../atelya/b2/sol-des-photos/chaine}
export PYTHONIOENCODING=utf-8
for essai in avant apres; do
  if [ "$essai" = avant ]; then export ATELYA_SOL_JUSTE=0; else export ATELYA_SOL_JUSTE=1; fi
  echo "=== $essai (ATELYA_SOL_JUSTE=$ATELYA_SOL_JUSTE) $(date +%H:%M)"
  $PY pc/verification/essai_lecture_photos.py "$SORTIE/$essai" --cas app-001 app-002 app-004 --versions a c
  code=$?
  if [ $code -ne 0 ]; then echo "PLANTÉ : la chaîne « $essai » a rendu le code $code"; exit $code; fi
done
echo "=== FINI $(date +%H:%M)"
