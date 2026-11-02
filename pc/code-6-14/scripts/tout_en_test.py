"""Range tous les plans d'un jeu dans la partie « test » (jeu fabriqué seulement pour la note)."""
import json, sys
from pathlib import Path
f = Path(sys.argv[1]) / "repartition.json"
r = json.loads(f.read_text(encoding="utf-8"))
ids = sorted(sum([v for v in r["partitions"].values() if isinstance(v, list)], []))
r["partitions"] = {"train": [], "validation": [], "test": ids}
f.write_text(json.dumps(r, indent=1), encoding="utf-8")
print(len(ids), "plans en test")
