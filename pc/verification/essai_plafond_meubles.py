r"""Essai : plafonner le nombre de meubles d'une sorte dans une pièce au nombre vu ENSEMBLE sur une même photo."""
import json, sys, math
from pathlib import Path
import cv2
RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
PC = RACINE.parent / "atelya"
from moteur.camera_photo import camera_depuis_dict
from moteur.images import lire_image
from moteur.owlv2 import charger, objets
from moteur.pas_du_sol import NOMS, REQUETES
from moteur import reperer_meubles as rm
from moteur.ranger_meubles import chevauchements, ranger
from moteur.sol_a_plat import piece_de, piece_de_l_appareil

CAS = {"app-001": (RACINE / "verites/app-001/cameras-photos.json", PC / "lectures-claude/app-001/logement.json", RACINE / "verites/app-001/meubles.json"),
       "app-002": (RACINE / "verites/app-002/cameras-photos.json", RACINE / "verites/app-002/logement.json", RACINE / "verites/app-002/meubles.json"),
       "app-002 seul": (PC / "b2/app-002/ecran-enchaine/lecture/questions-photos/cameras-photos-seul.json", RACINE / "verites/app-002/logement.json", RACINE / "verites/app-002/meubles.json"),
       "app-004": (PC / "lectures-claude/app-004/questions-photos/cameras-photos-seul.json", PC / "b2/app-004/chaine/logement-sols.json", None)}
lire = lambda p: json.loads(Path(p).read_text(encoding="utf-8"))
owl = charger(); requetes = owl.textes(NOMS)
groupe_de = {n: g for n, g in REQUETES.items() if g in rm.TYPE_DE_GROUPE}
for nom, (releve, logement, verite) in CAS.items():
    if not Path(releve).is_file(): print(nom, "pas de fiche", releve); continue
    releve, logement = lire(releve), lire(logement); logement["meubles"] = []
    dossier = RACINE / releve["photos"]; modele = releve.get("fichier", "{nom}.png")
    vus, par_photo = [], []
    for n, d in releve["cameras"].items():
        rgb = cv2.cvtColor(lire_image(dossier / modele.format(nom=n)), cv2.COLOR_BGR2RGB)
        cam = camera_depuis_dict(d["camera"])
        piece, _ = piece_de_l_appareil(cam, logement["pieces"])
        v = rm.meubles_owl_d_une_photo(objets(owl.detecter(rgb, requetes), NOMS, seuil=0.1), groupe_de, cam, rgb.shape[1], rgb.shape[0], piece)
        vus += v; par_photo.append(rm.fusionner(v))
    trouves = [rm.coller_au_mur(m, piece_de(m["position"], logement["pieces"])) for m in rm.fusionner(vus)]
    # (1) grosses pièces uniques : plafond par (pièce, sorte) = le plus grand nombre vu sur UNE photo
    plafond = {}
    for liste in par_photo:
        compte = {}
        for m in liste:
            p = piece_de(m["position"], logement["pieces"])
            if p: compte[(p["id"], m["groupe"])] = compte.get((p["id"], m["groupe"]), 0) + 1
        for k, c in compte.items(): plafond[k] = max(plafond.get(k, 0), c)
    UNIQUES = ("table", "canape", "lit", "fauteuil")
    EN_GRAPPE = ("chaise", "rangement") if "--rangement" in sys.argv else ("chaise",)
    gardes, pris = [], {}
    tri = sorted(trouves, key=lambda m: -m["vues"] * m["confiance"])
    for m in tri:
        p = piece_de(m["position"], logement["pieces"])
        if p is None: continue
        k = (p["id"], m["groupe"])
        if m["groupe"] in UNIQUES:
            if pris.get(k, 0) < plafond.get(k, 0): pris[k] = pris.get(k, 0) + 1; gardes.append(m)
        elif m["groupe"] not in EN_GRAPPE:
            gardes.append(m)
    # (2) chaises : par GRAPPE (chaises à moins de LIEN l'une de l'autre), pas plus que le nombre vu ensemble sur une photo
    LIEN, PRES = float(next((a.split("=")[1] for a in sys.argv if a.startswith("--lien=")), 1.0)), 0.8
    for g in EN_GRAPPE:
        ch = [m for m in tri if m["groupe"] == g and piece_de(m["position"], logement["pieces"])]
        grappes = []
        for m in ch:
            liees = [gr for gr in grappes if any(math.dist(m["position"], x["position"]) < LIEN for x in gr)]
            nouvelle = [m] + [x for gr in liees for x in gr]
            grappes = [gr for gr in grappes if gr not in liees] + [nouvelle]
        for gr in grappes:
            maxi = max((sum(1 for v in liste if v["groupe"] == g and any(math.dist(v["position"], x["position"]) < PRES for x in gr)) for liste in par_photo), default=0)
            gardes += sorted(gr, key=lambda m: -m["vues"] * m["confiance"])[:max(maxi, 1)]
    cams = [camera_depuis_dict(d["camera"]) for d in releve["cameras"].values()]
    for titre, liste in (("sans plafond", trouves), ("avec plafond", gardes)):
        ms, _ = ranger(rm.vers_meubles_du_logement(liste, logement), logement)
        ligne = f"{nom:13s} {titre} + rangement : {len(ms):2d} meubles"
        if verite:
            r = rm.noter_meubles([{"groupe": rm.groupe(m["categorie"]), "position": m["position"]} for m in ms], lire(verite)["meubles"], cameras=cams, logement=logement)
            ligne += f" ; retrouvés {r['retrouves']}, en trop {r['en_trop']} ; {r['par_groupe']}"
        else:
            c = {}
            for m in ms: c[m["categorie"]] = c.get(m["categorie"], 0) + 1
            ligne += f" ; {c}"
        print(ligne, flush=True)
