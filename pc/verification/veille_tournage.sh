#!/usr/bin/env bash
# VEILLE D'UN TOURNAGE (23/11/2026 ; leçon du 22/11 : un import Unreal resté bloqué 4 h 30 sans que personne le voie).
#
#     bash pc/verification/veille_tournage.sh <journal du tournage> <minutes> <dossier surveillé> [<dossier> …]
#
# Rend la main (une ligne) dès que : le tournage a fini (« code= » dans son journal), il a planté (« PLANTÉ », « Traceback »),
# PLUS AUCUN FICHIER n'a bougé depuis 15 minutes dans les dossiers surveillés (alerte d'immobilité), ou les <minutes> sont
# passées (point d'étape). À relancer toutes les 30 minutes tant que le tournage dure.
set -u
JOURNAL="$1"; MINUTES="$2"; shift 2
FIN=$(( $(date +%s) + MINUTES * 60 ))
dernier() {  # l'âge (s) du fichier le plus récent des dossiers surveillés, et son nom
  find "$@" "$JOURNAL" -type f -mmin -20 -printf '%T@ %p\n' 2>/dev/null | sort -n | tail -1
}
while true; do
  if grep -q "code=" "$JOURNAL" 2>/dev/null; then echo "FINI : $(tail -2 "$JOURNAL" | tr '\n' ' ')"; exit 0; fi
  if grep -q "PLANT\|Traceback" "$JOURNAL" 2>/dev/null; then echo "PLANTÉ : $(grep "PLANT\|Traceback" "$JOURNAL" | tail -2 | tr '\n' ' ')"; exit 1; fi
  D=$(dernier "$@")
  if [ -z "$D" ]; then echo "IMMOBILE : plus aucun fichier ne bouge depuis 20 minutes ; journal : $(tail -1 "$JOURNAL")"; exit 2; fi
  AGE=$(( $(date +%s) - $(printf '%.0f' "${D%% *}") ))
  if [ "$AGE" -gt 900 ]; then echo "IMMOBILE : rien depuis $((AGE / 60)) min (dernier : ${D#* }) ; journal : $(tail -1 "$JOURNAL")"; exit 2; fi
  if [ "$(date +%s)" -ge "$FIN" ]; then echo "EN COURS : journal : $(tail -1 "$JOURNAL") ; dernier fichier il y a ${AGE} s : ${D#* }"; exit 0; fi
  sleep 30
done
