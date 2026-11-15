"""Les photos du client à l'ÉCRAN DE VÉRIFICATION : « d'où est prise cette photo ? » (15/11/2026, décision NT « en deux temps »).

POURQUOI : le client nomme la pièce de chaque photo ; pour celles qu'Atelya ne sait pas ranger (deux chambres jumelles, une
photo qui ne colle pas à la pièce nommée), l'écran de vérification montre la photo et pose la question ; NT clique sur le plan
là où se tenait le photographe et tire vers ce qu'il regardait. Ce module fait les deux bouts côté Atelya :
  - `questions_pour_l_ecran` : la fiche du calage (moteur/caler_photos.py, outils/habillage/caler_photos_seul.py) → le bloc
    « photos » donné à l'écran (une question par photo à pointer, avec la photo réduite et la place qu'Atelya propose) ;
  - `ranger_les_reponses` : ce que l'écran rend → le fichier « pieces-des-photos.json » complété (« endroits »), que le
    calage relit tout seul.
Format (ajout FACULTATIF au format verification/0.1, qui ne change pas pour le reste) :
  verification["photos"] = {"questions": [{"nom", "image" (data URL), "question", "piece", "hesite_avec", "proposition":
                                           {"x", "y", "cap"} ou None, "largeur", "hauteur"}]}
  resultat["photos"]     = {"endroits": {nom: [x, y, cap]}, "passees": [nom]}   (mètres du plan ; cap en degrés, 0 = vers les
                                                                                 x croissants, sens inverse des aiguilles)
"""
from __future__ import annotations

import base64
import re
from pathlib import Path

import cv2

from .images import lire_image

VERSION = "0.1.0"
LARGEUR_PHOTO = 1000  # la photo montrée à l'écran : assez grande pour reconnaître la pièce, assez légère pour tenir dans la page


def _photo_reduite(chemin: Path, largeur: int = LARGEUR_PHOTO) -> tuple[str, int, int]:
    """La photo en data URL JPEG, réduite à `largeur` pixels de large au plus → (data URL, largeur, hauteur)."""
    im = lire_image(chemin)
    if im is None:
        raise FileNotFoundError(chemin)
    h, w = im.shape[:2]
    if w > largeur:
        im = cv2.resize(im, (largeur, round(h * largeur / w)), interpolation=cv2.INTER_AREA)
    ok, jpg = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not ok:
        raise ValueError(f"photo illisible : {chemin}")
    return "data:image/jpeg;base64," + base64.b64encode(jpg.tobytes()).decode("ascii"), im.shape[1], im.shape[0]


def avec_les_noms(texte: str, logement: dict | None) -> str:
    """Le même texte, les identifiants des pièces (« chambre_1 ») remplacés par leur NOM, tel que l'écran l'affiche sur le plan
    (« Chambre 2 ») : c'est ce nom-là que la personne qui vérifie a sous les yeux."""
    for p in sorted((logement or {}).get("pieces", []), key=lambda p: -len(p["id"])):
        if p.get("nom"):
            texte = re.sub(rf"(?<![\w]){re.escape(p['id'])}(?![\w])", f"« {p['nom']} »", texte)
    return texte


def questions_pour_l_ecran(fiche: dict, dossier: Path, largeur: int = LARGEUR_PHOTO, logement: dict | None = None) -> dict:
    """La fiche du calage → le bloc « photos » de l'écran de vérification. Une question par photo de `fiche["a_pointer"]`,
    dans l'ordre : d'abord celles où Atelya hésite entre des pièces qui se ressemblent, puis les doutes, puis les autres.
    logement : pour écrire les questions avec les NOMS des pièces affichés à l'écran plutôt qu'avec leurs identifiants."""
    modele = fiche.get("fichier", "{nom}.jpg")
    connues = {**fiche.get("incertaines", {}), **fiche.get("a_verifier", {})}
    rang = lambda n: 0 if connues.get(n, {}).get("hesite_avec") else 1 if connues.get(n, {}).get("a_verifier") else 2
    questions = []
    for nom in sorted(fiche.get("a_pointer", {}), key=lambda n: (rang(n), n)):
        d = connues.get(nom, {})
        image, w, h = _photo_reduite(Path(dossier) / modele.format(nom=nom), largeur)
        cam = d.get("camera")
        questions.append({"nom": nom, "image": image, "largeur": w, "hauteur": h, "question": avec_les_noms(fiche["a_pointer"][nom], logement),
                          "piece": d.get("piece"), "hesite_avec": d.get("hesite_avec", []),
                          "proposition": {"x": cam["x"], "y": cam["y"], "cap": cam["cap"]} if cam else None})
    return {"questions": questions}


def ranger_les_reponses(pieces: dict | None, reponses: dict | None) -> dict:
    """Le fichier « pieces-des-photos.json » (ou None) complété par ce que l'écran a rendu (`resultat["photos"]`) : les
    endroits pointés s'ajoutent à « endroits » (un nouvel endroit remplace l'ancien). Rien n'est retiré de ce que le client
    a dit. Une photo « passée » à l'écran reste sans endroit : Atelya la laissera de côté."""
    d = dict(pieces or {})
    if not isinstance(d.get("pieces"), dict):  # forme courte {photo: pièce} → forme longue
        d = {"pieces": d}
    endroits = dict(d.get("endroits", {}))
    for nom, v in ((reponses or {}).get("endroits") or {}).items():
        if not isinstance(v, (list, tuple)) or len(v) < 2:
            raise ValueError(f"endroit mal formé pour {nom} : {v!r}")
        endroits[nom] = [round(float(x), 3) for x in v[:3]]
    if endroits:
        d["endroits"] = endroits
    return d
