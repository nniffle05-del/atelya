"""L'« œil » DINOv2 d'Atelya (étape A3).

DINOv2 (Meta, licence Apache 2.0, code et poids) est un réseau déjà entraîné sur 142 millions de photos :
il sait reconnaître traits, textures, papier, ombres. Il regarde l'image par carrés de 14 pixels, trop
grossier tout seul pour un mur de 4 pixels. On garde donc le U-Net d'Atelya (la finesse des traits) et on
lui AJOUTE l'avis de DINOv2 au fond du réseau, là où l'image est 16 fois plus petite : chaque carré de
16 px du plan reçoit l'avis de DINOv2 sur ce carré et son voisinage.

- DINOv2 est FIGÉ (on ne change pas ses réglages) sauf --degeler N (ses N derniers blocs apprennent).
- La « fusion » (2 petites convolutions) part de ZÉRO : au départ, Atelya + œil répond EXACTEMENT comme
  l'essai 5. Tout ce qui change ensuite vient de l'apprentissage.
- Le fichier .pt ne contient pas DINOv2 figé (il est rechargé depuis modeles-externes\\).

Pour ne lancer AUCUN code venu d'internet, le réseau DINOv2 est réécrit ici (ViTDino, ~50 lignes, même
architecture que dinov2/models/vision_transformer.py) ; seuls les POIDS officiels de Meta sont téléchargés
(fichiers de nombres, lus avec torch.load(weights_only=True), qui refuse tout code) :
    https://dl.fbaipublicfiles.com/dinov2/dinov2_vits14/dinov2_vits14_pretrain.pth  (~85 Mo)
    https://dl.fbaipublicfiles.com/dinov2/dinov2_vitb14/dinov2_vitb14_pretrain.pth  (~330 Mo)
rangés dans atelya\\modeles-externes\\ (accord NT 2026-11-02). Licence Apache 2.0.
"""
from __future__ import annotations

import math
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F

from entrainer import UNet

OEILS = {"vits14": (384, 6), "vitb14": (768, 12)}  # largeur, têtes ; 12 blocs, patch 14, grille 37 x 37
DOSSIER_POIDS = Path(__file__).resolve().parent / "modeles-externes"
_MOY = (0.485, 0.456, 0.406)
_ECART = (0.229, 0.224, 0.225)


class _Attention(nn.Module):
    def __init__(self, d: int, tetes: int):
        super().__init__()
        self.tetes = tetes
        self.qkv = nn.Linear(d, d * 3)
        self.proj = nn.Linear(d, d)

    def forward(self, x):
        b, n, d = x.shape
        q, k, v = self.qkv(x).reshape(b, n, 3, self.tetes, d // self.tetes).permute(2, 0, 3, 1, 4)
        x = F.scaled_dot_product_attention(q, k, v)
        return self.proj(x.transpose(1, 2).reshape(b, n, d))


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
        assert grille.shape[-2:] == (h, w)
        return torch.cat([pos[:, :1], grille.permute(0, 2, 3, 1).reshape(1, h * w, -1)], 1)

    def forward_features(self, x: torch.Tensor) -> dict:
        h, w = x.shape[2] // 14, x.shape[3] // 14
        t = self.patch_embed(x)
        t = torch.cat([self.cls_token.expand(t.shape[0], -1, -1), t], 1)
        t = t + self._positions(h, w).to(t.dtype)
        for b in self.blocks:
            t = b(t)
        t = self.norm(t)
        return {"x_norm_clstoken": t[:, 0], "x_norm_patchtokens": t[:, 1:]}


def charger_dinov2(nom: str) -> nn.Module:
    d, tetes = OEILS[nom]
    m = ViTDino(d, tetes)
    poids = torch.load(DOSSIER_POIDS / f"dinov2_{nom}_pretrain.pth", map_location="cpu", weights_only=True)
    manque, trop = m.load_state_dict(poids, strict=False)
    if manque or trop:
        raise RuntimeError(f"poids DINOv2 {nom} inattendus : manque {manque[:5]}, en trop {trop[:5]}")
    return m


class UNetOeil(UNet):
    """Le U-Net d'Atelya + l'œil DINOv2 ajouté au fond du réseau."""

    def __init__(self, base: int = 32, contexte: bool = True, oeil: str = "vits14", degeler: int = 0):
        super().__init__(base, contexte=contexte)
        self.nom_oeil, self.degeler = oeil, degeler
        self.oeil = charger_dinov2(oeil)
        for p in self.oeil.parameters():
            p.requires_grad_(False)
        if degeler > 0:
            for b in self.oeil.blocks[-degeler:]:
                for p in b.parameters():
                    p.requires_grad_(True)
            for p in self.oeil.norm.parameters():
                p.requires_grad_(True)
        c = base * 16
        # GroupNorm : remet l'avis de DINOv2 à une échelle raisonnable (ses valeurs vont jusqu'à quelques dizaines),
        # sans dépendre des moyennes BatchNorm (figées par --figer-bn).
        self.fusion = nn.Sequential(nn.Conv2d(OEILS[oeil][0], c, 1), nn.GroupNorm(32, c), nn.GELU(),
                                    nn.Conv2d(c, c, 3, padding=1))
        nn.init.zeros_(self.fusion[3].weight)
        nn.init.zeros_(self.fusion[3].bias)
        self.register_buffer("moy", torch.tensor(_MOY).view(1, 3, 1, 1), persistent=False)
        self.register_buffer("ecart", torch.tensor(_ECART).view(1, 3, 1, 1), persistent=False)

    def train(self, mode: bool = True):
        super().train(mode)
        self.oeil.eval()  # pas de « dropout » dans l'œil, même pendant l'apprentissage
        return self

    def avis_oeil(self, x: torch.Tensor) -> torch.Tensor:
        """x : (lot, 1, H, W), gris 0-1, H et W multiples de 16 → (lot, d, H/16, W/16)."""
        h, w = x.shape[2] // 16, x.shape[3] // 16
        v = F.interpolate(x, size=(h * 14, w * 14), mode="bilinear", align_corners=False, antialias=True)
        v = (v.expand(-1, 3, -1, -1) - self.moy) / self.ecart
        with torch.set_grad_enabled(self.degeler > 0 and torch.is_grad_enabled()):
            t = self.oeil.forward_features(v)["x_norm_patchtokens"]
        return t.transpose(1, 2).reshape(x.shape[0], -1, h, w)

    def forward(self, x):
        avis = self.avis_oeil(x)
        gardes = []
        for i, b in enumerate(self.desc):
            x = b(x if i == 0 else F.max_pool2d(x, 2))
            gardes.append(x)
        gardes.pop()
        with torch.autocast(x.device.type, enabled=False):  # la fusion en 32 bits : pas de débordement en 16 bits
            x = (x.float() + self.fusion(avis.float())).to(x.dtype)
        x = self.contexte(x)
        for m, f in zip(self.mont, self.fus):
            x = f(torch.cat([m(x), gardes.pop()], 1))
        return self.tete(x)

    def etat_a_sauver(self) -> dict:
        """Tout sauf l'œil figé (rechargé depuis modeles-externes) ; les blocs dégelés sont gardés."""
        gardes = [f"oeil.blocks.{len(self.oeil.blocks) - k}." for k in range(1, self.degeler + 1)] + ["oeil.norm."]
        return {k: v for k, v in self.state_dict().items()
                if not k.startswith("oeil.") or (self.degeler > 0 and any(k.startswith(g) for g in gardes))}


def construire(base: int, contexte: bool, oeil: str | None, degeler: int = 0) -> nn.Module:
    if not oeil or oeil == "aucun":
        return UNet(base, contexte=contexte)
    return UNetOeil(base, contexte=contexte, oeil=oeil, degeler=degeler)


def etat(modele: nn.Module) -> dict:
    return modele.etat_a_sauver() if isinstance(modele, UNetOeil) else modele.state_dict()


def charger_modele(chemin: Path, dev) -> nn.Module:
    """Charge n'importe quel modèle Atelya : ancien U-Net (essais 2 à 6) ou U-Net + œil (essai 7)."""
    sauve = torch.load(chemin, map_location=dev)
    modele = construire(sauve.get("base", 32), sauve.get("contexte", True), sauve.get("oeil"), sauve.get("degeler", 0))
    manque, _ = modele.load_state_dict(sauve["modele"], strict=False)
    manque = [k for k in manque if not k.startswith("oeil.")]
    if manque:
        raise RuntimeError(f"réglages manquants dans {chemin} : {manque[:5]}")
    return modele.to(dev).eval()
