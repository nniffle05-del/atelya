r"""Compte les logements lus qu'on ne peut pas construire en 3D, et dit pourquoi (ouverture dans un angle, chevauchement).
    ..\atelya\.venv\Scripts\python.exe pc\verification\diag_constructible.py [--detail]
"""
import math, sys
from pathlib import Path
sys.path.insert(0, ".")
from moteur.geometrie import calculer_briques, _ajustements_aux_angles, PRECISION
from moteur.logement import charger_logement

DETAIL = "--detail" in sys.argv

def diag(chemin):
    L = charger_logement(chemin)
    try:
        calculer_briques(L); return "OK"
    except ValueError as e:
        msg = str(e)
    if not DETAIL:
        return msg[:90]
    aj = _ajustements_aux_angles(L.murs)
    murs = {m.id: m for m in L.murs}
    lignes = [msg[:90]]
    for o in L.ouvertures:
        m = murs[o.mur]; l = m.longueur; td, tf = aj[m.id]
        g, d = o.position, o.position + o.largeur
        if g < max(td) - PRECISION or d > l + min(tf) + PRECISION:
            lignes.append(f"   {o.id} {o.type} sur {m.id} (L={l:.2f}, ep={m.epaisseur:.2f}) pos {g:.3f}-{d:.3f} ; angle début {max(td):.3f} fin {l + min(tf):.3f} ; dépasse début {max(0, max(td)-g)*100:.1f} cm, fin {max(0, d-(l+min(tf)))*100:.1f} cm")
    par_mur = {}
    for o in L.ouvertures: par_mur.setdefault(o.mur, []).append(o)
    for mid, os_ in par_mur.items():
        os_.sort(key=lambda o: o.position)
        for a, b in zip(os_, os_[1:]):
            if b.position < a.position + a.largeur - PRECISION:
                lignes.append(f"   {a.id}/{b.id} ({a.type}/{b.type}) se chevauchent sur {mid} de {(a.position + a.largeur - b.position)*100:.1f} cm")
    return "\n".join(lignes)

ok = 0; tous = []
for d in sorted(Path("../atelya/lectures-verification").glob("fr-0*/logement.json")):
    r = diag(d); ok += r == "OK"; tous.append(d.parent.name)
    print(d.parent.name, r)
print(f"VRAIS PLANS constructibles : {ok}/{len(tous)}")
n = 0; motifs = {}
for d in sorted(Path("../atelya/banc-echelle-apres/logements").glob("*.json")):
    r = diag(d)
    if r != "OK":
        n += 1
        if DETAIL and n <= 8: print(d.name, r)
        cle = "chevauche" if "chevauche" in r else "angle" if "angle" in r else r.split("\n")[0][:40]
        motifs[cle] = motifs.get(cle, 0) + 1
print(f"FABRIQUÉS refusés : {n}/1066 {motifs}")
