r"""Piloter Chrome sans fenêtre comme le ferait une personne : ouvrir une page, cliquer avec une VRAIE souris, lire ce qui
est affiché, prendre des captures d'écran à tout moment. Sert aux essais de bout en bout de l'écran de vérification quand la
page doit rester ouverte longtemps (elle attend un calcul d'Atelya) : `--dump-dom` et `--screenshot` ne le permettent pas.

Rien à installer : Chrome se pilote par son « protocole de débogage » (des messages JSON envoyés sur une liaison WebSocket),
et la liaison est écrite ici avec la seule bibliothèque standard de Python.

    with Chrome() as c:
        c.ouvrir("http://127.0.0.1:8765/")
        c.attendre("window.Verification && !!window.Verification.etat.v")
        c.cliquer("#valider")
        c.capture(Path("capture.png"))
"""
from __future__ import annotations

import base64
import json
import os
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


class Liaison:
    """Une liaison WebSocket, côté client, juste ce qu'il faut pour parler à Chrome."""

    def __init__(self, adresse: str):
        hote, chemin = adresse.removeprefix("ws://").split("/", 1)
        nom, port = hote.split(":")
        self.s = socket.create_connection((nom, int(port)), timeout=60)
        cle = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall((f"GET /{chemin} HTTP/1.1\r\nHost: {hote}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
                        f"Sec-WebSocket-Key: {cle}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
        tete = b""
        while b"\r\n\r\n" not in tete:
            tete += self._lire(1)
        if b" 101 " not in tete.split(b"\r\n", 1)[0]:
            raise ConnectionError(f"Chrome refuse la liaison : {tete[:80]!r}")

    def _lire(self, n: int) -> bytes:
        d = b""
        while len(d) < n:
            m = self.s.recv(n - len(d))
            if not m:
                raise ConnectionError("liaison coupée par Chrome")
            d += m
        return d

    def envoyer(self, texte: str, code: int = 1) -> None:
        d, masque = texte.encode("utf-8"), os.urandom(4)
        n = len(d)
        tete = bytes([0x80 | code]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n) if n < 65536
                                       else bytes([0x80 | 127]) + struct.pack(">Q", n))
        self.s.sendall(tete + masque + bytes(b ^ masque[i % 4] for i, b in enumerate(d)))

    def recevoir(self) -> str:
        morceaux = []
        while True:
            a, b = self._lire(2)
            code, n = a & 0x0F, b & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._lire(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._lire(8))[0]
            d = self._lire(n)
            if code == 9:    # « tu es là ? » → « oui »
                self.envoyer(d.decode("utf-8", "replace"), 10)
            elif code == 8:
                raise ConnectionError("Chrome a fermé la liaison")
            elif code in (0, 1, 2):
                morceaux.append(d)
                if a & 0x80:
                    return b"".join(morceaux).decode("utf-8")

    def fermer(self) -> None:
        try:
            self.s.close()
        except OSError:
            pass


class Chrome:
    def __init__(self, largeur: int = 1500, hauteur: int = 950):
        if not CHROME.is_file():
            raise FileNotFoundError(f"Chrome introuvable : {CHROME}")
        with socket.socket() as s:  # un port libre pour le débogage
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.profil = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)  # profil neuf : rien de gardé d'un essai à l'autre
        self.proc = subprocess.Popen([str(CHROME), "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                                      f"--remote-debugging-port={self.port}", f"--user-data-dir={self.profil.name}",
                                      f"--window-size={largeur},{hauteur}", "about:blank"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.n = 0
        fin = time.time() + 30
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json", timeout=2) as f:
                    pages = [p for p in json.loads(f.read()) if p.get("type") == "page"]
                if pages:
                    break
            except OSError:
                pass
            if time.time() > fin:
                self.proc.kill()
                raise TimeoutError("Chrome ne s'est pas ouvert")
            time.sleep(0.3)
        self.liaison = Liaison(pages[0]["webSocketDebuggerUrl"])
        self.erreurs: list[str] = []  # les erreurs JavaScript de la page, vues au passage
        self.ordre("Page.enable")
        self.ordre("Runtime.enable")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.fermer()

    def ordre(self, methode: str, **parametres) -> dict:
        self.n += 1
        self.liaison.envoyer(json.dumps({"id": self.n, "method": methode, "params": parametres}))
        while True:
            m = json.loads(self.liaison.recevoir())
            if m.get("method") == "Runtime.exceptionThrown":
                d = m["params"]["exceptionDetails"]
                self.erreurs.append(d.get("exception", {}).get("description") or d.get("text", "?"))
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(f"{methode} : {m['error']}")
                return m.get("result", {})

    def ouvrir(self, adresse: str) -> None:
        self.ordre("Page.navigate", url=adresse)

    def recharger(self) -> None:
        self.ordre("Page.reload")

    def lire(self, js: str):
        """La valeur d'une expression JavaScript dans la page."""
        r = self.ordre("Runtime.evaluate", expression=js, returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in r:
            raise RuntimeError("JavaScript : " + str(r["exceptionDetails"].get("exception", {}).get("description") or r["exceptionDetails"]))
        return r["result"].get("value")

    def attendre(self, js: str, delai: float = 30, pas: float = 0.25, quoi: str = ""):
        """Attend que l'expression soit vraie ; rend sa valeur."""
        fin = time.time() + delai
        while True:
            try:
                v = self.lire(js)
            except RuntimeError:
                v = None  # la page est en train de changer
            if v:
                return v
            if time.time() > fin:
                raise TimeoutError(f"toujours pas après {delai:.0f} s : {quoi or js}")
            time.sleep(pas)

    def souris(self, sorte: str, x: float, y: float) -> None:
        """sorte : mousePressed, mouseMoved ou mouseReleased, aux coordonnées de la fenêtre."""
        self.ordre("Input.dispatchMouseEvent", type=sorte, x=x, y=y, button="left", buttons=0 if sorte == "mouseReleased" else 1,
                   clickCount=0 if sorte == "mouseMoved" else 1)

    def cliquer_en(self, x: float, y: float) -> None:
        self.souris("mouseMoved", x, y); self.souris("mousePressed", x, y); self.souris("mouseReleased", x, y)

    def cliquer(self, selecteur: str) -> None:
        """Un vrai clic au milieu d'un élément visible."""
        r = self.lire(f"(() => {{ const e = document.querySelector({json.dumps(selecteur)}); if (!e) return null; e.scrollIntoView({{block: 'nearest'}});"
                      "const r = e.getBoundingClientRect(); return (r.width && r.height && !e.disabled) ? [r.left + r.width / 2, r.top + r.height / 2] : null; })()")
        if not r:
            raise RuntimeError(f"rien à cliquer : {selecteur} (absent, caché ou grisé)")
        self.cliquer_en(*r)

    def tirer(self, x0: float, y0: float, x1: float, y1: float, pas: int = 6) -> None:
        """Appuyer en (x0, y0), glisser, relâcher en (x1, y1)."""
        self.souris("mouseMoved", x0, y0); self.souris("mousePressed", x0, y0)
        for k in range(1, pas + 1):
            self.souris("mouseMoved", x0 + (x1 - x0) * k / pas, y0 + (y1 - y0) * k / pas)
        self.souris("mouseReleased", x1, y1)

    def capture(self, chemin: Path) -> Path:
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_bytes(base64.b64decode(self.ordre("Page.captureScreenshot", format="png")["data"]))
        return chemin

    def fermer(self) -> None:
        try:
            self.ordre("Browser.close")
        except Exception:
            pass
        self.liaison.fermer()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.profil.cleanup()
