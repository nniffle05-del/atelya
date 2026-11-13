"""Les CIELS PHOTOGRAPHIÉS : le fond vu par les fenêtres du film (cinématique, étape 4, 12/11/2026, accord écrit de NT).

Pourquoi : la maquette n'a rien autour du logement ; par les fenêtres on voyait la brume de l'atmosphère d'Unreal à l'horizon,
blanc-gris, sans couleur (mesuré : 96 % du dehors presque blanc). Un ciel photographié (bleu, nuages) est posé COMME UN DÉCOR :
il ne fait AUCUNE lumière (la lumière reste le vrai soleil et le vrai ciel calculés, règle 20). Un ciel seul et non une rue :
une rue inventée ne serait pas la vue du logement (risque de tromper l'acheteur) ; la vraie vue viendra des photos du client.

Fichiers : ..\atelya\bibliotheque\ciels\ (LISEZMOI.txt : source, auteurs, licence CC0), copiés sans accent dans
D:\Atelya-Unreal\Paquets\ciels\ pour Unreal. Seulement pour un ciel de JOUR ensoleillé (soleil haut) : un ciel de midi derrière
une fin de journée serait faux.
"""
from __future__ import annotations

import math

# soleil_u : colonne du soleil dans l'image (0..1, mesurée sur le fichier : pixel le plus lumineux) ; on tourne le ciel pour
# qu'il tombe sur la direction du vrai soleil du film. force : nits (cd/m²) d'Unreal par unité de l'image (calibrée : voir
# produit-livre-client.md, étape 4).
CIELS = {
    "jour_soleil": {"fichier": "kloofendal_48d_partly_cloudy_puresky_4k.hdr", "soleil_u": 0.595, "soleil_hauteur_deg": 47.9,
                    "force": 1.0},
}


def ciel_photo(ambiance_id: str, dossier: str) -> dict | None:
    """Le réglage « ciel_photo » de la préparation Unreal pour cet éclairage (None : pas de ciel photographié)."""
    c = CIELS.get(ambiance_id)
    if c is None:
        return None
    return {"image": f"{dossier.rstrip('/')}/{c['fichier']}", "soleil_u": c["soleil_u"], "force": c["force"]}


def decalage(soleil_u: float, vers_soleil_unreal: tuple[float, float, float]) -> float:
    """Le décalage de la colonne de l'image pour que le soleil de la photo tombe sur l'azimut du vrai soleil (repère d'Unreal :
    colonne u = azimut / 2π + décalage, azimut = atan2(y, x))."""
    azimut = math.atan2(vers_soleil_unreal[1], vers_soleil_unreal[0])
    return (soleil_u - azimut / (2 * math.pi)) % 1.0
