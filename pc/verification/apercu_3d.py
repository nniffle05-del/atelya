"""Fabrique une page 3D autonome à partir d'un logement.json : un seul fichier HTML, à ouvrir d'un double-clic ou à envoyer.
Mêmes volumes que pour Blender (moteur/geometrie.py), sans matières ni lumière réaliste : c'est un aperçu, pas un rendu.
Aucune bibliothèque : le dessin 3D est écrit à la main, avec WebGL, qui est déjà dans les navigateurs.
    ..\\atelya\\.venv\\Scripts\\python.exe pc\\verification\\apercu_3d.py logement.json sortie.html
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from moteur.geometrie import calculer_briques  # noqa: E402
from moteur.logement import charger_logement  # noqa: E402

COULEURS_SOL = {"Séjour": (.80, .70, .55), "Chambre": (.74, .62, .47), "Cuisine": (.78, .78, .74), "Salle d'eau": (.72, .82, .85),
                "Salle de bains": (.72, .82, .85), "WC": (.72, .82, .85), "Entrée": (.76, .74, .68), "Dégagement": (.76, .74, .68)}
MUR = (.94, .93, .90)
ALLEGE = (.90, .89, .86)


def trianguler(contour):
    """Découpe un polygone (sens direct) en triangles, par oreilles."""
    def aire(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def dedans(p, a, b, c):
        return aire(a, b, p) > 1e-9 and aire(b, c, p) > 1e-9 and aire(c, a, p) > 1e-9

    reste = list(range(len(contour)))
    triangles = []
    garde = 0
    while len(reste) > 3 and garde < 10000:
        garde += 1
        for k in range(len(reste)):
            i, j, m = reste[k - 1], reste[k], reste[(k + 1) % len(reste)]
            a, b, c = contour[i], contour[j], contour[m]
            if aire(a, b, c) <= 1e-9:
                continue
            if any(dedans(contour[q], a, b, c) for q in reste if q not in (i, j, m)):
                continue
            triangles.append((i, j, m))
            reste.pop(k)
            break
        else:
            reste.pop(0)  # contour abîmé : on avance quand même, un aperçu ne doit pas bloquer
    if len(reste) == 3:
        triangles.append(tuple(reste))
    return triangles


def prisme(brique, couleur, sortie):
    c = brique.contour
    b, h = brique.z_bas, brique.z_haut
    aire = sum(c[i][0] * c[(i + 1) % len(c)][1] - c[(i + 1) % len(c)][0] * c[i][1] for i in range(len(c)))
    if aire < 0:
        c = c[::-1]

    def sommet(p, z, n):
        # La 3D de la page a l'axe Y vers le haut : le plan (x, y) devient (x, -y).
        sortie.extend([round(p[0], 3), round(z, 3), round(-p[1], 3), round(n[0], 3), round(n[1], 3), round(n[2], 3), *couleur])

    for i, j, m in trianguler(c):
        for q in (i, j, m):
            sommet(c[q], h, (0, 1, 0))
        if h > b:
            for q in (m, j, i):
                sommet(c[q], b, (0, -1, 0))
    if h > b:
        for i in range(len(c)):
            p, q = c[i], c[(i + 1) % len(c)]
            dx, dy = q[0] - p[0], q[1] - p[1]
            l = (dx * dx + dy * dy) ** .5 or 1
            n = (dy / l, 0, dy and dx / l or dx / l)
            for r, z in ((p, b), (q, b), (q, h), (p, b), (q, h), (p, h)):
                sommet(r, z, n)


def main() -> int:
    logement = charger_logement(Path(sys.argv[1]))
    briques = calculer_briques(logement)
    noms = {p.id: p.nom for p in logement.pieces}
    v = []
    for b in briques:
        if b.categorie == "plafond":
            continue  # sans plafond, on voit dans les pièces (maison de poupée)
        if b.categorie == "sol":
            nom = noms.get(b.element, "")
            couleur = next((c for k, c in COULEURS_SOL.items() if nom.startswith(k)), (.78, .76, .72))
        elif b.categorie == "menuiserie":
            couleur = (.62, .55, .46)
        else:
            couleur = ALLEGE if b.z_bas > 0 or b.z_haut < logement.hauteur_sous_plafond else MUR
        prisme(b, couleur, v)
    # Les vitres : une plaque bleutée dans chaque fenêtre et porte-fenêtre.
    murs = {m.id: m for m in logement.murs}
    vitres = []
    for o in logement.ouvertures:
        if o.type == "porte":
            continue
        m = murs[o.mur]
        lm = ((m.fin[0] - m.debut[0]) ** 2 + (m.fin[1] - m.debut[1]) ** 2) ** .5
        d = ((m.fin[0] - m.debut[0]) / lm, (m.fin[1] - m.debut[1]) / lm)
        a = (m.debut[0] + d[0] * o.position, m.debut[1] + d[1] * o.position)
        c = (a[0] + d[0] * o.largeur, a[1] + d[1] * o.largeur)
        vitres.append([a[0], -a[1], c[0], -c[1], o.allege, o.allege + o.hauteur])
    etiquettes = []
    for p in logement.pieces:
        xs, ys = zip(*p.contour)
        a = 0.0
        cx = cy = 0.0
        for i in range(len(p.contour)):
            x1, y1 = p.contour[i]
            x2, y2 = p.contour[(i + 1) % len(p.contour)]
            k = x1 * y2 - x2 * y1
            a += k
            cx += (x1 + x2) * k
            cy += (y1 + y2) * k
        etiquettes.append({"nom": p.nom, "surface": round(abs(a) / 2, 1), "x": round(cx / (3 * a), 2), "y": round(-cy / (3 * a), 2)})
    donnees = {"sommets": v, "vitres": vitres, "etiquettes": etiquettes, "hauteur": logement.hauteur_sous_plafond}
    gabarit = Path(__file__).with_name("apercu_3d.gabarit.html").read_text(encoding="utf-8")
    Path(sys.argv[2]).parent.mkdir(parents=True, exist_ok=True)
    Path(sys.argv[2]).write_text(gabarit.replace("/*DONNEES*/null", json.dumps(donnees, ensure_ascii=False, separators=(",", ":"))), encoding="utf-8")
    print(f"{len(briques)} briques, {len(v) // 54} triangles (environ), {len(vitres)} vitres → {sys.argv[2]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
