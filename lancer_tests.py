"""Lanceur de tests sans pytest (le PC n'a pas pytest) : exécute chaque fonction test_* de tests/*.py."""
import importlib.util, sys, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
ok = ko = 0
for f in sorted(Path(__file__).parent.glob("tests/test_*.py")):
    spec = importlib.util.spec_from_file_location(f.stem, f); m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
    except Exception:
        ko += 1; print(f"ECHEC import {f.name}"); traceback.print_exc(); continue
    for nom in [n for n in dir(m) if n.startswith("test_")]:
        fn = getattr(m, nom)
        if fn.__code__.co_argcount:
            print(f"saute {f.name}::{nom} (a besoin d'arguments pytest)"); continue
        try:
            fn(); ok += 1
        except Exception:
            ko += 1; print(f"ECHEC {f.name}::{nom}"); traceback.print_exc()
print(f"TESTS : {ok} OK, {ko} en échec")
sys.exit(1 if ko else 0)
