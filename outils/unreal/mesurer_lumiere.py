"""Mesurer la LUMIÈRE d'un film : fenêtres brûlées, zones trop sombres, sauts d'exposition (cinématique, étape 4, 12/11/2026).

    python outils/unreal/mesurer_lumiere.py <dossier du film> --masques <dossier d'essai> --balade <balade.json>
        --logement <logement.json> [--eclairage jour_soleil] [--sortie lumiere.json] [--graphe lumiere.png] [--planche pires.jpg]

<dossier du film> : image-0001.png… (Movie Render Queue) ; <dossier d'essai> : les masques « FinalImageM_MasqueBlancs.NNNN.png »
du photographe (rouge = murs et plafonds, vert = dehors vu par une fenêtre ; moteur/unreal/preparer_cinematique.py). Chaque
image du film qui a un masque est mesurée à la taille du masque (moteur/cinema/lumiere.mesurer_image), rangée dans la pièce où
se trouve la caméra (balade.json + logement.json), puis le bilan du film (lumiere.resumer) est écrit en JSON.
"""
import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
from moteur import photographe  # noqa: E402
from moteur.cinema import lumiere  # noqa: E402
from moteur.sol_a_plat import piece_de  # noqa: E402

PASSE_MASQUE = "M_MasqueBlancs"


def _lire(chemin: Path) -> np.ndarray:
    im = cv2.imdecode(np.fromfile(str(chemin), dtype=np.uint8), cv2.IMREAD_COLOR)
    if im is None:
        sys.exit(f"PLANTÉ : image illisible {chemin}")
    return im


def masques(chemin: Path) -> tuple[np.ndarray, np.ndarray]:
    """(murs, dehors) d'un masque d'essai, bords retirés (pixels mêlés à leurs voisins)."""
    bvr = _lire(chemin)
    noyau = np.ones((3, 3), np.uint8)
    murs = cv2.erode((bvr[..., 2] > 127).astype(np.uint8), noyau) > 0
    dehors = cv2.erode((bvr[..., 1] > 127).astype(np.uint8), noyau) > 0
    return murs, dehors


def paires(film: Path, essai: Path) -> list[tuple[int, Path, Path]]:
    """(numéro d'image 0.., image du film, masque) pour chaque masque qui a son image dans le film."""
    sortie = []
    for m in sorted(essai.glob(f"*{PASSE_MASQUE}.*.png")):
        n = int(m.name.rsplit(".", 2)[-2])
        image = film / f"image-{n:04d}.png"
        if image.is_file():
            sortie.append((n - 1, image, m))
    return sortie


def graphe(mesures: list[dict], ips: int, chemin: Path, titre: str) -> None:
    """Trois courbes au fil du film : clarté des murs (écart à la visée, en crans), part du dehors laiteux, part sombre."""
    larg, haut, marge = 1600, 900, 60
    im = np.full((haut, larg, 3), 255, np.uint8)
    duree = max(m["image"] for m in mesures) / ips or 1
    bandes = [("Murs : clarte - visee (crans, -1.5..+1.5)", "murs_ecart_crans", -1.5, 1.5, (40, 90, 200), True),
              ("Fenetres : part du dehors presque blanc (0..100 %)", "dehors_blanc", 0.0, 1.0, (40, 160, 40), False),
              ("Interieur : part sombre < 50/255 (0..20 %)", "sombre", 0.0, 0.2, (60, 60, 60), False)]
    h_bande = (haut - 2 * marge) // len(bandes)
    for k, (nom, cle, lo, hi, couleur, inverse) in enumerate(bandes):
        y0 = marge + k * h_bande
        cv2.rectangle(im, (marge, y0), (larg - marge, y0 + h_bande - 20), (200, 200, 200), 1)
        cv2.putText(im, nom, (marge + 5, y0 + 18), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
        if lo < 0 < hi:
            yz = int(y0 + (h_bande - 20) * (hi - 0) / (hi - lo))
            cv2.line(im, (marge, yz), (larg - marge, yz), (180, 180, 180), 1)
        points = []
        for m in mesures:
            v = m.get(cle)
            if v is None or (cle == "dehors_blanc" and m.get("dehors_part", 0) < 0.01):
                if len(points) > 1:
                    cv2.polylines(im, [np.array(points, np.int32)], False, couleur, 2, cv2.LINE_AA)
                points = []
                continue
            v = -v if inverse else v  # murs : vers le haut = plus clairs
            x = int(marge + (larg - 2 * marge) * (m["image"] / ips) / duree)
            y = int(y0 + (h_bande - 20) * (hi - min(max(v, lo), hi)) / (hi - lo))
            points.append((x, y))
        if len(points) > 1:
            cv2.polylines(im, [np.array(points, np.int32)], False, couleur, 2, cv2.LINE_AA)
    for s in range(0, int(duree) + 1, 2):
        x = int(marge + (larg - 2 * marge) * s / duree)
        cv2.putText(im, f"{s}s", (x - 10, haut - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 1, cv2.LINE_AA)
    cv2.putText(im, titre, (marge, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2, cv2.LINE_AA)
    cv2.imencode(".png", im)[1].tofile(str(chemin))


def planche(mesures: list[dict], film: Path, ips: int, chemin: Path, n: int = 4) -> None:
    """Les images où le dehors est le plus « laiteux » (vue du dehors ≥ 3 % de l'image) et les plus sombres, contour vert = dehors."""
    fen = sorted((m for m in mesures if m.get("dehors_part", 0) >= 0.03), key=lambda m: -m.get("dehors_blanc", 0))[:n]
    som = sorted(mesures, key=lambda m: -m.get("sombre", 0))[:n]
    vignettes = []
    for m, quoi in [(x, "fenetre") for x in fen] + [(x, "sombre") for x in som]:
        im = cv2.resize(_lire(film / f"image-{m['image'] + 1:04d}.png"), (640, 360), interpolation=cv2.INTER_AREA)
        if quoi == "fenetre" and m.get("_masque"):
            _, dehors = masques(Path(m["_masque"]))
            contours, _ = cv2.findContours(cv2.resize(dehors.astype(np.uint8), (640, 360),
                                                      interpolation=cv2.INTER_NEAREST), cv2.RETR_EXTERNAL,
                                           cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(im, contours, -1, (0, 200, 0), 2)
        texte = (f"{m['image'] / ips:.1f}s {m.get('piece')} dehors blanc {100 * m.get('dehors_blanc', 0):.0f}%" if quoi == "fenetre"
                 else f"{m['image'] / ips:.1f}s {m.get('piece')} sombre {100 * m.get('sombre', 0):.0f}%")
        cv2.rectangle(im, (0, 0), (640, 26), (255, 255, 255), -1)
        cv2.putText(im, texte, (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 200), 1, cv2.LINE_AA)
        vignettes.append(im)
    while len(vignettes) % 4:
        vignettes.append(np.full((360, 640, 3), 255, np.uint8))
    lignes = [np.hstack(vignettes[i:i + 4]) for i in range(0, len(vignettes), 4)]
    cv2.imencode(".jpg", np.vstack(lignes), [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tofile(str(chemin))


def mesurer_film(film: Path, essai: Path, balade: dict, logement: dict, clarte: float) -> list[dict]:
    points = balade["trajet"]["points"]
    n_images = int(balade["trajet"].get("images", len(points)))
    pieces = logement.get("pieces", [])
    mesures = []
    for numero, image, masque in paires(film, essai):
        murs, dehors = masques(masque)
        h, w = murs.shape
        rvb = cv2.resize(_lire(image), (w, h), interpolation=cv2.INTER_AREA)[..., ::-1].astype(float) / 255.0
        k = round(numero * (len(points) - 1) / max(n_images - 1, 1))
        x, y = points[min(k, len(points) - 1)][:2]
        piece = piece_de((x, y), pieces)
        m = {"image": numero, "piece": piece["id"] if piece else None, "_masque": str(masque),
             **lumiere.mesurer_image(rvb, murs, dehors, clarte)}
        mesures.append(m)
    if not mesures:
        sys.exit(f"PLANTÉ : aucune paire image du film + masque ({film}, {essai})")
    return mesures


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("film")
    p.add_argument("--masques", required=True)
    p.add_argument("--balade", required=True)
    p.add_argument("--logement", required=True)
    p.add_argument("--eclairage", default="jour_soleil")
    p.add_argument("--sortie")
    p.add_argument("--graphe")
    p.add_argument("--planche")
    p.add_argument("--titre", default="")
    p.add_argument("--avant", help="lumiere.json d'un film précédent du même vol : comparaison chiffre par chiffre")
    a = p.parse_args()
    film = Path(a.film)
    balade = json.loads(Path(a.balade).read_text(encoding="utf-8"))
    logement = json.loads(Path(a.logement).read_text(encoding="utf-8"))
    ips = int(balade["trajet"].get("ips", 24))
    clarte = photographe.CLARTE_UNREAL.get(a.eclairage, photographe.CLARTE_MURS)
    mesures = mesurer_film(film, Path(a.masques), balade, logement, clarte)
    bilan = lumiere.resumer(mesures, ips)
    sortie = Path(a.sortie) if a.sortie else film / "lumiere.json"
    sortie.write_text(json.dumps({"film": str(film), "eclairage": a.eclairage, "clarte_visee": clarte, "bilan": bilan,
                                  "images": [{k: v for k, v in m.items() if not k.startswith("_")} for m in mesures]},
                                 indent=1, ensure_ascii=False), encoding="utf-8")
    if a.graphe:
        graphe(mesures, ips, Path(a.graphe), a.titre or film.name)
    if a.planche:
        planche(mesures, film, ips, Path(a.planche))
    print(json.dumps(bilan, indent=1, ensure_ascii=False))
    if a.avant:
        avant = json.loads(Path(a.avant).read_text(encoding="utf-8"))["bilan"]
        print("\nAVANT / APRÈS (mêmes images)")
        for l in lumiere.comparer(avant, bilan):
            print(f"  {l['chiffre']:<52} {str(l['avant']):>8} -> {str(l['apres']):<8} {l['verdict']}")


if __name__ == "__main__":
    main()
