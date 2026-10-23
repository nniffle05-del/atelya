/*
 * La page de saisie : ce qui se passe quand on clique, et le dessin.
 * Les calculs eux-mêmes sont dans calculs.js.
 */
(function () {
  "use strict";

  const C = window.Calculs;
  const RAYON_AIMANT = 12; // en pixels d'écran
  const RAYON_ALIGNEMENT = 6; // en pixels d'écran
  const SEUIL_CONTROLE = 1; // écart (en %) au-delà duquel on prévient
  const CONSIGNES = {
    plan: "Étape 1 : choisissez l'image du plan dans le panneau de droite.",
    echelle: "Étape 2 : cliquez les deux bouts d'une cote, puis tapez sa valeur à droite.",
    controle: "Étape 3 : cliquez les deux bouts d'une autre cote pour vérifier l'échelle.",
    murs: "Étape 4 : cliquez le milieu des murs, angle après angle. Échap pour terminer une série.",
    origine: "Étape 5 : cliquez le coin intérieur sud-ouest du logement.",
    selection: "Cliquez un mur pour le modifier.",
  };

  const etat = {
    image: null,
    imageNom: null,
    imageDataUrl: null,
    vue: { zoom: 1, dx: 0, dy: 0 },
    echelle: null, // {p1, p2, longueur, pxParM}
    controle: null, // {p1, p2, longueur, ecart}
    origine: null, // [x, y] en pixels du plan
    murs: [], // {id, debut, fin, epaisseur, longueurTapee}
    compteur: 0,
    mode: "plan",
    points: [], // clics en attente (pour les murs : toute la série en cours)
    souris: null, // position de la souris, en pixels du plan
    maj: false, // touche Maj enfoncée
    selection: null, // index du mur choisi
    historique: [],
  };
  window.Saisie = { etat }; // lecture seule, pour les tests automatiques

  const $ = (id) => document.getElementById(id);
  const canvas = $("plan");
  const ctx = canvas.getContext("2d");

  // ---------- Repères ----------

  function ecranVersPlan(ev) {
    const r = canvas.getBoundingClientRect();
    return [(ev.clientX - r.left - etat.vue.dx) / etat.vue.zoom, (ev.clientY - r.top - etat.vue.dy) / etat.vue.zoom];
  }

  function planVersEcran(p) {
    return [p[0] * etat.vue.zoom + etat.vue.dx, p[1] * etat.vue.zoom + etat.vue.dy];
  }

  const pxParM = () => (etat.echelle ? etat.echelle.pxParM : null);
  const enPx = (m) => m.map((mur) => ({ ...mur, epaisseurPx: mur.epaisseur * pxParM() }));
  const formatM = (v, d = 2) => v.toFixed(d).replace(".", ",");

  // ---------- Historique (Annuler) ----------

  function memoriser() {
    etat.historique.push(JSON.stringify({ echelle: etat.echelle, controle: etat.controle, origine: etat.origine, murs: etat.murs, compteur: etat.compteur }));
    if (etat.historique.length > 100) etat.historique.shift();
  }

  function annuler() {
    if (etat.points.length) {
      etat.points = [];
    } else {
      const precedent = etat.historique.pop();
      if (!precedent) return;
      Object.assign(etat, JSON.parse(precedent));
      etat.selection = null;
    }
    rafraichir();
  }

  // ---------- Aimants ----------

  function extremites() {
    const pts = [];
    for (const m of etat.murs) pts.push(m.debut, m.fin);
    return pts;
  }

  /** Le point réellement retenu pour un clic à `p`, selon le mode et les aimants. */
  function pointAimante(p) {
    const rayon = RAYON_AIMANT / etat.vue.zoom;
    const precedent = etat.points[etat.points.length - 1];
    if (etat.mode === "murs") {
      const accroche = pointLePlusProcheAvecChaine(p, rayon);
      if (accroche) return { point: accroche, accroche: true };
      if (etat.maj) return { point: p, accroche: false };
      // Redresser le mur, puis caler la coordonnée restée libre sur les angles existants.
      let q = p;
      let axes = "xy";
      if (precedent) {
        q = C.redresser(precedent, p);
        if (q[1] === precedent[1] && q[0] !== precedent[0]) axes = "x"; // mur horizontal
        else if (q[0] === precedent[0]) axes = "y"; // mur vertical
      }
      const aligne = C.aligner(q, [...extremites(), ...etat.points], RAYON_ALIGNEMENT / etat.vue.zoom, axes);
      return { point: aligne.point, accroche: false, guides: aligne.guides };
    }
    if (etat.mode === "echelle" || etat.mode === "controle") {
      if (etat.points.length === 1 && !etat.maj) return { point: C.redresser(precedent, p), accroche: false };
      return { point: p, accroche: false };
    }
    if (etat.mode === "origine" && etat.echelle) {
      const coin = C.pointLePlusProche(p, C.coinsDesFaces(enPx(etat.murs)), rayon);
      if (coin) return { point: coin, accroche: true };
    }
    return { point: p, accroche: false };
  }

  function pointLePlusProcheAvecChaine(p, rayon) {
    // Le point de départ de la série en cours compte aussi, même avant le premier mur.
    return C.pointLePlusProche(p, [...extremites(), ...etat.points], rayon);
  }

  // ---------- Clics ----------

  function clic(p) {
    if (!etat.image) return;
    const { point, accroche } = pointAimante(p);
    switch (etat.mode) {
      case "echelle":
      case "controle":
        etat.points = etat.points.length >= 2 ? [point] : [...etat.points, point];
        break;
      case "murs":
        clicMur(point, accroche);
        break;
      case "origine":
        memoriser();
        etat.origine = point;
        break;
      case "selection":
        etat.selection = murSous(p);
        break;
    }
    rafraichir();
  }

  function clicMur(point, accroche) {
    if (!etat.echelle) {
      message("Calez d'abord l'échelle (étape 2) : l'épaisseur des murs en dépend.", "erreur");
      return;
    }
    if (etat.points.length === 0) {
      etat.points = [point];
      return;
    }
    const debut = etat.points[etat.points.length - 1];
    if (C.distance(debut, point) < 2 / etat.vue.zoom) return; // double-clic : on ignore
    memoriser();
    const epaisseur = epaisseurChoisie();
    const brut = { debut, fin: point, epaisseurPx: epaisseur * pxParM() };
    const corrige = C.accrocherAuxFaces(brut, enPx(etat.murs), RAYON_AIMANT / etat.vue.zoom / 2);
    etat.murs.push({ id: nouvelId(), debut: corrige.debut, fin: corrige.fin, epaisseur, longueurTapee: null });
    const finDeplacee = C.distance(corrige.fin, point) > 1e-6;
    const boucleFermee = accroche && C.distance(point, etat.points[0]) < 1e-6;
    // Une série s'arrête quand elle revient à son départ, ou quand un mur bute contre un autre.
    etat.points = boucleFermee || finDeplacee ? [] : [...etat.points, corrige.fin];
  }

  function nouvelId() {
    const ids = new Set(etat.murs.map((m) => m.id));
    let id;
    do id = "M" + ++etat.compteur;
    while (ids.has(id));
    return id;
  }

  function epaisseurChoisie() {
    const choix = document.querySelector('input[name="ep"]:checked').value;
    if (choix !== "autre") return Number(choix);
    const v = Number($("ep-autre").value);
    return v > 0 ? v : 0.2;
  }

  function murSous(p) {
    let meilleur = null;
    let dMin = Infinity;
    etat.murs.forEach((m, i) => {
      const d = distanceSegment(p, m.debut, m.fin);
      const tolerance = Math.max((m.epaisseur * pxParM()) / 2, 6 / etat.vue.zoom);
      if (d <= tolerance && d < dMin) {
        dMin = d;
        meilleur = i;
      }
    });
    return meilleur;
  }

  function distanceSegment(p, a, b) {
    const l2 = (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2;
    const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * (b[0] - a[0]) + (p[1] - a[1]) * (b[1] - a[1])) / l2));
    return C.distance(p, [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]);
  }

  // ---------- Échelle et contrôle ----------

  function validerEchelle() {
    const l = Number($("echelle-longueur").value);
    try {
      const s = C.echelle(etat.points[0], etat.points[1], l);
      memoriser();
      // Les murs déjà tracés gardent leur position sur l'image : seules les mesures changent.
      etat.echelle = { p1: etat.points[0], p2: etat.points[1], longueur: l, pxParM: s };
      etat.controle = null;
      etat.points = [];
      message(`Échelle calée : 1 m = ${formatM(s, 1)} pixels. Contrôlez-la maintenant sur une autre cote (étape 3).`, "ok");
      choisirMode("controle");
    } catch (e) {
      message("Échelle refusée : " + e.message, "erreur");
    }
  }

  function validerControle() {
    const l = Number($("controle-longueur").value);
    if (!etat.echelle) return message("Calez d'abord l'échelle (étape 2).", "erreur");
    if (!(l > 0)) return message("Tapez la longueur réelle de la cote contrôlée.", "erreur");
    const ecart = C.ecartControle(etat.points[0], etat.points[1], l, etat.echelle.pxParM);
    etat.controle = { p1: etat.points[0], p2: etat.points[1], longueur: l, ecart };
    etat.points = [];
    if (Math.abs(ecart) <= SEUIL_CONTROLE) {
      message(`Contrôle réussi : écart de ${formatM(ecart, 1)} %. Passez aux murs (étape 4).`, "ok");
      choisirMode("murs");
    } else {
      message(`Attention : écart de ${formatM(ecart, 1)} %. Le plan est peut-être déformé, ou un clic est imprécis. Refaites l'échelle ou le contrôle en zoomant.`, "alerte");
    }
    rafraichir();
  }

  // ---------- Modifier un mur ----------

  function appliquerLongueur() {
    const i = etat.selection;
    const l = Number($("sel-longueur").value);
    if (i == null || !(l > 0)) return;
    memoriser();
    etat.murs = C.appliquerLongueur(etat.murs, i, l, pxParM());
    rafraichir();
  }

  function renommer() {
    const i = etat.selection;
    const nom = $("sel-id").value.trim();
    if (i == null) return;
    if (!nom || etat.murs.some((m, j) => j !== i && m.id === nom)) {
      message("Ce nom est vide ou déjà pris.", "erreur");
      $("sel-id").value = etat.murs[i].id;
      return;
    }
    memoriser();
    etat.murs[i].id = nom;
    rafraichir();
  }

  function changerEpaisseur() {
    const i = etat.selection;
    const v = Number($("sel-epaisseur").value);
    if (i == null || !(v > 0)) return;
    memoriser();
    etat.murs[i].epaisseur = v;
    rafraichir();
  }

  function supprimer() {
    if (etat.selection == null) return;
    memoriser();
    etat.murs.splice(etat.selection, 1);
    etat.selection = null;
    rafraichir();
  }

  // ---------- Fichiers ----------

  function chargerImage(fichier) {
    if (!fichier) return;
    if (fichier.type === "application/pdf") {
      message("Les PDF ne sont pas encore lus directement. Ouvrez-le dans Aperçu, puis Fichier › Exporter… › PNG.", "erreur");
      return;
    }
    const lecteur = new FileReader();
    lecteur.onload = () => installerImage(lecteur.result, fichier.name, true);
    lecteur.readAsDataURL(fichier);
  }

  function installerImage(dataUrl, nom, nouvelle) {
    const img = new Image();
    img.onload = () => {
      etat.image = img;
      etat.imageNom = nom;
      etat.imageDataUrl = dataUrl;
      if (nouvelle) {
        etat.echelle = etat.controle = etat.origine = null;
        etat.murs = [];
        etat.historique = [];
        etat.compteur = 0;
        choisirMode("echelle");
        message("Plan chargé. Calez maintenant l'échelle (étape 2).", "ok");
      }
      $("plan-info").textContent = `${nom} — ${img.naturalWidth} × ${img.naturalHeight} pixels`;
      ajuster();
    };
    img.onerror = () => message("Cette image n'a pas pu être lue.", "erreur");
    img.src = dataUrl;
  }

  function saisieCourante() {
    return {
      projet_id: $("projet-id").value.trim(),
      hauteur_sous_plafond: Number($("hsp").value),
      echelle: etat.echelle,
      origine: etat.origine,
      murs: etat.murs,
    };
  }

  function enregistrerLogement() {
    const erreurs = C.verifierSaisie(saisieCourante());
    if (erreurs.length) return message("Impossible d'enregistrer : " + erreurs.join(" ; ") + ".", "erreur");
    if (etat.controle == null) message("Note : l'échelle n'a pas été contrôlée (étape 3).", "alerte");
    telecharger("logement.json", C.construireLogement(saisieCourante()));
    message("logement.json enregistré dans vos Téléchargements.", "ok");
  }

  function enregistrerSaisie() {
    if (!etat.image) return message("Rien à enregistrer : aucun plan n'est chargé.", "erreur");
    const s = saisieCourante();
    telecharger(`saisie-${s.projet_id || "plan"}.json`, {
      version: C.VERSION_SAISIE,
      ...s,
      controle: etat.controle,
      compteur: etat.compteur,
      image: { nom: etat.imageNom, dataUrl: etat.imageDataUrl },
    });
    message("Saisie enregistrée dans vos Téléchargements.", "ok");
  }

  function reprendre(fichier) {
    if (!fichier) return;
    const lecteur = new FileReader();
    lecteur.onload = () => {
      try {
        const s = JSON.parse(lecteur.result);
        if (s.version !== C.VERSION_SAISIE) throw new Error("ce fichier n'est pas une saisie de plan");
        Object.assign(etat, { echelle: s.echelle, controle: s.controle, origine: s.origine, murs: s.murs, compteur: s.compteur || 0, historique: [], points: [], selection: null });
        $("projet-id").value = s.projet_id;
        $("hsp").value = s.hauteur_sous_plafond;
        installerImage(s.image.dataUrl, s.image.nom, false);
        choisirMode("selection");
        message("Saisie reprise.", "ok");
      } catch (e) {
        message("Reprise impossible : " + e.message, "erreur");
      }
    };
    lecteur.readAsText(fichier);
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

  // ---------- Vue (zoom et déplacement) ----------

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

  // ---------- Dessin ----------

  function dessiner() {
    const dpr = window.devicePixelRatio || 1;
    const r = canvas.getBoundingClientRect();
    if (canvas.width !== Math.round(r.width * dpr) || canvas.height !== Math.round(r.height * dpr)) {
      canvas.width = Math.round(r.width * dpr);
      canvas.height = Math.round(r.height * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.fillStyle = "#e9ebee";
    ctx.fillRect(0, 0, r.width, r.height);
    if (!etat.image) {
      ctx.fillStyle = "#636c76";
      ctx.font = "16px -apple-system, sans-serif";
      ctx.textAlign = "center";
      ctx.fillText("Chargez l'image du plan (panneau de droite), ou glissez-la ici.", r.width / 2, r.height / 2);
      return;
    }
    const { zoom, dx, dy } = etat.vue;
    const trait = 1 / zoom; // un pixel d'écran, exprimé en pixels du plan
    ctx.setTransform(dpr * zoom, 0, 0, dpr * zoom, dpr * dx, dpr * dy);
    ctx.drawImage(etat.image, 0, 0);

    // Murs
    etat.murs.forEach((m, i) => {
      const choisi = i === etat.selection;
      dessinerMur(m.debut, m.fin, m.epaisseur * pxParM(), choisi ? "rgba(234,88,12,0.45)" : "rgba(37,99,235,0.32)");
      ctx.strokeStyle = choisi ? "#c2410c" : "#1d4ed8";
      ctx.lineWidth = 1.5 * trait;
      ligne(m.debut, m.fin);
      for (const p of [m.debut, m.fin]) rond(p, 3 * trait, ctx.strokeStyle);
    });

    // Échelle et contrôle
    if (etat.echelle) cote(etat.echelle.p1, etat.echelle.p2, "#15803d", trait);
    if (etat.controle) cote(etat.controle.p1, etat.controle.p2, Math.abs(etat.controle.ecart) <= SEUIL_CONTROLE ? "#15803d" : "#b45309", trait);

    // Clics en attente et aperçu sous la souris
    const couleur = etat.mode === "murs" ? "#1d4ed8" : "#15803d";
    etat.points.forEach((p) => rond(p, 4 * trait, couleur));
    let apercu = null;
    if (etat.souris && ["murs", "echelle", "controle", "origine"].includes(etat.mode)) {
      apercu = pointAimante(etat.souris);
      const dernier = etat.points[etat.points.length - 1];
      if (dernier && etat.points.length < (etat.mode === "murs" ? Infinity : 2)) {
        if (etat.mode === "murs" && etat.echelle) dessinerMur(dernier, apercu.point, epaisseurChoisie() * pxParM(), "rgba(37,99,235,0.18)");
        ctx.setLineDash([6 * trait, 4 * trait]);
        ctx.strokeStyle = couleur;
        ctx.lineWidth = 1.5 * trait;
        ligne(dernier, apercu.point);
        ctx.setLineDash([]);
      }
      if (apercu.guides) {
        ctx.setLineDash([3 * trait, 3 * trait]);
        ctx.strokeStyle = "#db2777";
        ctx.lineWidth = trait;
        for (const g of apercu.guides) if (g) ligne(g, apercu.point);
        ctx.setLineDash([]);
      }
      rond(apercu.point, (apercu.accroche ? 6 : 3) * trait, apercu.accroche ? "#db2777" : couleur);
    }

    // Origine
    if (etat.origine) {
      const o = etat.origine;
      const l = 40 * trait;
      ctx.strokeStyle = "#dc2626";
      ctx.lineWidth = 2 * trait;
      ligne(o, [o[0] + l, o[1]]);
      ligne(o, [o[0], o[1] - l]);
      rond(o, 4 * trait, "#dc2626");
    }

    // Textes, à taille fixe à l'écran
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.font = "600 12px -apple-system, sans-serif";
    ctx.textAlign = "center";
    if (etat.echelle && zoom * pxParM() > 25) {
      for (const m of etat.murs) etiquette(milieu(m.debut, m.fin), formatM(C.distance(m.debut, m.fin) / pxParM()), "#1d4ed8");
    }
    if (etat.origine) etiquette(planVersEcran(etat.origine), "(0, 0)", "#dc2626", [24, 16]);
    const dernier = etat.points[etat.points.length - 1];
    if (apercu && dernier && etat.echelle && etat.mode !== "origine") {
      etiquette(planVersEcran(apercu.point), formatM(C.distance(dernier, apercu.point) / pxParM()) + " m", couleur, [0, -16]);
    }
  }

  function dessinerMur(a, b, epPx, remplissage) {
    const l = C.distance(a, b);
    if (l === 0) return;
    const n = [(-(b[1] - a[1]) / l) * (epPx / 2), ((b[0] - a[0]) / l) * (epPx / 2)];
    ctx.fillStyle = remplissage;
    ctx.beginPath();
    ctx.moveTo(a[0] + n[0], a[1] + n[1]);
    ctx.lineTo(b[0] + n[0], b[1] + n[1]);
    ctx.lineTo(b[0] - n[0], b[1] - n[1]);
    ctx.lineTo(a[0] - n[0], a[1] - n[1]);
    ctx.closePath();
    ctx.fill();
  }

  function cote(a, b, couleur, trait) {
    ctx.strokeStyle = couleur;
    ctx.lineWidth = 2 * trait;
    ligne(a, b);
    rond(a, 4 * trait, couleur);
    rond(b, 4 * trait, couleur);
  }

  function ligne(a, b) {
    ctx.beginPath();
    ctx.moveTo(a[0], a[1]);
    ctx.lineTo(b[0], b[1]);
    ctx.stroke();
  }

  function rond(p, rayon, couleur) {
    ctx.fillStyle = couleur;
    ctx.beginPath();
    ctx.arc(p[0], p[1], rayon, 0, 2 * Math.PI);
    ctx.fill();
  }

  function milieu(a, b) {
    return planVersEcran([(a[0] + b[0]) / 2, (a[1] + b[1]) / 2]);
  }

  function etiquette(pos, texte, couleur, decalage = [0, 0]) {
    const [x, y] = [pos[0] + decalage[0], pos[1] + decalage[1]];
    const w = ctx.measureText(texte).width + 8;
    ctx.fillStyle = "rgba(255,255,255,0.9)";
    ctx.fillRect(x - w / 2, y - 9, w, 17);
    ctx.fillStyle = couleur;
    ctx.fillText(texte, x, y + 4);
  }

  // ---------- Panneau de droite ----------

  function choisirMode(mode) {
    etat.mode = mode;
    etat.points = [];
    if (mode !== "selection") etat.selection = null;
    rafraichir();
  }

  function rafraichir() {
    document.querySelectorAll(".mode[data-mode]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.mode === etat.mode)));
    document.querySelectorAll("[data-panneau]").forEach((s) => s.classList.toggle("cache", s.dataset.panneau !== etat.mode));
    $("consigne").textContent = CONSIGNES[etat.mode];
    $("echelle-valider").disabled = !(etat.mode === "echelle" && etat.points.length === 2);
    $("controle-valider").disabled = !(etat.mode === "controle" && etat.points.length === 2);
    $("echelle-info").textContent = etat.echelle ? `Échelle actuelle : 1 m = ${formatM(etat.echelle.pxParM, 1)} pixels (cote de ${formatM(etat.echelle.longueur)} m).` : "Pas encore d'échelle.";
    $("controle-info").innerHTML = etat.controle
      ? `<span class="${Math.abs(etat.controle.ecart) <= SEUIL_CONTROLE ? "ok" : "alerte"}">Écart : ${formatM(etat.controle.ecart, 1)} %</span>`
      : "Pas encore de contrôle.";
    $("origine-info").textContent = etat.origine ? "Origine placée." : "Origine pas encore placée.";
    $("ep-autre").classList.toggle("cache", document.querySelector('input[name="ep"]:checked').value !== "autre");

    // Liste des murs
    $("nb-murs").textContent = etat.murs.length;
    $("liste-murs").innerHTML = "";
    etat.murs.forEach((m, i) => {
      const tr = document.createElement("tr");
      tr.className = "mur" + (i === etat.selection ? " choisi" : "");
      const l = etat.echelle ? formatM(C.distance(m.debut, m.fin) / pxParM()) + " m" : "—";
      const mesure = m.longueurTapee != null;
      tr.innerHTML = `<td></td><td class="nb">${l}</td><td class="nb">${formatM(m.epaisseur)}</td><td><span class="badge ${mesure ? "mesure" : ""}">${mesure ? "mesuré" : "estimé"}</span></td>`;
      tr.firstChild.textContent = m.id;
      tr.addEventListener("click", () => {
        choisirMode("selection");
        etat.selection = i;
        rafraichir();
      });
      $("liste-murs").appendChild(tr);
    });

    // Détail du mur choisi
    const m = etat.selection != null ? etat.murs[etat.selection] : null;
    $("selection-vide").classList.toggle("cache", !!m);
    $("selection-detail").classList.toggle("cache", !m);
    if (m) {
      $("sel-id").value = m.id;
      $("sel-longueur").value = etat.echelle ? (C.distance(m.debut, m.fin) / pxParM()).toFixed(3) : "";
      $("sel-epaisseur").value = m.epaisseur;
    }
    dessiner();
  }

  function message(texte, genre) {
    const p = document.createElement("p");
    p.className = genre;
    p.textContent = texte;
    $("messages").replaceChildren(p);
  }

  function afficherPosition() {
    if (!etat.souris || !etat.echelle || !etat.origine) return ($("position").textContent = "");
    const [x, y] = C.versMetres(etat.souris, etat.origine, pxParM());
    $("position").innerHTML = `x <strong>${formatM(x)}</strong> m · y <strong>${formatM(y)}</strong> m`;
  }

  // ---------- Événements ----------

  let appui = null; // pour distinguer un clic d'un glisser
  canvas.addEventListener("pointerdown", (ev) => {
    appui = { x: ev.clientX, y: ev.clientY, dx: etat.vue.dx, dy: etat.vue.dy, glisse: false };
    canvas.setPointerCapture(ev.pointerId);
  });
  canvas.addEventListener("pointermove", (ev) => {
    etat.souris = ecranVersPlan(ev);
    etat.maj = ev.shiftKey;
    if (appui) {
      const ddx = ev.clientX - appui.x;
      const ddy = ev.clientY - appui.y;
      if (appui.glisse || Math.hypot(ddx, ddy) > 4) {
        appui.glisse = true;
        etat.vue.dx = appui.dx + ddx;
        etat.vue.dy = appui.dy + ddy;
      }
    }
    afficherPosition();
    dessiner();
  });
  canvas.addEventListener("pointerup", (ev) => {
    if (appui && !appui.glisse && ev.button === 0) {
      etat.maj = ev.shiftKey;
      clic(ecranVersPlan(ev));
    }
    appui = null;
  });
  canvas.addEventListener("pointerleave", () => {
    etat.souris = null;
    dessiner();
  });
  canvas.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    const r = canvas.getBoundingClientRect();
    if (ev.ctrlKey || ev.metaKey) {
      zoomer(Math.exp(-ev.deltaY * 0.01), [ev.clientX - r.left, ev.clientY - r.top]);
    } else {
      etat.vue.dx -= ev.deltaX;
      etat.vue.dy -= ev.deltaY;
      dessiner();
    }
  }, { passive: false });

  document.addEventListener("keydown", (ev) => {
    const dansUnChamp = ["INPUT", "SELECT", "TEXTAREA"].includes(document.activeElement.tagName);
    if ((ev.metaKey || ev.ctrlKey) && ev.key === "z") {
      if (!dansUnChamp) {
        ev.preventDefault();
        annuler();
      }
      return;
    }
    if (dansUnChamp) {
      if (ev.key === "Enter") {
        if (document.activeElement.id === "echelle-longueur" && etat.points.length === 2) validerEchelle();
        if (document.activeElement.id === "controle-longueur" && etat.points.length === 2) validerControle();
        if (document.activeElement.id === "sel-longueur") appliquerLongueur();
      }
      return;
    }
    if (ev.key === "Escape" || ev.key === "Enter") {
      etat.points = [];
      rafraichir();
    } else if (ev.key === "+" || ev.key === "=") zoomer(1.25);
    else if (ev.key === "-") zoomer(0.8);
    else if ((ev.key === "Delete" || ev.key === "Backspace") && etat.selection != null) supprimer();
    else if (ev.key === "Shift") {
      etat.maj = true;
      dessiner();
    }
  });
  document.addEventListener("keyup", (ev) => {
    if (ev.key === "Shift") {
      etat.maj = false;
      dessiner();
    }
  });

  document.querySelectorAll(".mode[data-mode]").forEach((b) => b.addEventListener("click", () => choisirMode(b.dataset.mode)));
  $("zoom-plus").addEventListener("click", () => zoomer(1.25));
  $("zoom-moins").addEventListener("click", () => zoomer(0.8));
  $("zoom-ajuster").addEventListener("click", ajuster);
  $("annuler").addEventListener("click", annuler);
  $("fichier-plan").addEventListener("change", (ev) => chargerImage(ev.target.files[0]));
  $("echelle-valider").addEventListener("click", validerEchelle);
  $("controle-valider").addEventListener("click", validerControle);
  $("murs-terminer").addEventListener("click", () => {
    etat.points = [];
    rafraichir();
  });
  document.querySelectorAll('input[name="ep"]').forEach((r) => r.addEventListener("change", rafraichir));
  $("sel-appliquer").addEventListener("click", appliquerLongueur);
  $("sel-id").addEventListener("change", renommer);
  $("sel-epaisseur").addEventListener("change", changerEpaisseur);
  $("sel-supprimer").addEventListener("click", supprimer);
  $("enregistrer-logement").addEventListener("click", enregistrerLogement);
  $("enregistrer-saisie").addEventListener("click", enregistrerSaisie);
  $("reprendre").addEventListener("click", () => $("fichier-saisie").click());
  $("fichier-saisie").addEventListener("change", (ev) => {
    reprendre(ev.target.files[0]);
    ev.target.value = "";
  });

  // Glisser-déposer d'une image sur la zone du plan
  const zone = $("zone");
  zone.addEventListener("dragover", (ev) => {
    ev.preventDefault();
    zone.classList.add("depot");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("depot"));
  zone.addEventListener("drop", (ev) => {
    ev.preventDefault();
    zone.classList.remove("depot");
    chargerImage(ev.dataTransfer.files[0]);
  });

  new ResizeObserver(() => dessiner()).observe(zone);
  rafraichir();
})();
