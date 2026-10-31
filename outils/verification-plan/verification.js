/*
 * L'écran de vérification : le plan d'origine en fond, la lecture d'Atelya par-dessus,
 * les doutes en orange, et les corrections (étape B).
 * Les calculs (et toutes les corrections) sont dans calculs-verif.js ; ici, seulement
 * les clics, le panneau de droite et le dessin.
 */
(function () {
  "use strict";

  const C = window.CalculsVerif;
  const COULEURS = {
    mur: "#1d4ed8",
    porte: "#16a34a",
    fenetre: "#0891b2",
    porte_fenetre: "#9333ea",
    piece: "rgba(147, 197, 253, 0.35)",
    pieceBord: "#3b82f6",
    doute: "#ea580c",
    douteFond: "rgba(234, 88, 12, 0.28)",
    choisi: "#facc15",
  };
  const NOMS_OUVERTURES = { porte: "Porte", fenetre: "Fenêtre", porte_fenetre: "Porte-fenêtre" };
  const CONSIGNE_COMPARER = "Comparez le plan et ce qu'Atelya a lu (curseur de transparence à droite). Glisser pour se déplacer, molette pour zoomer.";
  const CONSIGNES = {
    choisir: "Cliquez un élément pour le corriger. Glissez un mur pour le déplacer. Glissez ailleurs pour vous déplacer.",
    mur: "Cliquez le premier bout du mur, puis le second. Échap pour abandonner.",
    porte: "Cliquez sur un mur, à l'endroit de la porte.",
    fenetre: "Cliquez sur un mur, à l'endroit de la fenêtre.",
    porte_fenetre: "Cliquez sur un mur, à l'endroit de la porte-fenêtre.",
  };
  const VISEE = 8; // pixels d'écran : à quelle distance un clic « touche » un élément

  const etat = {
    v: null, // le fichier de vérification en cours (corrigé au fil des clics)
    image: null,
    matrice: null,
    inverse: null,
    doutes: [],
    douteux: new Set(),
    resultat: null, // le dernier résultat validé
    choisi: null, // id de l'élément choisi
    douteChoisi: null, // clé du doute choisi
    outil: "choisir",
    corriger: false, // false : on regarde et on compare seulement ; true : les outils de correction apparaissent
    depart: null, // premier bout d'un mur en cours d'ajout (m)
    souris: null, // position de la souris (m)
    glisse: null, // {genre: "vue"|"mur", ...}
    apercu: null, // copie corrigée affichée pendant qu'on glisse un mur
    historique: [],
    refaire: [],
    vue: { zoom: 1, dx: 0, dy: 0 },
    calques: { pieces: true, murs: true, ouvertures: true },
    opacite: 0.7,
  };
  window.Verification = { etat }; // lecture seule, pour les tests automatiques

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
    etat.douteChoisi = null;
    $("accueil").style.display = "none";
    message("");
    recalculer();
    ajuster();
    rafraichir();
  }

  function recalculer() {
    etat.matrice = C.matriceDuCalage(etat.v.calage);
    etat.inverse = C.inverse(etat.matrice);
    etat.doutes = C.trouverDoutes(etat.v);
    etat.douteux = new Set(etat.doutes.map((d) => d.element).filter(Boolean));
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
      etat.historique.push(etat.v);
      etat.refaire = [];
      etat.v = nouveau;
      recalculer();
      message(texte || "");
      rafraichir();
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
    recalculer();
    message("Dernière correction annulée.");
    rafraichir();
  }

  function refaire() {
    if (!etat.refaire.length) return;
    etat.historique.push(etat.v);
    etat.v = etat.refaire.pop();
    recalculer();
    message("Correction rétablie.");
    rafraichir();
  }

  // ---------- Vue ----------

  function ajuster() {
    if (!etat.image) return;
    const r = canvas.getBoundingClientRect();
    const z = Math.min(r.width / etat.image.naturalWidth, r.height / etat.image.naturalHeight) * 0.95;
    etat.vue = { zoom: z, dx: (r.width - etat.image.naturalWidth * z) / 2, dy: (r.height - etat.image.naturalHeight * z) / 2 };
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

  /** Centre la vue sur un rectangle de pixels du plan [x, y, l, h]. */
  function cadrer(rect) {
    const r = canvas.getBoundingClientRect();
    const marge = 400;
    const z = Math.min(2.5, r.width / (rect[2] + marge), r.height / (rect[3] + marge));
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

  function rectangleDuDoute(d) {
    if (d.zone_px) return d.zone_px;
    const e = formeDe(d.element);
    return e ? rectangleDe(e.points) : null;
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
    ctx.drawImage(etat.image, 0, 0);

    const v = etat.apercu || etat.v;
    const f = formes(v);
    const trait = 1 / z; // un pixel d'écran

    ctx.globalAlpha = etat.opacite;
    if (etat.calques.pieces) {
      for (const p of f.pieces) {
        const doute = etat.douteux.has(p.id);
        chemin(p.points);
        ctx.fillStyle = doute ? COULEURS.douteFond : COULEURS.piece;
        ctx.fill();
        ctx.lineWidth = (doute ? 3 : 1.5) * trait;
        ctx.strokeStyle = doute ? COULEURS.doute : COULEURS.pieceBord;
        ctx.setLineDash(doute ? [] : [6 * trait, 4 * trait]);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
    if (etat.calques.murs) {
      for (const m of f.murs) {
        chemin(m.points);
        ctx.fillStyle = etat.douteux.has(m.id) ? COULEURS.doute : COULEURS.mur;
        ctx.fill();
      }
    }
    if (etat.calques.ouvertures) {
      for (const o of f.ouvertures) {
        chemin(o.points);
        ctx.fillStyle = COULEURS[o.type] || COULEURS.porte;
        ctx.fill();
        if (etat.douteux.has(o.id)) {
          ctx.lineWidth = 4 * trait;
          ctx.strokeStyle = COULEURS.doute;
          ctx.stroke();
        }
      }
    }
    ctx.globalAlpha = 1;

    for (const d of etat.doutes) {
      if (!d.zone_px) continue;
      const [x, y, l, h] = d.zone_px;
      ctx.fillStyle = COULEURS.douteFond;
      ctx.fillRect(x, y, l, h);
      ctx.lineWidth = 2 * trait;
      ctx.strokeStyle = COULEURS.doute;
      ctx.strokeRect(x, y, l, h);
    }

    // L'élément choisi : contour jaune bien visible.
    const choisi = etat.choisi && [...f.murs, ...f.ouvertures, ...f.pieces].find((x) => x.id === etat.choisi);
    if (choisi) {
      chemin(choisi.points);
      ctx.lineWidth = 4 * trait;
      ctx.strokeStyle = COULEURS.choisi;
      ctx.stroke();
    }

    if (etat.calques.pieces) {
      ctx.textAlign = "center";
      for (const p of f.pieces) etiquette(p.centre, [p.nom, `${formatM(p.surface)} m²`], etat.douteux.has(p.id), z);
    }

    // Le doute choisi dans la liste : un cadre pointillé.
    const dc = etat.doutes.find((d) => d.cle === etat.douteChoisi);
    const rect = dc && rectangleDuDoute(dc);
    if (rect) {
      const m = 10 * trait;
      ctx.lineWidth = 3 * trait;
      ctx.strokeStyle = COULEURS.doute;
      ctx.setLineDash([8 * trait, 5 * trait]);
      ctx.strokeRect(rect[0] - m, rect[1] - m, rect[2] + 2 * m, rect[3] + 2 * m);
      ctx.setLineDash([]);
    }

    // Le mur en cours d'ajout.
    if (etat.outil === "mur" && etat.depart && etat.souris) {
      const fin = C.aimanter(etat.v.logement, etat.souris, etat.depart, metresPour(VISEE * 1.5, etat.souris));
      const ep = epaisseurNouveauMur();
      if (C.longueur(etat.depart, fin) > 0.01) {
        chemin(C.polygoneMur({ debut: etat.depart, fin, epaisseur: ep }).map(px));
        ctx.fillStyle = "rgba(29, 78, 216, 0.5)";
        ctx.fill();
        const a = px(etat.depart), b = px(fin);
        etiquette([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 18 * trait], [`${formatM(C.longueur(etat.depart, fin))} m`], false, z);
      }
    }
  }

  function etiquette(pos, lignes, doute, z) {
    const taille = 13 / z;
    ctx.textAlign = "center";
    ctx.font = `600 ${taille}px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
    const larg = Math.max(...lignes.map((l) => ctx.measureText(l).width)) + 10 / z;
    const haut = lignes.length * taille * 1.3 + 6 / z;
    const x = pos[0] - larg / 2, y = pos[1] - haut / 2;
    ctx.fillStyle = doute ? "#fff7ed" : "rgba(255,255,255,0.9)";
    ctx.strokeStyle = doute ? COULEURS.doute : COULEURS.pieceBord;
    ctx.lineWidth = 1.5 / z;
    ctx.beginPath();
    ctx.roundRect(x, y, larg, haut, 4 / z);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = doute ? "#9a3412" : "#1e3a8a";
    lignes.forEach((l, i) => {
      ctx.font = `${i ? 400 : 600} ${taille}px -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif`;
      ctx.fillText(l, pos[0], y + 3 / z + taille * (1.05 + i * 1.3));
    });
  }

  // ---------- Panneau de droite ----------

  function nomDe(id) {
    if (id == null) return "Zone du plan";
    const t = trouverElement(id);
    if (!t) return id;
    if (t.genre === "piece") return `Pièce « ${t.e.nom} »`;
    if (t.genre === "ouverture") return `${NOMS_OUVERTURES[t.e.type]} ${t.e.id}`;
    return `Mur ${id}`;
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
    $("refaire").disabled = !etat.refaire.length;
    document.querySelectorAll("[data-outil]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.outil === etat.outil)));
    $("consigne").textContent = etat.corriger ? CONSIGNES[etat.outil] : CONSIGNE_COMPARER;
    document.body.classList.toggle("comparer", !etat.corriger);
    $("mode-corriger").setAttribute("aria-pressed", String(etat.corriger));
    canvas.style.cursor = etat.outil === "choisir" ? "default" : "crosshair";
    if (!v) return;
    const lg = v.logement;
    $("titre").textContent = `${lg.projet_id}${v.plan ? " — " + v.plan : ""}`;

    const ech = v.echelle || {};
    $("bandeau").textContent = ech.etat === "a_verifier"
      ? `Échelle à vérifier : ${ech.raison || "Atelya n'a pas pu la confirmer"}. Choisissez un mur coté et tapez sa vraie longueur.`
      : "";

    // Les doutes, avec leurs propositions en un clic.
    $("nb-doutes").textContent = `(${etat.doutes.length})`;
    const ul = $("doutes");
    ul.innerHTML = "";
    if (!etat.doutes.length) ul.append(el("p", { class: "info", texte: "Plus rien à vérifier." }));
    for (const d of etat.doutes) {
      const props = el("div", { class: "propositions" });
      for (const p of d.propositions || []) {
        props.append(el("button", {
          texte: p.libelle,
          onclick: (ev) => {
            ev.stopPropagation();
            corriger((x) => C.appliquerAction(x, p.action, d), `« ${p.libelle} » appliqué.`);
          },
        }));
      }
      const li = el("li", {
        onclick: () => {
          etat.douteChoisi = d.cle;
          etat.choisi = d.element;
          const rect = rectangleDuDoute(d);
          if (rect) cadrer(rect);
          rafraichir();
        },
      }, el("strong", { texte: nomDe(d.element) }), el("br"), d.raison, props);
      if (d.cle === etat.douteChoisi) li.className = "choisi";
      ul.append(li);
    }

    afficherFiche();

    const erreurs = C.verifierCoherence(lg);
    const coh = $("coherence");
    coh.innerHTML = "";
    if (!erreurs.length) coh.append(el("span", { class: "ok", texte: "Oui : le logement est complet et cohérent." }));
    else coh.append(el("span", { texte: "Pas encore :" }), el("ul", {}, ...erreurs.map((e) => el("li", { texte: e }))));

    const tb = $("pieces");
    tb.innerHTML = "";
    let total = 0;
    for (const p of lg.pieces || []) {
      const s = C.surfacePolygone(p.contour);
      total += s;
      const tr = el("tr", { onclick: () => choisir(p.id) }, el("td", { texte: p.nom }), el("td", { class: "nb", texte: `${formatM(s)} m²` }));
      if (etat.douteux.has(p.id)) tr.className = "douteux";
      tb.append(tr);
    }
    const nbP = (lg.ouvertures || []).filter((o) => o.type === "porte").length;
    const nbF = (lg.ouvertures || []).length - nbP;
    $("resume").textContent = `Total ${formatM(total)} m² · ${lg.murs.length} murs · ${nbP} portes · ${nbF} fenêtres et portes-fenêtres`;
    dessiner();
  }

  /** La fiche de l'élément choisi : ce qu'on peut y corriger. */
  function afficherFiche() {
    const sec = $("choix");
    const fiche = $("fiche");
    fiche.innerHTML = "";
    const t = etat.choisi && trouverElement(etat.choisi);
    sec.hidden = !t;
    if (!t) return;
    const { genre, e } = t;
    const boutons = el("div", { class: "ligne" },
      el("button", { texte: "C'est juste", onclick: () => corriger((x) => C.confirmer(x, e.id), "Noté comme vérifié.") }),
      el("button", { class: "danger", texte: "Supprimer", onclick: () => supprimerChoisi() }));

    if (genre === "piece") {
      const liste = el("select", { id: "f-nom" }, ...[...new Set([e.nom, ...C.NOMS_PIECES])].map((n) => el("option", { value: n, texte: n })));
      liste.value = e.nom;
      liste.addEventListener("change", () => corriger((x) => C.renommerPiece(x, e.id, liste.value), `Pièce renommée « ${liste.value} ».`));
      const libre = el("input", { type: "text", id: "f-nom-libre", placeholder: "ou tapez un autre nom puis Entrée" });
      libre.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter") corriger((x) => C.renommerPiece(x, e.id, libre.value), `Pièce renommée « ${libre.value.trim()} ».`);
      });
      fiche.append(el("p", { texte: `Pièce ${e.id} · ${formatM(C.surfacePolygone(e.contour))} m²` }),
        el("label", { texte: "Nom de la pièce" }), liste, libre, boutons);
    } else if (genre === "ouverture") {
      const mur = etat.v.logement.murs.find((m) => m.id === e.mur);
      const type = el("select", { id: "f-type" }, ...Object.entries(NOMS_OUVERTURES).map(([k, n]) => el("option", { value: k, texte: n })));
      type.value = e.type;
      type.addEventListener("change", () => corriger((x) => C.modifierOuverture(x, e.id, { type: type.value }), "Type changé."));
      const larg = el("input", { type: "text", id: "f-largeur", value: formatM(e.largeur) });
      const pos = el("input", { type: "text", id: "f-position", value: formatM(e.position) });
      const appliquer = () => {
        const l = lireNombre(larg.value), p = lireNombre(pos.value);
        if (!(l > 0) || !(p >= 0)) return message("Largeur et position : des nombres en mètres, ex. 0,83.", true);
        corriger((x) => C.modifierOuverture(x, e.id, { largeur: l, position: p }), "Mesures corrigées.");
      };
      for (const champ of [larg, pos]) champ.addEventListener("keydown", (ev) => ev.key === "Enter" && appliquer());
      fiche.append(el("p", { texte: `${NOMS_OUVERTURES[e.type]} ${e.id}, dans le mur ${e.mur}${mur ? ` (${formatM(C.longueur(mur.debut, mur.fin))} m)` : ""}` }),
        el("label", { texte: "Type" }), type,
        el("label", { texte: "Largeur (m)" }), larg,
        el("label", { texte: "Distance depuis le début du mur (m)" }), pos,
        el("div", { class: "ligne" }, el("button", { class: "plein", texte: "Appliquer les mesures", onclick: appliquer })),
        boutons);
    } else {
      const l = C.longueur(e.debut, e.fin);
      const cote = el("input", { type: "text", id: "f-cote", placeholder: `lue : ${formatM(l)} m` });
      const ep = el("input", { type: "text", id: "f-epaisseur", value: formatM(e.epaisseur) });
      const lue = () => {
        const n = lireNombre(cote.value);
        if (!(n > 0)) { message("Tapez la longueur de la cote en mètres, ex. 4,80.", true); return null; }
        return n;
      };
      ep.addEventListener("keydown", (ev) => {
        if (ev.key !== "Enter") return;
        const n = lireNombre(ep.value);
        if (n > 0) corriger((x) => C.modifierMur(x, e.id, { epaisseur: n }), "Épaisseur corrigée.");
      });
      fiche.append(el("p", { texte: `Mur ${e.id} · longueur lue ${formatM(l)} m · épaisseur ${formatM(e.epaisseur)} m` }),
        el("label", { texte: "Corriger une cote : vraie longueur de ce mur (m)" }), cote,
        el("div", { class: "ligne" },
          el("button", { texte: "Ce mur seulement", onclick: () => { const n = lue(); if (n) corriger((x) => C.longueurMur(x, e.id, n), "Longueur du mur corrigée."); } }),
          el("button", { class: "plein", texte: "Tout le plan", title: "Toute l'échelle était fausse : on corrige toutes les longueurs dans la même proportion",
            onclick: () => { const n = lue(); if (n) corriger((x) => C.mettreAEchelle(x, n / l), `Échelle de tout le plan corrigée (× ${formatM(n / l, 3)}).`); } })),
        el("label", { texte: "Épaisseur (m), puis Entrée" }), ep,
        el("p", { class: "info", texte: "Pour le déplacer : glissez-le sur le plan." }),
        boutons);
    }
  }

  function choisir(id) {
    etat.choisi = id;
    rafraichir();
  }

  function supprimerChoisi() {
    if (!etat.choisi) return;
    const nom = nomDe(etat.choisi);
    if (corriger((x) => C.supprimer(x, etat.choisi), `${nom} supprimé(e).`)) etat.choisi = null;
    rafraichir();
  }

  function epaisseurNouveauMur() {
    return 0.1; // une cloison ; à corriger ensuite dans la fiche si c'est un mur porteur
  }

  function changerOutil(outil) {
    etat.outil = outil;
    etat.depart = null;
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

    if (!etat.corriger) { // mode « comparer » : on ne fait que se déplacer
      etat.glisse = { genre: "vue", dernier: [ev.clientX, ev.clientY] };
      return;
    }
    if (etat.outil === "mur") {
      const q = C.aimanter(lg, p, etat.depart, metresPour(VISEE * 1.5, p));
      if (!etat.depart) { etat.depart = q; dessiner(); return; }
      if (corriger((x) => C.ajouterMur(x, etat.depart, q, epaisseurNouveauMur()), "Mur ajouté (cloison de 10 cm).")) {
        etat.choisi = etat.v.logement.murs[etat.v.logement.murs.length - 1].id;
        etat.depart = null;
        rafraichir();
      }
      return;
    }
    if (etat.outil in NOMS_OUVERTURES) {
      const m = C.murLePlusProche(lg, p, tol * 2);
      if (!m) return message("Cliquez sur un mur (ou tout près).", true);
      if (corriger((x) => C.ajouterOuverture(x, m.id, etat.outil, m.le_long), `${NOMS_OUVERTURES[etat.outil]} ajoutée.`)) {
        const o = etat.v.logement.ouvertures;
        etat.choisi = o[o.length - 1].id;
        rafraichir();
      }
      return;
    }
    const sous = C.elementSous(lg, p, tol);
    if (sous) {
      etat.choisi = sous.id;
      if (sous.genre === "mur") etat.glisse = { genre: "mur", id: sous.id, depart: p, bouge: false };
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
    const g = etat.glisse;
    if (g && g.genre === "vue") {
      etat.vue.dx += ev.clientX - g.dernier[0];
      etat.vue.dy += ev.clientY - g.dernier[1];
      g.dernier = [ev.clientX, ev.clientY];
    } else if (g && g.genre === "mur") {
      const delta = [p[0] - g.depart[0], p[1] - g.depart[1]];
      if (Math.hypot(...delta) > metresPour(3, p)) g.bouge = true;
      if (g.bouge) {
        try { etat.apercu = C.deplacerMur(etat.v, g.id, delta); g.delta = delta; } catch (e) { /* on garde l'aperçu précédent */ }
      }
    }
    $("position").textContent = `x ${formatM(p[0])} m · y ${formatM(p[1])} m`;
    dessiner();
  }

  function relache() {
    const g = etat.glisse;
    etat.glisse = null;
    etat.apercu = null;
    if (g && g.genre === "mur" && g.bouge && g.delta) {
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
      message("Impossible de valider : " + erreurs.join(" ; "), true);
      return;
    }
    if (etat.doutes.length) {
      const ok = await demander(`Il reste ${etat.doutes.length} point(s) à vérifier`,
        "Vous pouvez revenir les régler (un clic sur « C'est juste » suffit si c'est bon), ou valider quand même : ils seront notés dans le rapport.");
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
  $("mode-corriger").addEventListener("click", () => {
    etat.corriger = !etat.corriger;
    if (!etat.corriger) { etat.choisi = null; etat.depart = null; etat.outil = "choisir"; }
    rafraichir();
  });
  if (parametres.get("mode") === "corriger") etat.corriger = true;
  $("abandonner").addEventListener("click", () => { versSite({ type: PREFIXE + "abandon" }); message("Vérification abandonnée."); });
  $("refaire").addEventListener("click", refaire);
  document.querySelectorAll("[data-outil]").forEach((b) => b.addEventListener("click", () => changerOutil(b.dataset.outil)));
  $("opacite").addEventListener("input", (ev) => { etat.opacite = ev.target.value / 100; dessiner(); });
  document.querySelectorAll("[data-calque]").forEach((c) =>
    c.addEventListener("change", () => { etat.calques[c.dataset.calque] = c.checked; dessiner(); }));

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
    if (!etat.corriger) { if (ev.key === "+" || ev.key === "=") zoomer(1.25); if (ev.key === "-") zoomer(0.8); return; }
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
    for (const id of ["exemple"]) $(id).hidden = true;
    document.querySelector('label[for="fichiers"]').hidden = true;
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
