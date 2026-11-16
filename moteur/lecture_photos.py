r"""LA LECTURE DES PHOTOS PAR CLAUDE : le format de ce qu'il rend (lecture-photos/0.1), essai du 16/11/2026.

Pourquoi (accord de NT du 16/11/2026 : « je veux bien qu'on teste avec cette technique, et on verra par la suite ») : mesurer,
sans rien dépenser, ce que la maquette gagnerait si Claude COMPRENAIT les photos à la place des petits détecteurs. Le partage
est le même que pour le plan (moteur/lecture_claude.py) : Claude donne le SENS, Atelya garde la GÉOMÉTRIE.

Ce qu'Atelya envoie : chaque photo avec les rectangles de son détecteur NUMÉROTÉS (outils/lecture_photos/preparer_photos.py).
Ce que Claude rend, par photo :
- `objets` : pour chaque numéro, ce que c'est vraiment — une `sorte` de la liste fermée SORTES (une catégorie de meuble de la
  maquette, ou un équipement qu'elle ne sait pas encore porter, ou « faux » si le rectangle ne montre rien de tel, ou
  « autre ») ; `meme_que` si le rectangle montre le même objet qu'un autre numéro ; `forme` et `couleur` en clair, facultatifs ;
- `sol` : la famille du sol de la pièce où se tient le photographe (lames, point_de_hongrie, batons_rompus, carreaux), s'il est
  le même partout (`uniforme`) et, sinon, l'autre famille que la pièce montre (`autre_famille`) ;
- `manquants` : ce que la photo montre et qu'aucun rectangle n'encadre (sorte + rectangle approché).
Claude ne donne AUCUNE place en mètres. Une fenêtre qui descend jusqu'au sol se dit « porte_fenetre ».

Ce module contrôle la fiche (sortes connues, numéros existants) et la traduit pour le reste d'Atelya (moteur/photos_lues.py).
Les lectures faites à la main dans la conversation, à la place du service payant : verites/<logement>/lecture_des_photos.py.
"""
from __future__ import annotations

import re

from moteur.meubles import NOMS_MEUBLES

SCHEMA = "lecture-photos/0.1"
# ce que la maquette ne sait pas encore porter, mais que Claude doit pouvoir nommer (compté « vu, pas représenté »)
EQUIPEMENTS = ("cheminee", "radiateur", "baignoire", "douche", "wc", "lavabo", "evier", "electromenager", "hotte", "applique",
               "plafonnier", "passe_plat", "etagere_murale", "rideaux", "store")
OUVERTURES = ("fenetre", "porte_fenetre", "porte")
SORTES = (*NOMS_MEUBLES, *EQUIPEMENTS, *OUVERTURES, "autre", "faux")
FAMILLES_DE_SOL = ("lames", "point_de_hongrie", "batons_rompus", "carreaux")
COULEURS_DITES = ("blanc cassé", "bois clair", "bois foncé", "gris clair", "gris anthracite", "blanc", "blanche", "noir", "noire", "gris",
                  "grise", "bleu", "bleue", "jaune", "beige", "crème", "rouge", "vert", "verte", "rose", "mauve", "brun", "marron",
                  "doré", "inox", "bois", "pin", "rotin")
FORMES_DITES = ("ronde", "rond", "ovale", "rectangulaire", "carrée", "carré", "d'angle", "octogonal", "une place", "double")


def consigne() -> str:
    """Le texte qui dirait à Claude quoi remplir (envoyé plus tard par l'API avec chaque photo ; rien n'est envoyé ici)."""
    return f"""Tu regardes une photo d'un logement. Des rectangles numérotés y encadrent ce qu'un détecteur automatique a repéré ;
il se trompe souvent sur ce que c'est. Tu remplis une fiche JSON au format {SCHEMA} :

{{"objets": {{"<numéro>": {{"sorte": "…", "meme_que": <numéro>, "forme": "…", "couleur": "…", "note": "…"}}, …}},
 "sol": {{"famille": "…", "uniforme": true, "autre_famille": "…"}},
 "manquants": [{{"sorte": "…", "boite": [x0, y0, x1, y1]}}]}}

- Pour CHAQUE numéro, « sorte » dit ce que le rectangle montre vraiment, parmi : {", ".join(SORTES)}.
  « faux » : le rectangle ne montre rien de tel (un reflet, un morceau de mur, un filigrane). « autre » : un objet hors de la liste.
  Une fenêtre dont la vitre descend jusqu'au sol est une « porte_fenetre » ; sur allège (un mur dessous), une « fenetre ».
  Une armoire ou un placard à portes est un « placard » ; un buffet est un « rangement » ; les meubles de cuisine sont
  « meuble_cuisine_bas », « meuble_cuisine_haut » ou « colonne_cuisine » ; un luminaire qui pend du plafond est une
  « suspension », collé au plafond un « plafonnier », fixé au mur une « applique ». Un écran d'ordinateur n'est pas une « television ».
- « meme_que » : seulement si ce rectangle montre le MÊME objet qu'un autre numéro (un morceau, ou deux rectangles pour un meuble).
- « forme » (ronde, rectangulaire…) et « couleur » (bleu, blanc, bois clair…) : en un ou deux mots, si c'est net.
- « sol » : la famille du sol de la pièce où se tient le photographe, parmi {", ".join(FAMILLES_DE_SOL)} ; « uniforme » : faux si
  cette pièce montre deux sols différents (un tapis n'est pas un sol), et alors « autre_famille » dit le second.
- « manquants » : ce que la photo montre d'important et qu'aucun rectangle n'encadre (rectangle approché, en pixels).
- Ne donne aucune mesure en mètres. Ne recopie aucun nom ni aucune adresse.

Réponds uniquement par la fiche JSON."""


def controler(fiche: dict, numeros: set[int]) -> list[str]:
    """Les défauts d'une fiche de photo (liste vide = utilisable) : sorte inconnue, numéro inconnu ou oublié, « meme_que » inconnu."""
    defauts = []
    lus = fiche.get("objets") or {}
    for n, o in lus.items():
        if not str(n).isdigit() or int(n) not in numeros:
            defauts.append(f"numéro {n} inconnu")
            continue
        if o.get("meme_que") is not None:
            if int(o["meme_que"]) not in numeros or int(o["meme_que"]) == int(n):
                defauts.append(f"numéro {n} : « meme_que » {o['meme_que']} inconnu")
            elif (lus.get(str(o["meme_que"])) or {}).get("meme_que") is not None:
                defauts.append(f"numéro {n} : « meme_que » {o['meme_que']} renvoie lui-même à un autre numéro")
        elif o.get("sorte") not in SORTES:
            defauts.append(f"numéro {n} : sorte {o.get('sorte')!r} inconnue")
    for n in sorted(numeros - {int(n) for n in lus if str(n).isdigit()}):
        defauts.append(f"numéro {n} oublié")
    sol = fiche.get("sol") or {}
    for cle in ("famille", "autre_famille"):
        if sol.get(cle) is not None and sol[cle] not in FAMILLES_DE_SOL:
            defauts.append(f"sol : {cle} {sol[cle]!r} inconnue")
    for m in fiche.get("manquants") or []:
        if m.get("sorte") not in SORTES:
            defauts.append(f"manquant : sorte {m.get('sorte')!r} inconnue")
        if len(m.get("boite") or []) != 4:
            defauts.append(f"manquant {m.get('sorte')} : rectangle absent")
    return defauts


def objets_lus(fiche: dict, liste: list[dict], manquants: bool = True) -> list[dict]:
    """Les objets d'une photo tels que Claude les a compris : la liste numérotée d'Atelya (`liste` : numero, boite, note…)
    avec la sorte de Claude ; les « faux » et les doublons (« meme_que ») retirés ; les « manquants » ajoutés (rectangle
    approché : `approche` vrai, note 0,5). Un numéro que Claude n'a pas rempli garde ce que le détecteur croyait."""
    sortie = []
    lus = fiche.get("objets") or {}
    for o in liste:
        l = lus.get(str(o["numero"]))
        if l is None:
            sortie.append(objet_du_detecteur(o))
            continue
        if l.get("sorte") == "faux" or l.get("meme_que") is not None:
            continue
        sortie.append({"numero": o["numero"], "boite": o["boite"], "note": o["note"], "sorte": l["sorte"], "forme": l.get("forme"),
                       "couleur_dite": l.get("couleur"), "dit": l.get("note")})
    if manquants:
        for k, m in enumerate(fiche.get("manquants") or [], start=1):
            sortie.append({"numero": -k, "boite": [float(v) for v in m["boite"]], "note": 0.5, "sorte": m["sorte"], "forme": m.get("forme"),
                           "couleur_dite": m.get("couleur"), "dit": m.get("note"), "approche": True})
    return sortie


# ---------------------------------------------------------------- sans Claude : ce que le détecteur croit (pour comparer)
# sorte du banc (moteur/fidelite_photos.VOCABULAIRE) → sorte de la lecture, quand la phrase du détecteur n'en dit pas plus
SORTE_DU_DETECTEUR = {"canape": "canape", "fauteuil": "fauteuil", "chaise": "chaise", "table": "table", "lit": "lit", "rangement": "rangement",
                      "tapis": "tapis", "lampe": "lampadaire", "plante": "plante", "luminaire": "suspension", "television": "television",
                      "tableau": "tableau", "miroir": "miroir", "cheminee": "cheminee", "radiateur": "radiateur", "rideaux": "rideaux",
                      "baie": "fenetre", "porte": "porte", "cuisine": "meuble_cuisine_bas", "electromenager": "electromenager",
                      "lavabo": "lavabo", "baignoire": "baignoire", "douche": "douche", "wc": "wc"}


def objet_du_detecteur(o: dict) -> dict:
    """Un objet de la liste numérotée, avec la sorte que le DÉTECTEUR lui donne (sa phrase si elle est précise, sinon sa sorte)."""
    from moteur.meubles_photos import CATEGORIE_DE

    sorte = CATEGORIE_DE.get(o.get("phrase")) or SORTE_DU_DETECTEUR.get(o.get("detecteur"), "autre")
    return {"numero": o["numero"], "boite": o["boite"], "note": o["note"], "sorte": sorte, "forme": None, "couleur_dite": None, "dit": None}


def objets_du_detecteur(liste: list[dict]) -> list[dict]:
    """La même liste SANS lecture de Claude : chaque rectangle garde ce que le détecteur croit (la référence de l'essai)."""
    return [objet_du_detecteur(o) for o in liste]


# ---------------------------------------------------------------- lectures notées à la main (à la place du service payant)
def _mots(texte: str, liste: tuple[str, ...]) -> str | None:
    bas = f" {texte.lower()} "
    return next((m for m in liste if re.search(rf"(?<![\w']){re.escape(m)}(?![\w])", bas)), None)


def fiche_depuis_notes(objets: str, sol: str | None = None, manquants: str = "") -> dict:
    """Une fiche lecture-photos/0.1 depuis des notes courtes (verites/<logement>/lecture_des_photos.py) :
    - objets : « 1 canape bleu ; 2 table ronde, bois ; 3 = 1 ; 4 faux » (numéro, sorte, puis ce qu'on en dit ; « = n » : même objet) ;
    - sol : « lames », ou « lames + carreaux » si la pièce a deux sols ;
    - manquants : « radiateur 0,600,215,790 ; canape 0,660,250,803 gris »."""
    fiche: dict = {"objets": {}, "sol": {"famille": None, "uniforme": True}, "manquants": []}
    for morceau in (m.strip() for m in objets.split(";")):
        if not morceau:
            continue
        numero, _, reste = morceau.partition(" ")
        reste = reste.strip()
        if reste.startswith("="):
            fiche["objets"][numero] = {"meme_que": int(reste[1:].strip())}
            continue
        sorte, _, dit = reste.partition(" ")
        o = {"sorte": sorte}
        if dit.strip():
            o["note"] = dit.strip()
            if (c := _mots(dit, COULEURS_DITES)):
                o["couleur"] = c
            if (f := _mots(dit, FORMES_DITES)):
                o["forme"] = f
        fiche["objets"][numero] = o
    if sol:
        familles = [f.strip() for f in sol.split("+")]
        fiche["sol"] = {"famille": familles[0], "uniforme": len(familles) == 1}
        if len(familles) > 1:
            fiche["sol"]["autre_famille"] = familles[1]
    for morceau in (m.strip() for m in manquants.split(";")):
        if not morceau:
            continue
        sorte, boite, *dit = morceau.split(" ", 2)
        m = {"sorte": sorte, "boite": [int(v) for v in boite.split(",")]}
        if dit and dit[0].strip():
            m["note"] = dit[0].strip()
            if (c := _mots(dit[0], COULEURS_DITES)):
                m["couleur"] = c
            if (f := _mots(dit[0], FORMES_DITES)):
                m["forme"] = f
        fiche["manquants"].append(m)
    return fiche


def lecture_depuis_notes(notes: dict[str, dict]) -> dict:
    """Toutes les photos d'un logement : {photo: {"objets": …, "sol": …, "manquants": …}} → {"schema", "photos": {photo: fiche}}."""
    return {"schema": SCHEMA, "photos": {nom: fiche_depuis_notes(n.get("objets", ""), n.get("sol"), n.get("manquants", ""))
                                         for nom, n in notes.items()}}
