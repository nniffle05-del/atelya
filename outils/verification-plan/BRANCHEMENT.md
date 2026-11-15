# Brancher l'écran de vérification dans le site interne

*Fiche pour l'associé (plateforme interne). Rien n'est à changer côté moteur : l'écran est déjà prêt.*

## En une phrase

Quand Atelya a lu un plan et qu'il reste des **vérifications humaines** à faire, l'onglet du site
affiche l'écran de vérification dans un cadre (`<iframe>`), lui envoie la lecture d'Atelya et l'image
du plan, puis récupère le **logement.json corrigé** quand la personne clique « Terminer ».

```
Site (onglet « Plans à vérifier »)                 Écran de vérification (iframe)
──────────────────────────────────                 ─────────────────────────────
                                   ◄── pret ──────  (l'écran a fini de charger)
  ouvrir {verification, plan} ────────────────►     affiche le plan + doutes en orange
                                                    … la personne corrige …
                                   ◄── valide {resultat}   (bouton « Terminer »)
                              ou   ◄── abandon            (bouton « Abandonner »)
```

## 1. Héberger les fichiers de l'écran

Copier le dossier `outils/verification-plan/` (sauf `tests/` et `exemples/`) sur le site,
par exemple sous `/outils/verification/`. Ce sont des fichiers fixes (HTML + JavaScript),
**sans aucune dépendance** ni installation, qui fonctionnent sans Internet.

## 2. Afficher l'écran dans l'onglet

```html
<iframe id="ecran-verification"
        src="/outils/verification/index.html?origine=https://ADRESSE-DU-SITE"
        style="width:100%;height:85vh;border:0"></iframe>
```

`origine` = l'adresse du site (protocole + domaine, sans chemin). Par sécurité, l'écran n'écoute
et ne répond **qu'à cette adresse**. S'il est servi depuis le même domaine que le site, on peut l'omettre.

## 3. Se parler par messages (`window.postMessage`)

```js
const ecran = document.getElementById("ecran-verification");
const ORIGINE_ECRAN = new URL(ecran.src, location.href).origin;

window.addEventListener("message", (ev) => {
  if (ev.origin !== ORIGINE_ECRAN || ev.source !== ecran.contentWindow) return;
  const m = ev.data || {};

  if (m.type === "atelya-verification:pret") {
    ecran.contentWindow.postMessage({
      type: "atelya-verification:ouvrir",
      verification: lectureAtelya,   // le contenu de verification.json (objet JS)
      plan: imageDuPlan,             // un Blob/File, une adresse d'image, ou une data URL
    }, ORIGINE_ECRAN);
  }
  if (m.type === "atelya-verification:valide") {
    enregistrer(m.resultat);         // voir § 5 ; m.resultat.logement = le logement.json corrigé
  }
  if (m.type === "atelya-verification:abandon") {
    /* la personne a fermé sans valider : le plan reste « à vérifier » */
  }
});
```

Une page de démonstration complète fait exactement cela : `exemples/site-demo.html`
(à ouvrir via un petit serveur web, ex. `python3 -m http.server`, puis
`http://localhost:8000/outils/verification-plan/exemples/site-demo.html`).

Autre façon, sans messages : `index.html?verification=/chemin/lecture.json&plan=/chemin/plan.png`
(les deux fichiers sur le même domaine que l'écran). Dans ce cas, « Terminer » télécharge le fichier.

## 4. Ce que le site envoie : `verification/0.1`

Produit par le moteur (côté Atelya) pour chaque plan à vérifier.

```json
{
  "schema": "verification/0.1",
  "plan": "nom de l'image (pour info)",
  "calage": {"px_par_m": 100, "origine_px": [210, 760]},
  "echelle": {"etat": "lue", "source": "cotes"},
  "logement": { "schema": "logement/0.1", "...": "la lecture d'Atelya" },
  "doutes": [
    {"element": "chambre", "raison": "Atelya hésite entre bureau et chambre",
     "propositions": [{"libelle": "Chambre", "action": {"type": "renommer", "id": "chambre", "nom": "Chambre"}}]},
    {"element": null, "zone_px": [815, 630, 40, 100], "raison": "porte oubliée ?"}
  ]
}
```

- `calage` : comment poser les mètres sur l'image (ou `{"matrice": 3×3}` pour une photo de biais).
- `echelle.etat` : `"a_verifier"` affiche un bandeau orange en haut de l'écran.
- `doutes` : facultatif ; l'écran ajoute aussi ses propres doutes (confiance < 70 %, mur très court…).

## 5. Ce que l'écran renvoie : `resultat-verification/0.1`

```json
{
  "schema": "resultat-verification/0.1",
  "projet_id": "CAS-TEST-00",
  "statut": "valide",
  "logement": { "schema": "logement/0.1", "...": "le logement corrigé, à envoyer vers la 3D" },
  "rapport": {
    "date": "2026-10-31T12:30:00Z",
    "corrections": 4,
    "elements_verifies": 4,
    "doutes_restants": [],
    "echelle": {"etat": "lue", "source": "cotes"}
  }
}
```

- `statut` : `"valide"` (plus aucun doute) ou `"valide_avec_doutes"` (la personne a validé quand même ;
  les doutes restants sont listés dans `rapport.doutes_restants`).
- `logement` est toujours **cohérent** : l'écran refuse de valider un logement que le moteur ne saurait pas lire.
- Les éléments corrigés par la personne ont `confiance: 1` et une `source` qui finit par `+verification`.
  À garder : ces logements corrigés pourront plus tard servir à réentraîner Atelya
  (avec l'accord des clients, à prévoir dans les conditions d'utilisation).

## 6. Le plan 2D propre à livrer au client (PDF)

Une fois le plan validé, le moteur dessine la page à livrer : marque Atelya, titre, adresse, date,
plan à l'échelle (1/50, 1/75, 1/100…), nom, surface et dimensions de chaque pièce, surface habitable
indicative, barre d'échelle, et la mention « surfaces indicatives, pas un mesurage Carrez ».

```bash
python -m moteur.plan_propre resultat.json --sortie plan.pdf \
       --titre "Appartement T3" --adresse "12 rue des Lilas|75011 Paris"
```

- `resultat.json` = le `resultat-verification/0.1` renvoyé par l'écran (§ 5), tel quel.
- Le site peut aussi y glisser un objet `infos` facultatif, repris sur la page :
  `{"titre": "...", "adresse": "ligne 1\nligne 2", "reference": "...", "nord_deg": 20}`.
  L'adresse vient de la commande du client (Atelya ne peut pas la deviner). `nord_deg` (angle du nord
  depuis le haut de la page, sens horaire) n'est à donner que si on le connaît : sans lui, pas de flèche.
- Garde-fou : un logement qui n'est pas passé par « Terminer » sort avec « BROUILLON, NON VÉRIFIÉ »
  en travers de la page.
- Sorties : `plan.pdf` (A4 ou A3, 300 points par pouce) et `plan.png` (aperçu).

## Ce qui reste à faire côté moteur

Le moteur ne produit pas encore `verification.json` à partir d'une vraie lecture d'Atelya
(il faut y ajouter le calage image ↔ mètres). C'est la prochaine étape côté moteur ; d'ici là,
le format ci-dessus est figé et l'exemple `exemples/exemple-cas-test-00.verification.json` permet d'essayer.

## Photos du client : « d'où est prise cette photo ? » (ajout du 15/11/2026, facultatif)

Le fichier de vérification peut porter, EN PLUS, un champ `photos` ; sans lui l'écran se comporte exactement comme avant
(le format `verification/0.1` ne change pas pour le reste).

```json
"photos": {
  "seules": true,
  "questions": [
    {"nom": "photo-14", "image": "data:image/jpeg;base64,…", "largeur": 1000, "hauteur": 667,
     "question": "Atelya hésite entre « Chambre 2 » et « Chambre 3 ». Pointez d'où la photo est prise.",
     "piece": "chambre_2", "hesite_avec": ["chambre_1"], "proposition": {"x": 13.2, "y": 4.4, "cap": -62.0}}
  ]
}
```

- `questions` : une question par photo qu'Atelya ne sait pas ranger. `image` est la photo elle-même (data URL) ; `proposition`
  (ou `null`) est la place qu'Atelya propose sans en être sûr, dessinée en orange.
- `seules` : `true` quand le plan a déjà été vérifié ; l'écran ne repose alors aucune question sur le plan.
- À l'écran : la photo, la question, et sur le plan on CLIQUE là où se tenait le photographe puis on TIRE vers ce qu'il
  regardait. Boutons « C'est bien la place proposée », « Je ne sais pas », « Effacer ma réponse ».

Le résultat porte alors, EN PLUS, à sa racine (jamais dans `logement`) :

```json
"photos": {"endroits": {"photo-14": [13.13, 4.14, -58.1]}, "passees": ["photo-13"]}
```

- `endroits` : pour chaque photo pointée, `[x, y, cap]` en mètres du plan ; `cap` en degrés (0 = vers la droite du plan, 90 =
  vers le haut) ; `[x, y]` seulement si la personne a cliqué sans tirer.
- `passees` : les photos pour lesquelles la personne a répondu « Je ne sais pas ».
- Écran ouvert seul : le bouton « Terminer » télécharge `<projet>-photos.json` (`{"schema": "reponses-photos/0.1",
  "projet_id", "photos"}`), à donner à `outils\habillage\questions_photos.py ranger`. Dans le site : le champ `photos` est
  dans le `resultat` du message `atelya-verification:valide`.
