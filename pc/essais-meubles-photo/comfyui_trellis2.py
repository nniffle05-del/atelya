"""ESSAI SEULEMENT (accord écrit de NT, 16/11/2026) : fait fabriquer un meuble 3D par TRELLIS.2 dans ComfyUI, SUR LE PC, à partir
d'une image détourée (fond transparent). Rien ne sort du PC.

POURQUOI : voir ce que vaut TRELLIS.2 (Microsoft, MIT) sur un de nos meubles, et savoir s'il tient sur la carte de 8 Go.
ComfyUI (GPL-3) est un OUTIL À PART, lancé à la main dans D:\\Atelya-Essais\\comfyui ; il doit déjà tourner (127.0.0.1:8188).

L'enchaînement officiel (`3d_pixal3d_trellis2_image_to_model.json`) est traduit ici dans le format que le service de ComfyUI
attend, avec SEULEMENT la branche TRELLIS.2 : Pixal3D (fermé à l'UE) et MoGe (qui ne sert qu'à lui) sont retirés du graphe.

    python pc/essais-meubles-photo/comfyui_trellis2.py <image dans ComfyUI/input> <prefixe de sortie>
        [--finesse 1024] [--texture 2048] [--detourage alpha|birefnet] [--voir]
"""
import argparse
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

SERVICE = "http://127.0.0.1:8188"
MODELE = Path("D:/Atelya-Essais/comfyui/enchainement/modele-officiel.json")
WIDGETS = {"INT", "FLOAT", "STRING", "BOOLEAN", "COMBO", "COLOR", "LOAD_3D", "COMFY_DYNAMICCOMBO_V3"}
SANS_EFFET = {"Note", "MarkdownNote"}


def lire(url, corps=None, delai=60):
    donnees = None if corps is None else json.dumps(corps).encode("utf-8")
    req = urllib.request.Request(url, data=donnees, headers={"Content-Type": "application/json"} if donnees else {})
    with urllib.request.urlopen(req, timeout=delai) as r:
        return json.loads(r.read().decode("utf-8"))


def traduire(graphe, fiches):
    """Format de l'écran de ComfyUI (nœuds + liens) → format du service ({id: {class_type, inputs}})."""
    liens = {l[0]: (str(l[1]), l[2]) for l in graphe["links"]}
    sortie = {}
    for n in graphe["nodes"]:
        if n["type"] in SANS_EFFET:
            continue
        fiche = fiches[n["type"]]
        entrees = {}
        valeurs = list(n.get("widgets_values") or [])
        lies = {e["name"]: liens[e["link"]] for e in n.get("inputs", []) if e.get("link") is not None}
        k = 0
        for groupe in ("required", "optional"):
            for nom, spec in (fiche["input"].get(groupe) or {}).items():
                sorte = spec[0]
                options = spec[1] if len(spec) > 1 and isinstance(spec[1], dict) else {}
                est_widget = isinstance(sorte, list) or sorte in WIDGETS
                if est_widget and k < len(valeurs):
                    entrees[nom] = valeurs[k]
                    k += 1
                    if options.get("control_after_generate") or nom in ("seed", "noise_seed"):
                        k += 1  # la case « fixed / randomize » de l'écran n'est pas une entrée
                    if sorte == "COMFY_DYNAMICCOMBO_V3":  # un choix qui amène ses propres réglages : « nom.sous-réglage »
                        choisi = next(o for o in options["options"] if o["key"] == entrees[nom])
                        for groupe2 in ("required", "optional"):
                            for sous in (choisi["inputs"].get(groupe2) or {}):
                                entrees[f"{nom}.{sous}"] = valeurs[k]
                                k += 1
                if nom in lies:
                    entrees[nom] = [lies[nom][0], lies[nom][1]]
        sortie[str(n["id"])] = {"class_type": n["type"], "inputs": entrees, "_titre": n.get("title")}
    return sortie


def resoudre_aiguillages(api, choix):
    """Remplace chaque aiguillage (ComfySwitchNode) par la branche choisie : l'autre branche disparaît du graphe."""
    def valeur_bool(v):
        if isinstance(v, list):
            return valeur_bool(api[v[0]]["inputs"].get("value"))
        return bool(v)
    cible = {}
    for ident, n in api.items():
        if n["class_type"] == "ComfySwitchNode":
            vrai = choix.get(ident, valeur_bool(n["inputs"].get("switch")))
            cible[ident] = n["inputs"]["on_true" if vrai else "on_false"]
    def suivre(v):
        while isinstance(v, list) and v[0] in cible:
            v = cible[v[0]]
        return v
    for n in api.values():
        for nom, v in list(n["inputs"].items()):
            n["inputs"][nom] = suivre(v)
    for ident in cible:
        del api[ident]


def garder_les_ancetres(api, finales):
    vus, pile = set(), list(finales)
    while pile:
        i = pile.pop()
        if i in vus:
            continue
        vus.add(i)
        for v in api[i]["inputs"].values():
            if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and v[0] in api:
                pile.append(v[0])
    for i in list(api):
        if i not in vus:
            del api[i]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("image")
    p.add_argument("prefixe")
    p.add_argument("--finesse", type=int, default=1024)
    p.add_argument("--texture", type=int, default=2048)
    p.add_argument("--detourage", default="alpha", choices=["alpha", "birefnet"])
    p.add_argument("--voir", action="store_true", help="écrit le graphe traduit et s'arrête")
    a = p.parse_args()

    graphe = json.loads(MODELE.read_text(encoding="utf-8"))
    fiches = lire(f"{SERVICE}/object_info", delai=120)
    api = traduire(graphe, fiches)
    par_titre = {n["_titre"]: i for i, n in api.items() if n["_titre"]}
    # 316 = « Boolean (Switch to Trellis2) » ; 248 = « Switch: Remove background » (faux = le fond transparent de l'image sert de masque)
    api[par_titre["Boolean (Switch to Trellis2)"]]["inputs"]["value"] = True
    resoudre_aiguillages(api, {par_titre["Switch: Remove background"]: a.detourage == "birefnet"})
    for n in api.values():
        c, e = n["class_type"], n["inputs"]
        if c == "CLIPVisionLoader":
            e["clip_name"] = "dino_v3_vit_l.safetensors"
        elif c == "LoadImage":
            e["image"] = a.image
        elif c == "Trellis2UpsampleStage":
            nom = next(k for k, v in e.items() if not isinstance(v, list))
            e[nom] = a.finesse
        elif c == "Save3DAdvanced":
            e["filename_prefix"] = a.prefixe
        elif c == "PrimitiveInt" and n["_titre"] == "Texture Resolution":
            e["value"] = a.texture
    finales = [i for i, n in api.items() if n["class_type"] == "Save3DAdvanced"]
    garder_les_ancetres(api, finales)
    interdits = [n["class_type"] for n in api.values() if "Pixal" in n["class_type"] or "MoGe" in n["class_type"]
                 or "pixal" in json.dumps(n["inputs"]).lower()]
    if interdits:
        sys.exit(f"PLANTÉ : la branche Pixal3D est restée dans le graphe : {interdits}")
    for n in api.values():
        n.pop("_titre", None)
    Path("D:/Atelya-Essais/comfyui/enchainement/graphe-trellis2.json").write_text(json.dumps(api, indent=1), encoding="utf-8")
    print(len(api), "étapes :", sorted({n["class_type"] for n in api.values()}))
    if a.voir:
        return
    rep = lire(f"{SERVICE}/prompt", {"prompt": api, "client_id": uuid.uuid4().hex})
    if rep.get("node_errors"):
        sys.exit("PLANTÉ : graphe refusé : " + json.dumps(rep["node_errors"], ensure_ascii=False)[:1500])
    ident = rep["prompt_id"]
    print("lancé :", ident, flush=True)
    debut = time.time()
    while True:
        time.sleep(5)
        h = lire(f"{SERVICE}/history/{ident}")
        if ident in h:
            etat = h[ident].get("status", {})
            print(f"fini en {time.time() - debut:.0f} s :", etat.get("status_str"), flush=True)
            if etat.get("status_str") != "success":
                for m in etat.get("messages", []):
                    if m[0] == "execution_error":
                        d = m[1]
                        sys.exit(f"PLANTÉ à l'étape {d.get('node_type')} : {d.get('exception_type')} : {str(d.get('exception_message'))[:600]}")
                sys.exit("PLANTÉ : " + json.dumps(etat, ensure_ascii=False)[:800])
            for i, s in h[ident].get("outputs", {}).items():
                print("sortie", i, json.dumps(s, ensure_ascii=False)[:300])
            return
        if time.time() - debut > 3600:
            sys.exit("PLANTÉ : plus d'une heure sans réponse")


if __name__ == "__main__":
    main()
