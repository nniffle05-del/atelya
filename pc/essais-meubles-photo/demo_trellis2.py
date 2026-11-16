"""ESSAI SEULEMENT (accord écrit de NT du 16/11/2026) : envoie UNE image détourée à la démonstration publique officielle de TRELLIS.2
(Microsoft, hébergée par Hugging Face, sans compte) et rapporte l'objet 3D (GLB).

POURQUOI : TRELLIS.2 demande 24 Go de mémoire de carte, le PC en a 8. La démonstration sert à VOIR la qualité sur un de nos meubles.
RIEN de ce qui en sort ne va dans le produit : son export passe par nvdiffrast (non commercial). Jamais de photo d'un client ici :
l'image part sur des serveurs aux États-Unis (« Users are advised against uploading data containing sensitive or private information »).

    python pc/essais-meubles-photo/demo_trellis2.py <image détourée .png> <sortie .glb> [--resolution 1024] [--graine 0]

Bibliothèque standard seulement (rien à installer). L'image est envoyée sous un nom neutre.
"""
import argparse
import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

BASE = "https://microsoft-trellis-2.hf.space/gradio_api"


def _json(url, corps=None, delai=120):
    donnees = None if corps is None else json.dumps(corps).encode("utf-8")
    req = urllib.request.Request(url, data=donnees, headers={"Content-Type": "application/json"} if donnees else {})
    with urllib.request.urlopen(req, timeout=delai) as r:
        return json.loads(r.read().decode("utf-8"))


def envoyer_fichier(chemin):
    limite = uuid.uuid4().hex
    contenu = Path(chemin).read_bytes()
    corps = (f"--{limite}\r\nContent-Disposition: form-data; name=\"files\"; filename=\"objet.png\"\r\n"
             f"Content-Type: image/png\r\n\r\n").encode() + contenu + f"\r\n--{limite}--\r\n".encode()
    req = urllib.request.Request(f"{BASE}/upload", data=corps, headers={"Content-Type": f"multipart/form-data; boundary={limite}"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))[0]


def appeler(dependances, nom, donnees, session, delai=900):
    """Lance une étape de la démonstration et attend sa réponse (file d'attente + flux d'événements)."""
    indice = dependances[nom]
    _json(f"{BASE}/queue/join", {"data": donnees, "fn_index": indice, "session_hash": session, "event_data": None, "trigger_id": None})
    debut = time.time()
    with urllib.request.urlopen(f"{BASE}/queue/data?session_hash={session}", timeout=delai) as flux:
        for ligne in flux:
            ligne = ligne.decode("utf-8", "replace").strip()
            if not ligne.startswith("data:"):
                continue
            ev = json.loads(ligne[5:])
            msg = ev.get("msg")
            if msg == "estimation":
                print(f"   [{nom}] file d'attente : rang {ev.get('rank')}, attente estimée {ev.get('rank_eta')}", flush=True)
            elif msg == "process_starts":
                print(f"   [{nom}] calcul lancé", flush=True)
            elif msg == "process_completed":
                if not ev.get("success", False):
                    raise RuntimeError(f"PLANTÉ à l'étape {nom} : {json.dumps(ev.get('output'), ensure_ascii=False)[:600]}")
                print(f"   [{nom}] fini en {time.time() - debut:.0f} s", flush=True)
                return ev["output"]["data"]
            elif msg in ("close_stream", "unexpected_error"):
                raise RuntimeError(f"PLANTÉ à l'étape {nom} : flux fermé ({json.dumps(ev, ensure_ascii=False)[:400]})")
    raise RuntimeError(f"PLANTÉ à l'étape {nom} : pas de réponse")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("image")
    p.add_argument("sortie")
    p.add_argument("--resolution", default="1024", choices=["512", "1024", "1536"])
    p.add_argument("--graine", type=int, default=0)
    a = p.parse_args()
    if not Path(a.image).is_file():
        sys.exit(f"PLANTÉ : image introuvable {a.image}")
    config = _json(BASE.replace("/gradio_api", "") + "/config")
    dependances = {d["api_name"]: d["id"] for d in config["dependencies"] if d.get("api_name")}
    session = uuid.uuid4().hex[:12]
    appeler(dependances, "start_session", [], session)
    chemin = envoyer_fichier(a.image)
    image = {"path": chemin, "meta": {"_type": "gradio.FileData"}, "orig_name": "objet.png", "mime_type": "image/png"}
    image = appeler(dependances, "preprocess_image", [image], session)[0]
    t0 = time.time()
    appeler(dependances, "image_to_3d", [image, a.graine, a.resolution, 7.5, 0.7, 12, 5.0, 7.5, 0.5, 12, 3.0, 1.0, 0.0, 12, 3.0], session)
    t1 = time.time()
    sortie = appeler(dependances, "extract_glb", [None, 300000, 2048], session)  # None = l'état gardé par le serveur
    t2 = time.time()
    fichier = next(s for s in sortie if isinstance(s, dict) and (s.get("url") or s.get("path")))
    url = fichier.get("url") or f"{BASE}/file={fichier['path']}"
    with urllib.request.urlopen(url, timeout=300) as r:
        Path(a.sortie).write_bytes(r.read())
    bilan = {"image": Path(a.image).name, "resolution": a.resolution, "graine": a.graine, "secondes_fabrication": round(t1 - t0, 1),
             "secondes_export": round(t2 - t1, 1), "octets": Path(a.sortie).stat().st_size, "source": "démonstration publique TRELLIS.2",
             "usage": "essai seulement, jamais dans le produit"}
    Path(a.sortie).with_suffix(".json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(bilan, ensure_ascii=False))


if __name__ == "__main__":
    main()
