"""L'« œil » DINOv2 de Meta, pour le moteur (brique photos, 09/11/2026 ; même réseau que pc/a3/oeil.py, étape A3).

DINOv2 (Meta, licence Apache 2.0, code et poids ; texte de la licence : pc/a3/LICENSE-DINOv2.txt) est un réseau déjà
entraîné sur 142 millions de photos : il transforme chaque carré de 14 × 14 pixels d'une image en une « empreinte »
(384 nombres pour la petite version ViT-S/14, 768 pour ViT-B/14) qui décrit ce qu'on y voit (texture, motif, matière).
Deux parquets en point de Hongrie ont des empreintes proches ; un point de Hongrie et des lames droites, non.

Aucun code venu d'internet n'est lancé : le réseau est réécrit ici (~50 lignes, même architecture que
dinov2/models/vision_transformer.py) ; seuls les POIDS officiels de Meta sont lus (fichiers de nombres, torch.load avec
weights_only=True, qui refuse tout code), rangés dans ..\\atelya\\modeles-externes\\ (accord NT du 02/11/2026).
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

OEILS = {"vits14": (384, 6), "vitb14": (768, 12)}  # largeur, têtes ; 12 blocs, carrés de 14 px
MOYENNE = np.array([0.485, 0.456, 0.406], np.float32)
ECART = np.array([0.229, 0.224, 0.225], np.float32)
POIDS_PC = Path(__file__).resolve().parents[2] / "atelya" / "modeles-externes"


def dossier_poids() -> Path:
    return Path(os.environ.get("ATELYA_MODELES_EXTERNES", POIDS_PC))


class _Attention(nn.Module):
    def __init__(self, d: int, tetes: int):
        super().__init__()
        self.tetes = tetes
        self.qkv = nn.Linear(d, d * 3)
        self.proj = nn.Linear(d, d)

    def forward(self, x):
        b, n, d = x.shape
        q, k, v = self.qkv(x).reshape(b, n, 3, self.tetes, d // self.tetes).permute(2, 0, 3, 1, 4)
        return self.proj(F.scaled_dot_product_attention(q, k, v).transpose(1, 2).reshape(b, n, d))


class _Echelle(nn.Module):  # « LayerScale »
    def __init__(self, d: int):
        super().__init__()
        self.gamma = nn.Parameter(torch.ones(d))

    def forward(self, x):
        return x * self.gamma


class _Mlp(nn.Module):
    def __init__(self, d: int):
        super().__init__()
        self.fc1, self.fc2 = nn.Linear(d, 4 * d), nn.Linear(4 * d, d)

    def forward(self, x):
        return self.fc2(F.gelu(self.fc1(x)))


class _Bloc(nn.Module):
    def __init__(self, d: int, tetes: int):
        super().__init__()
        self.norm1, self.attn, self.ls1 = nn.LayerNorm(d, eps=1e-6), _Attention(d, tetes), _Echelle(d)
        self.norm2, self.mlp, self.ls2 = nn.LayerNorm(d, eps=1e-6), _Mlp(d), _Echelle(d)

    def forward(self, x):
        x = x + self.ls1(self.attn(self.norm1(x)))
        return x + self.ls2(self.mlp(self.norm2(x)))


class _Patchs(nn.Module):
    def __init__(self, d: int):
        super().__init__()
        self.proj = nn.Conv2d(3, d, 14, stride=14)

    def forward(self, x):
        return self.proj(x).flatten(2).transpose(1, 2)


class ViTDino(nn.Module):
    """DINOv2 ViT-S/14 ou ViT-B/14 (sans « registres »), noms de réglages identiques aux poids de Meta."""

    def __init__(self, d: int, tetes: int, blocs: int = 12, grille: int = 37):
        super().__init__()
        self.patch_embed = _Patchs(d)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, d))
        self.pos_embed = nn.Parameter(torch.zeros(1, 1 + grille * grille, d))
        self.mask_token = nn.Parameter(torch.zeros(1, d))  # pas utilisé, présent dans les poids
        self.blocks = nn.ModuleList(_Bloc(d, tetes) for _ in range(blocs))
        self.norm = nn.LayerNorm(d, eps=1e-6)

    def _positions(self, h: int, w: int) -> torch.Tensor:
        pos = self.pos_embed.float()
        m = int(math.sqrt(pos.shape[1] - 1))
        if (h, w) == (m, m):
            return pos
        grille = pos[:, 1:].reshape(1, m, m, -1).permute(0, 3, 1, 2)
        # Comme DINOv2 : bicubique, avec le « + 0,1 » historique sur le facteur d'échelle.
        grille = F.interpolate(grille, scale_factor=((h + 0.1) / m, (w + 0.1) / m), mode="bicubic", antialias=False)
        return torch.cat([pos[:, :1], grille.permute(0, 2, 3, 1).reshape(1, h * w, -1)], 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """(empreinte de l'image entière « CLS », empreintes des carrés de 14 px)."""
        h, w = x.shape[2] // 14, x.shape[3] // 14
        t = self.patch_embed(x)
        t = torch.cat([self.cls_token.expand(t.shape[0], -1, -1), t], 1)
        t = t + self._positions(h, w).to(t.dtype)
        for b in self.blocks:
            t = b(t)
        t = self.norm(t)
        return t[:, 0], t[:, 1:]


def charger(nom: str = "vits14", appareil: str | None = None) -> ViTDino:
    d, tetes = OEILS[nom]
    m = ViTDino(d, tetes)
    chemin = dossier_poids() / f"dinov2_{nom}_pretrain.pth"
    if not chemin.is_file():
        raise FileNotFoundError(f"poids DINOv2 introuvables : {chemin}")
    manque, trop = m.load_state_dict(torch.load(chemin, map_location="cpu", weights_only=True), strict=False)
    if manque or trop:
        raise RuntimeError(f"poids DINOv2 {nom} inattendus : manque {manque[:5]}, en trop {trop[:5]}")
    appareil = appareil or ("cuda" if torch.cuda.is_available() else "cpu")
    return m.eval().to(appareil)


@torch.no_grad()
def empreintes(oeil: ViTDino, images: np.ndarray, lot: int = 64) -> np.ndarray:
    """Une empreinte par image (N, H, W, 3, uint8 RGB ; H et W multiples de 14) : l'empreinte « CLS » suivie de la moyenne
    des empreintes des carrés, normée (longueur 1)."""
    appareil = next(oeil.parameters()).device
    sorties = []
    for i in range(0, len(images), lot):
        x = (images[i:i + lot].astype(np.float32) / 255.0 - MOYENNE) / ECART
        x = torch.from_numpy(x).permute(0, 3, 1, 2).to(appareil)
        with torch.autocast(device_type=appareil.type, enabled=appareil.type == "cuda"):
            cls, carres = oeil(x)
        e = torch.cat([cls.float(), carres.float().mean(1)], 1)
        sorties.append(F.normalize(e, dim=1).cpu().numpy())
    return np.concatenate(sorties) if sorties else np.zeros((0, 2 * oeil.norm.normalized_shape[0]), np.float32)
