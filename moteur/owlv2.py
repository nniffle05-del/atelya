"""OWLv2 de Google : un détecteur d'objets « à qui on dit quoi chercher » (brique photos, 10/11/2026).

On lui donne une photo et des mots (« a bed », « a dining table »…) ; il rend des RECTANGLES autour des objets qui
correspondent, avec une note de confiance. Il a appris sur des millions de VRAIES photos : il sait déjà ce qu'est un lit
avec sa couette, là où nos photos fabriquées (Blender) ne montrent que des blocs lisses.

Licence : Apache 2.0 pour le code ET les poids (README officiel scenic/projects/owl_vit, § License ; texte lu en entier :
..\\atelya\\modeles-externes\\owlv2-base\\LICENSE-scenic-Apache-2.0.txt). Accord de NT pour le téléchargement : 10/11/2026.

Aucun code venu d'internet n'est lancé et aucune bibliothèque n'est installée : le réseau est RÉÉCRIT ici d'après
l'implémentation de référence (transformers/models/owlv2/modeling_owlv2.py, Apache 2.0, © The HuggingFace Team et Google),
et seuls les POIDS officiels sont lus, à la main (format « safetensors » = un en-tête JSON puis des nombres bruts : aucun
code ne peut s'y cacher). Le découpage des mots (« BPE » de CLIP) est réécrit aussi (vocab.json et merges.txt).

Architecture (version de base, B/16) : photo remise au carré (gris à droite / en bas) et réduite à 960 × 960 ; découpée
en 60 × 60 carrés de 16 px ; un « transformeur » de vision (12 blocs, largeur 768) ; pour CHAQUE carré : un rectangle
proposé (box_head), une note « c'est un objet » (objectness_head) et une empreinte comparée aux mots (class_head).
Les mots passent par le transformeur de texte de CLIP (12 blocs, largeur 512, 16 jetons au plus).
"""
from __future__ import annotations

import functools
import json
import os
import re
import struct
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

POIDS_PC = Path(__file__).resolve().parents[2] / "atelya" / "modeles-externes" / "owlv2-base"
MOYENNE = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
ECART = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)
TAILLE = 960
CARRE = 16
JETONS = 16
DEBUT, FIN = 49406, 49407


def dossier_poids() -> Path:
    return Path(os.environ.get("ATELYA_OWLV2", POIDS_PC))


# ---------------------------------------------------------------- lecture des poids (safetensors) à la main
_TYPES = {"F32": np.float32, "F16": np.float16, "I64": np.int64}


def lire_safetensors(chemin: Path) -> dict[str, torch.Tensor]:
    """Fichier safetensors : 8 octets (taille de l'en-tête), en-tête JSON {nom: {dtype, shape, data_offsets}}, puis les
    nombres bruts. Aucun code exécuté."""
    with open(chemin, "rb") as f:
        n = struct.unpack("<Q", f.read(8))[0]
        entete = json.loads(f.read(n))
        brut = f.read()
    sortie = {}
    for nom, info in entete.items():
        if nom == "__metadata__":
            continue
        a, b = info["data_offsets"]
        t = np.frombuffer(brut, dtype=_TYPES[info["dtype"]], count=(b - a) // np.dtype(_TYPES[info["dtype"]]).itemsize,
                          offset=a).reshape(info["shape"])
        sortie[nom] = torch.from_numpy(t.copy())
    return sortie


# ---------------------------------------------------------------- découpage des mots (BPE de CLIP)
@functools.lru_cache(maxsize=1)
def _octets_vers_lettres() -> dict[int, str]:
    bs = list(range(ord("!"), ord("~") + 1)) + list(range(ord("¡"), ord("¬") + 1)) + list(range(ord("®"), ord("ÿ") + 1))
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b)
            cs.append(256 + n)
            n += 1
    return dict(zip(bs, [chr(c) for c in cs]))


class Mots:
    """Transforme une phrase en numéros de jetons, exactement comme CLIP (minuscules, morceaux de mots « BPE »)."""

    MOTIF = re.compile(r"<\|startoftext\|>|<\|endoftext\|>|'s|'t|'re|'ve|'m|'ll|'d|[^\W\d_]+|\d|[^\s\w]+|_+", re.IGNORECASE)

    def __init__(self, dossier: Path):
        self.code = json.loads((dossier / "vocab.json").read_text(encoding="utf-8"))
        fusions = (dossier / "merges.txt").read_text(encoding="utf-8").strip().split("\n")[1:49152 - 256 - 2 + 1]
        self.rangs = {tuple(f.split()): i for i, f in enumerate(fusions)}
        self.cache: dict[str, list[str]] = {}

    def _bpe(self, morceau: str) -> list[str]:
        if morceau in self.cache:
            return self.cache[morceau]
        mot = tuple(morceau[:-1]) + (morceau[-1] + "</w>",)
        while len(mot) > 1:
            paires = {(mot[i], mot[i + 1]) for i in range(len(mot) - 1)}
            meilleure = min(paires, key=lambda p: self.rangs.get(p, float("inf")))
            if meilleure not in self.rangs:
                break
            a, b = meilleure
            nouveau, i = [], 0
            while i < len(mot):
                if i < len(mot) - 1 and mot[i] == a and mot[i + 1] == b:
                    nouveau.append(a + b)
                    i += 2
                else:
                    nouveau.append(mot[i])
                    i += 1
            mot = tuple(nouveau)
        self.cache[morceau] = list(mot)
        return self.cache[morceau]

    def numeros(self, phrase: str) -> list[int]:
        """[DÉBUT, …jetons…, FIN] complétés par des 0 jusqu'à 16 (coupés au-delà, FIN gardée)."""
        octets = _octets_vers_lettres()
        texte = " ".join(phrase.lower().split())
        ids = []
        for m in self.MOTIF.findall(texte):
            ids += [self.code[j] for j in self._bpe("".join(octets[b] for b in m.encode("utf-8")))]
        ids = [DEBUT] + ids[:JETONS - 2] + [FIN]
        return ids + [0] * (JETONS - len(ids))


# ---------------------------------------------------------------- le réseau
def _quick_gelu(x):
    return x * torch.sigmoid(1.702 * x)


class _Attention(nn.Module):
    def __init__(self, d: int, tetes: int):
        super().__init__()
        self.tetes = tetes
        self.q_proj, self.k_proj, self.v_proj, self.out_proj = (nn.Linear(d, d) for _ in range(4))

    def forward(self, x, causal: bool = False):
        b, n, d = x.shape
        q, k, v = (p(x).reshape(b, n, self.tetes, d // self.tetes).transpose(1, 2) for p in (self.q_proj, self.k_proj, self.v_proj))
        return self.out_proj(F.scaled_dot_product_attention(q, k, v, is_causal=causal).transpose(1, 2).reshape(b, n, d))


class _Mlp(nn.Module):
    def __init__(self, d: int, h: int):
        super().__init__()
        self.fc1, self.fc2 = nn.Linear(d, h), nn.Linear(h, d)

    def forward(self, x):
        return self.fc2(_quick_gelu(self.fc1(x)))


class _Couche(nn.Module):
    def __init__(self, d: int, tetes: int):
        super().__init__()
        self.self_attn = _Attention(d, tetes)
        self.layer_norm1, self.layer_norm2 = nn.LayerNorm(d, eps=1e-5), nn.LayerNorm(d, eps=1e-5)
        self.mlp = _Mlp(d, 4 * d)

    def forward(self, x, causal: bool = False):
        x = x + self.self_attn(self.layer_norm1(x), causal)
        return x + self.mlp(self.layer_norm2(x))


class _Encodeur(nn.Module):
    def __init__(self, d: int, tetes: int, n: int = 12):
        super().__init__()
        self.layers = nn.ModuleList(_Couche(d, tetes) for _ in range(n))

    def forward(self, x, causal: bool = False):
        for c in self.layers:
            x = c(x, causal)
        return x


class _EmbVision(nn.Module):
    def __init__(self, d: int = 768):
        super().__init__()
        self.class_embedding = nn.Parameter(torch.zeros(d))
        self.patch_embedding = nn.Conv2d(3, d, CARRE, CARRE, bias=False)
        self.position_embedding = nn.Embedding((TAILLE // CARRE) ** 2 + 1, d)

    def forward(self, px):
        x = self.patch_embedding(px).flatten(2).transpose(1, 2)
        x = torch.cat([self.class_embedding.expand(x.shape[0], 1, -1), x], 1)
        return x + self.position_embedding.weight[None]


class _Vision(nn.Module):
    def __init__(self, d: int = 768):
        super().__init__()
        self.embeddings = _EmbVision(d)
        self.pre_layernorm, self.post_layernorm = nn.LayerNorm(d, eps=1e-5), nn.LayerNorm(d, eps=1e-5)
        self.encoder = _Encodeur(d, 12)

    def forward(self, px):
        return self.post_layernorm(self.encoder(self.pre_layernorm(self.embeddings(px))))


class _EmbTexte(nn.Module):
    def __init__(self, d: int = 512):
        super().__init__()
        self.token_embedding = nn.Embedding(49408, d)
        self.position_embedding = nn.Embedding(JETONS, d)

    def forward(self, ids):
        return self.token_embedding(ids) + self.position_embedding.weight[None, : ids.shape[1]]


class _Texte(nn.Module):
    def __init__(self, d: int = 512):
        super().__init__()
        self.embeddings = _EmbTexte(d)
        self.encoder = _Encodeur(d, 8)
        self.final_layer_norm = nn.LayerNorm(d, eps=1e-5)

    def forward(self, ids):
        x = self.final_layer_norm(self.encoder(self.embeddings(ids), causal=True))
        return x[torch.arange(x.shape[0]), ids.argmax(-1)]  # le jeton FIN (le plus grand numéro)


class _Tete(nn.Module):  # box_head (4 sorties) et objectness_head (1 sortie)
    def __init__(self, d: int, sorties: int):
        super().__init__()
        self.dense0, self.dense1, self.dense2 = nn.Linear(d, d), nn.Linear(d, d), nn.Linear(d, sorties)

    def forward(self, x):
        return self.dense2(F.gelu(self.dense1(F.gelu(self.dense0(x)))))


class _TeteClasses(nn.Module):
    def __init__(self, d: int = 768, dt: int = 512):
        super().__init__()
        self.dense0 = nn.Linear(d, dt)
        self.logit_shift, self.logit_scale = nn.Linear(d, 1), nn.Linear(d, 1)

    def forward(self, x, requetes):
        e = self.dense0(x)
        e = e / (torch.linalg.norm(e, dim=-1, keepdim=True) + 1e-6)
        q = requetes / (torch.linalg.norm(requetes, dim=-1, keepdim=True) + 1e-6)
        return (e @ q.T + self.logit_shift(x)) * (F.elu(self.logit_scale(x)) + 1), e


class _Clip(nn.Module):
    def __init__(self):
        super().__init__()
        self.vision_model, self.text_model = _Vision(), _Texte()
        self.visual_projection = nn.Linear(768, 512, bias=False)
        self.text_projection = nn.Linear(512, 512, bias=False)
        self.logit_scale = nn.Parameter(torch.zeros(()))


def _biais_des_boites(n: int = TAILLE // CARRE) -> torch.Tensor:
    """Chaque carré propose d'abord un rectangle centré sur lui, de sa taille (même calcul que la référence)."""
    c = torch.arange(1, n + 1, dtype=torch.float32) / n
    xx, yy = torch.meshgrid(c, c, indexing="xy")
    xy = torch.stack([xx, yy], -1).reshape(-1, 2).clip(0, 1)
    b_xy = torch.log(xy + 1e-4) - torch.log1p(-xy + 1e-4)
    t = torch.full_like(b_xy, 1.0 / n)
    b_t = torch.log(t + 1e-4) - torch.log1p(-t + 1e-4)
    return torch.cat([b_xy, b_t], -1)


class Owlv2(nn.Module):
    def __init__(self):
        super().__init__()
        self.owlv2 = _Clip()
        self.class_head = _TeteClasses()
        self.box_head = _Tete(768, 4)
        self.objectness_head = _Tete(768, 1)
        self.layer_norm = nn.LayerNorm(768, eps=1e-5)
        self.register_buffer("biais_boites", _biais_des_boites(), persistent=False)
        self.mots: Mots | None = None

    @property
    def appareil(self):
        return self.layer_norm.weight.device

    @torch.no_grad()
    def textes(self, phrases: list[str]) -> torch.Tensor:
        """(q, 512) : l'empreinte de chaque phrase cherchée."""
        ids = torch.tensor([self.mots.numeros(p) for p in phrases], device=self.appareil)
        return self.owlv2.text_projection(self.owlv2.text_model(ids))

    @torch.no_grad()
    def carte(self, photo_rgb: np.ndarray) -> torch.Tensor:
        """(3600, 768) : l'empreinte de chacun des 60 × 60 carrés (photo remise au carré)."""
        x = self.owlv2.vision_model(preparer(photo_rgb).to(self.appareil))
        x = self.layer_norm(x[:, 1:] * x[:, :1])
        return x[0]

    @torch.no_grad()
    def detecter(self, photo_rgb: np.ndarray, requetes: torch.Tensor, carte: torch.Tensor | None = None) -> dict:
        """Toutes les propositions des 3 600 carrés : rectangles (x0, y0, x1, y1) en pixels de la photo d'origine,
        notes par requête (0-1, après sigmoïde), note « objet » (0-1), et l'empreinte de chaque carré (pour comparer)."""
        h, w = photo_rgb.shape[:2]
        x = self.carte(photo_rgb) if carte is None else carte
        logits, empreintes = self.class_head(x, requetes)
        objet = self.objectness_head(x)[:, 0]
        b = torch.sigmoid(self.box_head(x) + self.biais_boites)
        cote = max(h, w)
        boites = torch.stack([b[:, 0] - b[:, 2] / 2, b[:, 1] - b[:, 3] / 2, b[:, 0] + b[:, 2] / 2, b[:, 1] + b[:, 3] / 2], 1) * cote
        return {"boites": boites.float().cpu().numpy(), "notes": torch.sigmoid(logits).float().cpu().numpy(),
                "logits": logits.float().cpu().numpy(), "objet": torch.sigmoid(objet).float().cpu().numpy(),
                "empreintes": empreintes.float().cpu().numpy(), "taille": (h, w)}


def preparer(photo_rgb: np.ndarray) -> torch.Tensor:
    """Comme la référence : 0-1, remise au carré avec du gris 0,5 à droite et en bas, flou d'anticrénelage
    (écart = (facteur − 1) / 2, bords en miroir), réduction bilinéaire à 960 × 960, puis normalisation de CLIP."""
    img = photo_rgb.astype(np.float32) / 255.0
    h, w = img.shape[:2]
    cote = max(h, w)
    carre = np.full((cote, cote, 3), 0.5, np.float32)
    carre[:h, :w] = img
    facteur = cote / TAILLE
    if facteur > 1:
        s = (facteur - 1) / 2
        carre = cv2.GaussianBlur(carre, (0, 0), sigmaX=s, sigmaY=s, borderType=cv2.BORDER_REFLECT_101)
    if cote != TAILLE:
        carre = cv2.resize(carre, (TAILLE, TAILLE), interpolation=cv2.INTER_LINEAR)
    carre = (np.clip(carre, 0, 1) - MOYENNE) / ECART
    return torch.from_numpy(carre.transpose(2, 0, 1).copy())[None]


def charger(dossier: Path | None = None, appareil: str | None = None) -> Owlv2:
    dossier = Path(dossier or dossier_poids())
    if not (dossier / "model.safetensors").is_file():
        raise FileNotFoundError(f"poids d'OWLv2 introuvables : {dossier / 'model.safetensors'}")
    m = Owlv2()
    manquants, en_trop = m.load_state_dict(lire_safetensors(dossier / "model.safetensors"), strict=False)
    if manquants or en_trop:
        raise RuntimeError(f"poids d'OWLv2 incompatibles : manquants {manquants[:5]}, en trop {en_trop[:5]}")
    m.mots = Mots(dossier)
    appareil = appareil or ("cuda" if torch.cuda.is_available() else "cpu")
    return m.to(appareil).eval()


def boites_iou(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Recouvrement (intersection / union) entre chaque rectangle de a et chaque rectangle de b."""
    x0 = np.maximum(a[:, None, 0], b[None, :, 0])
    y0 = np.maximum(a[:, None, 1], b[None, :, 1])
    x1 = np.minimum(a[:, None, 2], b[None, :, 2])
    y1 = np.minimum(a[:, None, 3], b[None, :, 3])
    inter = np.clip(x1 - x0, 0, None) * np.clip(y1 - y0, 0, None)
    aa = (a[:, 2] - a[:, 0]) * (a[:, 3] - a[:, 1])
    ab = (b[:, 2] - b[:, 0]) * (b[:, 3] - b[:, 1])
    return inter / np.maximum(aa[:, None] + ab[None, :] - inter, 1e-9)


def objets(sortie: dict, noms: list[str], seuil: float = 0.2, recouvrement_max: float = 0.5) -> list[dict]:
    """Les objets retenus : pour chaque carré, la requête la mieux notée ; gardé si sa note ≥ seuil ; puis, entre deux
    rectangles qui se recouvrent à plus de `recouvrement_max`, on garde le mieux noté (quelle que soit la requête)."""
    notes = sortie["notes"]
    meilleure = notes.argmax(1)
    note = notes[np.arange(len(notes)), meilleure]
    garde = np.nonzero(note >= seuil)[0]
    garde = garde[np.argsort(-note[garde])]
    h, w = sortie["taille"]
    retenus: list[int] = []
    for i in garde:
        if retenus and boites_iou(sortie["boites"][i:i + 1], sortie["boites"][retenus]).max() > recouvrement_max:
            continue
        retenus.append(int(i))
    out = []
    for i in retenus:
        x0, y0, x1, y1 = sortie["boites"][i]
        out.append({"nom": noms[int(meilleure[i])], "note": round(float(note[i]), 3), "carre": i,
                    "boite": [round(float(max(0, x0)), 1), round(float(max(0, y0)), 1),
                              round(float(min(w, x1)), 1), round(float(min(h, y1)), 1)]})
    return out
