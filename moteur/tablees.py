r"""LES CHAISES AUTOUR DE LEUR TABLE : sièges rangés le long des côtés de leur table, de leur îlot ou de leur bureau, tournés
vers lui, rentrés comme sur les photos (étape 3, 17/11/2026).

Pourquoi (NT, 17/11/2026 : « il faudra que tu apprennes aussi à Atelya à mettre les chaises sous les tables, comme sur les
photos, vu que là ça n'a pas trop de sens ») : chaque chaise était posée là où tombait son pied sur sa photo (à 30-50 cm près),
tournée vers le mur le plus proche ou le milieu de la pièce, puis écartée de la table quand elle la traversait. Autour d'une
table, cela donnait des chaises de travers, à des distances inégales, parfois dos à la table.

Or une tablée est RÉGULIÈRE : les chaises sont le long des côtés, face à la table, à pas égaux, toutes rentrées pareil. La photo
dit COMBIEN de chaises et à peu près OÙ ; le reste est de la géométrie :
1. chaque siège posé d'après les photos rejoint la table (l'îlot, le bureau) de sa pièce dont il est à moins de PORTEE_M ;
2. la DISPOSITION (combien de sièges sur chaque côté : un bureau n'a que son devant, un îlot ses deux grands côtés, une table
   ses quatre côtés, une place tous les 55 cm) est celle qui met les sièges vus le plus près de leurs places, à régularité
   égale : autant de chaises de chaque grand côté, les bouts plutôt libres, les tabourets d'un îlot du même côté. (Essayé
   d'abord : chaque siège au côté le plus proche — 3 chaises d'un côté et 1 de l'autre pour une table qui en a 2 et 2.)
3. sur chaque côté, les sièges sont mis à pas égaux, dans l'ordre où les photos les montrent, face à la table ; le pas est
   celui que les photos montrent entre voisins ;
4. tous sont rentrés pareil : de ce que les photos montrent en moyenne (le milieu du siège entre 10 et 30 cm du bord : une
   chaise n'est jamais rentrée de plus de 35 % sous sa table, moteur.collisions.SOUS_LA_TABLE) ; un tabouret touche son îlot ;
5. autour d'une table RONDE (ou carrée), les sièges gardent leur direction vue depuis le milieu de la table, écartés d'au moins
   une largeur de chaise.
Un siège qui ne tiendrait pas dans la pièce à sa place rangée (côté de table contre un mur) reste où les photos l'ont mis. Ce
qu'une personne a placé (relevé, écran de vérification) n'est jamais déplacé — ni les tables, ni les sièges.
7. Les sièges d'une même tablée sont assortis : même taille et même couleur, donc le même modèle dans la maquette.
6. La table se cale sur ses chaises (au plus 50 cm) : mesuré sur les relevés, les chaises posées une à une étaient plus près de
   leur vraie place (9 à 54 cm) que leur table (39 cm), et rangées autour d'une table mal placée elles reculaient.
"""
from __future__ import annotations

import math

import numpy as np

VERSION = "0.1.0"
SIEGES = ("chaise", "tabouret_haut", "chaise_de_bureau")
PORTEUSES = ("table", "ilot", "bureau")
PORTEE_M = 0.8  # un siège à moins de 80 cm du bord d'une table est à cette table (sa place est lue à 30-50 cm près)
PLACE_M = 0.55  # la largeur d'une place assise le long d'un côté
ECART_M = (0.10, 0.30)  # le milieu d'une chaise est entre 10 et 30 cm du bord de sa table (relevés d'app-001 et app-002 : 5 à 28 cm)
ECART_COURANT_M = 0.15
JEU_ILOT_M = 0.02  # un tabouret ne passe pas sous son îlot : il le touche presque
RONDE_M = 0.05  # une table dont les deux côtés diffèrent de moins de 5 cm est ronde (ou carrée) : sièges en couronne
DANS_LA_PIECE = 0.9
RENTRE_MAX = 0.33  # part d'un siège sous sa table, au plus (le contrôle des collisions en tolère 0,35)
RANGE_M = 0.45  # un siège à moins de 45 cm du bord d'une table et tourné vers elle est rangé à cette table
BOUT_M = 0.10  # ce que « coûte » un siège en bout de table quand on compare deux dispositions (m) : les bouts sont plutôt libres
INEGAL_M = 0.15  # … et une chaise de plus d'un grand côté que de l'autre
PLACE_ILOT_M = 0.6  # un îlot a au moins 60 cm de long par tabouret : il est allongé s'il en a plus que sa longueur n'en prend
ILOT_MAX_M = 3.0
MARGE_BOUT_M = 0.4  # les sièges d'un côté laissent en tout 40 cm libres aux bouts de ce côté
SEUL_AU_MILIEU_M = 1.2  # un siège seul sur un côté de moins de 1,20 m est au milieu
POIDS_TABLE = 2.0  # la place lue de la table pèse comme celle de deux chaises quand la tablée se cale
CALAGE_MAX_M = 0.5  # une table n'est jamais déplacée de plus de 50 cm vers ses chaises


def _axes(m: dict) -> tuple[np.ndarray, np.ndarray]:
    """(direction de la face, direction de la largeur) d'un meuble."""
    a = math.radians(float(m.get("face", 0.0) or 0.0))
    return np.array([math.cos(a), math.sin(a)]), np.array([-math.sin(a), math.cos(a)])


def cotes(table: dict) -> list[dict]:
    """Les côtés de la table où des sièges peuvent se mettre : {"milieu", "dehors" (vers l'extérieur), "long" (direction le long
    du côté), "longueur"}. Un bureau : son devant ; un îlot : ses deux grands côtés ; une table : ses quatre côtés."""
    f, t = _axes(table)
    l, p = float(table["dimensions"][0]), float(table["dimensions"][1])
    c = np.asarray(table["position"], float)
    devant = {"milieu": c + f * p / 2, "dehors": f, "long": t, "longueur": l}
    derriere = {"milieu": c - f * p / 2, "dehors": -f, "long": t, "longueur": l}
    if table["categorie"] == "bureau":
        return [devant]
    if table["categorie"] == "ilot":
        return [devant, derriere]
    return [devant, derriere, {"milieu": c + t * l / 2, "dehors": t, "long": f, "longueur": p},
            {"milieu": c - t * l / 2, "dehors": -t, "long": f, "longueur": p}]


def _au_bord(point: np.ndarray, table: dict) -> float:
    """La distance du point au rectangle de la table (0 dedans)."""
    f, t = _axes(table)
    d = point - np.asarray(table["position"], float)
    x, y = abs(float(d @ t)) - float(table["dimensions"][0]) / 2, abs(float(d @ f)) - float(table["dimensions"][1]) / 2
    return float(math.hypot(max(x, 0.0), max(y, 0.0)))


def _au_cote(point: np.ndarray, cote: dict) -> float:
    """La distance du point au segment de ce côté."""
    s = float(np.clip((point - cote["milieu"]) @ cote["long"], -cote["longueur"] / 2, cote["longueur"] / 2))
    return float(np.linalg.norm(point - (cote["milieu"] + s * cote["long"])))


def _tient(siege: dict, piece: dict | None) -> bool:
    from moteur.ranger_meubles import part_dans_la_piece

    return piece is None or part_dans_la_piece(siege, piece) >= DANS_LA_PIECE


def _pose(siege: dict, centre: np.ndarray, vers: np.ndarray) -> dict:
    return {**siege, "position": [round(float(centre[0]), 3), round(float(centre[1]), 3)],
            "face": round(math.degrees(math.atan2(vers[1], vers[0])), 1)}


def _pas_trop_rentre(siege: dict, table: dict) -> dict:
    """Le siège reculé de 2 cm en 2 cm, dos tourné, tant qu'il est rentré sous la table de plus que le contrôle des collisions ne
    le tolère (un siège posé en biais contre une table ronde : la boîte de la table est carrée)."""
    from moteur.ranger_meubles import recouvrement

    if table["categorie"] == "ilot":
        return siege
    a = math.radians(float(siege["face"]))
    arriere = -np.array([math.cos(a), math.sin(a)])
    essai = siege
    for k in range(1, 26):
        if recouvrement(essai, table) <= RENTRE_MAX:
            break
        centre = np.asarray(siege["position"], float) + arriere * 0.02 * k
        essai = {**siege, "position": [round(float(centre[0]), 3), round(float(centre[1]), 3)]}
    return essai


def sieges_ranges(meubles: list[dict]) -> dict[int, dict]:
    """Les sièges déjà rangés à une table ({id() du siège: sa table}) : tout près de son bord et tournés vers elle. Sert à la
    réparation des collisions (moteur/collisions.py) : une table qu'elle déplace emmène ses chaises."""
    from moteur.ranger_meubles import accroche

    tables = [m for m in meubles if m["categorie"] in PORTEUSES and not accroche(m)]
    sortie = {}
    for s in meubles:
        if s["categorie"] not in SIEGES or accroche(s):
            continue
        p = np.asarray(s["position"], float)
        a = math.radians(float(s.get("face", 0.0) or 0.0))
        regard = np.array([math.cos(a), math.sin(a)])
        for t in tables:
            if t.get("piece") != s.get("piece") or _au_bord(p, t) > RANGE_M:
                continue
            f, tr = _axes(t)
            d = np.asarray(t["position"], float) - p
            # le point de la table le plus proche du siège, le long de son regard : il regarde la table s'il la touche des yeux
            x, y = float(d @ tr), float(d @ f)
            vers = np.array([float(regard @ tr), float(regard @ f)])
            if x * vers[0] + y * vers[1] <= 0:
                continue
            en_travers = abs(x * vers[1] - y * vers[0])  # l'écart entre son regard et le milieu de la table
            if en_travers <= max(float(t["dimensions"][0]), float(t["dimensions"][1])) / 2:
                sortie[id(s)] = t
                break
    return sortie


def _en_couronne(table: dict, sieges: list[dict], ecart: float, vus: list[np.ndarray]) -> list[dict]:
    """Autour d'une table ronde : chaque siège garde sa direction vue du milieu de la table ; deux voisins sont écartés d'au
    moins une place ; tous à la même distance, face au milieu."""
    c = np.asarray(table["position"], float)
    rayon = float(table["dimensions"][0]) / 2
    angles = [math.atan2(v[1] - c[1], v[0] - c[0]) for v in vus]
    ordre = sorted(range(len(sieges)), key=lambda i: angles[i])
    sortie = [dict(s) for s in sieges]
    # l'angle qu'occupe une place : deux chaises voisines, tournées vers le milieu, ne se touchent pas par leurs coins de devant
    large = max(float(x["dimensions"][0]) for x in sieges) + 0.04
    profond = max(float(x["dimensions"][1]) for x in sieges)
    if len(sieges) > 1:  # trop de sièges pour tenir si près d'une petite table : tous reculés jusqu'à tenir côte à côte
        ecart = max(ecart, large / (2 * math.sin(math.pi / len(sieges))) + 0.01 - rayon + profond / 2)
    devant = max(rayon + ecart - profond / 2, large / 2)
    pas_min = 2 * math.asin(min(1.0, large / (2 * devant)))
    a = [angles[i] for i in ordre]
    for _ in range(50):  # écarter les voisins trop serrés, de proche en proche, en tournant autour de la table
        bouge = False
        for k in range(len(a) if len(a) > 1 else 0):
            suivant = (k + 1) % len(a)
            trou = (a[suivant] - a[k]) % (2 * math.pi)  # du siège k au suivant, en tournant dans le sens direct
            if trou < pas_min - 1e-6:
                a[k] -= (pas_min - trou) / 2
                a[suivant] += (pas_min - trou) / 2
                bouge = True
        if not bouge:
            break
    for i, angle in zip(ordre, a):
        d = np.array([math.cos(angle), math.sin(angle)])
        sortie[i] = _pas_trop_rentre(_pose(sieges[i], c + d * (rayon + ecart), -d), table)
    return sortie


def ranger(meubles: list[dict], logement: dict, journal=None) -> tuple[list[dict], list[dict]]:
    """Les meubles, sièges rangés autour de leur table (ordre d'origine gardé), et ce qui a été fait :
    [{"table", "sieges": [ids], "restes": [ids des sièges laissés où ils étaient]}]."""
    from moteur.ranger_meubles import _fixe, accroche

    pieces = {p["id"]: p for p in logement.get("pieces", [])}
    sortie = [dict(m) for m in meubles]
    tables = [m for m in sortie if m["categorie"] in PORTEUSES and not accroche(m)]
    membres: dict[int, list[int]] = {}
    for i, s in enumerate(sortie):
        if s["categorie"] not in SIEGES or _fixe(s) or accroche(s):
            continue
        p = np.asarray(s["position"], float)
        candidates = [(_au_bord(p, t), k) for k, t in enumerate(tables) if t.get("piece") == s.get("piece")]
        candidates = [c for c in candidates if c[0] <= PORTEE_M]
        if not candidates:
            continue
        # une chaise de bureau va au bureau quand elle en a un à sa portée, même si une table est plus près
        bureaux = [c for c in candidates if tables[c[1]]["categorie"] == "bureau"]
        choix = min(bureaux)[1] if bureaux and s["categorie"] == "chaise_de_bureau" else min(candidates)[1]
        membres.setdefault(choix, []).append(i)
    actions = []
    for k, indices in membres.items():
        table = tables[k]
        piece = pieces.get(table.get("piece"))
        vus = {i: np.asarray(sortie[i]["position"], float) for i in indices}  # où les photos montrent chaque siège
        if table["categorie"] == "ilot" and not _fixe(table):
            # un îlot posé à la longueur courante de sa sorte (2 m) et vu avec quatre tabourets en fait au moins 2,40 m
            longueur = min(len(indices) * PLACE_ILOT_M, ILOT_MAX_M)
            if longueur > float(table["dimensions"][0]) + 1e-6:
                allonge = {**table, "dimensions": [round(longueur, 2), *table["dimensions"][1:]]}
                if _tient(allonge, piece):
                    table.update(dimensions=allonge["dimensions"])
        places, restes = _places(table, {i: sortie[i] for i in indices}, vus, piece)
        # 6. la table se cale sur ses chaises : si, en moyenne, elles sont vues décalées de leurs places, c'est la table qui est
        #    mal placée (une chaise a un pied net sur la photo, une table est cachée par ses chaises)
        if places and not _fixe(table):
            ecart = np.mean([vus[i] - np.asarray(places[i]["position"], float) for i in places], axis=0) * len(places) / (len(places) + POIDS_TABLE)
            n = float(np.linalg.norm(ecart))
            if n > 0.03:
                ecart *= min(1.0, CALAGE_MAX_M / n)
                calee = {**table, "position": [round(float(table["position"][0] + ecart[0]), 3), round(float(table["position"][1] + ecart[1]), 3)]}
                if _tient(calee, piece):
                    table.update(position=calee["position"])
                    places, restes = _places(table, {i: sortie[i] for i in indices}, vus, piece)
        ranges = []
        for i, neuf in places.items():
            if _tient(neuf, piece):
                sortie[i] = neuf
                ranges.append(i)
            else:
                restes.append(i)
        _assortir([sortie[i] for i in ranges])
        actions.append({"table": table["id"], "sieges": [sortie[i]["id"] for i in ranges], "restes": [sortie[i]["id"] for i in restes]})
        if journal:
            journal(f"  tablée : {len(ranges)} siège(s) rangé(s) autour de {table['categorie']} {table['id']}"
                    + (f", {len(restes)} laissé(s) où les photos les montrent" if restes else ""))
    return sortie, actions


def _assortir(sieges: list[dict]) -> None:
    """Les sièges d'une même tablée sont les MÊMES : même taille, même couleur (la médiane de ce que les photos montrent), donc
    le même modèle dans la maquette (moteur.construire choisit un modèle par sorte, taille et couleur ; avant, quatre tabourets
    vus de quatre couleurs un peu différentes étaient quatre modèles différents)."""
    par_sorte: dict[str, list[dict]] = {}
    for s in sieges:
        par_sorte.setdefault(s["categorie"], []).append(s)
    for groupe in par_sorte.values():
        if len(groupe) < 2:
            continue
        couleurs = [g["couleur"] for g in groupe if g.get("couleur")]
        couleur = [int(v) for v in np.median(np.array(couleurs), axis=0)] if couleurs else None
        for g in groupe:
            g["dimensions"] = list(groupe[0]["dimensions"])
            if couleur is not None:
                g["couleur"] = list(couleur)


def _places(table: dict, sieges: dict[int, dict], vus: dict[int, np.ndarray], piece: dict | None = None) -> tuple[dict[int, dict], list[int]]:
    """La place rangée de chaque siège autour de la table ({indice: siège posé}), et les sièges sans place (côtés pleins)."""
    l, p = float(table["dimensions"][0]), float(table["dimensions"][1])
    indices = list(sieges)
    if table["categorie"] == "table" and abs(l - p) <= RONDE_M:
        c0 = np.asarray(table["position"], float)
        ecart = float(np.clip(np.median([float(np.linalg.norm(vus[i] - c0)) - l / 2 for i in indices]), *ECART_M))
        return dict(zip(indices, _en_couronne(table, list(sieges.values()), ecart, [vus[i] for i in indices]))), []
    cs = cotes(table)
    grand = max(c["longueur"] for c in cs)
    bouts = [c["longueur"] < grand - RONDE_M for c in cs]
    nombre = [1 if table["categorie"] == "bureau" or bouts[j] else max(1, int(c["longueur"] / PLACE_M + 1e-6)) for j, c in enumerate(cs)]
    # tous rentrés pareil : la distance que les photos montrent, en moyenne, entre le milieu des sièges et le bord le plus proche
    if table["categorie"] == "ilot":
        ecart = None  # un tabouret touche son îlot : sa demi-profondeur + le jeu
    else:
        dehors = [min(_au_cote(vus[i], c) for c in cs) * (1.0 if _au_bord(vus[i], table) > 0 else -1.0) for i in indices]
        ecart = float(np.clip(np.median(dehors), *ECART_M))

    def place(j: int, le_long: float, i: int) -> dict:
        c = cs[j]
        dehors = float(sieges[i]["dimensions"][1]) / 2 + JEU_ILOT_M if ecart is None else ecart
        return _pas_trop_rentre(_pose(sieges[i], c["milieu"] + le_long * c["long"] + dehors * c["dehors"], -c["dehors"]), table)

    # 2. la DISPOSITION : combien de sièges sur chaque côté. Toutes les dispositions possibles sont essayées, sièges à pas égaux ;
    #    la meilleure est celle où les sièges vus sont le plus près de leurs places, à régularité égale (autant de chaises de
    #    chaque grand côté, les bouts de table plutôt libres ; les tabourets d'un îlot du même côté)
    total = min(len(indices), sum(nombre))
    meilleure = None
    for partage in _partages(total, nombre):
        creneaux = [(j, cs[j]["longueur"] * ((r + 0.5) / k - 0.5)) for j, k in enumerate(partage) for r in range(k)]
        essai = [place(j, le_long, indices[0]) for j, le_long in creneaux]
        if piece is not None and not all(_tient(e, piece) for e in essai):
            continue  # un côté de la table est contre un mur : personne ne s'y assoit
        cout = [[math.dist(e["position"], vus[i]) for i in indices] for e in essai]  # créneaux × sièges
        choix = affectation(cout)
        longs = [k for j, k in enumerate(partage) if not bouts[j]]
        if table["categorie"] == "ilot":
            if len(longs) > 1 and min(longs) > 0:
                continue  # les tabourets d'un îlot sont tous du même côté (l'autre est celui de la cuisine)
            irregulier = 0.0
        else:
            irregulier = INEGAL_M * (max(longs) - min(longs)) + BOUT_M * sum(k for j, k in enumerate(partage) if bouts[j])
        note = sum(cout[c][choix[c]] for c in range(len(creneaux))) + irregulier
        if meilleure is None or note < meilleure[0]:
            meilleure = (note, partage, {indices[choix[c]]: creneaux[c][0] for c in range(len(creneaux))})
    if meilleure is None:
        return {}, indices
    _, partage, cote_de = meilleure
    # 3. le long de chaque côté : dans l'ordre vu, à pas égaux — le pas que les photos montrent entre voisins (deux chaises aux
    #    deux bouts d'un grand côté y restent), le même des deux grands côtés quand ils ont autant de sièges
    pas_vu: dict[int, float] = {}
    rangs: dict[int, list[int]] = {}
    for j, c in enumerate(cs):
        rangs[j] = sorted((i for i, jj in cote_de.items() if jj == j), key=lambda i: float((vus[i] - c["milieu"]) @ c["long"]))
        k = len(rangs[j])
        if k >= 2:
            le_long = [float((vus[i] - c["milieu"]) @ c["long"]) for i in rangs[j]]
            pas_vu[j] = float(np.clip((le_long[-1] - le_long[0]) / (k - 1), PLACE_M, max(PLACE_M, (c["longueur"] - MARGE_BOUT_M) / (k - 1))))
    for j in list(pas_vu):
        for jj in pas_vu:
            if jj > j and not bouts[j] and not bouts[jj] and len(rangs[j]) == len(rangs[jj]):
                pas_vu[j] = pas_vu[jj] = (pas_vu[j] + pas_vu[jj]) / 2
    places = {}
    for j, c in enumerate(cs):
        k = len(rangs[j])
        for rang, i in enumerate(rangs[j]):
            if k >= 2:
                le_long = pas_vu[j] * (rang - (k - 1) / 2)
            elif bouts[j] or c["longueur"] < SEUL_AU_MILIEU_M:
                le_long = 0.0
            else:  # seul sur un grand côté : là où la photo le montre (son voisin n'a peut-être pas été vu)
                limite = c["longueur"] / 2 - MARGE_BOUT_M / 2
                le_long = float(np.clip((vus[i] - c["milieu"]) @ c["long"], -limite, limite))
            places[i] = place(j, le_long, i)
    return places, [i for i in indices if i not in cote_de]


def _partages(total: int, nombre: list[int]):
    """Toutes les façons de mettre `total` sièges sur des côtés qui en prennent au plus `nombre`."""
    if len(nombre) == 1:
        if total <= nombre[0]:
            yield (total,)
        return
    for k in range(min(total, nombre[0]) + 1):
        for reste in _partages(total - k, nombre[1:]):
            yield (k, *reste)


def affectation(cout: list[list[float]]) -> list[int]:
    """L'affectation de coût total minimal (méthode hongroise) : pour chaque ligne, sa colonne. Il faut lignes ≤ colonnes."""
    n, m = len(cout), len(cout[0]) if cout else 0
    u, v, p, chemin = [0.0] * (n + 1), [0.0] * (m + 1), [0] * (m + 1), [0] * (m + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0, mini, pris = 0, [math.inf] * (m + 1), [False] * (m + 1)
        while True:
            pris[j0] = True
            i0, delta, j1 = p[j0], math.inf, 0
            for j in range(1, m + 1):
                if not pris[j]:
                    c = cout[i0 - 1][j - 1] - u[i0] - v[j]
                    if c < mini[j]:
                        mini[j], chemin[j] = c, j0
                    if mini[j] < delta:
                        delta, j1 = mini[j], j
            for j in range(m + 1):
                if pris[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    mini[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            p[j0] = p[chemin[j0]]
            j0 = chemin[j0]
    sortie = [0] * n
    for j in range(1, m + 1):
        if p[j]:
            sortie[p[j] - 1] = j - 1
    return sortie
