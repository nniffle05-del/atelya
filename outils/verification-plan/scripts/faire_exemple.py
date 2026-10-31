"""Fabrique l'exemple de l'écran de vérification à partir du cas test n°0 (plan + logement de référence).
On y glisse volontairement des erreurs « comme Atelya » pour montrer les doutes en orange."""
import base64, json, re, sys
from pathlib import Path
src_json, src_png, dest = map(Path, sys.argv[1:4])
texte = re.sub(r"//.*", "", src_json.read_text(encoding="utf-8"))
ref = json.loads(texte)
lg = {k: ref[k] for k in ("schema", "projet_id", "unites", "hauteur_sous_plafond")}
for cle in ("murs", "ouvertures", "pieces"):
    lg[cle] = [dict(e, statut="estime", source="atelya", confiance=0.95) for e in ref[cle]]
for p in lg["pieces"]:
    p.pop("surface", None)
# Erreurs volontaires
ch = next(p for p in lg["pieces"] if p["id"] == "chambre")
ch.update(nom="Bureau", confiance=0.55)
fen = next(o for o in lg["ouvertures"] if o["id"] == "F_sejour_ouest")
fen["confiance"] = 0.6
lg["ouvertures"] = [o for o in lg["ouvertures"] if o["id"] != "P_sdb"]  # porte oubliée
lg["murs"].append({"id": "M_tache", "debut": [2.2, 3.6], "fin": [2.45, 3.6], "epaisseur": 0.1,
                   "statut": "estime", "source": "atelya", "confiance": 0.8})
verification = {
    "schema": "verification/0.1",
    "plan": "plan.png (cas test n°0)",
    "calage": {"px_par_m": 100, "origine_px": [210, 760]},
    "echelle": {"etat": "lue", "source": "cotes"},
    "logement": lg,
    "doutes": [
        {"element": None, "zone_px": [815, 630, 40, 100],
         "raison": "la cloison semble ouverte ici : porte oubliée ?",
         "propositions": [
             {"libelle": "Ajouter la porte", "action": {"type": "ajouter_ouverture", "mur": "C_sdb", "ouverture": "porte",
                                                       "position": 0.4, "largeur": 0.8}},
             {"libelle": "Il n'y a pas de porte", "action": {"type": "resoudre"}}]},
        {"element": "chambre", "raison": "Atelya hésite entre bureau (55 %) et chambre (40 %)",
         "propositions": [
             {"libelle": "Chambre", "action": {"type": "renommer", "id": "chambre", "nom": "Chambre"}},
             {"libelle": "Bureau", "action": {"type": "renommer", "id": "chambre", "nom": "Bureau"}}]},
    ],
}
image = "data:image/png;base64," + base64.b64encode(src_png.read_bytes()).decode()
dest.write_text("// Exemple fabriqué par scripts/faire_exemple.py : le cas test n°0 avec des erreurs volontaires.\n"
                "window.EXEMPLE_VERIFICATION = " + json.dumps({"verification": verification, "image": image}, ensure_ascii=False) + ";\n",
                encoding="utf-8")
(dest.parent / "exemple-cas-test-00.verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=1), encoding="utf-8")
