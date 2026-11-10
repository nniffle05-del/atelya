/*
 * L'écran de vérification : le plan d'origine, la lecture d'Atelya par-dessus, et les points
 * à vérifier présentés un par un, avec les corrections.
 * Les calculs (et toutes les corrections) sont dans calculs-verif.js ; ici, seulement
 * les clics, le panneau de droite et le dessin.
 *
 * 08/11/2026 : un point peut montrer plusieurs zones (`zones_px` : les niveaux non lus d'une image à
 * plusieurs niveaux, voir calculs-verif.js) ; chacune est entourée en orange, et tant que ce point est en
 * cours, le cadrage (ajuster) montre le logement lu ET ces parties.
 */
(function () {
  "use strict";

  const C = window.CalculsVerif;
  const COULEURS = {
    mur: "#1d4ed8",
    murFond: "rgba(29, 78, 216, 0.28)",
    murLecture: "#334155",
    porte: "#16a34a",
    fenetre: "#0891b2",
    porte_fenetre: "#9333ea",
    pieceBord: "#3b82f6",
    pieceLecture: "#eef2f7",
    doute: "#ea580c",
    douteFond: "rgba(234, 88, 12, 0.22)",
    choisi: "#7c3aed",
  };
  const NOMS_OUVERTURES = { porte: "Porte", fenetre: "Fenêtre", porte_fenetre: "Porte-fenêtre" };
  const CONSIGNES = {
    mur: "Cliquez le premier bout du mur, puis le second.",
    porte: "Cliquez sur un mur, à l'endroit de la porte.",
    fenetre: "Cliquez sur un mur, à l'endroit de la fenêtre.",
    porte_fenetre: "Cliquez sur un mur, à l'endroit de la porte-fenêtre.",
    couper: "Cliquez sur un mur, là où il faut le couper. Vous pourrez ajuster au centimètre.",
    morceau: "Cliquez sur un mur au début du morceau à enlever, puis à sa fin. Vous pourrez ajuster au centimètre.",
    relier: "Cliquez sur le bout d'un mur, puis sur le bout de l'autre.",
  };
  const VISEE = 8; // pixels d'écran : à quelle distance un clic « touche » un élément

  const etat = {
    v: null, // le fichier de vérification en cours (corrigé au fil des clics)
    image: null,
    matrice: null,
    inverse: null,
    doutes: [],
    points: [], // les points à vérifier, dans l'ordre
    rangPoint: 0, // le point affiché
    resultat: null, // le dernier résultat validé
    choisi: null, // id de l'élément choisi
    outil: "choisir",
    affichage: "deux", // "plan" : le plan seul ; "lecture" : la lecture seule ; "deux" : l'une sur l'autre
    depart: null, // premier bout d'un mur en cours d'ajout (m)
    trace: null, // ce qu'on va couper ou enlever : {id, t: [une ou deux positions en m depuis le début du mur]}
    detail: new Set(), // les doutes que la personne a demandé à voir un par un
    mesure: null, // la clé du point dont le formulaire de mesure est ouvert
    fermeture: false, // true après un recalcul des pièces : on montre ce qui n'est pas fermé
    deplacementPropose: null, // en cm : ce qu'il manque d'après la mesure donnée
    relier: null, // premier bout à relier : {id, bout, point}
    accroche: null, // le point où un bout de mur vient de s'accrocher (m)
    fait: null, // le point qu'on vient de régler, à regarder avant de passer au suivant : {titre, texte, zone_px}
    depart_lecture: null, // la lecture d'Atelya, telle qu'à l'ouverture
    pastilles: [], // où sont dessinées les pastilles : {rang, x, y} en pixels d'écran
    references: new WeakMap(), // pour chaque version du plan : ses murs quand les pièces ont été calculées (suit « Annuler »)
    souris: null, // position de la souris (m)
    glisse: null, // {genre: "vue"|"mur", ...}
    apercu: null, // copie corrigée affichée pendant qu'on glisse un mur
    historique: [],
    refaire: [],
    vue: { zoom: 1, dx: 0, dy: 0 },
  };
  window.Verification = { etat, choisir, reprendre }; // pour les tests automatiques

  // ---------- Branchement au site interne ----------
  //
  // L'écran peut être ouvert seul (double-clic sur index.html) ou DANS une page du site
  // (balise <iframe>). Dans ce cas, le site et l'écran se parlent par messages
  // (window.postMessage), voir BRANCHEMENT.md :
  //   écran → site : {type: "atelya-verification:pret"}
  //   site → écran : {type: "atelya-verification:ouvrir", verification, plan}
  //   écran → site : {type: "atelya-verification:valide", resultat}  ou  {type: "atelya-verification:abandon"}
  // Par sécurité, l'écran n'écoute et ne répond qu'à l'adresse du site donnée dans ?origine=…
  const PREFIXE = "atelya-verification:";
  const parametres = new URLSearchParams(window.location.search);
  const integre = window.parent !== window;
  const origineSite = (() => {
    if (parametres.get("origine")) return parametres.get("origine");
    try { return document.referrer ? new URL(document.referrer).origin : null; } catch (e) { return null; }
  })();

  function versSite(message) {
    if (integre && origineSite) window.parent.postMessage(message, origineSite);
  }

  const $ = (id) => document.getElementById(id);
  const canvas = $("plan");
  const ctx = canvas.getContext("2d");
  const formatM = (v, d = 2) => v.toFixed(d).replace(".", ",");
  const lireNombre = (texte) => parseFloat(String(texte).replace(",", "."));

  // ---------- Ouvrir ----------

  function ouvrir(verification, image) {
    const erreurs = C.verifierFichier(verification);
    if (erreurs.length) {
      message("Fichier de vérification refusé : " + erreurs.join(" ; "), true);
      return;
    }
    etat.v = verification;
    etat.image = image;
    etat.historique = [];
    etat.refaire = [];
    etat.choisi = null;
    etat.rangPoint = 0;
    etat.fait = null;
    etat.detail = new Set();
    etat.fermeture = false;
    etat.mesure = null;
    etat.deplacementPropose = null;
    etat.references.set(verification, empreinteMurs(verification));
    etat.depart_lecture = verification;
    $("accueil").style.display = "none";
    message("");
    recalculer();
    ajuster();
    rafraichir();
    proposerReprise();
  }

  // ---------- Garder le travail ----------
  //
  // Chaque correction s'enregistre dans le navigateur. Dans le site interne, c'est le site qui garde les fichiers.

  const cleSauvegarde = () => `atelya-verification|${etat.depart_lecture.logement.projet_id}`;
  const heure = (date) => new Date(date).toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });

  function photoDuTravail() {
    return C.travail(etat.v, { detail: [...etat.detail], fermeture: etat.fermeture, murs_calcules: etat.references.get(etat.v) || null });
  }

  function sauvegarder() {
    if (integre || !etat.v) return;
    try {
      localStorage.setItem(cleSauvegarde(), JSON.stringify(photoDuTravail()));
      $("sauvegarde").textContent = "✓ Enregistré";
    } catch (e) {
      $("sauvegarde").textContent = "Non enregistré : téléchargez votre travail";
    }
  }

  function proposerReprise() {
    $("reprise").hidden = true;
    if (integre) return;
    let t = null;
    try { t = JSON.parse(localStorage.getItem(cleSauvegarde())); } catch (e) { return; }
    if (!t || !t.verification || JSON.stringify(t.verification.logement) === JSON.stringify(etat.v.logement)) return;
    $("reprise-texte").textContent = `Vous avez déjà travaillé sur ce plan (le ${heure(t.date)}).`;
    $("reprise").hidden = false;
    $("reprise-oui").onclick = () => reprendre(t);
    $("reprise-non").onclick = repartir;
  }

  /** Repart d'un travail enregistré (dans le navigateur ou dans un fichier). */
  function reprendre(contenu) {
    try {
      const r = C.reprendreTravail(etat.depart_lecture, contenu);
      etat.v = r.v;
      etat.historique = [];
      etat.refaire = [];
      etat.detail = new Set(r.detail);
      etat.fermeture = r.fermeture;
      etat.references.set(r.v, r.murs_calcules || empreinteMurs(r.v));
      etat.choisi = null;
      etat.rangPoint = 0;
      etat.mesure = null;
      etat.fait = null;
      $("reprise").hidden = true;
      recalculer();
      ajuster();
      message("Travail repris.");
      rafraichir();
      sauvegarder();
    } catch (e) {
      message("Reprise impossible : " + e.message, true);
    }
  }

  function repartir() {
    try { localStorage.removeItem(cleSauvegarde()); } catch (e) { /* rien à effacer */ }
    etat.v = JSON.parse(JSON.stringify(etat.depart_lecture));
    etat.references.set(etat.v, empreinteMurs(etat.v));
    etat.historique = [];
    etat.refaire = [];
    etat.detail = new Set();
    etat.fermeture = false;
    etat.choisi = null;
    etat.rangPoint = 0;
    etat.mesure = null;
    etat.fait = null;
    $("reprise").hidden = true;
    $("sauvegarde").textContent = "";
    recalculer();
    ajuster();
    message("Vous repartez de la lecture d'Atelya.");
    rafraichir();
  }

  const empreinteMurs = (v) => JSON.stringify(v.logement.murs.map((m) => [m.debut, m.fin, m.epaisseur]));

  function recalculer() {
    etat.matrice = C.matriceDuCalage(etat.v.calage);
    etat.inverse = C.inverse(etat.matrice);
    etat.doutes = C.trouverDoutes(etat.v);
    etat.points = C.pointsAVerifier(etat.v, { detail: etat.detail, fermeture: etat.fermeture });
    etat.rangPoint = Math.min(etat.rangPoint, Math.max(0, etat.points.length - 1));
    if (etat.choisi && !trouverElement(etat.choisi)) etat.choisi = null;
  }

  function lireTexte(fichier) {
    return new Promise((ok, ko) => {
      const r = new FileReader();
      r.onload = () => ok(r.result);
      r.onerror = () => ko(r.error);
      r.readAsText(fichier);
    });
  }

  function chargerImage(source) {
    return new Promise((ok, ko) => {
      const img = new Image();
      img.onload = () => ok(img);
      img.onerror = () => ko(new Error("image illisible"));
      img.src = source;
    });
  }

  async function ouvrirFichiers(fichiers) {
    const liste = [...fichiers];
    const json = liste.find((f) => f.name.toLowerCase().endsWith(".json"));
    const img = liste.find((f) => f.type.startsWith("image/"));
    if (!json || !img) {
      message("Il faut choisir les deux fichiers ensemble : le .json de vérification et l'image du plan.", true);
      return;
    }
    try {
      const v = JSON.parse(await lireTexte(json));
      const image = await chargerImage(URL.createObjectURL(img));
      ouvrir(v, image);
    } catch (e) {
      message("Ouverture impossible : " + e.message, true);
    }
  }

  async function ouvrirExemple() {
    const ex = window.EXEMPLE_VERIFICATION;
    if (!ex) return message("Exemple introuvable (fichier exemples/exemple-cas-test-00.js).", true);
    ouvrir(JSON.parse(JSON.stringify(ex.verification)), await chargerImage(ex.image));
  }

  // ---------- Corriger, annuler, rétablir ----------

  /** Applique une correction (une fonction qui renvoie une copie corrigée) et la garde pour « Annuler ». */
  function corriger(correction, texte) {
    if (!etat.v) return false;
    try {
      const nouveau = correction(etat.v);
      if (nouveau === etat.v) return false;
      const pointAvant = etat.fait ? null : etat.points[etat.rangPoint];
      etat.historique.push(etat.v);
      etat.refaire = [];
      etat.references.set(nouveau, etat.references.get(etat.v));
      etat.v = nouveau;
      recalculer();
      if (pointAvant && !etat.points.some((x) => x.cle === pointAvant.cle)) {
        etat.fait = { titre: pointAvant.titre, texte: texte || "C'est fait.", zone_px: pointAvant.zone_px };
        message("");
      } else message(texte || "");
      rafraichir();
      sauvegarder();
      return true;
    } catch (e) {
      message(e.message, true);
      return false;
    }
  }

  function annuler() {
    if (!etat.historique.length) return;
    etat.refaire.push(etat.v);
    etat.v = etat.historique.pop();
    etat.fait = null;
    recalculer();
    message("Dernière correction annulée.");
    rafraichir();
    sauvegarder();
  }

  function refaire() {
    if (!etat.refaire.length) return;
    etat.historique.push(etat.v);
    etat.v = etat.refaire.pop();
    etat.fait = null;
    recalculer();
    message("Correction rétablie.");
    rafraichir();
    sauvegarder();
  }

  // ---------- Vue ----------

  function pixelsParMetre() {
    const a = px([0, 0]), b = px([1, 0]), c = px([0, 1]);
    return (Math.hypot(b[0] - a[0], b[1] - a[1]) + Math.hypot(c[0] - a[0], c[1] - a[1])) / 2;
  }

  /** Montre tout le logement, cadré sur ses murs avec un peu de marge pour voir les cotes autour. */
  function ajuster() {
    if (!etat.image) return;
    const r = canvas.getBoundingClientRect();
    let rect = [0, 0, etat.image.naturalWidth, etat.image.naturalHeight];
    if (etat.v) {
      let b = rectangleDe(formes(etat.v).murs.flatMap((m) => m.points));
      // Point « plusieurs niveaux » en cours : on cadre aussi les parties non lues, pour voir d'un coup ce qui a été lu et ce qui manque.
      const point = etat.points && etat.points[etat.rangPoint];
      if (point && point.genre === "niveaux" && point.zone_px) {
        const [zx, zy, zl, zh] = point.zone_px;
        const x0 = Math.min(b[0], zx), y0 = Math.min(b[1], zy);
        b = [x0, y0, Math.max(b[0] + b[2], zx + zl) - x0, Math.max(b[1] + b[3], zy + zh) - y0];
      }
      const marge = Math.max(0.08 * Math.max(b[2], b[3]), pixelsParMetre());
      const x0 = Math.max(0, b[0] - marge), y0 = Math.max(0, b[1] - marge);
      rect = [x0, y0, Math.min(etat.image.naturalWidth, b[0] + b[2] + marge) - x0, Math.min(etat.image.naturalHeight, b[1] + b[3] + marge) - y0];
    }
    const z = Math.min(r.width / rect[2], r.height / rect[3]) * 0.97;
    etat.vue = { zoom: z, dx: r.width / 2 - (rect[0] + rect[2] / 2) * z, dy: r.height / 2 - (rect[1] + rect[3] / 2) * z };
    dessiner();
  }

  function zoomer(facteur, centre) {
    const r = canvas.getBoundingClientRect();
    const c = centre || [r.width / 2, r.height / 2];
    const z = Math.min(40, Math.max(0.05, etat.vue.zoom * facteur));
    const f = z / etat.vue.zoom;
    etat.vue = { zoom: z, dx: c[0] - (c[0] - etat.vue.dx) * f, dy: c[1] - (c[1] - etat.vue.dy) * f };
    dessiner();
  }

  /** Centre la vue sur un rectangle de pixels du plan [x, y, l, h], avec environ 1,5 m autour pour se repérer. */
  function cadrer(rect) {
    const r = canvas.getBoundingClientRect();
    const marge = 3 * pixelsParMetre();
    const z = Math.min(r.width / (rect[2] + marge), r.height / (rect[3] + marge));
    etat.vue = { zoom: z, dx: r.width / 2 - (rect[0] + rect[2] / 2) * z, dy: r.height / 2 - (rect[1] + rect[3] / 2) * z };
    dessiner();
  }

  function ecranVersImage(ev) {
    const r = canvas.getBoundingClientRect();
    return [(ev.clientX - r.left - etat.vue.dx) / etat.vue.zoom, (ev.clientY - r.top - etat.vue.dy) / etat.vue.zoom];
  }

  const ecranVersMetres = (ev) => C.versPixel(etat.inverse, ecranVersImage(ev));
  const px = (p) => C.versPixel(etat.matrice, p);

  /** Combien de mètres font `n` pixels d'écran, autour d'un point (m). */
  function metresPour(n, p) {
    const a = px(p), b = px([p[0] + 1, p[1]]), c = px([p[0], p[1] + 1]);
    const pxParM = (Math.hypot(b[0] - a[0], b[1] - a[1]) + Math.hypot(c[0] - a[0], c[1] - a[1])) / 2;
    return n / (etat.vue.zoom * pxParM);
  }

  // ---------- Formes en pixels ----------

  function formes(v) {
    const lg = v.logement;
    const murs = new Map(lg.murs.map((m) => [m.id, m]));
    return {
      murs: lg.murs.map((m) => ({ id: m.id, points: C.polygoneMur(m).map(px) })),
      ouvertures: (lg.ouvertures || []).filter((o) => murs.has(o.mur)).map((o) => ({
        id: o.id, type: o.type, points: C.polygoneOuverture(o, murs.get(o.mur)).map(px),
      })),
      pieces: (lg.pieces || []).map((p) => ({
        id: p.id, nom: p.nom, surface: C.surfacePolygone(p.contour),
        points: p.contour.map(px), centre: px(C.centrePolygone(p.contour)),
      })),
    };
  }

  function rectangleDe(points) {
    const xs = points.map((p) => p[0]);
    const ys = points.map((p) => p[1]);
    const x = Math.min(...xs), y = Math.min(...ys);
    return [x, y, Math.max(...xs) - x, Math.max(...ys) - y];
  }

  function formeDe(id) {
    const f = formes(etat.v);
    return [...f.murs, ...f.ouvertures, ...f.pieces].find((x) => x.id === id) || null;
  }

  function trouverElement(id) {
    const lg = etat.v.logement;
    for (const [genre, liste] of [["mur", lg.murs], ["ouverture", lg.ouvertures || []], ["piece", lg.pieces || []]]) {
      const e = liste.find((x) => x.id === id);
      if (e) return { genre, e };
    }
    return null;
  }

  // ---------- Dessin ----------

  function chemin(points) {
    ctx.beginPath();
    points.forEach((p, i) => (i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1])));
    ctx.closePath();
  }

  function dessiner() {
    const dpr = window.devicePixelRatio || 1;
    const r = canvas.getBoundingClientRect();
    if (canvas.width !== Math.round(r.width * dpr) || canvas.height !== Math.round(r.height * dpr)) {
      canvas.width = Math.round(r.width * dpr);
      canvas.height = Math.round(r.height * dpr);
    }
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (!etat.image) return;
    const z = etat.vue.zoom;
    ctx.setTransform(dpr * z, 0, 0, dpr * z, dpr * etat.vue.dx, dpr * etat.vue.dy);
    if (etat.affichage === "lecture") {
      ctx.fillStyle = "#fff";
      ctx.fillRect(0, 0, etat.image.naturalWidth, etat.image.naturalHeight);
    } else {
      ctx.globalAlpha = etat.affichage === "deux" ? 0.75 : 1; // un peu estompé : la lecture ressort sans cacher le plan
      ctx.drawImage(etat.image, 0, 0);
      ctx.globalAlpha = 1;
    }
    if (etat.affichage === "plan") return;

    const seule = etat.affichage === "lecture";
    const v = etat.apercu || etat.v;
    const f = formes(v);
    const trait = 1 / z; // un pixel d'écran
    const point = etat.fait ? null : etat.points[etat.rangPoint];
    const enCours = new Set(point ? point.elements : []);

    for (const p of f.pieces) {
      chemin(p.points);
      if (seule) { ctx.fillStyle = COULEURS.pieceLecture; ctx.fill(); }
      if (enCours.has(p.id)) { ctx.fillStyle = COULEURS.douteFond; ctx.fill(); }
      ctx.lineWidth = trait;
      ctx.strokeStyle = COULEURS.pieceBord;
      ctx.setLineDash(seule ? [] : [5 * trait, 4 * trait]);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    for (const m of f.murs) {
      chemin(m.points);
      ctx.fillStyle = seule ? COULEURS.murLecture : COULEURS.murFond;
      ctx.fill();
      if (!seule) {
        ctx.lineWidth = trait;
        ctx.strokeStyle = COULEURS.mur;
        ctx.stroke();
      }
    }
    ctx.globalAlpha = seule ? 1 : 0.6; // on doit voir le symbole du plan à travers
    for (const o of f.ouvertures) {
      chemin(o.points);
      ctx.fillStyle = COULEURS[o.type] || COULEURS.porte;
      ctx.fill();
    }
    ctx.globalAlpha = 1;

    // Le point en cours : ses éléments entourés d'orange, et sa zone s'il n'est lié à aucun élément.
    for (const e of [...f.murs, ...f.ouvertures, ...f.pieces]) {
      if (!enCours.has(e.id)) continue;
      chemin(e.points);
      ctx.lineWidth = 3 * trait;
      ctx.strokeStyle = COULEURS.doute;
      ctx.stroke();
    }
    if (point && point.zone_px && !point.elements.length) {
      // Plusieurs parties à montrer (niveaux non lus) : chacune entourée ; sinon la zone du point.
      for (const [x, y, l, h] of (point.zones_px && point.zones_px.length ? point.zones_px : [point.zone_px])) {
        const m = 6 * trait;
        ctx.fillStyle = COULEURS.douteFond;
        ctx.fillRect(x, y, l, h);
        ctx.lineWidth = 3 * trait;
        ctx.strokeStyle = COULEURS.doute;
        ctx.setLineDash([8 * trait, 5 * trait]);
        ctx.strokeRect(x - m, y - m, l + 2 * m, h + 2 * m);
        ctx.setLineDash([]);
      }
    }

    // Le point qu'on vient de régler : l'endroit reste entouré en vert, le temps de regarder le résultat.
    if (etat.fait && etat.fait.zone_px) {
      const [x, y, l, h] = etat.fait.zone_px;
      const m = 8 * trait;
      ctx.lineWidth = 3 * trait;
      ctx.strokeStyle = "#16a34a";
      ctx.setLineDash([8 * trait, 5 * trait]);
      ctx.strokeRect(x - m, y - m, l + 2 * m, h + 2 * m);
      ctx.setLineDash([]);
    }

    // L'élément qu'on est en train de corriger.
    const choisi = etat.choisi && [...f.murs, ...f.ouvertures, ...f.pieces].find((x) => x.id === etat.choisi);
    if (choisi) {
      chemin(choisi.points);
      ctx.lineWidth = 4 * trait;
      ctx.strokeStyle = COULEURS.choisi;
      ctx.stroke();
    }

    // Le mur en cours d'ajout.
    if (etat.outil === "mur" && etat.depart && etat.souris) {
      const fin = C.aimanter(etat.v.logement, etat.souris, etat.depart, metresPour(VISEE * 1.5, etat.souris));
      if (C.longueur(etat.depart, fin) > 0.01) {
        chemin(C.polygoneMur({ debut: etat.depart, fin, epaisseur: epaisseurNouveauMur() }).map(px));
        ctx.fillStyle = "rgba(29, 78, 216, 0.5)";
        ctx.fill();
      }
    }

    // Les poignées : à chaque bout du mur choisi, ou de tous les murs pour l'outil « relier ».
    const rond = (q, couleur, rayon = 6) => {
      const c = px(q);
      ctx.beginPath();
      ctx.arc(c[0], c[1], rayon * trait, 0, 2 * Math.PI);
      ctx.fillStyle = couleur;
      ctx.fill();
      ctx.lineWidth = 1.5 * trait;
      ctx.strokeStyle = "#fff";
      ctx.stroke();
    };
    const murChoisi = etat.outil === "choisir" && etat.choisi && v.logement.murs.find((m) => m.id === etat.choisi);
    if (murChoisi) { rond(murChoisi.debut, COULEURS.choisi); rond(murChoisi.fin, COULEURS.choisi); }
    const ouvertureChoisie = etat.outil === "choisir" && etat.choisi && (v.logement.ouvertures || []).find((o) => o.id === etat.choisi);
    if (ouvertureChoisie) { // ses deux bords : à tirer pour changer la largeur
      const bords = C.bordsOuverture(v.logement, ouvertureChoisie);
      if (bords) { rond(bords[0], COULEURS.choisi, 5); rond(bords[1], COULEURS.choisi, 5); }
    }
    if (etat.outil === "relier") {
      for (const m of v.logement.murs) { rond(m.debut, "#94a3b8", 4); rond(m.fin, "#94a3b8", 4); }
      if (etat.relier) rond(etat.relier.point, COULEURS.choisi, 7);
    }
    if (etat.accroche) rond(etat.accroche, "#16a34a", 8);
    if (point && point.trait_m) { // le trou dans les murs : un trait rouge à l'endroit exact, et le mur proposé en vert
      const [ta, tb] = point.trait_m.map(px);
      ctx.beginPath();
      ctx.moveTo(ta[0], ta[1]);
      ctx.lineTo(tb[0], tb[1]);
      ctx.lineWidth = 5 * trait;
      ctx.strokeStyle = "#dc2626";
      ctx.setLineDash([10 * trait, 6 * trait]);
      ctx.stroke();
      ctx.setLineDash([]);
      if (point.mur_propose) {
        const [ma, mb] = [point.mur_propose.debut, point.mur_propose.fin].map(px);
        ctx.beginPath();
        ctx.moveTo(ma[0], ma[1]);
        ctx.lineTo(mb[0], mb[1]);
        ctx.lineWidth = 3 * trait;
        ctx.strokeStyle = "#16a34a";
        ctx.stroke();
        rond(point.mur_propose.debut, "#16a34a", 5);
        rond(point.mur_propose.fin, "#16a34a", 5);
      }
    }
    dessinerTrace(v, trait);

    dessinerEtiquettes(f, enCours, dpr);
    dessinerPastilles(f, dpr);
  }

  /** Une pastille numérotée pour chaque point à vérifier. Le point en cours est plus grand et plus foncé. */
  function dessinerPastilles(f, dpr) {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const formesParId = new Map([...f.murs, ...f.ouvertures, ...f.pieces].map((e) => [e.id, e]));
    const places = [];
    etat.points.forEach((point, rang) => {
      let rect = point.zone_px;
      if (!rect) {
        const pts = point.elements.flatMap((id) => (formesParId.get(id) ? formesParId.get(id).points : []));
        if (!pts.length) return;
        rect = rectangleDe(pts);
      }
      let x = (rect[0] + rect[2] / 2) * etat.vue.zoom + etat.vue.dx, y = (rect[1] + rect[3] / 2) * etat.vue.zoom + etat.vue.dy;
      while (places.some((q) => Math.hypot(q.x - x, q.y - y) < 22)) x += 22; // à côté de la voisine, jamais dessus
      places.push({ rang, x, y });
    });
    etat.pastilles = places;
    ctx.textAlign = "center";
    for (const { rang, x, y } of places) {
      const actuel = rang === etat.rangPoint && !etat.fait;
      ctx.beginPath();
      ctx.arc(x, y, actuel ? 13 : 10, 0, 2 * Math.PI);
      ctx.fillStyle = actuel ? "#9a3412" : COULEURS.doute;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = "#fff";
      ctx.stroke();
      ctx.fillStyle = "#fff";
      ctx.font = '700 11px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
      ctx.fillText(String(rang + 1), x, y + 4);
    }
  }

  function pastilleSous(ev) {
    const r = canvas.getBoundingClientRect();
    const x = ev.clientX - r.left, y = ev.clientY - r.top;
    return etat.affichage === "plan" || etat.outil !== "choisir" ? null : etat.pastilles.find((q) => Math.hypot(q.x - x, q.y - y) <= 12) || null;
  }

  const sensMur = (m) => { const l = C.longueur(m.debut, m.fin); return { l, d: [(m.fin[0] - m.debut[0]) / l, (m.fin[1] - m.debut[1]) / l] }; };

  /** La position sous la souris sur le mur visé : {id, t}, ou null. */
  function viseeSurMur(lg) {
    if (!etat.souris) return null;
    const m = C.murLePlusProche(lg, etat.souris, metresPour(VISEE * 2, etat.souris));
    return m ? { id: m.id, t: C.aimanterSurMur(lg, m.id, m.le_long, metresPour(VISEE, etat.souris)).t } : null;
  }

  /** Les repères de coupe : le trait à l'endroit visé, les distances aux deux bouts, et le morceau qui va partir. */
  function dessinerTrace(v, trait) {
    if (etat.outil !== "couper" && etat.outil !== "morceau") return;
    const lg = v.logement;
    const marque = (id, t, couleur) => {
      const m = lg.murs.find((x) => x.id === id);
      if (!m) return;
      const { d } = sensMur(m);
      const n = [-d[1], d[0]], c = [m.debut[0] + d[0] * t, m.debut[1] + d[1] * t], h = Math.max(m.epaisseur, 0.15);
      const a = px([c[0] + n[0] * h, c[1] + n[1] * h]), b = px([c[0] - n[0] * h, c[1] - n[1] * h]);
      ctx.beginPath();
      ctx.moveTo(a[0], a[1]);
      ctx.lineTo(b[0], b[1]);
      ctx.lineWidth = 2.5 * trait;
      ctx.strokeStyle = couleur;
      ctx.stroke();
    };
    const tr = etat.trace;
    if (tr && tr.t.length === 2) {
      const m = lg.murs.find((x) => x.id === tr.id);
      if (m) {
        const { d } = sensMur(m);
        const a = px([m.debut[0] + d[0] * tr.t[0], m.debut[1] + d[1] * tr.t[0]]), b = px([m.debut[0] + d[0] * tr.t[1], m.debut[1] + d[1] * tr.t[1]]);
        ctx.beginPath();
        ctx.moveTo(a[0], a[1]);
        ctx.lineTo(b[0], b[1]);
        ctx.lineWidth = 5 * trait;
        ctx.strokeStyle = "#dc2626";
        ctx.stroke();
      }
    }
    if (tr) for (const t of tr.t) marque(tr.id, t, "#dc2626");
    const vise = viseeSurMur(lg);
    if (!vise) return;
    marque(vise.id, vise.t, "#7c3aed");
    const m = lg.murs.find((x) => x.id === vise.id);
    const { l, d } = sensMur(m);
    const c = px([m.debut[0] + d[0] * vise.t, m.debut[1] + d[1] * vise.t]);
    const z = etat.vue.zoom, dpr = window.devicePixelRatio || 1;
    const x = c[0] * z + etat.vue.dx, y = c[1] * z + etat.vue.dy;
    const texte = `${formatM(vise.t)} m  |  ${formatM(l - vise.t)} m`;
    ctx.save();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.font = '600 13px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
    const larg = ctx.measureText(texte).width + 14;
    ctx.fillStyle = "#1f2937";
    ctx.beginPath();
    const haut = y - 40 < 64 ? y + 16 : y - 40; // sous le mur s'il passerait derrière la consigne
    ctx.roundRect(x - larg / 2, haut, larg, 24, 5);
    ctx.fill();
    ctx.fillStyle = "#fff";
    ctx.textAlign = "center";
    ctx.fillText(texte, x, haut + 17);
    ctx.restore();
  }

  /** Les noms des pièces, écrits à taille fixe et sans jamais se chevaucher : ceux qui n'ont plus la place attendent un zoom. */
  function dessinerEtiquettes(f, enCours, dpr) {
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    const places = [];
    const avecPlace = [...f.pieces].sort((a, b) => (enCours.has(b.id) - enCours.has(a.id)) || (b.surface - a.surface));
    for (const p of avecPlace) {
      const x = p.centre[0] * etat.vue.zoom + etat.vue.dx, y = p.centre[1] * etat.vue.zoom + etat.vue.dy;
      const lignes = [p.nom, `${formatM(p.surface, 1)} m²`];
      ctx.font = '600 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif';
      const larg = Math.max(...lignes.map((l) => ctx.measureText(l).width)) + 10, haut = 34;
      const essais = [[0, 0], [0, -haut], [0, haut], [larg, 0], [-larg, 0]];
      const place = essais.map(([a, b]) => [x + a - larg / 2, y + b - haut / 2, larg, haut])
        .find((r) => !places.some((q) => r[0] < q[0] + q[2] && q[0] < r[0] + r[2] && r[1] < q[1] + q[3] && q[1] < r[1] + r[3]));
      if (!place) continue;
      places.push(place);
      etiquette(place, lignes, enCours.has(p.id));
    }
  }

  function etiquette([x, y, larg, haut], lignes, doute) {
    ctx.textAlign = "center";
    ctx.fillStyle = doute ? "rgba(255, 247, 237, 0.95)" : "rgba(255, 255, 255, 0.85)";
    ctx.strokeStyle = doute ? COULEURS.doute : "rgba(59, 130, 246, 0.5)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.roundRect(x, y, larg, haut, 4);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = doute ? "#9a3412" : "#1e3a8a";
    lignes.forEach((l, i) => {
      ctx.font = `${i ? 400 : 600} 12px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
      ctx.fillText(l, x + larg / 2, y + 14 + i * 14);
    });
  }

  // ---------- Panneau de droite ----------

  function nomDe(id) {
    const t = trouverElement(id);
    if (!t) return "Élément";
    if (t.genre === "piece") return `La pièce « ${t.e.nom} »`;
    if (t.genre === "ouverture") return `${NOMS_OUVERTURES[t.e.type]}`;
    return "Le mur";
  }

  function el(balise, attributs = {}, ...enfants) {
    const e = document.createElement(balise);
    for (const [k, val] of Object.entries(attributs)) {
      if (k.startsWith("on")) e.addEventListener(k.slice(2), val);
      else if (k === "texte") e.textContent = val;
      else e.setAttribute(k, val);
    }
    e.append(...enfants);
    return e;
  }

  function rafraichir() {
    const v = etat.v;
    $("annuler").disabled = !etat.historique.length;
    $("valider").disabled = !etat.v;
    $("refaire").hidden = !etat.refaire.length;
    document.querySelectorAll("[data-vue]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.vue === etat.affichage)));
    const outilActif = etat.outil !== "choisir";
    $("consigne-outil").hidden = !outilActif;
    if (outilActif) $("consigne").textContent = CONSIGNES[etat.outil];
    canvas.style.cursor = outilActif ? "crosshair" : "grab";
    if (!v) return;
    const lg = v.logement;
    $("titre").textContent = lg.projet_id;
    $("bandeau").textContent = etat.affichage === "plan" ? "Plan tel qu'il a été déposé. Pour corriger, revenez sur « Les deux »." : "";

    afficherPoint();
    afficherPrecision();
    afficherFiche();
    $("alerte-pieces").hidden = empreinteMurs(v) === etat.references.get(v);

    const tb = $("pieces");
    tb.innerHTML = "";
    const douteuses = new Set(etat.points.flatMap((p) => p.elements));
    let total = 0;
    for (const p of lg.pieces || []) {
      const s = C.surfacePolygone(p.contour);
      total += s;
      const tr = el("tr", { onclick: () => { choisir(p.id); cadrer(rectangleDe(p.contour.map(px))); } }, el("td", { texte: p.nom }), el("td", { class: "nb", texte: `${formatM(s, 1)} m²` }));
      if (douteuses.has(p.id)) tr.className = "douteux";
      tb.append(tr);
    }
    $("ouvrir-pieces").textContent = `Pièces (${(lg.pieces || []).length})`;
    const nbP = (lg.ouvertures || []).filter((o) => o.type === "porte").length;
    const nbF = (lg.ouvertures || []).length - nbP;
    $("resume").textContent = `Total ${formatM(total, 1)} m² · ${nbP} portes · ${nbF} fenêtres et portes-fenêtres`;
    dessiner();
  }

  /** Le point en cours : ce qu'il faut regarder, en français, et les choix possibles. */
  function afficherPoint() {
    const sec = $("point");
    const actions = $("point-actions");
    actions.innerHTML = "";
    const n = etat.points.length;
    const point = etat.points[etat.rangPoint];
    if (etat.fait) {
      sec.classList.add("fini");
      $("point-nav").hidden = true;
      $("point-numero").textContent = "✓ C'est fait";
      $("point-titre").textContent = etat.fait.titre;
      $("point-texte").textContent = `${etat.fait.texte} Regardez le résultat sur le plan, puis continuez. Si ce n'est pas bon, annulez.`;
      actions.append(
        el("button", { class: "bouton principal", id: "fait-suivant", texte: n ? "C'est bon, point suivant ›" : "C'est bon, voir la fin ›", onclick: montrerPoint }),
        el("button", { class: "bouton", id: "fait-annuler", texte: "↶ Annuler cette correction", onclick: annuler }));
      return;
    }
    sec.classList.toggle("fini", !n);
    $("point-nav").hidden = n < 2;
    $("point-precedent").disabled = etat.rangPoint === 0;
    $("point-suivant").disabled = etat.rangPoint >= n - 1;
    if (!point) {
      $("point-numero").textContent = "Tout est vérifié";
      $("point-titre").textContent = "Plus aucun point";
      const erreurs = C.verifierCoherence(etat.v.logement);
      $("point-texte").textContent = erreurs.length
        ? `À corriger avant de terminer : ${erreurs.join(" ; ")}.`
        : "Jetez un dernier coup d'œil au plan : Atelya peut s'être trompé sans le savoir. Puis cliquez sur « Terminer ».";
      return;
    }
    $("point-numero").textContent = `Point ${etat.rangPoint + 1} sur ${n}`;
    $("point-titre").textContent = point.titre;
    $("point-texte").textContent = point.texte;
    let nom = null;
    if (point.genre === "morceaux") {
      const pieces = etat.v.logement.pieces.filter((p) => point.elements.includes(p.id));
      const grande = [...pieces].sort((a, b) => C.surfacePolygone(b.contour) - C.surfacePolygone(a.contour))[0];
      const sansNumero = grande.nom.replace(/\s+\d+$/, "");
      nom = el("select", { "aria-label": "Nom de la pièce réunie" }, ...[...new Set([sansNumero, ...pieces.map((p) => p.nom), ...C.NOMS_PIECES])].map((x) => el("option", { value: x, texte: `Nom : ${x}` })));
      actions.append(nom);
    }
    if (etat.mesure === point.cle && point.mesure) return afficherMesure(point);
    for (const a of point.actions) {
      actions.append(el("button", {
        class: `bouton${a.principal ? " principal" : ""}${a.danger ? " danger" : ""}`,
        texte: a.libelle,
        onclick: () => choisirPourLePoint(point, a, nom && nom.value),
      }));
    }
    if (point.elements.length === 1 && point.genre !== "echelle" && !point.actions.some((a) => a.action.type === "outil")) {
      actions.append(el("button", { class: "bouton", texte: "Non, je corrige", onclick: () => choisir(point.elements[0]) }));
    }
  }

  /** « Non » sur une mesure : la vraie taille, puis la bonne correction : tout le plan, ou un seul mur mal placé. */
  function afficherMesure(point) {
    const actions = $("point-actions");
    const { mesure } = point;
    const champX = el("input", { type: "text", id: "m-x", value: formatM(mesure.x), inputmode: "decimal" });
    const champY = el("input", { type: "text", id: "m-y", value: formatM(mesure.y), inputmode: "decimal" });
    const conseil = el("div", { id: "m-conseil" });
    const lire = () => {
      const x = lireNombre(champX.value), y = lireNombre(champY.value);
      return x > 0 && y > 0 ? { x, y, kx: x / mesure.x, ky: y / mesure.y } : null;
    };
    const toutLePlan = (k) => {
      if (corriger((v) => C.mettreAEchelle(v, k), "Toutes les mesures du plan sont corrigées.")) {
        etat.mesure = null;
        rafraichir();
      }
    };
    const verifier = () => {
      conseil.innerHTML = "";
      const m = lire();
      if (!m) return message("Tapez deux nombres en mètres, par exemple 5,68.", true);
      message("");
      if (Math.abs(m.kx - 1) < 0.002 && Math.abs(m.ky - 1) < 0.002) return message("Ces mesures sont déjà celles d'Atelya : il n'y a rien à corriger.");
      if (Math.abs(m.kx / m.ky - 1) <= 0.01) return toutLePlan((m.kx + m.ky) / 2);
      // Un côté juste et l'autre faux : l'échelle n'y est pour rien, c'est un mur mal placé.
      const sensFaux = Math.abs(m.ky - 1) > Math.abs(m.kx - 1) ? "y" : "x";
      const ecartCm = Math.round(Math.abs(m[sensFaux] - mesure[sensFaux]) * 100);
      conseil.append(el("p", { texte: `Les deux côtés ne sont pas faux de la même façon : il y a ${ecartCm} cm d'écart ${sensFaux === "y" ? "dans le sens haut-bas" : "dans le sens gauche-droite"}. C'est sans doute un seul mur mal placé.` }),
        el("button", { class: "bouton principal", id: "m-mur", texte: "Déplacer le mur", onclick: () => {
          etat.deplacementPropose = ecartCm;
          etat.mesure = null;
          const piece = etat.v.logement.pieces.find((x) => x.id === mesure.piece);
          cadrer(rectangleDe(piece.contour.map(px)));
          message(`Cliquez sur le mur à déplacer de ${ecartCm} cm : la fiche à droite vous laisse choisir le sens.`);
          rafraichir();
        } }),
        el("button", { class: "bouton", id: "m-tout", texte: "Corriger tout le plan quand même", onclick: () => toutLePlan((m.kx + m.ky) / 2) }));
    };
    actions.append(el("div", { id: "mesure" },
      el("label", { texte: `« ${mesure.nom} », d'après le plan, en mètres` }),
      el("div", { class: "deux-colonnes" },
        el("div", {}, el("label", { texte: "Gauche-droite" }), champX),
        el("div", {}, el("label", { texte: "Haut-bas" }), champY)),
      el("button", { class: "bouton principal", id: "m-appliquer", texte: "Corriger", onclick: verifier }),
      el("button", { class: "bouton", texte: "Revenir", onclick: () => { etat.mesure = null; rafraichir(); } }),
      conseil));
  }

  /** Couper ou enlever un morceau : la position au centimètre, à taper ou à reprendre en cliquant de nouveau sur le mur. */
  function afficherPrecision() {
    const sec = $("precision");
    sec.innerHTML = "";
    const tr = etat.trace;
    const m = tr && etat.v.logement.murs.find((x) => x.id === tr.id);
    sec.hidden = !m || (etat.outil !== "couper" && etat.outil !== "morceau");
    if (sec.hidden) return;
    const { l } = sensMur(m);
    const a = px(m.debut), b = px(m.fin);
    const couche = Math.abs(b[0] - a[0]) >= Math.abs(b[1] - a[1]);
    const nomBout = couche ? (a[0] <= b[0] ? "gauche" : "droit") : (a[1] <= b[1] ? "haut" : "bas");
    const champ = (id, rang, texte) => {
      const c = el("input", { type: "text", id, value: formatM(tr.t[rang]), inputmode: "decimal" });
      const lireChamp = () => {
        const n = lireNombre(c.value);
        if (!(n >= 0) || n > l) return message(`Tapez une distance entre 0 et ${formatM(l)} m.`, true);
        tr.t[rang] = n;
        message("");
        rafraichir();
      };
      c.addEventListener("keydown", (ev) => ev.key === "Enter" && lireChamp());
      c.addEventListener("change", lireChamp);
      return [el("label", { texte }), c];
    };
    if (etat.outil === "couper") {
      sec.append(el("h2", { texte: "Couper ce mur" }), el("p", { texte: `Il mesure ${formatM(l)} m. Tapez la position, ou cliquez ailleurs sur le mur.` }),
        ...champ("f-t1", 0, `Distance depuis le bout ${nomBout} (m)`),
        el("button", { class: "bouton principal", id: "couper-ici", texte: "Couper ici", onclick: () => {
          if (corriger((x) => C.couperMur(x, tr.id, tr.t[0]), "Mur coupé en deux : chaque morceau se retouche à part.")) changerOutil("choisir");
        } }));
      return;
    }
    sec.append(el("h2", { texte: "Enlever ce morceau de mur" }));
    if (tr.t.length < 2) {
      sec.append(el("p", { texte: "Cliquez maintenant à la fin du morceau, sur le même mur." }), ...champ("f-t1", 0, `Début, depuis le bout ${nomBout} (m)`));
      return;
    }
    sec.append(el("p", { texte: `Morceau de ${formatM(Math.abs(tr.t[1] - tr.t[0]))} m, sur un mur de ${formatM(l)} m.` }),
      ...champ("f-t1", 0, `Début, depuis le bout ${nomBout} (m)`), ...champ("f-t2", 1, `Fin, depuis le bout ${nomBout} (m)`),
      el("button", { class: "bouton principal", id: "enlever-ici", texte: "Enlever ce morceau", onclick: () => {
        if (corriger((x) => C.enleverMorceau(x, tr.id, tr.t[0], tr.t[1]), "Morceau de mur enlevé.")) changerOutil("choisir");
      } }));
  }

  function choisirPourLePoint(point, choix, nom) {
    if (choix.action.type === "outil") return changerOutil(choix.action.outil);
    if (choix.action.type === "mesurer") { etat.mesure = point.cle; return rafraichir(); }
    if (choix.action.type === "detail") {
      for (const d of point.doutes) etat.detail.add(d.cle);
      recalculer();
      return montrerPoint();
    }
    const fait = { regler: "Noté.", supprimer_tout: "Supprimé.", fusionner: "Pièces réunies.", fermer: "Mur ajouté et pièces recalculées." }[choix.action.type];
    if (corriger((x) => C.reglerPoint(x, point, choix.action, nom), fait)) {
      if (choix.action.type === "fermer") { etat.references.set(etat.v, empreinteMurs(etat.v)); sauvegarder(); }
      etat.choisi = null;
      rafraichir(); // on reste au même endroit : le résultat se regarde avant de passer au suivant
    }
  }

  /** Amène le plan sur le point en cours. */
  function montrerPoint() {
    etat.fait = null;
    const point = etat.points[etat.rangPoint];
    if (point && point.zone_px && point.genre !== "niveaux") cadrer(point.zone_px);
    else ajuster(); // « plusieurs niveaux » : le logement lu ET les parties non lues (voir ajuster)
    rafraichir();
  }

  function allerAuPoint(sens) {
    etat.rangPoint = Math.max(0, Math.min(etat.points.length - 1, etat.rangPoint + sens));
    etat.choisi = null;
    etat.mesure = null;
    montrerPoint();
  }

  /** La fiche de l'élément cliqué : ce qu'on peut y corriger. */
  function afficherFiche() {
    const sec = $("choix");
    const fiche = $("fiche");
    fiche.innerHTML = "";
    const t = etat.choisi && trouverElement(etat.choisi);
    sec.hidden = !t;
    if (!t) return;
    const { genre, e } = t;
    const supprimerBouton = (texte) => el("button", { class: "bouton danger", texte, onclick: () => supprimerChoisi() });

    if (genre === "piece") {
      $("choix-titre").textContent = `${e.nom} · ${formatM(C.surfacePolygone(e.contour), 1)} m²`;
      const liste = el("select", { id: "f-nom" }, ...[...new Set([e.nom, ...C.NOMS_PIECES])].map((n) => el("option", { value: n, texte: n })));
      liste.value = e.nom;
      liste.addEventListener("change", () => corriger((x) => C.renommerPiece(x, e.id, liste.value), `Pièce renommée « ${liste.value} ».`));
      const libre = el("input", { type: "text", id: "f-nom-libre", placeholder: "ou tapez un autre nom puis Entrée" });
      libre.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") corriger((x) => C.renommerPiece(x, e.id, libre.value), `Pièce renommée « ${libre.value.trim()} ».`);
      });
      const autres = (etat.v.logement.pieces || []).filter((p) => p.id !== e.id);
      const avec = el("select", { id: "f-fusion" }, el("option", { value: "", texte: "Réunir avec une autre pièce…" }), ...autres.map((p) => el("option", { value: p.id, texte: `${p.nom} (${formatM(C.surfacePolygone(p.contour), 1)} m²)` })));
      avec.addEventListener("change", () => {
        if (avec.value && corriger((x) => C.fusionnerPieces(x, [e.id, avec.value], e.nom), "Pièces réunies.")) rafraichir();
      });
      // B2 : les plinthes de la pièce. Atelya les suppose (règle par défaut) ou les voit sur une photo ; la personne tranche.
      const NOMS_PLINTHES = { bois: "Plinthes en bois", carrelage: "Plinthes en carrelage (comme le sol)", aucune: "Pas de plinthes" };
      const plinthes = el("select", { id: "f-plinthes" },
        ...(e.plinthes ? [] : [el("option", { value: "", texte: "Au choix d'Atelya (rien de vu)" })]),
        ...C.CHOIX_PLINTHES.map((k) => el("option", { value: k, texte: NOMS_PLINTHES[k] })));
      plinthes.value = e.plinthes ? e.plinthes.choix : "";
      plinthes.addEventListener("change", () => {
        if (plinthes.value) corriger((x) => C.reglerPlinthes(x, e.id, plinthes.value), `${NOMS_PLINTHES[plinthes.value]}.`);
      });
      const origineDe = (f) => !f ? "" : f.statut === "mesure" ? "Choisi à l'écran."
        : f.statut === "estime" ? `Vu par Atelya sur la photo (${f.source}).`
        : "Supposé par Atelya : personne ne l'a vu. À changer si besoin.";
      const origine = origineDe(e.plinthes);
      // B2 temps 2 : la corniche (moulure du plafond), même principe que les plinthes.
      const NOMS_CORNICHE = { moulure: "Corniche moulurée (gradins)", simple: "Corniche simple (une bande)", aucune: "Pas de corniche" };
      const corniche = el("select", { id: "f-corniche" },
        ...(e.corniche ? [] : [el("option", { value: "", texte: "Au choix d'Atelya (rien de vu)" })]),
        ...C.CHOIX_CORNICHE.map((k) => el("option", { value: k, texte: NOMS_CORNICHE[k] })));
      corniche.value = e.corniche ? e.corniche.choix : "";
      corniche.addEventListener("change", () => {
        if (corniche.value) corriger((x) => C.reglerCorniche(x, e.id, corniche.value), `${NOMS_CORNICHE[corniche.value]}.`);
      });
      // B2-2 : les portes d'un placard, même principe que les plinthes.
      const placard = [];
      if (C.estPlacard(e)) {
        const NOMS_PLACARD = { coulissantes: "Portes coulissantes", battantes: "Portes battantes (comme une armoire)", aucune: "Pas de portes (placard ouvert)" };
        const portes = el("select", { id: "f-placard" },
          ...(e.placard ? [] : [el("option", { value: "", texte: "Au choix d'Atelya (rien de vu)" })]),
          ...C.CHOIX_PLACARD.map((k) => el("option", { value: k, texte: NOMS_PLACARD[k] })));
        portes.value = e.placard ? e.placard.choix : "";
        portes.addEventListener("change", () => {
          if (portes.value) corriger((x) => C.reglerPlacard(x, e.id, portes.value), `${NOMS_PLACARD[portes.value]}.`);
        });
        placard.push(el("label", { texte: "Portes du placard" }), portes, el("p", { class: "aide", texte: origineDe(e.placard) }));
      }
      // B2-3 : le sol de la pièce.
      const sol = el("select", { id: "f-sol" },
        ...(e.sol ? [] : [el("option", { value: "", texte: "Au choix d'Atelya (rien de vu)" })]),
        ...Object.entries(C.SOLS).map(([k, n]) => el("option", { value: k, texte: n })));
      sol.value = e.sol ? e.sol.matiere : "";
      sol.addEventListener("change", () => {
        if (sol.value) corriger((x) => C.reglerSol(x, e.id, sol.value), `Sol : ${C.SOLS[sol.value]}.`);
      });
      fiche.append(el("label", { texte: "Nom de la pièce" }), liste, libre,
        el("label", { texte: "Sol" }), sol, el("p", { class: "aide", texte: origineDe(e.sol) }),
        el("label", { texte: "Plinthes (la planche au pied des murs)" }), plinthes, el("p", { class: "aide", texte: origine }), ...placard,
        el("label", { texte: "Corniche (la moulure autour du plafond)" }), corniche, el("p", { class: "aide", texte: origineDe(e.corniche) }),
        el("label", { texte: "Une seule pièce avec une autre ?" }), avec,
        el("div", { class: "ligne" }, supprimerBouton("Supprimer cette pièce")));
    } else if (genre === "ouverture") {
      $("choix-titre").textContent = `${NOMS_OUVERTURES[e.type]} de ${formatM(e.largeur)} m`;
      const type = el("select", { id: "f-type" }, ...Object.entries(NOMS_OUVERTURES).map(([k, n]) => el("option", { value: k, texte: n })));
      type.value = e.type;
      type.addEventListener("change", () => corriger((x) => C.modifierOuverture(x, e.id, { type: type.value }), "Type changé."));
      const larg = el("input", { type: "text", id: "f-largeur", value: formatM(e.largeur) });
      const pos = el("input", { type: "text", id: "f-position", value: formatM(e.position) });
      const appliquer = () => {
        const l = lireNombre(larg.value), p = lireNombre(pos.value);
        if (!(l > 0) || !(p >= 0)) return message("Tapez un nombre en mètres, par exemple 0,83.", true);
        corriger((x) => C.modifierOuverture(x, e.id, { largeur: l, position: p }), "Mesures corrigées.");
      };
      for (const champ of [larg, pos]) champ.addEventListener("keydown", (ev) => ev.key === "Enter" && appliquer());
      fiche.append(el("p", { class: "info", texte: "À la souris : faites-la glisser le long du mur (ou jusqu'à un autre mur) ; "
          + "tirez un des ronds à ses bords pour changer sa largeur. Elle se colle seule contre un angle à moins de 8 cm." }),
        el("label", { texte: "C'est…" }), type,
        el("label", { texte: "Largeur en mètres, puis Entrée" }), larg,
        el("details", {}, el("summary", { texte: "La déplacer le long du mur" }), el("label", { texte: "Distance depuis le bout du mur (m), puis Entrée" }), pos),
        el("div", { class: "ligne" }, supprimerBouton("Supprimer")));
    } else {
      const l = C.longueur(e.debut, e.fin);
      $("choix-titre").textContent = `Mur de ${formatM(l)} m`;
      const cote = el("input", { type: "text", id: "f-cote", placeholder: `lue : ${formatM(l)} m` });
      const ep = el("input", { type: "text", id: "f-epaisseur", value: formatM(e.epaisseur) });
      const pasEpaisseur = (delta) => {
        const n = Math.round((e.epaisseur + delta) * 1000) / 1000;
        if (n >= 0.02) corriger((x) => C.modifierMur(x, e.id, { epaisseur: n }), `Épaisseur : ${formatM(n)} m.`);
      };
      const lue = () => {
        const n = lireNombre(cote.value);
        if (!(n > 0)) { message("Tapez la longueur en mètres, par exemple 4,80.", true); return null; }
        return n;
      };
      ep.addEventListener("keydown", (ev) => {
        if (ev.key !== "Enter") return;
        const n = lireNombre(ep.value);
        if (n > 0) corriger((x) => C.modifierMur(x, e.id, { epaisseur: n }), "Épaisseur corrigée.");
      });
      fiche.append(el("label", { texte: "Sa vraie longueur d'après le plan (m)" }), cote,
        el("div", { class: "ligne" },
          el("button", { class: "bouton principal", texte: "Tout mettre à la bonne taille", title: "Toutes les mesures du plan sont corrigées dans la même proportion",
            onclick: () => { const n = lue(); if (n) corriger((x) => C.mettreAEchelle(x, n / l), "Toutes les mesures du plan sont corrigées."); } }),
          el("button", { class: "bouton", texte: "Ce mur seulement", onclick: () => { const n = lue(); if (n) corriger((x) => C.longueurMur(x, e.id, n), "Longueur du mur corrigée."); } })),
        ...deplacementPrecis(e),
        el("label", { texte: "Épaisseur en mètres" }),
        el("div", { class: "reglage" },
          el("button", { class: "bouton", id: "f-ep-moins", texte: "−", title: "1 cm de moins", onclick: () => pasEpaisseur(-0.01) }), ep,
          el("button", { class: "bouton", id: "f-ep-plus", texte: "+", title: "1 cm de plus", onclick: () => pasEpaisseur(0.01) })),
        el("p", { class: "info", texte: "Pour le rallonger : tirez un des ronds à ses bouts. Pour le déplacer : faites-le glisser." }),
        el("div", { class: "ligne" },
          el("button", { class: "bouton", texte: "Le couper", onclick: () => changerOutil("couper") }),
          el("button", { class: "bouton", texte: "Enlever un morceau", onclick: () => changerOutil("morceau") })),
        el("div", { class: "ligne" }, supprimerBouton("Supprimer ce mur")));
    }
  }

  /** Déplacer un mur d'une distance exacte, dans un sens clair à l'écran. */
  function deplacementPrecis(e) {
    const { d } = sensMur(e);
    const n = [-d[1], d[0]];
    const milieu = [(e.debut[0] + e.fin[0]) / 2, (e.debut[1] + e.fin[1]) / 2];
    const a = px(milieu), b = px([milieu[0] + n[0], milieu[1] + n[1]]);
    const couche = Math.abs(b[1] - a[1]) >= Math.abs(b[0] - a[0]); // la normale va vers le haut ou le bas de l'écran
    const positif = couche ? (b[1] < a[1] ? "↑ Haut" : "↓ Bas") : (b[0] > a[0] ? "→ Droite" : "← Gauche");
    const negatif = couche ? (b[1] < a[1] ? "↓ Bas" : "↑ Haut") : (b[0] > a[0] ? "← Gauche" : "→ Droite");
    const champ = el("input", { type: "text", id: "f-deplace", inputmode: "decimal", placeholder: "en centimètres", value: etat.deplacementPropose == null ? "" : String(etat.deplacementPropose) });
    const pousser = (signe) => {
      const cm = lireNombre(champ.value);
      if (!(cm > 0)) return message("Tapez le déplacement en centimètres, par exemple 10.", true);
      const k = (signe * cm) / 100;
      if (corriger((x) => C.deplacerMur(x, e.id, [n[0] * k, n[1] * k]), `Mur déplacé de ${cm} cm.`)) etat.deplacementPropose = null;
      rafraichir();
    };
    const boutons = [[positif, 1], [negatif, -1]].sort((u, w) => (u[0] < w[0] ? -1 : 1));
    return [el("label", { texte: "Le déplacer exactement de (cm)" }), champ,
      el("div", { class: "ligne" }, ...boutons.map(([t, signe]) => el("button", { class: "bouton", texte: t, "data-sens": String(signe), onclick: () => pousser(signe) })))];
  }

  function choisir(id) {
    etat.choisi = id;
    rafraichir();
  }

  function supprimerChoisi() {
    if (!etat.choisi) return;
    const nom = nomDe(etat.choisi);
    if (corriger((x) => C.supprimer(x, etat.choisi), `${nom} : supprimé.`)) etat.choisi = null;
    rafraichir();
  }

  function epaisseurNouveauMur() {
    return 0.1; // une cloison ; à corriger ensuite dans la fiche si c'est un mur porteur
  }

  function changerOutil(outil) {
    etat.outil = outil;
    etat.depart = null;
    etat.trace = null;
    etat.relier = null;
    if (outil !== "choisir" && etat.affichage === "plan") etat.affichage = "deux";
    $("menu-ajouter").hidden = true;
    $("ouvrir-ajouter").setAttribute("aria-expanded", "false");
    rafraichir();
  }

  function message(texte, erreur = false) {
    const m = $("message");
    m.textContent = texte;
    m.className = erreur ? "erreur" : "info";
  }

  // ---------- Souris ----------

  function appui(ev) {
    if (!etat.v) return;
    canvas.setPointerCapture(ev.pointerId);
    const p = ecranVersMetres(ev);
    const tol = metresPour(VISEE, p);
    const lg = etat.v.logement;

    // Une poignée du mur choisi passe avant une pastille posée au même endroit.
    const murPoignee = etat.choisi && lg.murs.find((m) => m.id === etat.choisi);
    const surPoignee = murPoignee && ["debut", "fin"].some((b) => C.longueur(p, murPoignee[b]) <= metresPour(VISEE * 1.5, p));
    const pastille = surPoignee ? null : pastilleSous(ev);
    if (pastille) {
      etat.rangPoint = pastille.rang;
      etat.choisi = null;
      etat.mesure = null;
      montrerPoint();
      return;
    }
    if (etat.affichage === "plan") { // le plan seul : on ne fait que le regarder
      etat.glisse = { genre: "vue", dernier: [ev.clientX, ev.clientY] };
      return;
    }
    if (etat.outil === "mur") {
      const q = C.aimanter(lg, p, etat.depart, metresPour(VISEE * 1.5, p));
      if (!etat.depart) { etat.depart = q; dessiner(); return; }
      if (corriger((x) => C.ajouterMur(x, etat.depart, q, epaisseurNouveauMur()), "Mur ajouté (cloison de 10 cm).")) {
        etat.choisi = etat.v.logement.murs[etat.v.logement.murs.length - 1].id;
        changerOutil("choisir");
      }
      return;
    }
    if (etat.outil in NOMS_OUVERTURES) {
      const m = C.murLePlusProche(lg, p, tol * 2);
      if (!m) return message("Cliquez sur un mur (ou tout près).", true);
      if (corriger((x) => C.ajouterOuverture(x, m.id, etat.outil, m.le_long), `${NOMS_OUVERTURES[etat.outil]} ajoutée.`)) {
        const o = etat.v.logement.ouvertures;
        etat.choisi = o[o.length - 1].id;
        changerOutil("choisir");
      }
      return;
    }
    if (etat.outil === "couper" || etat.outil === "morceau") {
      const m = C.murLePlusProche(lg, p, tol * 2);
      if (!m) return message("Cliquez sur un mur (ou tout près).", true);
      const t = C.aimanterSurMur(lg, m.id, m.le_long, metresPour(VISEE, p)).t;
      const tr = etat.trace;
      if (!tr || tr.id !== m.id) etat.trace = { id: m.id, t: [t] };
      else if (etat.outil === "couper") tr.t = [t];
      else if (tr.t.length < 2) tr.t.push(t);
      else tr.t[Math.abs(t - tr.t[0]) <= Math.abs(t - tr.t[1]) ? 0 : 1] = t; // reprend la marque la plus proche
      message("");
      rafraichir();
      return;
    }
    if (etat.outil === "relier") {
      const b = C.boutLePlusProche(lg, p, metresPour(VISEE * 2, p), etat.relier && etat.relier.id);
      if (!b) return message(etat.relier ? "Cliquez sur le bout de l'autre mur." : "Cliquez sur le bout d'un mur (un des petits ronds).", true);
      if (!etat.relier) { etat.relier = b; message("Cliquez maintenant sur le bout de l'autre mur."); dessiner(); return; }
      const a = etat.relier;
      if (corriger((x) => C.relierMurs(x, a.id, a.bout, b.id, b.bout), "Murs reliés.")) changerOutil("choisir");
      return;
    }
    const murOuvert = etat.choisi && lg.murs.find((m) => m.id === etat.choisi);
    if (murOuvert) {
      const rayon = metresPour(VISEE * 1.5, p);
      for (const bout of ["debut", "fin"]) {
        if (C.longueur(p, murOuvert[bout]) <= rayon) {
          etat.glisse = { genre: "bout", id: murOuvert.id, bout, bouge: false };
          return;
        }
      }
    }
    const ouvertureOuverte = etat.choisi && (lg.ouvertures || []).find((o) => o.id === etat.choisi);
    if (ouvertureOuverte) {
      const bords = C.bordsOuverture(lg, ouvertureOuverte);
      const rayon = metresPour(VISEE * 1.2, p);
      for (const bord of [0, 1]) {
        if (bords && C.longueur(p, bords[bord]) <= rayon) {
          etat.glisse = { genre: "bord", id: ouvertureOuverte.id, bord, bouge: false };
          return;
        }
      }
    }
    const sous = C.elementSous(lg, p, tol);
    if (sous) {
      etat.choisi = sous.id;
      if (sous.genre === "mur") etat.glisse = { genre: "mur", id: sous.id, depart: p, bouge: false };
      if (sous.genre === "ouverture") etat.glisse = { genre: "ouverture", id: sous.id, depart: p, bouge: false };
      rafraichir();
    } else {
      etat.choisi = null;
      etat.glisse = { genre: "vue", dernier: [ev.clientX, ev.clientY] };
      rafraichir();
    }
  }

  function mouvement(ev) {
    if (!etat.v) return;
    const p = ecranVersMetres(ev);
    etat.souris = p;
    if (!etat.glisse && etat.outil === "choisir") canvas.style.cursor = pastilleSous(ev) ? "pointer" : "grab";
    const g = etat.glisse;
    if (g && g.genre === "vue") {
      etat.vue.dx += ev.clientX - g.dernier[0];
      etat.vue.dy += ev.clientY - g.dernier[1];
      g.dernier = [ev.clientX, ev.clientY];
    } else if (g && g.genre === "bout") {
      const a = C.accrocherBout(etat.v.logement, g.id, g.bout, p, metresPour(VISEE * 1.5, p));
      etat.accroche = a.accroche ? a.point : null;
      try {
        etat.apercu = C.deplacerBout(etat.v, g.id, g.bout, a.point);
        g.point = a.point;
        g.erreur = null;
      } catch (e) {
        g.erreur = e.message; // on garde l'aperçu précédent
      }
    } else if (g && (g.genre === "ouverture" || g.genre === "bord")) {
      if (g.genre === "bord" || C.longueur(p, g.depart) > metresPour(3, p)) g.bouge = true;
      if (g.bouge) {
        try {
          etat.apercu = g.genre === "bord" ? C.etirerOuverture(etat.v, g.id, g.bord, p)
            : C.deplacerOuverture(etat.v, g.id, p, metresPour(VISEE * 2, p));
          g.point = p;
          g.erreur = null;
        } catch (e) { g.erreur = e.message; } // on garde l'aperçu précédent
      }
    } else if (g && g.genre === "mur") {
      const delta = [p[0] - g.depart[0], p[1] - g.depart[1]];
      if (Math.hypot(...delta) > metresPour(3, p)) g.bouge = true;
      if (g.bouge) {
        try { etat.apercu = C.deplacerMur(etat.v, g.id, delta); g.delta = delta; } catch (e) { /* on garde l'aperçu précédent */ }
      }
    }
    dessiner();
  }

  function relache() {
    const g = etat.glisse;
    etat.glisse = null;
    etat.apercu = null;
    etat.accroche = null;
    if (g && g.genre === "bout") {
      if (g.erreur) message(g.erreur, true);
      if (g.point) corriger((x) => C.deplacerBout(x, g.id, g.bout, g.point), "Bout du mur déplacé.");
      else dessiner();
    } else if (g && g.genre === "ouverture" && g.bouge && g.point) {
      if (g.erreur) message(g.erreur, true);
      corriger((x) => C.deplacerOuverture(x, g.id, g.point, metresPour(VISEE * 2, g.point)),
        "Ouverture déplacée (elle reste dans le mur, sans déborder dans un angle).");
    } else if (g && g.genre === "bord" && g.bouge && g.point) {
      corriger((x) => C.etirerOuverture(x, g.id, g.bord, g.point), "Largeur de l'ouverture changée.");
    } else if (g && g.genre === "mur" && g.bouge && g.delta) {
      corriger((x) => C.deplacerMur(x, g.id, g.delta), "Mur déplacé (les murs et pièces qui le touchent ont suivi).");
    } else dessiner();
  }

  // ---------- Valider ----------

  function demander(titre, texte) {
    return new Promise((reponse) => {
      $("confirmation-titre").textContent = titre;
      $("confirmation-texte").textContent = texte;
      $("fond-confirmation").hidden = false;
      const fin = (oui) => { $("fond-confirmation").hidden = true; reponse(oui); };
      $("confirmation-oui").onclick = () => fin(true);
      $("confirmation-non").onclick = () => fin(false);
    });
  }

  async function valider() {
    if (!etat.v) return;
    const erreurs = C.verifierCoherence(etat.v.logement);
    if (erreurs.length) {
      message("Impossible de terminer : " + erreurs.join(" ; "), true);
      return;
    }
    if (empreinteMurs(etat.v) !== etat.references.get(etat.v)) {
      const ok = await demander("Les pièces ne sont pas à jour",
        "Vous avez changé des murs sans recalculer les pièces : leurs surfaces peuvent être fausses. Revenez cliquer sur « Recalculer les pièces », ou terminez quand même.");
      if (!ok) return;
    }
    if (etat.points.length) {
      const ok = await demander(`Il reste ${etat.points.length} point(s) à vérifier`,
        "Vous pouvez revenir les vérifier, ou terminer quand même : ce qui reste en doute sera noté dans le rapport.");
      if (!ok) return;
    }
    const r = C.resultat(etat.v, { corrections: etat.historique.length });
    etat.resultat = r;
    if (integre && origineSite) {
      versSite({ type: PREFIXE + "valide", resultat: r });
      message("Vérification envoyée au site.");
    } else {
      telecharger(`${r.projet_id}-logement.json`, r.logement);
      message("Logement corrigé enregistré (dossier Téléchargements).");
    }
  }

  function telecharger(nom, objet) {
    const blob = new Blob([JSON.stringify(objet, null, 2) + "\n"], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = nom;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  async function ouvrirDepuisSite(verification, plan) {
    try {
      const source = plan instanceof Blob ? URL.createObjectURL(plan) : plan;
      ouvrir(verification, await chargerImage(source));
    } catch (e) {
      message("Ouverture impossible : " + e.message, true);
    }
  }

  window.addEventListener("message", (ev) => {
    if (!integre || ev.source !== window.parent || ev.origin !== origineSite) return; // messages d'ailleurs : ignorés
    const m = ev.data || {};
    if (m.type === PREFIXE + "ouvrir") ouvrirDepuisSite(m.verification, m.plan);
  });

  // ---------- Événements ----------

  $("fichiers").addEventListener("change", (ev) => ouvrirFichiers(ev.target.files));
  $("exemple").addEventListener("click", ouvrirExemple);
  $("zoom-plus").addEventListener("click", () => zoomer(1.25));
  $("zoom-moins").addEventListener("click", () => zoomer(0.8));
  $("zoom-ajuster").addEventListener("click", ajuster);
  $("annuler").addEventListener("click", annuler);
  $("valider").addEventListener("click", valider);
  document.querySelectorAll("[data-vue]").forEach((b) => b.addEventListener("click", () => {
    etat.affichage = b.dataset.vue;
    etat.choisi = null;
    if (etat.outil !== "choisir") changerOutil("choisir");
    rafraichir();
  }));
  function refairePieces() {
    if (!etat.v) return;
    const r = C.piecesDepuisMurs(etat.v.logement);
    const parties = [`${r.pieces.length} pièce(s)`];
    if (r.reunies) parties.push(`${r.reunies} réunie(s) à une voisine`);
    if (r.nouvelles) parties.push(`${r.nouvelles} nouvelle(s)`);
    if (r.ouvertes.length) parties.push(`${r.ouvertes.length} pas fermée(s) : suivez les points ci-dessus`);
    etat.fermeture = true;
    if (corriger((x) => C.recalculerPieces(x), parties.join(" ; ") + ".")) {
      etat.references.set(etat.v, empreinteMurs(etat.v));
      etat.rangPoint = 0;
      etat.choisi = null;
      montrerPoint();
      sauvegarder();
    }
  }
  $("telecharger-travail").addEventListener("click", () => {
    if (etat.v) telecharger(`${etat.v.logement.projet_id}-travail.json`, photoDuTravail());
  });
  $("fichier-travail").addEventListener("change", async (ev) => {
    const f = ev.target.files[0];
    ev.target.value = "";
    if (!f || !etat.v) return;
    try { reprendre(JSON.parse(await lireTexte(f))); } catch (e) { message("Ce fichier est illisible : " + e.message, true); }
  });
  $("repartir").addEventListener("click", repartir);
  $("recalculer-pieces").addEventListener("click", refairePieces);
  $("recalculer-pieces-2").addEventListener("click", refairePieces);
  $("point-precedent").addEventListener("click", () => allerAuPoint(-1));
  $("point-suivant").addEventListener("click", () => allerAuPoint(1));
  $("fermer-choix").addEventListener("click", () => choisir(null));
  $("arreter-outil").addEventListener("click", () => changerOutil("choisir"));
  const volet = (bouton, cible) => $(bouton).addEventListener("click", () => {
    const ouvert = $(cible).hidden;
    $(cible).hidden = !ouvert;
    $(bouton).setAttribute("aria-expanded", String(ouvert));
    if (ouvert && cible !== "menu-ajouter") $(cible).scrollIntoView({ block: "start" });
  });
  volet("ouvrir-ajouter", "menu-ajouter");
  volet("ouvrir-pieces", "liste-pieces");
  volet("ouvrir-aide", "aide");
  $("abandonner").addEventListener("click", () => { versSite({ type: PREFIXE + "abandon" }); message("Vérification abandonnée."); });
  $("refaire").addEventListener("click", refaire);
  document.querySelectorAll("[data-outil]").forEach((b) => b.addEventListener("click", () => changerOutil(b.dataset.outil)));

  const zone = $("zone");
  zone.addEventListener("dragover", (ev) => { ev.preventDefault(); zone.classList.add("depot"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("depot"));
  zone.addEventListener("drop", (ev) => { ev.preventDefault(); zone.classList.remove("depot"); ouvrirFichiers(ev.dataTransfer.files); });

  canvas.addEventListener("pointerdown", appui);
  canvas.addEventListener("pointermove", mouvement);
  canvas.addEventListener("pointerup", relache);
  canvas.addEventListener("pointercancel", relache);
  canvas.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const r = canvas.getBoundingClientRect();
    zoomer(Math.exp(-ev.deltaY / (ev.ctrlKey ? 100 : 300)), [ev.clientX - r.left, ev.clientY - r.top]);
  }, { passive: false });
  window.addEventListener("keydown", (ev) => {
    const dansChamp = ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName);
    const cmd = ev.metaKey || ev.ctrlKey;
    if (cmd && ev.key.toLowerCase() === "z") { ev.preventDefault(); ev.shiftKey ? refaire() : annuler(); return; }
    if (cmd && ev.key.toLowerCase() === "y") { ev.preventDefault(); refaire(); return; }
    if (dansChamp) return;
    if (ev.key === "Escape") { etat.depart = null; etat.choisi = null; changerOutil("choisir"); }
    if ((ev.key === "Delete" || ev.key === "Backspace") && etat.choisi) { ev.preventDefault(); supprimerChoisi(); }
    if (ev.key === "+" || ev.key === "=") zoomer(1.25);
    if (ev.key === "-") zoomer(0.8);
  });
  window.addEventListener("resize", dessiner);
  rafraichir();

  // Au démarrage : dans le site, on se cache des boutons inutiles et on prévient qu'on est prêt.
  if (integre) {
    $("abandonner").hidden = false;
    $("accueil").textContent = "En attente du plan envoyé par le site…";
    if (!origineSite) message("Adresse du site inconnue : ajoutez ?origine=https://… à l'adresse de l'écran.", true);
    versSite({ type: PREFIXE + "pret", version: C.VERSION_VERIFICATION });
  }
  // Ou bien : ?verification=…&plan=… (adresses des deux fichiers, sur le même site que l'écran).
  if (parametres.get("verification") && parametres.get("plan")) {
    fetch(parametres.get("verification"))
      .then((r) => { if (!r.ok) throw new Error(`fichier de vérification introuvable (${r.status})`); return r.json(); })
      .then((v) => ouvrirDepuisSite(v, parametres.get("plan")))
      .catch((e) => message("Ouverture impossible : " + e.message, true));
  }
})();

