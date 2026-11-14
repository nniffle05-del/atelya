"""Depth Anything 3 « base » (ByteDance) : d'un LOT de photos d'un même lieu, la place et le zoom de chaque appareil.

POURQUOI : une photo seule ne suffit pas à dire d'où elle est prise (deux coins de pièce se ressemblent). Ce réseau
regarde plusieurs photos ENSEMBLE et rend, pour chacune : où était l'appareil par rapport aux autres (place + direction),
son zoom, et la profondeur de chaque pixel. L'échelle est LIBRE (les distances sont justes entre elles, pas en mètres) :
la mise en mètres reste à faire avec MoGe-2 ou la hauteur sous plafond.

Licence (lue le 14/11/2026) : code Apache 2.0 (dépôt ByteDance-Seed/Depth-Anything-3), poids `depth-anything/DA3-BASE`
Apache 2.0 (541 Mo, accord écrit de NT du 14/11/2026). Les versions « large », « giant » et « nested » sont CC BY-NC :
INTERDITES. Aucun code venu d'internet n'est lancé : le réseau est réécrit ici d'après les fichiers d'origine
(model/dinov2/*, model/dualdpt.py, model/dpt.py, model/cam_dec.py, model/utils/transform.py) ; seuls les POIDS sont lus,
à la main (`owlv2.lire_safetensors`), dans ..\\atelya\\modeles-externes\\da3-base.

Non réécrit (inutile ici) : la branche « rayons », l'entrée « appareils déjà connus » (cam_enc), les gaussiennes.
"""
from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .oeil_dinov2 import ECART, MOYENNE, dossier_poids
from .owlv2 import lire_safetensors

CARRE = 14
COTE = 504          # plus grand côté des photos données au réseau (px)
DEBUT_ENSEMBLE = 4  # à partir de ce bloc : un bloc sur deux regarde TOUTES les photos à la fois
SORTIES = (5, 7, 9, 11)


# ---------------------------------------------------------------- l'œil (DINOv2 ViT-B/14 modifié)
class _Tours(nn.Module):
    """Position de chaque carré donnée par ROTATION des nombres (« RoPE » 2D), fréquence 100."""

    def __init__(self):
        super().__init__()
        self.cache = {}

    def _un_axe(self, x, pos):
        d = x.shape[-1]
        cle = (d, int(pos.max()) + 1, x.device, x.dtype)
        if cle not in self.cache:
            inv = 1.0 / (100.0 ** (torch.arange(0, d, 2, device=x.device).float() / d))
            ang = torch.einsum("i,j->ij", torch.arange(cle[1], device=x.device, dtype=inv.dtype), inv)
            ang = torch.cat((ang, ang), -1).to(x.dtype)
            self.cache[cle] = (ang.cos(), ang.sin())
        c, s = self.cache[cle]
        c, s = F.embedding(pos, c)[:, None], F.embedding(pos, s)[:, None]
        x1, x2 = x[..., : d // 2], x[..., d // 2:]
        return x * c + torch.cat((-x2, x1), -1) * s

    def forward(self, x, pos):  # x : (lot, têtes, jetons, d) ; pos : (lot, jetons, 2) = ligne, colonne
        v, h = x.chunk(2, -1)
        return torch.cat((self._un_axe(v, pos[..., 0]), self._un_axe(h, pos[..., 1])), -1)


class _Attention(nn.Module):
    def __init__(self, dim, tetes, norme_qk, tours):
        super().__init__()
        self.tetes = tetes
        self.qkv = nn.Linear(dim, dim * 3)
        self.q_norm = nn.LayerNorm(dim // tetes) if norme_qk else nn.Identity()
        self.k_norm = nn.LayerNorm(dim // tetes) if norme_qk else nn.Identity()
        self.proj = nn.Linear(dim, dim)
        self.tours = [tours]  # dans une liste : objet partagé, sans poids, pas un sous-module

    def forward(self, x, pos=None):
        B, N, C = x.shape
        q, k, v = self.qkv(x).reshape(B, N, 3, self.tetes, C // self.tetes).permute(2, 0, 3, 1, 4)
        q, k = self.q_norm(q), self.k_norm(k)
        if self.tours[0] is not None and pos is not None:
            q, k = self.tours[0](q, pos), self.tours[0](k, pos)
        x = F.scaled_dot_product_attention(q, k, v)
        return self.proj(x.transpose(1, 2).reshape(B, N, C))


class _Echelle(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.gamma = nn.Parameter(torch.ones(dim))

    def forward(self, x):
        return x * self.gamma


class _Mlp(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.fc1, self.fc2 = nn.Linear(dim, dim * 4), nn.Linear(dim * 4, dim)

    def forward(self, x):
        return self.fc2(F.gelu(self.fc1(x)))


class _Bloc(nn.Module):
    def __init__(self, dim, tetes, norme_qk, tours):
        super().__init__()
        self.norm1, self.norm2 = nn.LayerNorm(dim, eps=1e-6), nn.LayerNorm(dim, eps=1e-6)
        self.attn, self.mlp = _Attention(dim, tetes, norme_qk, tours), _Mlp(dim)
        self.ls1, self.ls2 = _Echelle(dim), _Echelle(dim)

    def forward(self, x, pos=None):
        x = x + self.ls1(self.attn(self.norm1(x), pos))
        return x + self.ls2(self.mlp(self.norm2(x)))


class _Patchs(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.proj = nn.Conv2d(3, dim, CARRE, CARRE)

    def forward(self, x):
        return self.proj(x).flatten(2).transpose(1, 2)


def _photo_de_reference(x):
    """Quelle photo sert de repère (« saddle_balanced » d'origine) : celle dont le jeton de tête est le plus « moyen »."""
    S = x.shape[1]
    t = x[:, :, 0]
    u = t / t.norm(dim=-1, keepdim=True)
    sim = (u @ u.transpose(1, 2) - torch.eye(S, device=x.device)[None]).sum(-1) / (S - 1)
    mes = [sim, t.norm(dim=-1), u.var(dim=-1)]
    mes = [(m - m.min(1, keepdim=True).values) / (m.max(1, keepdim=True).values - m.min(1, keepdim=True).values + 1e-8) for m in mes]
    return int(sum((m - 0.5).abs() for m in mes).argmin(1)[0])


class _Oeil(nn.Module):
    def __init__(self, dim=768, tetes=12, blocs=12):
        super().__init__()
        self.dim = dim
        self.patch_embed = _Patchs(dim)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, dim))
        self.camera_token = nn.Parameter(torch.zeros(1, 2, dim))
        self.pos_embed = nn.Parameter(torch.zeros(1, 1370, dim))
        self.tours = _Tours()
        self.blocks = nn.ModuleList(_Bloc(dim, tetes, i >= DEBUT_ENSEMBLE, self.tours if i >= DEBUT_ENSEMBLE else None) for i in range(blocs))
        self.norm = nn.LayerNorm(dim)

    def _places(self, x, h, w):
        N = self.pos_embed.shape[1] - 1
        M = int(math.sqrt(N))
        if h * w == N and h == w:
            return self.pos_embed.to(x.dtype)
        p = self.pos_embed.float()
        g = F.interpolate(p[:, 1:].reshape(1, M, M, self.dim).permute(0, 3, 1, 2), mode="bicubic", antialias=False,
                          scale_factor=((h + 0.1) / M, (w + 0.1) / M))
        assert g.shape[-2:] == (h, w)
        return torch.cat((p[:, :1], g.permute(0, 2, 3, 1).reshape(1, -1, self.dim)), 1).to(x.dtype)

    def forward(self, x, reference: int | None = None):
        """x : (S, 3, H, W) → liste de (carrés (S, h*w, 2*dim), jeton d'appareil (S, 2*dim)) aux blocs SORTIES."""
        S, _, H, W = x.shape
        h, w = H // CARRE, W // CARRE
        x = self.patch_embed(x)
        x = torch.cat((self.cls_token.expand(S, -1, -1).to(x.dtype), x), 1)
        x = x + self._places(x, h, w)
        yy, xx = torch.meshgrid(torch.arange(h, device=x.device), torch.arange(w, device=x.device), indexing="ij")
        pos = torch.cat((torch.zeros(1, 2, dtype=torch.long, device=x.device), torch.stack((yy, xx), -1).reshape(-1, 2) + 1), 0)
        pos_seule = pos[None].expand(S, -1, -1)                                            # dans une photo : ligne, colonne
        pos_toutes = torch.cat((pos[:1], torch.ones_like(pos[1:])), 0).repeat(S, 1)[None]  # entre photos : pas de position
        ordre = list(range(S))
        seule, sorties = x, []
        for i, bloc in enumerate(self.blocks):
            if i == DEBUT_ENSEMBLE - 1 and (S >= 3 or reference is not None):
                ref = _photo_de_reference(x[None].float()) if reference is None else reference
                ordre = [ref] + [k for k in range(S) if k != ref]
                x, seule = x[ordre], seule[ordre]
            if i == DEBUT_ENSEMBLE:  # le jeton de tête devient le jeton « appareil » : repère pour la 1re, autre pour les suivantes
                x = x.clone()
                x[:, 0] = torch.cat((self.camera_token[0, :1], self.camera_token[0, 1:].expand(S - 1, -1)), 0).to(x.dtype)
            if i >= DEBUT_ENSEMBLE and i % 2 == 1:
                x = bloc(x.reshape(1, -1, self.dim), pos_toutes).reshape(S, -1, self.dim)
            else:
                x = bloc(x, pos_seule if i >= DEBUT_ENSEMBLE else None)
                seule = x
            if i in SORTIES:
                o = torch.cat((seule, x), -1)
                retour = [ordre.index(k) for k in range(S)]
                o = o[retour]
                sorties.append((torch.cat((o[:, 1:, : self.dim], self.norm(o[:, 1:, self.dim:])), -1), o[:, 0]))
        return sorties


# ---------------------------------------------------------------- la tête des profondeurs (DPT)
def _onde(dim, pos):
    om = 1.0 / 100 ** (torch.arange(dim // 2, dtype=torch.float32, device=pos.device) / (dim / 2.0))
    o = torch.einsum("m,d->md", pos.reshape(-1), om)
    return torch.cat((o.sin(), o.cos()), 1)


def _ajouter_places(x, W, H, part=0.1):
    """Petite onde qui dit à chaque point où il est dans la photo."""
    ph, pw = x.shape[-2:]
    a = W / H
    d = (a * a + 1.0) ** 0.5
    xs = torch.linspace(-a / d * (pw - 1) / pw, a / d * (pw - 1) / pw, pw, device=x.device)
    ys = torch.linspace(-1 / d * (ph - 1) / ph, 1 / d * (ph - 1) / ph, ph, device=x.device)
    uu, vv = torch.meshgrid(xs, ys, indexing="xy")
    c = x.shape[1]
    e = torch.cat((_onde(c // 2, uu), _onde(c // 2, vv)), -1).reshape(ph, pw, c) * part
    return x + e.permute(2, 0, 1)[None].to(x.dtype)


class _Residu(nn.Module):
    def __init__(self, f):
        super().__init__()
        self.conv1, self.conv2 = nn.Conv2d(f, f, 3, 1, 1), nn.Conv2d(f, f, 3, 1, 1)

    def forward(self, x):
        return self.conv2(F.relu(self.conv1(F.relu(x)))) + x


class _Fusion(nn.Module):
    def __init__(self, f, lateral=True):
        super().__init__()
        if lateral:
            self.resConfUnit1 = _Residu(f)
        self.resConfUnit2 = _Residu(f)
        self.out_conv = nn.Conv2d(f, f, 1)

    def forward(self, y, lateral=None, taille=None):
        if lateral is not None:
            y = y + self.resConfUnit1(lateral)
        y = self.resConfUnit2(y)
        y = F.interpolate(y, size=taille or (y.shape[-2] * 2, y.shape[-1] * 2), mode="bilinear", align_corners=True)
        return self.out_conv(y)


class _Tete(nn.Module):
    def __init__(self, dim=1536, f=128, canaux=(96, 192, 384, 768)):
        super().__init__()
        self.norm = nn.LayerNorm(dim)
        self.projects = nn.ModuleList(nn.Conv2d(dim, c, 1) for c in canaux)
        self.resize_layers = nn.ModuleList([nn.ConvTranspose2d(canaux[0], canaux[0], 4, 4), nn.ConvTranspose2d(canaux[1], canaux[1], 2, 2),
                                            nn.Identity(), nn.Conv2d(canaux[3], canaux[3], 3, 2, 1)])
        s = nn.Module()
        for i, c in enumerate(canaux):
            setattr(s, f"layer{i + 1}_rn", nn.Conv2d(c, f, 3, 1, 1, bias=False))
        s.refinenet1, s.refinenet2, s.refinenet3, s.refinenet4 = _Fusion(f), _Fusion(f), _Fusion(f), _Fusion(f, lateral=False)
        s.output_conv1 = nn.Conv2d(f, f // 2, 3, 1, 1)
        s.output_conv2 = nn.Sequential(nn.Conv2d(f // 2, 32, 3, 1, 1), nn.ReLU(), nn.Conv2d(32, 2, 1))
        self.scratch = s

    def forward(self, carres, H, W):
        """carres : 4 tenseurs (S, h*w, dim) → profondeur (S, H, W), confiance (S, H, W)."""
        S, _, C = carres[0].shape
        ph, pw = H // CARRE, W // CARRE
        n = []
        for i, c in enumerate(carres):
            x = self.norm(c).permute(0, 2, 1).reshape(S, C, ph, pw)
            n.append(self.resize_layers[i](_ajouter_places(self.projects[i](x), W, H)))
        s = self.scratch
        l1, l2, l3, l4 = s.layer1_rn(n[0]), s.layer2_rn(n[1]), s.layer3_rn(n[2]), s.layer4_rn(n[3])
        o = s.refinenet4(l4, taille=l3.shape[2:])
        o = s.refinenet3(o, l3, taille=l2.shape[2:])
        o = s.refinenet2(o, l2, taille=l1.shape[2:])
        o = s.output_conv1(s.refinenet1(o, l1))
        o = F.interpolate(o, size=(ph * CARRE, pw * CARRE), mode="bilinear", align_corners=True)
        o = s.output_conv2(_ajouter_places(o, W, H))
        return torch.exp(o[:, 0]), torch.exp(o[:, 1]) + 1


class _Appareils(nn.Module):
    """Du jeton « appareil » de chaque photo : déplacement (3), rotation en quaternion (4), angles de vue haut et large (2)."""

    def __init__(self, dim=1536):
        super().__init__()
        self.backbone = nn.Sequential(nn.Linear(dim, dim), nn.ReLU(), nn.Linear(dim, dim), nn.ReLU())
        self.fc_t, self.fc_qvec = nn.Linear(dim, 3), nn.Linear(dim, 4)
        self.fc_fov = nn.Sequential(nn.Linear(dim, 2), nn.ReLU())

    def forward(self, jeton):
        f = self.backbone(jeton)
        return self.fc_t(f), self.fc_qvec(f), self.fc_fov(f)


class _Colonne(nn.Module):
    def __init__(self):
        super().__init__()
        self.pretrained = _Oeil()


class DA3(nn.Module):
    def __init__(self):
        super().__init__()
        self.backbone, self.head, self.cam_dec = _Colonne(), _Tete(), _Appareils()


def quaternion_vers_matrice(q: torch.Tensor) -> torch.Tensor:
    """Quaternion (x, y, z, w) → matrice de rotation 3 × 3."""
    i, j, k, r = torch.unbind(q, -1)
    d = 2.0 / (q * q).sum(-1)
    o = torch.stack((1 - d * (j * j + k * k), d * (i * j - k * r), d * (i * k + j * r),
                     d * (i * j + k * r), 1 - d * (i * i + k * k), d * (j * k - i * r),
                     d * (i * k - j * r), d * (j * k + i * r), 1 - d * (i * i + j * j)), -1)
    return o.reshape(q.shape[:-1] + (3, 3))


# ---------------------------------------------------------------- usage
def charger(dossier: Path | None = None, appareil: str | None = None) -> DA3:
    dossier = Path(dossier or dossier_poids() / "da3-base")
    if not (dossier / "model.safetensors").is_file():
        raise FileNotFoundError(f"poids de Depth Anything 3 introuvables : {dossier / 'model.safetensors'}")
    m = DA3()
    poids = {k[6:]: v for k, v in lire_safetensors(dossier / "model.safetensors").items() if k.startswith("model.")}
    inutiles = ("cam_enc.", "_aux.")
    poids = {k: v for k, v in poids.items() if not any(s in k for s in inutiles)}
    manquants, en_trop = m.load_state_dict(poids, strict=False)
    if manquants or en_trop:
        raise RuntimeError(f"poids de Depth Anything 3 incompatibles : manquants {manquants[:5]}, en trop {en_trop[:5]}")
    appareil = appareil or ("cuda" if torch.cuda.is_available() else "cpu")
    return m.to(appareil).eval()


def preparer(rgb: np.ndarray, cote: int = COTE) -> np.ndarray:
    """Photo (H, W, 3) uint8 → photo réduite (plus grand côté = `cote`, côtés multiples de 14), comme l'outil d'origine."""
    h, w = rgb.shape[:2]
    e = cote / max(h, w)
    nw, nh = max(1, round(w * e)), max(1, round(h * e))
    im = cv2.resize(rgb, (nw, nh), interpolation=cv2.INTER_CUBIC if e > 1 else cv2.INTER_AREA)
    mw, mh = max(1, round(nw / CARRE)) * CARRE, max(1, round(nh / CARRE)) * CARRE
    if (mw, mh) != (nw, nh):
        im = cv2.resize(im, (mw, mh), interpolation=cv2.INTER_CUBIC if mw > nw or mh > nh else cv2.INTER_AREA)
    return im


@torch.no_grad()
def lire(modele: DA3, photos: list[np.ndarray], cote: int = COTE, reference: int | None = None) -> dict:
    """photos : liste de (H, W, 3) uint8 RGB, de même forme à peu près (sinon rognées au centre à la plus petite).
    Rend, à l'échelle LIBRE du réseau (la même pour toutes les photos du lot) :
      `profondeur` (S, h, w), `confiance` (S, h, w), sur les photos réduites ;
      `appareils` (S, 3, 4) : pour chaque photo, [rotation | place] de l'appareil dans le repère commun
                  (axes de l'appareil : x à droite, y en bas, z devant) ;
      `focale_px` (S, 2) : zoom en pixels de la photo RÉDUITE (large, haut) ; `taille` (h, w) ; `rognage` (S, 2)."""
    ims = [preparer(p, cote) for p in photos]
    h, w = min(i.shape[0] for i in ims), min(i.shape[1] for i in ims)
    rog = [((i.shape[0] - h) // 2, (i.shape[1] - w) // 2) for i in ims]
    ims = [i[t:t + h, g:g + w] for i, (t, g) in zip(ims, rog)]
    x = np.stack([(i.astype(np.float32) / 255.0 - MOYENNE) / ECART for i in ims]).transpose(0, 3, 1, 2)
    app = next(modele.parameters()).device
    x = torch.from_numpy(np.ascontiguousarray(x)).to(app)
    with torch.autocast(device_type=app.type, dtype=torch.float16, enabled=app.type == "cuda"):
        sorties = modele.backbone.pretrained(x, reference)
    carres = [c.float() for c, _ in sorties]
    prof, conf = [], []
    for s in range(0, len(ims), 4):  # la tête, 4 photos à la fois (mémoire)
        p, c = modele.head([c[s:s + 4] for c in carres], h, w)
        prof.append(p); conf.append(c)
    t, q, angles = modele.cam_dec(sorties[-1][1].float())
    R = quaternion_vers_matrice(q)
    fy = (h / 2.0) / torch.clamp(torch.tan(angles[:, 0] / 2.0), min=1e-6)
    fx = (w / 2.0) / torch.clamp(torch.tan(angles[:, 1] / 2.0), min=1e-6)
    return {"profondeur": torch.cat(prof).cpu().numpy(), "confiance": torch.cat(conf).cpu().numpy(),
            "appareils": torch.cat((R, t[..., None]), -1).cpu().numpy(), "focale_px": torch.stack((fx, fy), -1).cpu().numpy(),
            "taille": (h, w), "rognage": np.array(rog)}
