r"""Deux variantes photo par photo : mètres | repères px | hauteurs px | côtés px (avant → après), puis ce que l'affinage a fait.

    ..\atelya\.venv\Scripts\python.exe pc\essais-place-appareils\comparer.py <variante avant> <variante après>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from juger import SORTIE, juger, lire  # noqa: E402

a, b = sys.argv[1], sys.argv[2]
ja, jb = juger(a), juger(b)
for l in ja:
    fb = lire(SORTIE / b / f"{l}.json")["cameras"] if (SORTIE / b / f"{l}.json").is_file() else {}
    for n in sorted(set().union(*[ja[l][k] for k in ("metres", "reperes", "hauteurs", "cotes")])):
        t = [f"{k[:3]} {ja[l][k][n]:{f}} → {jb[l][k].get(n, float('nan')):{f}}" for k, f in (("metres", "4.2f"), ("reperes", "3.0f"), ("hauteurs", "3.0f"), ("cotes", "3.0f")) if n in ja[l][k]]
        af = fb.get(n, {}).get("affine", {})
        print(f"{l} {n} | " + " | ".join(t) + (f" || {af.get('comment')} {af.get('points')} {af.get('ecart')} f {fb[n]['camera']['f']:.0f} z {fb[n]['camera']['z']:.2f}" if af else ""))
