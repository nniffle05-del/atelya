"""La couche « fenêtre ou non » mise en service (moteur/modeles/fenetres-vitb14-v1.npz, lue par moteur/caler_photos.Fenetres) :
même apprentissage que moge6 (œil DINOv2 ViT-B/14 figé + une couche ; exemples = portes et fenêtres du plan projetées sur
les photos calées à la main), mais sur les DEUX logements à la fois. (Dans moge6, appris sur l'un et noté sur l'autre :
fenêtres trouvées ~70 %.) Classes : 0 autre, 1 porte, 2 fenêtre ou baie."""
import json, sys
from pathlib import Path
import numpy as np, torch
from moteur.images import lire_image
from moteur import camera_photo as cp, oeil_dinov2 as od
import etape_b as eb
import moge6 as m6

if __name__ == "__main__":
    sortie = Path(sys.argv[2]); torch.manual_seed(0)  # argv[1] : dossier de travail (moge1, chargé en passant, y crée un dossier)
    oeil = od.charger("vitb14"); X, Y = [], []
    for app in ("app-002", "app-001"):
        d = json.loads(Path(f"verites/{app}/cameras-photos.json").read_text(encoding="utf-8"))
        mod = eb.modele(json.loads(Path(f"verites/{app}/logement.json").read_text(encoding="utf-8")))
        for nom, c in d["cameras"].items():
            f = m6.carres(oeil, lire_image(Path(d["photos"]) / d.get("fichier", "{nom}.png").format(nom=nom)))
            y, sur = m6.etiquettes(mod, [c["camera"][n] for n in cp.NOMS], f.shape[:2], c["largeur"])
            X.append(f[sur]); Y.append(y[sur])
    X, Y = torch.from_numpy(np.concatenate(X)).cuda(), torch.from_numpy(np.concatenate(Y)).long().cuda()
    mu, sd = X.mean(0), X.std(0) + 1e-6
    lin = torch.nn.Linear(X.shape[1], 3).cuda()
    opt = torch.optim.AdamW(lin.parameters(), 1e-3, weight_decay=0.05)
    poids = (len(Y) / (3 * torch.bincount(Y, minlength=3).float().clamp(min=1))).clamp(max=10)
    for _ in range(400):
        opt.zero_grad()
        torch.nn.functional.cross_entropy(lin((X - mu) / sd), Y, weight=poids).backward()
        opt.step()
    k = lin((X - mu) / sd).argmax(1)
    print(f"{len(Y)} carrés | fenêtres : {int((Y == 2).sum())}, retrouvées sur les exemples appris {100 * float(((k == 2) & (Y == 2)).sum() / (Y == 2).sum()):.0f} %")
    np.savez_compressed(sortie, W=lin.weight.detach().cpu().numpy().astype(np.float32), b=lin.bias.detach().cpu().numpy().astype(np.float32),
                        mu=mu.cpu().numpy().astype(np.float32), sd=sd.cpu().numpy().astype(np.float32))
    print("écrit :", sortie)
