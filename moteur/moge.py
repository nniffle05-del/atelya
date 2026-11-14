"""MoGe-2 de Microsoft : d'UNE photo, la place en 3D (en mètres) de chaque point vu (14/11/2026, accord écrit NT).

Pourquoi : pour retrouver d'où une photo du client a été prise, les traits de la photo ne suffisent pas (les meubles et
le parquet noient les murs). MoGe-2 donne la PROFONDEUR : chaque pixel devient un point (x à droite, y vers le bas,
z devant l'appareil, en mètres), avec le zoom de l'appareil (focale) et l'orientation de chaque surface (normale).
La photo devient un morceau de pièce mesuré, qu'on peut poser sur le plan.

Licence : code MIT (Microsoft) + DINOv2 Apache 2.0 ; poids `Ruicheng/moge-2-vitb-normal` MIT (fichier LICENSE lu en
entier le 14/11/2026, copie à côté des poids). Aucun code d'internet n'est lancé : le réseau est réécrit ici d'après
`moge/model/v2.py` et `moge/model/modules/` (mêmes noms de réglages que les poids) ; l'œil est celui de
`moteur/oeil_dinov2.py`. Seuls les poids sont lus (`torch.load(weights_only=True)`), dans
..\\atelya\\modeles-externes\\moge-2-vitb-normal\\model.pt (419 Mo).
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from moteur.oeil_dinov2 import ViTDino, dossier_poids

DOSSIER = "moge-2-vitb-normal"
OEILS = {"dinov2_vits14": (384, 6, 12), "dinov2_vitb14": (768, 12, 12), "dinov2_vitl14": (1024, 16, 24)}


def _norme(sorte: str, c: int) -> nn.Module:
    if sorte == "group_norm":
        return nn.GroupNorm(c // 32, c)
    if sorte == "layer_norm":
        return nn.GroupNorm(1, c)
    if sorte == "instance_norm":
        return nn.InstanceNorm2d(c)
    return nn.Identity()


def _conv3(a: int, b: int) -> nn.Conv2d:
    return nn.Conv2d(a, b, 3, padding=1, padding_mode="replicate")


class _BlocResiduel(nn.Module):
    def __init__(self, c: int, cache: int, norme_entree: str, norme_cachee: str):
        super().__init__()
        self.layers = nn.Sequential(_norme(norme_entree, c), nn.ReLU(), _conv3(c, cache),
                                    _norme(norme_cachee, cache), nn.ReLU(), _conv3(cache, c))

    def forward(self, x):
        return x + self.layers(x)


def _agrandir(sorte: str, a: int, b: int) -> nn.Sequential:
    if sorte == "conv_transpose":
        return nn.Sequential(nn.ConvTranspose2d(a, b, 2, stride=2), _conv3(b, b))
    if sorte == "pixel_shuffle":
        return nn.Sequential(_conv3(a, b * 4), nn.PixelShuffle(2), _conv3(b, b))
    if sorte in ("nearest", "bilinear"):
        return nn.Sequential(nn.Upsample(scale_factor=2, mode=sorte, align_corners=False if sorte == "bilinear" else None),
                             _conv3(a, b))
    raise ValueError(f"agrandissement non prévu : {sorte}")


class _Pile(nn.Module):
    """« ConvStack » : une pyramide qui double la finesse à chaque étage."""

    def __init__(self, dim_in, dim_res_blocks, dim_out, resamplers, dim_times_res_block_hidden=1, num_res_blocks=1,
                 res_block_in_norm="layer_norm", res_block_hidden_norm="group_norm", activation="relu", **_):
        super().__init__()
        if activation != "relu":
            raise ValueError(f"activation non prévue : {activation}")
        n = len(dim_res_blocks)
        liste = lambda v: list(v) if isinstance(v, (list, tuple)) else [v] * n
        self.input_blocks = nn.ModuleList(nn.Conv2d(a, c, 1) if a is not None else nn.Identity()
                                          for a, c in zip(liste(dim_in), dim_res_blocks))
        self.resamplers = nn.ModuleList(_agrandir(s, a, b) for a, b, s in
                                        zip(dim_res_blocks[:-1], dim_res_blocks[1:], liste(resamplers)))
        self.res_blocks = nn.ModuleList(
            nn.Sequential(*(_BlocResiduel(c, dim_times_res_block_hidden * c, res_block_in_norm, res_block_hidden_norm)
                            for _ in range(k))) for c, k in zip(dim_res_blocks, liste(num_res_blocks)))
        self.output_blocks = nn.ModuleList(nn.Conv2d(c, b, 1) if b is not None else nn.Identity()
                                           for b, c in zip(liste(dim_out), dim_res_blocks))

    def forward(self, entrees):
        sorties, x = [], None
        for i in range(len(self.res_blocks)):
            f = self.input_blocks[i](entrees[i])
            x = f if i == 0 else x + f
            x = self.res_blocks[i](x)
            sorties.append(self.output_blocks[i](x.float()) if i == len(self.res_blocks) - 1 else None)
            if i < len(self.res_blocks) - 1:
                x = self.resamplers[i](x)
        return sorties


class _Oeil(nn.Module):
    def __init__(self, backbone: str, intermediate_layers, dim_out: int, **_):
        super().__init__()
        d, tetes, blocs = OEILS[backbone]
        self.backbone = ViTDino(d, tetes, blocs)
        self.couches = (list(range(blocs - intermediate_layers, blocs)) if isinstance(intermediate_layers, int)
                        else list(intermediate_layers))
        self.output_projections = nn.ModuleList(nn.Conv2d(d, dim_out, 1) for _ in self.couches)
        self.register_buffer("image_mean", torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1))
        self.register_buffer("image_std", torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1))

    def forward(self, image, lignes: int, colonnes: int):
        x = F.interpolate(image, (lignes * 14, colonnes * 14), mode="bilinear", align_corners=False, antialias=True)
        x = (x - self.image_mean) / self.image_std
        o = self.backbone
        t = o.patch_embed(x)
        t = torch.cat([o.cls_token.expand(t.shape[0], -1, -1), t], 1)
        t = t + o._positions(lignes, colonnes).to(t.dtype)
        somme, cls = 0, None
        for i, b in enumerate(o.blocks):
            t = b(t)
            if i in self.couches:
                n = o.norm(t)
                cls = n[:, 0]
                carte = n[:, 1:].permute(0, 2, 1).unflatten(2, (lignes, colonnes)).contiguous()
                somme = somme + self.output_projections[self.couches.index(i)](carte)
        return somme, cls


def _uv(largeur: int, hauteur: int, rapport: float, **k) -> torch.Tensor:
    """Coordonnées de chaque point de l'image, de −1 à 1 le long de la diagonale."""
    ex, ey = rapport / (1 + rapport ** 2) ** 0.5, 1 / (1 + rapport ** 2) ** 0.5
    u = torch.linspace(-ex * (largeur - 1) / largeur, ex * (largeur - 1) / largeur, largeur, **k)
    v = torch.linspace(-ey * (hauteur - 1) / hauteur, ey * (hauteur - 1) / hauteur, hauteur, **k)
    u, v = torch.meshgrid(u, v, indexing="xy")
    return torch.stack([u, v], -1)


class MoGe(nn.Module):
    def __init__(self, encoder, neck, points_head=None, mask_head=None, normal_head=None, scale_head=None,
                 remap_output="linear", num_tokens_range=(1200, 3600), **_):
        super().__init__()
        self.remap, self.carres = remap_output, tuple(num_tokens_range)
        self.encoder, self.neck = _Oeil(**encoder), _Pile(**neck)
        if points_head is not None:
            self.points_head = _Pile(**points_head)
        if mask_head is not None:
            self.mask_head = _Pile(**mask_head)
        if normal_head is not None:
            self.normal_head = _Pile(**normal_head)
        if scale_head is not None:
            dims = scale_head["dims"]
            couches = []
            for a, b in zip(dims[:-2], dims[1:-1]):
                couches += [nn.Linear(a, b), nn.ReLU(inplace=True)]
            self.scale_head = nn.Sequential(*couches, nn.Linear(dims[-2], dims[-1]))

    def forward(self, image: torch.Tensor, carres: int) -> dict:
        b, _, h, w = image.shape
        rapport = w / h
        lignes, colonnes = round((carres / rapport) ** 0.5), round((carres * rapport) ** 0.5)
        f, cls = self.encoder(image, lignes, colonnes)
        etages = []
        for niveau in range(5):
            uv = _uv(colonnes * 2 ** niveau, lignes * 2 ** niveau, rapport, dtype=f.dtype, device=f.device)
            uv = uv.permute(2, 0, 1).unsqueeze(0).expand(b, -1, -1, -1)
            etages.append(torch.cat([f, uv], 1) if niveau == 0 else uv)
        etages = self.neck_tout(etages)
        s = {}
        for nom in ("points", "normal", "mask"):
            if hasattr(self, nom + "_head"):
                v = getattr(self, nom + "_head")(etages)[-1]
                s[nom] = F.interpolate(v.float(), (h, w), mode="bilinear", align_corners=False)
        if "points" in s:
            p = s["points"].permute(0, 2, 3, 1)
            if self.remap == "exp":
                xy, z = p.split([2, 1], -1)
                z = torch.exp(z)
                p = torch.cat([xy * z, z], -1)
            elif self.remap == "sinh":
                p = torch.sinh(p)
            elif self.remap == "sinh_exp":
                xy, z = p.split([2, 1], -1)
                p = torch.cat([torch.sinh(xy), torch.exp(z)], -1)
            s["points"] = p
        if "normal" in s:
            s["normal"] = F.normalize(s["normal"].permute(0, 2, 3, 1), dim=-1)
        if "mask" in s:
            s["mask"] = s["mask"].squeeze(1).sigmoid()
        if hasattr(self, "scale_head"):
            s["metric_scale"] = self.scale_head(cls.float()).squeeze(1).exp()
        return s

    def neck_tout(self, etages):
        """Le « cou » rend TOUS ses étages (les têtes en ont besoin), contrairement aux têtes."""
        pile, sorties, x = self.neck, [], None
        for i in range(len(pile.res_blocks)):
            f = pile.input_blocks[i](etages[i])
            x = f if i == 0 else x + f
            x = pile.res_blocks[i](x)
            sorties.append(pile.output_blocks[i](x))
            if i < len(pile.res_blocks) - 1:
                x = pile.resamplers[i](x)
        return sorties


def focale_et_decalage(uv: np.ndarray, xyz: np.ndarray, focale: float | None = None) -> tuple[float, float]:
    """Les points sortent du réseau à un recul près le long du regard : on cherche le recul (et le zoom) pour lesquels
    chaque point retombe sur son pixel. Une seule inconnue (le recul), le zoom s'en déduit ; recherche de Gauss-Newton
    amortie (pas de scipy). `focale` donnée (relative à la demi-diagonale) : seul le recul est cherché."""
    uv, xy, z = uv.reshape(-1, 2).astype(np.float64), xyz[:, :2].astype(np.float64), xyz[:, 2].astype(np.float64)

    def ecart(d):
        p = xy / (z + d)[:, None]
        f = (p * uv).sum() / max(np.square(p).sum(), 1e-12) if focale is None else focale
        return (f * p - uv).ravel(), f

    d, amorti = 0.0, 1e-3
    e, f = ecart(d)
    for _ in range(60):
        pas = 1e-4 * max(1.0, abs(d))
        j = (ecart(d + pas)[0] - ecart(d - pas)[0]) / (2 * pas)
        delta = -(j @ e) / (j @ j * (1 + amorti) + 1e-18)
        e2, f2 = ecart(d + delta)
        if e2 @ e2 < e @ e:
            d, e, f, amorti = d + delta, e2, f2, amorti / 3
            if abs(delta) < 1e-6 * max(1.0, abs(d)):
                break
        else:
            amorti *= 5
            if amorti > 1e8:
                break
    return float(f), float(d)


def charger(appareil: str | None = None, dossier: str = DOSSIER) -> MoGe:
    chemin = dossier_poids() / dossier / "model.pt"
    if not chemin.is_file():
        raise FileNotFoundError(f"poids MoGe-2 introuvables : {chemin}")
    lu = torch.load(chemin, map_location="cpu", weights_only=True)
    m = MoGe(**lu["model_config"])
    manque, trop = m.load_state_dict(lu["model"], strict=False)
    if manque or trop:
        raise RuntimeError(f"poids MoGe-2 inattendus : manque {manque[:5]}, en trop {trop[:5]}")
    appareil = appareil or ("cuda" if torch.cuda.is_available() else "cpu")
    return m.eval().to(appareil)


def _monter(brut: np.ndarray, masque: np.ndarray, echelle: float, focale_px: float | None) -> dict:
    """Des points bruts du réseau (à un recul près) aux points en mètres, pour le zoom trouvé ou imposé."""
    h, w = masque.shape
    diag = math.hypot(h, w)
    uv = _uv(w, h, w / h, dtype=torch.float32).numpy()
    iy, ix = np.linspace(0, h - 1, 64).round().astype(int), np.linspace(0, w - 1, 64).round().astype(int)
    pb, ub, mb = brut[iy][:, ix], uv[iy][:, ix], masque[iy][:, ix]
    if int(mb.sum()) < 2:
        raise ValueError("MoGe-2 : aucun point fiable dans la photo")
    f, d = focale_et_decalage(ub[mb], pb[mb], None if focale_px is None else focale_px * 2 / diag)
    focale_px = f / 2 * diag  # f est relative à la demi-diagonale
    z = brut[..., 2] + d
    prof = z * echelle
    v, u = np.meshgrid(np.arange(h, dtype=np.float32) + 0.5 - h / 2, np.arange(w, dtype=np.float32) + 0.5 - w / 2, indexing="ij")
    points = np.stack([u / focale_px * prof, v / focale_px * prof, prof], -1).astype(np.float32)
    return {"points": points, "profondeur": prof.astype(np.float32), "masque": masque & (z > 0), "focale_px": float(focale_px)}


def relire(r: dict, focale_px: float) -> dict:
    """La même lecture, pour un AUTRE zoom (MoGe-2 hésite entre « zoom fort, pièce profonde » et « grand angle, pièce
    courte » : largeurs et hauteurs restent justes, la profondeur suit le zoom)."""
    return {**r, **_monter(r["brut"], r["masque_brut"], r["echelle"], focale_px)}


@torch.no_grad()
def lire(modele: MoGe, rgb: np.ndarray, finesse: int = 9, focale_px: float | None = None) -> dict:
    """rgb : (H, W, 3) uint8. Rend `points` (H, W, 3) en mètres dans le repère de l'appareil (x droite, y bas, z devant),
    `profondeur`, `masque` (points fiables), `normales`, `focale_px` (en pixels de la photo ; trouvée, ou imposée)."""
    appareil = next(modele.parameters()).device
    h, w = rgb.shape[:2]
    x = torch.from_numpy(rgb.astype(np.float32) / 255.0).permute(2, 0, 1)[None].to(appareil)
    mini, maxi = modele.carres
    carres = int(mini + finesse / 9 * (maxi - mini))
    with torch.autocast(device_type=appareil.type, dtype=torch.float16, enabled=appareil.type == "cuda"):
        s = modele(x, carres)
    brut = s["points"][0].float().cpu().numpy()
    masque = (s["mask"][0] > 0.5).cpu().numpy() if "mask" in s else np.ones((h, w), bool)
    echelle = float(s["metric_scale"][0]) if "metric_scale" in s else 1.0
    r = {"brut": brut, "masque_brut": masque, "echelle": echelle, **_monter(brut, masque, echelle, focale_px)}
    if "normal" in s:
        r["normales"] = s["normal"][0].float().cpu().numpy()
    return r
