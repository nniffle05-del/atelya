"""Portes et fenêtres reconnues à leur ASPECT : Atelya apprend, avec l'œil DINOv2 déjà en service, à dire pour chaque
petit carré de la photo « fenêtre », « porte » ou « autre ». Exemples : les portes et fenêtres du plan dessinées sur les
photos par la caméra faite à la main. Apprend sur UN logement, noté sur L'AUTRE (jamais sur les photos apprises)."""
import json, sys
from pathlib import Path
import cv2, numpy as np, torch
from moteur.images import lire_image, ecrire_image
from moteur import camera_photo as cp, oeil_dinov2 as od
import etape_b as eb
import moge4 as m4

LARG = 1204  # 86 carrés de 14 px


def carres(oeil, im):
    h = int(round(im.shape[0] * LARG / im.shape[1] / 14)) * 14
    x = cv2.cvtColor(cv2.resize(im, (LARG, h), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)
    x = (x.astype(np.float32) / 255.0 - od.MOYENNE) / od.ECART
    x = torch.from_numpy(x).permute(2, 0, 1)[None].to(next(oeil.parameters()).device)
    with torch.no_grad(), torch.autocast(device_type=x.device.type, enabled=x.device.type == "cuda"):
        _, c = oeil(x)
    return c[0].float().cpu().numpy().reshape(h // 14, LARG // 14, -1)


def etiquettes(mod, cam, forme, larg_photo):
    """Par carré : 0 autre, 1 porte, 2 fenêtre ou baie, d'après le plan vu par la caméra faite à la main."""
    e = forme[1] * 14 / larg_photo
    m = np.zeros((forme[0] * 14, forme[1] * 14), np.uint8)
    for i in m4.faces_vues(mod, cam):
        a, b = mod["A"][i], mod["B"][i]
        pts = [cp.projeter([p[0], p[1], zz], cam) for p, zz in ((a, mod["bas"][i]), (b, mod["bas"][i]), (b, mod["haut"][i]), (a, mod["haut"][i]))]
        if min(p[2] for p in pts) < 0.8:  # trop près de l'appareil (ou derrière) : contour sans valeur
            continue
        cv2.fillPoly(m, [np.array([[p[0] * e, p[1] * e] for p in pts], np.int32)], int(mod["genre"][i]))
    parts = np.stack([(m == k).reshape(forme[0], 14, forme[1], 14).mean((1, 3)) for k in (1, 2)], -1)
    y = np.where(parts.max(-1) > 0.6, parts.argmax(-1) + 1, 0)
    sur = (parts.max(-1) > 0.6) | (parts.sum(-1) < 0.05)  # les carrés à cheval sur un bord ne servent pas à apprendre
    return y, sur


def apprendre(X, Y, pas=400):
    X, Y = torch.from_numpy(X).cuda(), torch.from_numpy(Y).long().cuda()
    mu, sd = X.mean(0), X.std(0) + 1e-6
    lin = torch.nn.Linear(X.shape[1], 3).cuda()
    opt = torch.optim.AdamW(lin.parameters(), 1e-3, weight_decay=0.05)
    poids = (len(Y) / (3 * torch.bincount(Y, minlength=3).float().clamp(min=1))).clamp(max=10)
    for _ in range(pas):
        opt.zero_grad()
        torch.nn.functional.cross_entropy(lin((X - mu) / sd), Y, weight=poids).backward()
        opt.step()
    return lambda Z: torch.softmax(lin((torch.from_numpy(Z).cuda() - mu) / sd), -1).detach().cpu().numpy()


if __name__ == "__main__":
    sortie = Path(sys.argv[1]); sortie.mkdir(parents=True, exist_ok=True)
    oeil = od.charger("vitb14")
    D = {}
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        mod = eb.modele(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")))
        D[app] = []
        for nom, c in d["cameras"].items():
            im = lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom))
            f = carres(oeil, im)
            y, sur = etiquettes(mod, [c["camera"][n] for n in cp.NOMS], f.shape[:2], c["largeur"])
            D[app].append((nom, im, f, y, sur))
    for appris, note in (("app-001", "app-002"), ("app-002", "app-001")):
        X = np.concatenate([f[s] for _, _, f, y, s in D[appris]]); Y = np.concatenate([y[s] for _, _, f, y, s in D[appris]])
        predire = apprendre(X, Y)
        vp = np.zeros(3); fp = np.zeros(3); fn = np.zeros(3)
        for nom, im, f, y, s in D[note]:
            p = predire(f.reshape(-1, f.shape[-1])).reshape(*f.shape[:2], 3)
            np.save(sortie / f"{note}-{nom}.npy", p.astype(np.float16))
            k = p.argmax(-1)
            for c in (1, 2):
                vp[c] += ((k == c) & (y == c) & s).sum(); fp[c] += ((k == c) & (y != c) & s).sum(); fn[c] += ((k != c) & (y == c) & s).sum()
            H, W = im.shape[:2]
            g = cv2.resize(p, (W, H), interpolation=cv2.INTER_LINEAR)
            vis = (im * 0.45).astype(np.float32)
            vis += g[..., 2:3] * np.array([0, 200, 0], np.float32) * (g[..., 2:3] > 0.5) + g[..., 1:2] * np.array([200, 0, 200], np.float32) * (g[..., 1:2] > 0.5)
            yy = cv2.resize(y.astype(np.uint8), (W, H), interpolation=cv2.INTER_NEAREST)
            vis = np.clip(vis, 0, 255).astype(np.uint8)
            for c, coul in ((1, (255, 255, 255)), (2, (0, 255, 255))):
                cn, _ = cv2.findContours((yy == c).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                cv2.drawContours(vis, cn, -1, coul, 2)
            ecrire_image(sortie / f"{note}-{nom}.jpg", np.hstack([im, vis]))
        for c, n in ((2, "fenêtres"), (1, "portes")):
            print(f"appris sur {appris}, noté sur {note} | {n} : trouvées {100 * vp[c] / max(vp[c] + fn[c], 1):.0f} %, justes {100 * vp[c] / max(vp[c] + fp[c], 1):.0f} % ({int(vp[c] + fn[c])} carrés)")
