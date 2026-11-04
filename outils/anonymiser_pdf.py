"""Retire d'un PDF vectoriel les textes personnels (adresse, noms) avant tout travail dessus (RGPD, règle 17).

Les objets texte à retirer sont désignés par des mots-clés ; chaque texte de la page qui en contient un est effacé
du fichier (l'objet est supprimé, pas masqué). Les traits, les cotes et le reste des textes ne bougent pas.
Contrôle à la fin : les mots-clés ont disparu, et le nombre de traits et de textes restants est annoncé.

    ..\\atelya\\.venv\\Scripts\\python.exe outils\\anonymiser_pdf.py entree.pdf sortie.pdf "rue de Clichy" "AXEO" ...
"""
from __future__ import annotations

import sys
from pathlib import Path

import pdfplumber
import pypdfium2 as pdfium
from pypdfium2.raw import FPDF_PAGEOBJ_TEXT, FPDFText_LoadPage, FPDFTextObj_GetText, FPDFText_ClosePage
import ctypes


def texte_de_l_objet(page_pdfium, obj) -> str:
    """Le texte d'un objet texte, lu par pdfium (en UTF-16)."""
    page_texte = FPDFText_LoadPage(page_pdfium)
    try:
        n = FPDFTextObj_GetText(obj, page_texte, None, 0)
        tampon = (ctypes.c_ushort * max(n, 1))()
        FPDFTextObj_GetText(obj, page_texte, tampon, n)
        return bytes(tampon)[: max(0, (n - 1) * 2)].decode("utf-16-le", "replace")
    finally:
        FPDFText_ClosePage(page_texte)


def anonymiser(entree: Path, sortie: Path, mots_cles: list[str]) -> dict:
    cles = [m.casefold() for m in mots_cles]
    pdf = pdfium.PdfDocument(str(entree))
    retires = []
    for numero in range(len(pdf)):
        page = pdf[numero]
        a_retirer, autres = [], []
        for obj in page.get_objects(max_depth=4):
            if obj.type != FPDF_PAGEOBJ_TEXT:
                autres.append(obj)
                continue
            texte = texte_de_l_objet(page.raw, obj.raw)
            if any(c in texte.casefold() for c in cles):
                a_retirer.append((obj, texte))
            else:
                autres.append(obj)
        for obj, texte in a_retirer:
            page.remove_obj(obj)
            retires.append((numero + 1, texte.strip()))
            try:
                obj.close()  # l'objet détaché n'appartient plus à la page
            except Exception:  # noqa: BLE001 — selon la version de pypdfium2, déjà libéré
                pass
        if a_retirer:
            page.gen_content()
        for obj in autres:  # fermés avant la page, sinon pypdfium2 se plaint à la fin
            obj.close()
        page.close()
    pdf.save(str(sortie))
    pdf.close()
    # Contrôle indépendant, avec une autre bibliothèque.
    restes, traits, textes = [], 0, 0
    with pdfplumber.open(str(sortie)) as verif:
        for p in verif.pages:
            traits += len(p.lines) + len(p.rects) + len(p.curves)
            mots = p.extract_words(keep_blank_chars=True)
            textes += len(mots)
            restes += [w["text"] for w in mots if any(c in w["text"].casefold() for c in cles)]
    return {"retires": retires, "restes": restes, "traits": traits, "textes": textes}


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 2
    entree, sortie, mots = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:]
    r = anonymiser(entree, sortie, mots)
    for page, texte in r["retires"]:
        print(f"page {page} : retiré « {texte} »")
    print(f"reste {r['textes']} textes et {r['traits']} traits ; mots-clés encore présents : {r['restes'] or 'aucun'}")
    if r["restes"]:
        print("PLANTÉ : des textes personnels restent dans le fichier")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
