"""Point 2, temps A : pour chaque photo, les meilleures places DANS CHAQUE PIÈCE (et non les 8 meilleures en tout)."""
import json, os, sys, time
from pathlib import Path
import numpy as np
import etape_b as eb
import moge2 as m2
import moge5 as m5

PAR_PIECE = 2

if __name__ == "__main__":
    src, sortie, app = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
    d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
    mod = eb.modele(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")))
    mod = dict(mod, sorte=mod["genre"].copy(), genre=np.zeros_like(mod["genre"]))
    G = m2.grille(mod); pg = eb.piece_de(mod, G)
    tour, tsorte, tappui = m5.tirs(mod, G, np.arange(360.0))
    res = {}
    for nom in d["cameras"]:
        t0 = time.time()
        z = np.load(src / f"{app}-{nom}.npz"); z = {k_: z[k_] for k_ in z.files}
        if os.environ.get("ZOOM") == "main":  # essai « si le zoom était connu » : celui relevé à la main
            from moteur import moge
            f = d["cameras"][nom]["camera"]["f"] * z["masque"].shape[1] / d["cameras"][nom]["largeur"]
            z.update(moge.relire({"brut": z["brut"], "masque_brut": z["masque_brut"], "echelle": float(z["echelle"]), "masque": z["masque"]}, f))
        asp = np.load(src.parent / "aspect" / f"{app}-{nom}.npy") if m5.MODE in ("aspect", "fen") else None
        pr = m5.profil(z, mod["hsp"], asp)
        if pr is None:
            res[nom] = []; continue
        ph, rm, creux, sol, info = pr
        ip = ph.astype(int)
        notes = np.stack([np.stack([m5.note(rm[None] * e, tour[:, (cap + ip) % 360], creux[None], sol[None], tsorte[:, (cap + ip) % 360],
                                            tappui[:, (cap + ip) % 360]) for cap in range(360)], 1) for e in m5.ECH], 2)
        liste = []
        for p in range(len(mod["pieces"])):
            ici = np.where(pg == p)[0]
            if len(ici) < 4:
                continue
            n = notes[ici]; cands = []
            combien = int(np.clip(2 + len(ici) * 0.04 / 5, 2, 8))  # une place de plus par 5 m² (grille de 20 cm)
            for o in np.argsort(n.ravel())[::-1][:20000]:
                g, reste = divmod(int(o), 360 * len(m5.ECH)); cap, ie = divmod(reste, len(m5.ECH))
                q = np.array([*G[ici[g]], float(cap), m5.ECH[ie]])
                if all(np.hypot(*(q[:2] - c[:2])) > 0.8 or abs((cap - c[2] + 180) % 360 - 180) > 30 for c in cands):
                    cands.append(q)
                if len(cands) == combien:
                    break
            for q in cands:
                cam, v = m5.precis(mod, ph, rm, creux, sol, q)
                pp = eb.piece_de(mod, cam[None, :2])[0]
                liste.append({"piece": mod["ids"][pp], "cam": [float(x) for x in cam], "note": float(v)})
        res[nom] = liste
        print(app, nom, len(liste), "places,", f"{time.time() - t0:.0f} s", flush=True)
    (sortie / f"par-piece-{app}{os.environ.get('SUFF', '')}.json").write_text(json.dumps(res), encoding="utf-8")
