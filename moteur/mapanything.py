"""MapAnything (Meta), variante « apache » : d'un LOT de photos d'un même lieu, la place de chaque appareil EN MÈTRES.

POURQUOI : Depth Anything 3 (`da3.py`) recoupe bien les photos d'une même pièce mais à une échelle LIBRE (il faut MoGe-2
ou la hauteur sous plafond pour passer en mètres). MapAnything regarde les photos ENSEMBLE et rend, pour chacune : où
était l'appareil par rapport au premier (place + direction), la direction du rayon de vue de chaque pixel (donc le zoom),
la profondeur de chaque pixel, ET un facteur d'échelle qui met le tout en mètres.

Licence : code Apache 2.0 (dépôts facebookresearch/map-anything et castacks/UniCeption), poids
`facebook/map-anything-apache` Apache 2.0 (4,9 Go, dans ..\\atelya\\modeles-externes\\map-anything-apache). L'autre
variante (`facebook/map-anything`) est CC BY-NC : INTERDITE. Aucun code venu d'internet n'est lancé : le réseau est
réécrit ici d'après les fichiers d'origine (mapanything/models/mapanything/model.py, utils/image.py, utils/cropping.py,
utils/geometry.py, utils/inference.py ; uniception : encoders/dinov2.py, info_sharing/alternating_attention_transformer.py,
utils/transformer_blocks.py, prediction_heads/dpt.py, pose_head.py, mlp_head.py, adaptors.py, libs/croco/dpt_block.py ;
et le ViT de DINOv2). Seuls les POIDS sont lus, à la main, tenseur par tenseur.

Le réseau, dans l'ordre :
  1. l'œil : DINOv2 ViT-g/14, ses 24 premiers blocs, sans norme finale ; chaque photo seule ;
  2. une norme (`fusion_norm_layer`) sur les carrés de chaque photo (pas sur son jeton de tête) ;
  3. le partage : 16 blocs qui regardent tour à tour TOUTES les photos à la fois (blocs pairs) puis chaque photo seule
     (blocs impairs) ; la 1re photo est marquée « repère » ; un jeton d'échelle voyage avec les blocs pairs ;
  4. les têtes : DPT (rayons + profondeur + confiance + masque par pixel), pose (place + quaternion), échelle (mètres).

NON réécrit (inutile ici, on ne donne QUE des images) : les entrées géométriques facultatives (zoom, profondeur ou pose
déjà connus : `ray_dirs_encoder`, `depth_encoder`, `depth_scale_encoder`, `cam_rot_encoder`, `cam_trans_encoder`,
`cam_trans_scale_encoder`). Dans l'original, sans ces entrées, leur sortie est multipliée par zéro avant d'être ajoutée :
seul reste `fusion_norm_layer`, reproduit ici. Leurs poids sont IGNORÉS au chargement (liste `IGNORES`). Non réécrits
non plus : le masque des bords (arêtes de profondeur) et la confiance « multi-vues » du post-traitement d'origine.

Écarts connus à l'original : demi-précision float16 au lieu de bfloat16 pour l'œil et le partage (les normes et les têtes
restent en float32) ; réduction des photos par un Lanczos écrit ici (comme Pillow, à l'arrondi près).

MESURES (14/11/2026, RTX 2070 8 Go ; banc `pc/essais-cameras-seules/moge20.py`) : chargement ~5 s une fois le fichier
lu par Windows, 2,2 Go sur la carte ; un lot de 2 photos 0,4 s, 5 photos 1,1 s, 11 photos 2,8 s ; au plus 3,4 Go.
float16 contre float32 (même lot) : rotations identiques, profondeurs à 0,02 % près. Contrôle du portage sur 94 paires
de photos FABRIQUÉES aux caméras connues exactement (`..telya2rique-photos-essais`) : rotation médiane 3,1°
(68 paires à moins de 5°), distance trouvée / vraie 0,95, zoom / vrai 0,96. Sur les 22 vraies photos (34 paires de la même
pièce, relevé à la main) : rotation juste (< 15°) 25, déplacement juste (< 1 m, < 15°) 10 ; le zoom sort trop COURT
(0,82 × la main : ne pas s'en servir) et les distances un peu courtes (0,92 × ; échelle 0,82 × celle de MoGe-2).
"""
from __future__ import annotations

import json
import struct
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from .oeil_dinov2 import ECART, MOYENNE, dossier_poids

CARRE = 14
COTE = 518
# « fixed_mapping » d'origine : rapport large / haut moyen du lot → (large, haut) donné au réseau
TAILLES = {1.000: (518, 518), 1.321: (518, 392), 1.542: (518, 336), 1.762: (518, 294), 2.056: (518, 252),
           3.083: (518, 168), 0.757: (392, 518), 0.649: (336, 518), 0.567: (294, 518), 0.486: (252, 518)}
MEMOIRE_ATTENTION = 1.2e9  # octets : au-delà, les têtes d'attention sont calculées par paquets (lots de > 5 photos)
IGNORES = ("ray_dirs_encoder.", "depth_encoder.", "depth_scale_encoder.", "cam_rot_encoder.", "cam_trans_encoder.",
           "cam_trans_scale_encoder.")
_TYPES = {"F64": np.float64, "F32": np.float32, "F16": np.float16, "I64": np.int64, "I32": np.int32, "U8": np.uint8}


# ---------------------------------------------------------------- les blocs (les mêmes dans l'œil et dans le partage)
class _Norme(nn.LayerNorm):
    """Norme calculée en float32 même quand le reste est en demi-précision (en float16 les carrés débordent)."""

    def forward(self, x):
        return F.layer_norm(x.float(), self.normalized_shape, self.weight.float(), self.bias.float(), self.eps).to(x.dtype)


class _Attention(nn.Module):
    def __init__(self, dim, tetes, **k):
        super().__init__()
        self.tetes = tetes
        self.qkv, self.proj = nn.Linear(dim, dim * 3, **k), nn.Linear(dim, dim, **k)

    def forward(self, x):
        B, N, C = x.shape
        q, k, v = self.qkv(x).reshape(B, N, 3, self.tetes, C // self.tetes).permute(2, 0, 3, 1, 4)
        pas = max(1, int(MEMOIRE_ATTENTION / (B * N * N * x.element_size())))
        if pas >= self.tetes:
            o = F.scaled_dot_product_attention(q, k, v)
        else:  # beaucoup de jetons : quelques têtes à la fois, même résultat, moins de mémoire
            o = torch.cat([F.scaled_dot_product_attention(q[:, i:i + pas], k[:, i:i + pas], v[:, i:i + pas])
                           for i in range(0, self.tetes, pas)], 1)
        return self.proj(o.transpose(1, 2).reshape(B, N, C))


class _Echelle(nn.Module):
    def __init__(self, dim, **k):
        super().__init__()
        self.gamma = nn.Parameter(torch.ones(dim, **k))

    def forward(self, x):
        return x * self.gamma


class _SwiGLU(nn.Module):
    """Le « MLP » de DINOv2 géant (« swiglufused ») : deux moitiés, l'une sert de porte à l'autre."""

    def __init__(self, dim, **k):
        super().__init__()
        cache = (int(dim * 4 * 2 / 3) + 7) // 8 * 8
        self.w12, self.w3 = nn.Linear(dim, 2 * cache, **k), nn.Linear(cache, dim, **k)

    def forward(self, x):
        a, b = self.w12(x).chunk(2, -1)
        return self.w3(F.silu(a) * b)


class _Bloc(nn.Module):
    def __init__(self, dim, tetes, **k):
        super().__init__()
        self.norm1, self.norm2 = _Norme(dim, eps=1e-6, **k), _Norme(dim, eps=1e-6, **k)
        self.attn, self.mlp = _Attention(dim, tetes, **k), _SwiGLU(dim, **k)
        self.ls1, self.ls2 = _Echelle(dim, **k), _Echelle(dim, **k)

    def forward(self, x):
        x = x + self.ls1(self.attn(self.norm1(x)))
        return x + self.ls2(self.mlp(self.norm2(x)))


# ---------------------------------------------------------------- l'œil (DINOv2 ViT-g/14, 24 blocs, sans norme finale)
class _Patchs(nn.Module):
    def __init__(self, dim, **k):
        super().__init__()
        self.proj = nn.Conv2d(3, dim, CARRE, CARRE, **k)

    def forward(self, x):
        return self.proj(x).flatten(2).transpose(1, 2)


class _Oeil(nn.Module):
    def __init__(self, dim, tetes, blocs, **k):
        super().__init__()
        self.dim = dim
        self.patch_embed = _Patchs(dim, **k)
        self.cls_token = nn.Parameter(torch.zeros(1, 1, dim, **k))
        self.pos_embed = nn.Parameter(torch.zeros(1, 1370, dim, **k))
        self.blocks = nn.ModuleList(_Bloc(dim, tetes, **k) for _ in range(blocs))

    def _places(self, h, w):
        """Encodage de position appris sur 37 × 37 carrés, étiré (bicubique, « + 0,1 » d'origine) à h × w."""
        N = self.pos_embed.shape[1] - 1
        M = int(N ** 0.5)
        if h * w == N and h == w:
            return self.pos_embed
        p = self.pos_embed.float()
        g = F.interpolate(p[:, 1:].reshape(1, M, M, self.dim).permute(0, 3, 1, 2), mode="bicubic", antialias=False,
                          scale_factor=((h + 0.1) / M, (w + 0.1) / M))
        assert g.shape[-2:] == (h, w)
        return torch.cat((p[:, :1], g.permute(0, 2, 3, 1).reshape(1, -1, self.dim)), 1).to(self.pos_embed.dtype)

    def forward(self, x):
        """x : (S, 3, H, W) → carrés (S, h*w, dim), ligne par ligne, et jeton de tête (S, dim) de chaque photo."""
        S, _, H, W = x.shape
        x = self.patch_embed(x)
        x = torch.cat((self.cls_token.expand(S, -1, -1), x), 1) + self._places(H // CARRE, W // CARRE)
        for bloc in self.blocks:
            x = bloc(x)
        return x[:, 1:], x[:, 0]


class _Colonne(nn.Module):
    def __init__(self, dim, tetes, blocs, **k):
        super().__init__()
        self.model = _Oeil(dim, tetes, blocs, **k)


# ---------------------------------------------------------------- le partage entre photos (attention alternée)
class _Partage(nn.Module):
    def __init__(self, dim, tetes, blocs, sorties, **k):
        super().__init__()
        self.sorties = tuple(sorties)
        self.self_attention_blocks = nn.ModuleList(_Bloc(dim, tetes, **k) for _ in range(blocs))
        self.norm = _Norme(dim, eps=1e-6, **k)
        table = torch.zeros(1, dim, **k)  # marque de la photo « repère » : onde de la position 0 = 0, 1, 0, 1…
        if table.device.type != "meta":
            table[:, 1::2] = 1.0
        self.register_buffer("view_pos_table", table)

    def forward(self, carres, tetes, jeton):
        """carres (S, n, dim), tetes (S, dim), jeton d'échelle (dim) → [carrés normés après les blocs `sorties`, puis
        après le dernier] (chacun (S, n, dim)) et le jeton d'échelle normé (dim).
        Dans chaque photo : ses carrés PUIS son jeton de tête ; les photos à la suite ; le jeton d'échelle tout au bout."""
        S, n, D = carres.shape
        x = torch.cat((carres, tetes[:, None]), 1)
        x = torch.cat((x[:1] + self.view_pos_table.to(x.dtype), x[1:]), 0)  # la 1re photo est le repère
        e = jeton.reshape(1, 1, D)
        gardes = []
        for i, bloc in enumerate(self.self_attention_blocks):
            if i % 2 == 0:  # toutes les photos ensemble, avec le jeton d'échelle
                t = bloc(torch.cat((x.reshape(1, S * (n + 1), D), e), 1))
                x, e = t[:, :-1].reshape(S, n + 1, D), t[:, -1:]
            else:           # chaque photo seule ; le jeton d'échelle attend
                x = bloc(x)
            if i in self.sorties:
                gardes.append(self.norm(x[:, :n]))
        return gardes + [self.norm(x[:, :n])], self.norm(e)[0, 0]


# ---------------------------------------------------------------- les têtes
class _Residu(nn.Module):
    def __init__(self, f, **k):
        super().__init__()
        self.conv1, self.conv2 = nn.Conv2d(f, f, 3, 1, 1, **k), nn.Conv2d(f, f, 3, 1, 1, **k)

    def forward(self, x):
        return self.conv2(F.relu(self.conv1(F.relu(x)))) + x


class _Fusion(nn.Module):
    def __init__(self, f, lateral=True, **k):
        super().__init__()
        if lateral:
            self.resConfUnit1 = _Residu(f, **k)
        self.resConfUnit2 = _Residu(f, **k)
        self.out_conv = nn.Conv2d(f, f, 1, **k)

    def forward(self, y, lateral=None):
        if lateral is not None:
            y = y + self.resConfUnit1(lateral)
        y = F.interpolate(self.resConfUnit2(y), scale_factor=2, mode="bilinear", align_corners=True)
        return self.out_conv(y)


class _DPT(nn.Module):
    """Quatre niveaux (les carrés de l'œil, puis du partage après les blocs 7, 11 et 15) fondus en une carte 8 fois
    plus fine que les carrés."""

    def __init__(self, dim, f, canaux, **k):
        super().__init__()
        c = canaux
        avant = [nn.Sequential(nn.Conv2d(dim, c[0], 1, **k), nn.ConvTranspose2d(c[0], c[0], 4, 4, **k)),
                 nn.Sequential(nn.Conv2d(dim, c[1], 1, **k), nn.ConvTranspose2d(c[1], c[1], 2, 2, **k)),
                 nn.Sequential(nn.Conv2d(dim, c[2], 1, **k)),
                 nn.Sequential(nn.Conv2d(dim, c[3], 1, **k), nn.Conv2d(c[3], c[3], 3, 2, 1, **k))]
        self.input_process = nn.ModuleList(nn.Sequential(a, nn.Conv2d(ci, f, 3, 1, 1, bias=False, **k)) for a, ci in zip(avant, c))
        s = nn.Module()
        s.refinenet1, s.refinenet2, s.refinenet3 = _Fusion(f, **k), _Fusion(f, **k), _Fusion(f, **k)
        s.refinenet4 = _Fusion(f, lateral=False, **k)
        self.scratch = s

    def forward(self, niveaux):
        n = [p(x) for p, x in zip(self.input_process, niveaux)]
        y = self.scratch.refinenet4(n[3])[:, :, : n[2].shape[2], : n[2].shape[3]]
        y = self.scratch.refinenet3(y, n[2])
        y = self.scratch.refinenet2(y, n[1])
        return self.scratch.refinenet1(y, n[0])


class _Regresseur(nn.Module):
    def __init__(self, f, sorties=6, **k):
        super().__init__()
        self.conv1 = nn.Conv2d(f, f // 2, 3, 1, 1, **k)
        self.conv2 = nn.Sequential(nn.Conv2d(f // 2, f // 2, 3, 1, 1, **k), nn.ReLU(), nn.Conv2d(f // 2, sorties, 1, **k))

    def forward(self, x, taille):
        return self.conv2(F.interpolate(self.conv1(x), size=taille, mode="bilinear", align_corners=True))


class _ResConv(nn.Module):
    def __init__(self, c, **k):
        super().__init__()
        self.res_conv1, self.res_conv2, self.res_conv3 = nn.Conv2d(c, c, 1, **k), nn.Conv2d(c, c, 1, **k), nn.Conv2d(c, c, 1, **k)

    def forward(self, x):
        return x + F.relu(self.res_conv3(F.relu(self.res_conv2(F.relu(self.res_conv1(x))))))


class _Pose(nn.Module):
    """Des carrés finals d'une photo : la place de l'appareil (3) et sa rotation en quaternion x, y, z, w (4)."""

    def __init__(self, dim, c, **k):
        super().__init__()
        self.proj = nn.Conv2d(dim, c, 1, **k)
        self.res_conv = nn.ModuleList(_ResConv(c, **k) for _ in range(2))
        self.more_mlps = nn.Sequential(nn.Linear(c, c, **k), nn.ReLU(), nn.Linear(c, c, **k), nn.ReLU())
        self.fc_t, self.fc_rot = nn.Linear(c, 3, **k), nn.Linear(c, 4, **k)

    def forward(self, x):
        x = self.proj(x)
        for r in self.res_conv:
            x = r(x)
        x = self.more_mlps(x.mean((2, 3)))
        return self.fc_t(x), self.fc_rot(x)


class _TeteEchelle(nn.Module):
    def __init__(self, dim, c=196, **k):
        super().__init__()
        self.proj = nn.Linear(dim, c, **k)
        self.mlp = nn.ModuleList(nn.Sequential(nn.Linear(c, c, **k), nn.ReLU()) for _ in range(2))
        self.output_proj = nn.Linear(c, 1, **k)

    def forward(self, x):
        x = self.proj(x)
        for couche in self.mlp:
            x = couche(x)
        return self.output_proj(x)


# ---------------------------------------------------------------- le réseau entier
class MapAnything(nn.Module):
    """Les noms des sous-modules sont ceux du fichier de poids. `demi` : œil et partage en float16 (les normes calculent
    en float32, les têtes restent en float32). `appareil="meta"` : les formes seulement, sans mémoire (pour comparer au
    fichier de poids). Les valeurs par défaut sont celles de `config.json` ; plus petites pour les tests."""

    def __init__(self, dim=1536, tetes=24, blocs_oeil=24, blocs_partage=16, sorties=(7, 11), f=256,
                 canaux=(96, 192, 384, 768), demi=False, appareil=None):
        super().__init__()
        k = {"device": appareil}
        kd = {"device": appareil, "dtype": torch.float16 if demi else torch.float32}
        self.encoder = _Colonne(dim, tetes, blocs_oeil, **kd)
        self.fusion_norm_layer = _Norme(dim, eps=1e-6, **k)
        self.scale_token = nn.Parameter(torch.zeros(dim, **kd))
        self.info_sharing = _Partage(dim, tetes, blocs_partage, sorties, **kd)
        self.dense_head = nn.Sequential(_DPT(dim, f, canaux, **k), _Regresseur(f, **k))
        self.pose_head = _Pose(dim, 4 * CARRE * CARRE, **k)
        self.scale_head = _TeteEchelle(dim, **k)

    @torch.no_grad()
    def forward(self, x, lot_oeil=8, lot_tetes=2):
        """x : (S, 3, H, W), photos déjà normées, côtés multiples de 14, la 1re = le repère. Rend, à l'échelle LIBRE du
        réseau (à multiplier par `echelle` pour des mètres) : `rayons` (S, H, W, 3) directions de norme 1 dans le
        repère de chaque appareil, `long_rayon` (S, H, W) distance le long du rayon, `confiance` (S, H, W) ≥ 1,
        `masque` (S, H, W) vrai = point jugé sûr, `places` (S, 3), `quaternions` (S, 4) x y z w de norme 1, `echelle`."""
        S, _, H, W = x.shape
        h, w = H // CARRE, W // CARRE
        x = x.to(self.scale_token.dtype)
        vus = [self.encoder.model(x[s:s + lot_oeil]) for s in range(0, S, lot_oeil)]
        carres = self.fusion_norm_layer(torch.cat([c for c, _ in vus]))  # la norme : sur les carrés, pas sur le jeton de tête
        niveaux, e = self.info_sharing(carres, torch.cat([t for _, t in vus]), self.scale_token)
        if not all(bool(torch.isfinite(n).all()) for n in niveaux) or not bool(torch.isfinite(e).all()):
            raise FloatingPointError("MapAnything : débordement dans le réseau (demi-précision ?) : relancer avec demi=False")
        niveaux = [n.float().transpose(1, 2).reshape(S, -1, h, w) for n in [carres] + niveaux]
        dense = torch.cat([self.dense_head[1](self.dense_head[0]([n[s:s + lot_tetes] for n in niveaux]), (H, W))
                           for s in range(0, S, lot_tetes)])
        places, quats = self.pose_head(niveaux[3])
        rayons = dense[:, :3].permute(0, 2, 3, 1)
        return {"rayons": rayons / rayons.norm(dim=-1, keepdim=True).clamp(min=1e-8),
                "long_rayon": torch.exp(dense[:, 3]), "confiance": 1.0 + torch.exp(dense[:, 4]),
                "masque": torch.sigmoid(dense[:, 5]) > 0.5,
                "places": places, "quaternions": quats / quats.norm(dim=-1, keepdim=True).clamp(min=1e-8),
                "echelle": torch.exp(self.scale_head(e.float())).clamp(min=1e-8)[0]}


def quaternion_vers_matrice(q: torch.Tensor) -> torch.Tensor:
    """Quaternion (x, y, z, w) → matrice de rotation 3 × 3 (appareil → repère commun)."""
    i, j, k, r = torch.unbind(q, -1)
    d = 2.0 / (q * q).sum(-1)
    o = torch.stack((1 - d * (j * j + k * k), d * (i * j - k * r), d * (i * k + j * r),
                     d * (i * j + k * r), 1 - d * (i * i + k * k), d * (j * k - i * r),
                     d * (i * k - j * r), d * (j * k + i * r), 1 - d * (i * i + j * j)), -1)
    return o.reshape(q.shape[:-1] + (3, 3))


def zoom_depuis_rayons(rayons: np.ndarray) -> np.ndarray:
    """D'une carte de rayons (h, w, 3) d'un appareil à sténopé : (fx, fy, cx, cy) en pixels, par moindres carrés sur
    colonne = cx + fx · (x / z) et ligne = cy + fy · (y / z), un pixel sur ~50 par côté (comme l'outil d'origine)."""
    h, w = rayons.shape[:2]
    ys, xs = np.arange(0, h, max(1, h // 50)), np.arange(0, w, max(1, w // 50))
    r = rayons[ys][:, xs].astype(np.float64)
    sortie = []
    for axe, grille in ((0, np.broadcast_to(xs[None, :], r.shape[:2])), (1, np.broadcast_to(ys[:, None], r.shape[:2]))):
        A = np.stack([np.ones(grille.size), (r[..., axe] / r[..., 2]).ravel()], 1)
        sortie.append(np.linalg.solve(A.T @ A, A.T @ grille.ravel().astype(np.float64)))
    (cx, fx), (cy, fy) = sortie
    return np.array([fx, fy, cx, cy])


# ---------------------------------------------------------------- les poids
def _entete(chemin: Path) -> tuple[dict, dict, int]:
    """Fichier safetensors : 8 octets (taille de l'en-tête), en-tête JSON {nom: {dtype, shape, data_offsets}}, puis les
    nombres bruts. → (en-tête, alias, place du premier nombre). Les ALIAS (`__metadata__`) : un même tenseur connu sous
    deux noms dans le réseau d'origine (p. ex. `dpt_feature_head.*` = `dense_head.0.*`) n'est écrit qu'une fois."""
    with open(chemin, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        entete = json.loads(f.read(n))
    alias = entete.pop("__metadata__", None) or {}
    return entete, {a: v for a, v in alias.items() if v in entete}, 8 + n


def comparer_aux_poids(dossier: Path | None = None, modele: MapAnything | None = None) -> dict:
    """Sans lire les nombres : chaque poids du réseau réécrit a-t-il sa place dans le fichier, et l'inverse ?
    → `source` {nom dans le réseau: nom dans le fichier}, `manquants` (dans le réseau, pas dans le fichier), `en_trop`
    (dans le fichier, ni pris ni dans IGNORES), `ignores` (entrées géométriques non réécrites), `formes_fausses`,
    `alias` (noms en double du fichier ; aucun n'est nécessaire ici, nos noms sont ceux sous lesquels c'est écrit)."""
    dossier = Path(dossier or dossier_poids() / "map-anything-apache")
    entete, alias, _ = _entete(dossier / "model.safetensors")
    formes = {n: tuple(t.shape) for n, t in (modele or MapAnything(appareil="meta")).state_dict().items()}
    source = {n: (n if n in entete else alias.get(n)) for n in formes}
    manquants = sorted(n for n, s in source.items() if s is None)
    source = {n: s for n, s in source.items() if s is not None}
    pris = set(source.values())
    return {"source": source, "manquants": manquants,
            "formes_fausses": sorted(n for n, s in source.items() if tuple(entete[s]["shape"]) != formes[n]),
            "ignores": sorted(n for n in entete if n not in pris and n.startswith(IGNORES)),
            "en_trop": sorted(n for n in entete if n not in pris and not n.startswith(IGNORES)),
            "alias": alias, "nombres": {n: int(np.prod(i["shape"])) for n, i in entete.items()}}


def charger(dossier: Path | None = None, appareil: str | None = None, demi: bool | None = None) -> MapAnything:
    """Construit le réseau directement sur `appareil` (cuda par défaut) et y verse les poids TENSEUR PAR TENSEUR : jamais
    plus d'un tenseur du fichier en mémoire vive (le fichier fait 4,9 Go, le PC a 16 Go). `demi` (défaut : oui sur la
    carte) : œil et partage en float16, soit ~2,5 Go sur la carte au lieu de 4,9."""
    dossier = Path(dossier or dossier_poids() / "map-anything-apache")
    chemin = dossier / "model.safetensors"
    if not chemin.is_file():
        raise FileNotFoundError(f"poids de MapAnything introuvables : {chemin}")
    appareil = appareil or ("cuda" if torch.cuda.is_available() else "cpu")
    demi = torch.device(appareil).type == "cuda" if demi is None else demi
    m = MapAnything(demi=demi, appareil=appareil)
    c = comparer_aux_poids(dossier, m)
    if c["manquants"] or c["en_trop"] or c["formes_fausses"]:
        raise RuntimeError(f"poids de MapAnything incompatibles : manquants {c['manquants'][:5]}, en trop {c['en_trop'][:5]}, "
                           f"formes fausses {c['formes_fausses'][:5]}")
    entete, _, debut = _entete(chemin)
    with open(chemin, "rb") as f, torch.no_grad():
        for nom, cible in m.state_dict().items():
            info = entete[c["source"][nom]]
            a, b = info["data_offsets"]
            t = np.empty(info["shape"], _TYPES[info["dtype"]])
            f.seek(debut + a)
            if f.readinto(t) != b - a or t.nbytes != b - a:
                raise RuntimeError(f"poids de MapAnything : tenseur {nom} tronqué")
            cible.copy_(torch.from_numpy(t))  # copie vers la carte et, s'il le faut, vers la demi-précision
    return m.eval()


# ---------------------------------------------------------------- les photos
def _poids_reduction(n: int, m: int, lanczos: bool) -> np.ndarray:
    """Matrice (m, n) qui passe de n à m pixels, comme Pillow : Lanczos 3 (quand on réduit) ou bicubique a = -0,5
    (quand on agrandit), élargi d'autant qu'on réduit ; chaque ligne somme à 1."""
    pas = n / m
    large = max(pas, 1.0)
    rayon = (3.0 if lanczos else 2.0) * large
    P = np.zeros((m, n), np.float32)
    for i in range(m):
        c = (i + 0.5) * pas
        a, b = max(0, int(c - rayon + 0.5)), min(n, int(c + rayon + 0.5))
        x = np.abs((np.arange(a, b) + 0.5 - c) / large)
        if lanczos:
            p = np.where(x < 3, np.sinc(x) * np.sinc(x / 3), 0.0)
        else:
            p = np.where(x < 1, (1.5 * x - 2.5) * x * x + 1, np.where(x < 2, ((-0.5 * x + 2.5) * x - 4) * x + 2, 0.0))
        P[i, a:b] = p / p.sum()
    return P


def _redimensionner(rgb: np.ndarray, nw: int, nh: int, lanczos: bool) -> np.ndarray:
    """Comme `PIL.Image.resize` : les colonnes d'abord, puis les lignes, avec retour à des entiers 0-255 entre les deux."""
    x = torch.from_numpy(np.ascontiguousarray(rgb)).float()
    x = torch.einsum("hwc,ow->hoc", x, torch.from_numpy(_poids_reduction(rgb.shape[1], nw, lanczos))).round().clamp(0, 255)
    x = torch.einsum("hwc,oh->owc", x, torch.from_numpy(_poids_reduction(rgb.shape[0], nh, lanczos))).round().clamp(0, 255)
    return x.numpy().astype(np.uint8)


def taille_visee(photos: list[np.ndarray], cote: int = COTE) -> tuple[int, int]:
    """(large, haut) donné au réseau pour tout le lot, d'après le rapport large / haut MOYEN des photos : table d'origine
    pour 518 ; sinon plus grand côté = `cote` (ramené à un multiple de 14), l'autre arrondi à 14."""
    r = float(np.mean([p.shape[1] / p.shape[0] for p in photos]))
    if cote == COTE:
        return TAILLES[min(TAILLES, key=lambda k: abs(k - r))]
    n = cote // CARRE
    return (n * CARRE, max(1, round(n / r)) * CARRE) if r >= 1 else (max(1, round(n * r)) * CARRE, n * CARRE)


def preparer(rgb: np.ndarray, taille: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Photo (H, W, 3) uint8 → (photo réduite pour COUVRIR `taille` = (large, haut) puis rognée au centre, cadre) ;
    le cadre = (x0, y0, x1, y1) : la partie de la photo d'origine (en ses pixels) que voit le réseau."""
    tw, th = taille
    h, w = rgb.shape[:2]
    e = max(tw / w, th / h) + 1e-8
    nw, nh = int(np.floor(w * e)), int(np.floor(h * e))
    im = rgb if (nw, nh) == (w, h) else _redimensionner(rgb, nw, nh, lanczos=e < 1)
    g, t = (nw - tw) // 2, (nh - th) // 2
    return im[t:t + th, g:g + tw], np.array([g * w / nw, t * h / nh, (g + tw) * w / nw, (t + th) * h / nh])


@torch.no_grad()
def lire(modele: MapAnything, photos: list[np.ndarray], cote: int = COTE) -> dict:
    """photos : liste de (H, W, 3) uint8 RGB d'un même lieu ; la 1re sert de repère. Rend, EN MÈTRES :
      `profondeur` (S, h, w) : profondeur z dans le repère de chaque appareil, sur les photos réduites ;
      `confiance` (S, h, w) ≥ 1 ; `masque` (S, h, w) : vrai = point jugé sûr par le réseau (ni ciel ni reflet) ;
      `appareils` (S, 3, 4) : [rotation | place] appareil → repère commun, celui de la 1re photo TEL QUE LE RÉSEAU LE
                  REND (son propre appareil sort presque, pas exactement, à l'origine sans rotation) ; axes de
                  l'appareil : x à droite, y en bas, z devant ;
      `focale_px` (S, 2) : zoom (large, haut) en pixels de la photo RÉDUITE, déduit des rayons ; `centre_px` (S, 2) ;
      `taille` (h, w) ; `cadre` (S, 4) : x0, y0, x1, y1, la partie de chaque photo d'origine vue par le réseau ;
      `echelle` : le facteur métrique du réseau (déjà appliqué à `profondeur` et aux places) ;
      `rayons` (S, h, w, 3) : direction de vue de chaque pixel dans le repère de son appareil."""
    taille = taille_visee(photos, cote)
    prets = [preparer(p, taille) for p in photos]
    x = np.stack([(im.astype(np.float32) / 255.0 - MOYENNE) / ECART for im, _ in prets]).transpose(0, 3, 1, 2)
    app = next(modele.parameters()).device
    s = modele(torch.from_numpy(np.ascontiguousarray(x)).to(app))
    e = float(s["echelle"])
    rayons = s["rayons"].cpu().numpy()
    zoom = np.stack([zoom_depuis_rayons(r) for r in rayons])
    R = quaternion_vers_matrice(s["quaternions"])
    return {"profondeur": (s["rayons"][..., 2] * s["long_rayon"] * e).cpu().numpy(), "confiance": s["confiance"].cpu().numpy(),
            "masque": s["masque"].cpu().numpy(),
            "appareils": torch.cat((R, s["places"][..., None] * e), -1).cpu().numpy(),
            "focale_px": zoom[:, :2].astype(np.float32), "centre_px": zoom[:, 2:].astype(np.float32),
            "taille": (taille[1], taille[0]), "cadre": np.stack([c for _, c in prets]), "echelle": e, "rayons": rayons}
