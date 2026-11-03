"""Étape A3 : vérifie les poids DINOv2 (Meta, Apache 2.0) déjà téléchargés dans modeles-externes\\ et les fait tourner sur la carte.

Aucun code venu d'internet : le réseau est celui d'oeil.py ; les poids sont lus avec weights_only=True.
"""
import hashlib
import sys
import time

import torch

from oeil import DOSSIER_POIDS, charger_dinov2

dev = torch.device("cuda")
for nom in sys.argv[1:] or ["vits14", "vitb14"]:
    f = DOSSIER_POIDS / f"dinov2_{nom}_pretrain.pth"
    print(f"{f.name} : {f.stat().st_size} octets, sha256 {hashlib.sha256(f.read_bytes()).hexdigest()}", flush=True)
    t = time.time()
    m = charger_dinov2(nom).to(dev).eval()
    n = sum(p.numel() for p in m.parameters())
    g = torch.Generator().manual_seed(0)
    img = torch.rand(1, 3, 448, 448, generator=g)
    lot = torch.cat([img, img.flip(3), torch.rand(1, 3, 448, 448, generator=g)]).to(dev)
    with torch.no_grad(), torch.autocast("cuda"):
        r = m.forward_features(lot)
    c = torch.nn.functional.normalize(r["x_norm_clstoken"].float(), dim=1)
    print(f"{nom} : {n / 1e6:.1f} millions de réglages, jetons {tuple(r['x_norm_patchtokens'].shape)}, "
          f"ressemblance image/miroir {float(c[0] @ c[1]):.3f}, image/autre {float(c[0] @ c[2]):.3f}, "
          f"valeurs finies {bool(torch.isfinite(r['x_norm_patchtokens']).all())}, {time.time() - t:.1f} s", flush=True)
print("OK")
