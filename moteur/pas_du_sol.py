"""Ce qui n'est PAS du sol, repéré sur la photo AVANT la mise à plat (brique photos, 10/11/2026).

Pourquoi : la mise à plat (moteur/sol_a_plat.py) suppose que tout ce qu'on voit est posé au sol. Le dessus d'un lit, d'un
canapé ou d'un rangement (à 40-90 cm de haut) est alors projeté loin derrière, étiré en une grande tache blanche ou bois qui
vote pour une fausse famille de sol (app-002 : chambre 3 prise pour du carrelage à cause de la couette). Sur la photo
d'origine, un lit a encore une forme de lit : c'est là qu'il faut l'écarter.

Clés :
1. OWLv2 (moteur/owlv2.py, appris sur de vraies photos) : les rectangles des lits, canapés, fauteuils, rangements, tables,
   chaises. JAMAIS sur le seul mot « tapis » : un tapis est posé à plat (il n'est pas étiré) et OWLv2 prend parfois une
   zone de granito ou de carreaux pour un tapis — l'écarter ferait perdre une vraie zone de sol (leçon du 09/11/2026 :
   la règle « zones vues comme meuble » avait fait tomber app-001 de 81,5 à 52 %).
2. (facultatif, ÉCARTÉ par défaut) l'œil DINOv2 par carrés de 14 px (moteur/reperer_meubles.py) : probabilité qu'un carré
   montre un meuble. Un point est écarté s'il est dans un rectangle ET que DINOv2 y voit un meuble à plus de `p_dans`, ou si
   DINOv2 seul y voit un meuble à plus de `p_seul`.
Un point écarté n'est pas effacé : il est DOUTEUX (moteur/sol_a_plat.py) ; il vote peu, et une pièce assez vue proprement
n'est décidée que par ses cases propres (moteur/reconnaitre_sols.py).

Réglage retenu sur le contrôle fabriqué (10/11/2026, outils/habillage/essayer_pas_du_sol.py, fr-031/fr-038 jamais appris) :
OWLv2 seul, lits + canapés + rangements, note ≥ 0,25. Sol juste : tirages à vrais lits 70,3 → 84,1 % (sous les meubles 47 →
82 %), anciens tirages meublés 84,6 → 84,9 %, pièces vides 93,5 = 93,5 % ; pièces justes identiques partout (18, 15, 21 sur 25).
Écartés : tables et chaises (une pièce juste perdue : leur rectangle contient surtout du sol entre les pieds), fauteuils (idem),
DINOv2 seul (change aussi des pièces VIDES : il retire du vrai sol, dangereux sur vraies photos), OWLv2 + DINOv2 (moins bon).
"""
from __future__ import annotations

import cv2
import numpy as np

# Ce qu'on demande à OWLv2 et le groupe d'Atelya de chaque phrase (« autre » : demandé pour qu'une fenêtre, une porte ou un
# radiateur ne soit pas pris pour une armoire, jamais écarté).
REQUETES = {
    "a bed": "lit", "a bed with a duvet": "lit", "a bunk bed": "lit", "a loft bed": "lit",
    "a sofa": "canape", "a couch": "canape",
    "an armchair": "fauteuil",
    "a chair": "chaise", "a stool": "chaise", "an office chair": "chaise",
    "a dining table": "table", "a table": "table", "a coffee table": "table", "a desk": "table", "a side table": "table",
    "a chest of drawers": "rangement", "a cabinet": "rangement", "a bookshelf": "rangement", "a shelf": "rangement",
    "a tv stand": "rangement", "a nightstand": "rangement", "a bench": "rangement", "a wardrobe": "rangement",
    "a sideboard": "rangement", "kitchen cabinets": "rangement",
    "a rug": "tapis", "a carpet": "tapis",
    "a floor lamp": "lampe", "a lamp": "lampe",
    "a potted plant": "plante",
    "a window": "autre", "a door": "autre", "a radiator": "autre", "a painting": "autre", "a mirror": "autre",
    "a television": "autre", "a pillow": "autre", "a ceiling light": "autre",
}
NOMS = list(REQUETES)
GROUPES_ECARTES = ("lit", "canape", "rangement")
SEUIL_OWL = 0.25
P_DANS = -1.0  # < 0 : DINOv2 ne restreint pas les rectangles
P_SEUL = 1.01  # > 1 : désactivé


class PasDuSol:
    """Calcule le masque « pas du sol » d'une photo. Les résultats bruts (rectangles, probabilités) sont gardés par photo :
    plusieurs réglages peuvent être essayés sans refaire les calculs (`masque(..., reglage)`)."""

    def __init__(self, owl=None, oeil=None, clf_meubles=None):
        self.owl, self.oeil, self.clf = owl, oeil, clf_meubles
        self.requetes = owl.textes(NOMS) if owl is not None else None
        self.cache: dict[str, dict] = {}

    def brut(self, cle: str, rgb: np.ndarray) -> dict:
        if cle in self.cache:
            return self.cache[cle]
        d = {"taille": rgb.shape[:2]}
        if self.owl is not None:
            from moteur.owlv2 import objets
            sortie = self.owl.detecter(rgb, self.requetes)
            d["objets"] = objets(sortie, NOMS, seuil=0.1, recouvrement_max=0.7)
        if self.clf is not None:
            from moteur.reperer_meubles import CLASSES_MEUBLES, RIEN, empreintes_carres
            e = empreintes_carres(self.oeil, rgb)
            p = self.clf.probabilites(e.reshape(-1, e.shape[-1])).reshape(*e.shape[:2], -1)
            garde = [i for i, c in enumerate(CLASSES_MEUBLES) if c not in (RIEN, "tapis")]
            d["p_meuble"] = p[..., garde].sum(-1).astype(np.float32)
        self.cache[cle] = d
        return d

    def masque(self, cle: str, rgb: np.ndarray, seuil_owl: float = SEUIL_OWL, groupes=GROUPES_ECARTES,
               p_dans: float = P_DANS, p_seul: float = P_SEUL, avec_owl: bool = True) -> np.ndarray:
        d = self.brut(cle, rgb)
        h, w = d["taille"]
        boites = np.zeros((h, w), bool)
        if avec_owl and "objets" in d:
            for o in d["objets"]:
                if o["note"] >= seuil_owl and REQUETES[o["nom"]] in groupes:
                    x0, y0, x1, y1 = (int(round(c)) for c in o["boite"])
                    boites[max(0, y0):y1, max(0, x0):x1] = True
        if "p_meuble" in d:
            p = cv2.resize(d["p_meuble"], (w, h), interpolation=cv2.INTER_LINEAR)
            if avec_owl and "objets" in d:
                return (boites & (p > p_dans)) | (p > p_seul)
            return p > p_seul
        return boites


def charger(appareil: str | None = None, avec_owl: bool = True, modele_meubles=None, avec_dino: bool = True) -> PasDuSol:
    """OWLv2 (poids sur le PC) et, si avec_dino, l'œil DINOv2 et le repérage des meubles (moteur/modeles/meubles-vits14-v1.pt ;
    seulement pour les essais : le réglage retenu ne s'en sert pas)."""
    from pathlib import Path

    import torch

    from moteur.oeil_dinov2 import charger as charger_oeil
    from moteur.reconnaitre_sols import Classifieur
    owl = None
    if avec_owl:
        from moteur.owlv2 import charger as charger_owl
        owl = charger_owl(appareil=appareil)
    if not avec_dino:
        return PasDuSol(owl)
    modele_meubles = modele_meubles or Path(__file__).resolve().parent / "modeles" / "meubles-vits14-v1.pt"
    clf = Classifieur.depuis(torch.load(modele_meubles, weights_only=False))
    oeil = charger_oeil(clf.oeil, appareil=appareil)
    return PasDuSol(owl, oeil, clf)
