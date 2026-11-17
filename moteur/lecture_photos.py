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
- `manquants` : ce que la photo montre et qu'aucun rectangle n'encadre (sorte + rectangle approché) ;
- depuis la 0.3 (17/11/2026), pour un grand meuble adossé dont le rectangle ne montre qu'un morceau : `gauche`, `droite`
  (où il finit vraiment : des repères, voir BOUT plus bas) et `pied_cache`. Règle apprise à l'essai : « coin » seulement si on
  VOIT le meuble toucher le coin ; ne rien dire quand on ne sait pas (4 repères trop affirmatifs sur 15 ont fait reculer).
Claude ne donne AUCUNE place en mètres. Une fenêtre qui descend jusqu'au sol se dit « porte_fenetre ».

Ce module contrôle la fiche (sortes connues, numéros existants) et la traduit pour le reste d'Atelya (moteur/photos_lues.py).
Les lectures faites à la main dans la conversation, à la place du service payant : verites/<logement>/lecture_des_photos.py.
"""
from __future__ import annotations

import re

from moteur.meubles import NOMS_MEUBLES

SCHEMA = "lecture-photos/0.3"  # 0.2 (16/11/2026) : sortes précises des appareils de cuisine ; 0.3 (17/11/2026) : les BOUTS d'un
# grand meuble adossé (« gauche », « droite », « pied_cache ») ; les fiches 0.1 et 0.2 se lisent pareil
# Les bouts d'un meuble adossé (essai du 17/11/2026, « vas-y » de NT) : le détecteur n'encadre que ce qu'il VOIT d'un meuble ;
# un linéaire de cuisine derrière un îlot, un buffet derrière une table, un dressing qui file jusqu'au fond sortent en petit
# morceau. Claude dit où le meuble finit vraiment, de chaque côté de l'image, avec des REPÈRES et non des mètres :
#   « coin »  : il va jusqu'au bout de son mur de ce côté ;
#   « d<n> »  : il s'arrête au bord DROIT du rectangle n (il touche l'objet n, qui est à sa gauche) ; « g<n> » : à son bord gauche ;
#   « u<px> » : il s'arrête à peu près à cette abscisse de l'image (bout caché, deviné d'après ce qui dépasse) ;
#   « bord »  : le bord du rectangle est bien le vrai bout (la lecture le confirme : cette vue montre le meuble jusque-là) ;
#   « cadre » : il sort du cadre de la photo de ce côté (on n'en voit pas le bout) ;
#   rien      : la lecture ne dit rien, le bord du rectangle est pris tel quel.
# « pied_cache » : le bas du rectangle n'est pas le pied du meuble (caché par ce qui est devant) : sa place vient de son mur.
BOUT = re.compile(r"^(coin|bord|cadre|[gd]\d+|u\d+)$")
# Les RANGÉES de cuisine (17/11/2026, moteur/rangees.py) : par photo, `rangees` = [{"mur": {"repere": "vers" | "gauche" | "droite",
# "numero": n}, "suite": [{"sorte": "coin" | "angle" | "cadre" | "colonne_cuisine" | "meuble_cuisine_bas" | "refrigerateur" | "vide",
# "modules": 2, "reste": true, "numeros": [4, 7]}]}] — la suite des éléments d'un mur, de la gauche vers la droite de l'image.
# Notes courtes : « vers12 : coin colonne(4) bas*(24) coin ; gauche12 : cadre colonne(3) colonne angle » ; « bas x3(7) ».
SORTES_DE_RANGEE = {"coin": "coin", "angle": "angle", "cadre": "cadre", "colonne": "colonne_cuisine", "bas": "meuble_cuisine_bas",
                    "frigo": "refrigerateur", "vide": "vide"}
MUR_DE_RANGEE = re.compile(r"^(vers|gauche|droite)(\d+)(?:\+(\d))?$")  # « droite6+1 » : le mur d'après, passé un pilier
ELEMENT_DE_RANGEE = re.compile(r"^(coin|angle|cadre|colonne|bas|frigo|vide)(\*)?(?:x(\d+(?:\.\d+)?))?(?:\(([\d,]+)\))?$")
# ce que la maquette ne sait pas encore porter, mais que Claude doit pouvoir nommer (compté « vu, pas représenté »)
# les équipements du logement, que Claude nomme et qu'Atelya pose et dessine depuis le 16/11/2026 (moteur/equipements.py).
# « electromenager » seul reste accepté (fiches 0.1 : la note dit lequel, « electromenager four encastré ») ; depuis la 0.2 la
# consigne demande la sorte précise : refrigerateur, four, micro_ondes, plaque, lave_linge, lave_vaisselle.
EQUIPEMENTS = ("cheminee", "radiateur", "baignoire", "douche", "wc", "lavabo", "evier", "electromenager", "refrigerateur", "four",
               "micro_ondes", "plaque", "lave_linge", "lave_vaisselle", "hotte", "applique", "plafonnier", "passe_plat", "etagere_murale",
               "rideaux", "store")
OUVERTURES = ("fenetre", "porte_fenetre", "porte")
SORTES = tuple(dict.fromkeys((*NOMS_MEUBLES, *EQUIPEMENTS, *OUVERTURES, "autre", "faux")))
FAMILLES_DE_SOL = ("lames", "point_de_hongrie", "batons_rompus", "carreaux")
COULEURS_DITES = ("blanc cassé", "bois clair", "bois foncé", "gris clair", "gris anthracite", "blanc", "blanche", "noir", "noire", "gris",
                  "grise", "bleu", "bleue", "jaune", "beige", "crème", "rouge", "vert", "verte", "rose", "mauve", "brun", "marron",
                  "doré", "inox", "bois", "pin", "rotin")
FORMES_DITES = ("ronde", "rond", "ovale", "rectangulaire", "carrée", "carré", "d'angle", "octogonal", "une place", "double")


def consigne() -> str:
    """Le texte qui dirait à Claude quoi remplir (envoyé plus tard par l'API avec chaque photo ; rien n'est envoyé ici)."""
    return f"""Tu regardes une photo d'un logement. Des rectangles numérotés y encadrent ce qu'un détecteur automatique a repéré ;
il se trompe souvent sur ce que c'est. Tu remplis une fiche JSON au format {SCHEMA} :

{{"objets": {{"<numéro>": {{"sorte": "…", "meme_que": <numéro>, "forme": "…", "couleur": "…", "note": "…",
                          "gauche": "…", "droite": "…", "pied_cache": true}}, …}},
 "sol": {{"famille": "…", "uniforme": true, "autre_famille": "…"}},
 "manquants": [{{"sorte": "…", "boite": [x0, y0, x1, y1]}}]}}

- Pour CHAQUE numéro, « sorte » dit ce que le rectangle montre vraiment, parmi : {", ".join(SORTES)}.
  « faux » : le rectangle ne montre rien de tel (un reflet, un morceau de mur, un filigrane). « autre » : un objet hors de la liste.
  Une fenêtre dont la vitre descend jusqu'au sol est une « porte_fenetre » ; sur allège (un mur dessous), une « fenetre ».
  Une armoire ou un placard à portes est un « placard » ; un buffet est un « rangement » ; les meubles de cuisine sont
  « meuble_cuisine_bas », « meuble_cuisine_haut » ou « colonne_cuisine » ; un luminaire qui pend du plafond est une
  « suspension », collé au plafond un « plafonnier », fixé au mur une « applique ». Un écran d'ordinateur n'est pas une « television ».
  Un appareil de cuisine se nomme précisément : « refrigerateur », « four », « micro_ondes », « plaque », « lave_vaisselle »,
  « lave_linge » ; un radiateur porte-serviettes : « radiateur » avec la note « sèche-serviettes » ; des voilages (rideaux fins
  qui laissent passer le jour) : « rideaux » avec la note « voilages » ; une ouverture à mi-hauteur entre deux pièces, sans
  vitre : « passe_plat ».
- « meme_que » : seulement si ce rectangle montre le MÊME objet qu'un autre numéro (un morceau, ou deux rectangles pour un meuble).
- « forme » (ronde, rectangulaire…) et « couleur » (bleu, blanc, bois clair…) : en un ou deux mots, si c'est net.
- « sol » : la famille du sol de la pièce où se tient le photographe, parmi {", ".join(FAMILLES_DE_SOL)} ; « uniforme » : faux si
  cette pièce montre deux sols différents (un tapis n'est pas un sol), et alors « autre_famille » dit le second.
- « manquants » : ce que la photo montre d'important et qu'aucun rectangle n'encadre (rectangle approché, en pixels).
- Pour un GRAND MEUBLE ADOSSÉ à un mur (buffet, armoire, placard, bibliothèque, meuble télé, meubles et colonnes de cuisine) dont
  le rectangle ne montre qu'un morceau : « gauche » et « droite » disent où le meuble finit VRAIMENT de chaque côté de l'image :
  « coin » (il va jusqu'au bout de son mur), « d<n> » (il s'arrête au bord droit du rectangle n, qu'il touche), « g<n> » (au bord
  gauche du rectangle n), « u<abscisse en pixels> » (bout caché, à peu près là), « bord » (le bord du rectangle est bien le
  vrai bout : on voit le meuble finir là), « cadre » (le meuble sort de la photo de ce côté). Ne mets rien si tu ne sais pas.
  « pied_cache » : vrai si un autre objet cache le bas du meuble (un linéaire de cuisine derrière un îlot).
- Pour une CUISINE, ajoute « rangees » : pour chaque mur garni, {{"mur": {{"repere": "vers", "numero": n}}, "suite": […]}} où le mur
  est celui que touche le regard vers le rectangle n (ou « gauche » / « droite » : le mur voisin, au bout gauche / droit de celui-là
  à l'image ; avec « saut » : 1, le mur d'après, de l'autre côté d'un pilier) et la suite donne, de la GAUCHE vers la DROITE de l'image : « coin » (le bout du mur, seulement si tu VOIS la rangée
  le toucher), « angle » (le bout du mur, quand le coin est pris par la rangée du mur voisin), « cadre » (la rangée sort de la
  photo), puis chaque élément : « colonne_cuisine », « meuble_cuisine_bas », « refrigerateur », « vide », avec « numeros » (ses
  rectangles), « modules » (combien de largeurs de 60 cm, 1 par défaut) ou « reste » (il remplit ce qui reste du mur).
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
        defauts += [f"numéro {n} : {d}" for d in _defauts_des_bouts(o, numeros)]
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
        defauts += [f"manquant {m.get('sorte')} : {d}" for d in _defauts_des_bouts(m, numeros)]
    for k, r in enumerate(fiche.get("rangees") or [], start=1):
        mur, suite = r.get("mur") or {}, r.get("suite") or []
        if mur.get("repere") not in ("vers", "gauche", "droite") or int(mur.get("numero", -1)) not in numeros:
            defauts.append(f"rangée {k} : mur {mur!r} illisible ou numéro inconnu")
        if not any(e.get("sorte") in ("coin", "angle") for e in suite[:1] + suite[-1:]):
            defauts.append(f"rangée {k} : aucun bout calé sur un coin")
        if not any(e.get("sorte") in ("colonne_cuisine", "meuble_cuisine_bas", "refrigerateur") for e in suite):
            defauts.append(f"rangée {k} : aucun élément")
        for e in suite:
            if e.get("sorte") not in SORTES_DE_RANGEE.values():
                defauts.append(f"rangée {k} : élément {e.get('sorte')!r} inconnu")
            defauts += [f"rangée {k} : numéro {n} inconnu" for n in e.get("numeros") or [] if int(n) not in numeros]
    return defauts


def _defauts_des_bouts(o: dict, numeros: set[int]) -> list[str]:
    defauts = []
    for cote in ("gauche", "droite"):
        b = o.get(cote)
        if b is None:
            continue
        if not BOUT.match(str(b)):
            defauts.append(f"« {cote} » {b!r} illisible (coin, bord, cadre, g<n>, d<n> ou u<pixels>)")
        elif b[0] in "gd" and b[1:].isdigit() and int(b[1:]) not in numeros:
            defauts.append(f"« {cote} » renvoie au numéro {b[1:]}, inconnu")
    return defauts


def _bouts(o: dict, boites: dict[int, list[float]], propre: list[float]) -> dict | None:
    """Les bouts lus d'un meuble, prêts pour la géométrie : {"gauche": "coin" | "cadre" | abscisse en pixels, "droite": idem}.
    `propre` : le rectangle du meuble lui-même (« bord »)."""
    sortie = {}
    for cote in ("gauche", "droite"):
        b = o.get(cote)
        if b is None or not BOUT.match(str(b)):
            continue
        if b in ("coin", "cadre"):
            sortie[cote] = b
        elif b == "bord":
            sortie[cote] = float(propre[0 if cote == "gauche" else 2])
        elif b[0] == "u":
            sortie[cote] = float(b[1:])
        elif int(b[1:]) in boites:
            sortie[cote] = float(boites[int(b[1:])][0 if b[0] == "g" else 2])
    return sortie or None


def objets_lus(fiche: dict, liste: list[dict], manquants: bool = True, reunir: bool = True) -> list[dict]:
    """Les objets d'une photo tels que Claude les a compris : la liste numérotée d'Atelya (`liste` : numero, boite, note…)
    avec la sorte de Claude ; les « faux » et les doublons (« meme_que ») retirés ; les « manquants » ajoutés (rectangle
    approché : `approche` vrai, note 0,5). Un numéro que Claude n'a pas rempli garde ce que le détecteur croyait."""
    sortie = []
    lus = fiche.get("objets") or {}
    entieres: dict[int, list[float]] = {}
    for o in liste:
        l = lus.get(str(o["numero"])) or {}
        boite = list(o["boite"])
        if reunir and l.get("meme_que") is None:
            # les autres rectangles du MÊME objet (« meme_que ») en sont des morceaux : l'objet entier est leur réunion (un linéaire
            # de cuisine encadré en trois fois, un canapé en deux) — avant le 17/11/2026 ils étaient jetés et l'objet restait un bout
            for autre in liste:
                la = lus.get(str(autre["numero"])) or {}
                if la.get("meme_que") is not None and int(la["meme_que"]) == int(o["numero"]):
                    b = autre["boite"]
                    boite = [min(boite[0], b[0]), min(boite[1], b[1]), max(boite[2], b[2]), max(boite[3], b[3])]
        entieres[int(o["numero"])] = boite
    for o in liste:
        l = lus.get(str(o["numero"]))
        if l is None:
            sortie.append(objet_du_detecteur(o))
            continue
        if l.get("sorte") == "faux" or l.get("meme_que") is not None:
            continue
        lu = {"numero": o["numero"], "boite": entieres[int(o["numero"])], "note": o["note"], "sorte": l["sorte"], "forme": l.get("forme"),
              "couleur_dite": l.get("couleur"), "dit": l.get("note")}
        if (b := _bouts(l, entieres, lu["boite"])):
            lu["bouts"] = b
        if l.get("pied_cache"):
            lu["pied_cache"] = True
        sortie.append(lu)
    if manquants:
        for k, m in enumerate(fiche.get("manquants") or [], start=1):
            lu = {"numero": -k, "boite": [float(v) for v in m["boite"]], "note": 0.5, "sorte": m["sorte"], "forme": m.get("forme"),
                  "couleur_dite": m.get("couleur"), "dit": m.get("note"), "approche": True}
            if (b := _bouts(m, entieres, lu["boite"])):
                lu["bouts"] = b
            if m.get("pied_cache"):
                lu["pied_cache"] = True
            sortie.append(lu)
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


def _reperes(dit: str) -> tuple[str, dict]:
    """« gris, linéaire du fond {g=d4 d=coin pied} » → (« gris, linéaire du fond », {"gauche": "d4", "droite": "coin", "pied_cache": True})."""
    m = re.search(r"\{([^}]*)\}", dit)
    if not m:
        return dit.strip(), {}
    champs: dict = {}
    for mot in m.group(1).split():
        if mot == "pied":
            champs["pied_cache"] = True
        elif mot == "entier":  # le rectangle montre le meuble d'un bout à l'autre
            champs["gauche"] = champs["droite"] = "bord"
        elif mot[:2] in ("g=", "d="):
            champs["gauche" if mot[0] == "g" else "droite"] = mot[2:]
        else:
            raise ValueError(f"repère illisible : {mot!r} dans {dit!r}")
    return (dit[:m.start()] + dit[m.end():]).strip(), champs


def rangees_depuis_notes(texte: str) -> list[dict]:
    """« vers12 : coin colonne(4) bas*(24) coin ; gauche12 : cadre colonne(3) colonne angle » → le champ `rangees` d'une fiche."""
    sortie = []
    for morceau in (m.strip() for m in texte.split(";")):
        if not morceau:
            continue
        mur, _, reste = morceau.partition(":")
        m = MUR_DE_RANGEE.match(mur.strip())
        if not m:
            raise ValueError(f"mur de rangée illisible : {mur!r}")
        suite = []
        for mot in reste.split():
            e = ELEMENT_DE_RANGEE.match(mot)
            if not e:
                raise ValueError(f"élément de rangée illisible : {mot!r} dans {morceau!r}")
            el: dict = {"sorte": SORTES_DE_RANGEE[e.group(1)]}
            if e.group(2):
                el["reste"] = True
            if e.group(3):
                el["modules"] = float(e.group(3))
            if e.group(4):
                el["numeros"] = [int(v) for v in e.group(4).split(",")]
            suite.append(el)
        mur = {"repere": m.group(1), "numero": int(m.group(2))}
        if m.group(3):
            mur["saut"] = int(m.group(3))
        sortie.append({"mur": mur, "suite": suite})
    return sortie


def fiche_depuis_notes(objets: str, sol: str | None = None, manquants: str = "", rangees: str = "") -> dict:
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
        dit, champs = _reperes(dit)
        o = {"sorte": sorte, **champs}
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
        champs: dict = {}
        if dit:
            dit[0], champs = _reperes(dit[0])
        m = {"sorte": sorte, "boite": [int(v) for v in boite.split(",")], **champs}
        if dit and dit[0].strip():
            m["note"] = dit[0].strip()
            if (c := _mots(dit[0], COULEURS_DITES)):
                m["couleur"] = c
            if (f := _mots(dit[0], FORMES_DITES)):
                m["forme"] = f
        fiche["manquants"].append(m)
    if rangees.strip():
        fiche["rangees"] = rangees_depuis_notes(rangees)
    return fiche


def lecture_depuis_notes(notes: dict[str, dict]) -> dict:
    """Toutes les photos d'un logement : {photo: {"objets": …, "sol": …, "manquants": …}} → {"schema", "photos": {photo: fiche}}."""
    return {"schema": SCHEMA, "photos": {nom: fiche_depuis_notes(n.get("objets", ""), n.get("sol"), n.get("manquants", ""), n.get("rangees", ""))
                                         for nom, n in notes.items()}}
