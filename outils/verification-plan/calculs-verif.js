/*
 * Calculs de l'écran de vérification : passage mètres → pixels du plan,
 * formes à dessiner (murs, ouvertures, pièces), repérage des doutes.
 *
 * Aucun dessin ici, seulement des calculs : on peut donc les tester seuls
 * (voir tests/verif.test.js, lancé avec Node.js).
 *
 * Deux repères (mêmes conventions que la page de saisie de l'étape 3) :
 * - les PIXELS de l'image du plan : x vers la droite, y vers le BAS ;
 * - les MÈTRES du logement : x vers l'est, y vers le NORD (vers le haut),
 *   origine au coin intérieur sud-ouest.
 *
 * Le « calage » dit comment poser les mètres sur l'image. Deux façons de l'écrire :
 * - simple (plan à plat) : {"px_par_m": 100, "origine_px": [210, 760]} ;
 * - générale : {"matrice": [[a,b,c],[d,e,f],[g,h,i]]}, qui donne pour un point (x, y)
 *   en mètres le pixel (u/w, v/w) avec [u, v, w] = matrice × [x, y, 1].
 *   Elle couvre aussi un plan tourné ou une photo prise de biais.
 */
(function (racine) {
  "use strict";

  const VERSION_VERIFICATION = "verification/0.1";
  const SEUIL_CONFIANCE = 0.7; // en dessous, Atelya hésite : l'élément passe en orange
  const MUR_COURT = 0.3; // m
  const PORTE_ETROITE = 0.55; // m
  const OUVERTURE_LARGE = 3.0; // m

  function arrondi(valeur, decimales = 2) {
    const f = 10 ** decimales;
    return Math.round(valeur * f) / f + 0;
  }

  // ---------- Calage ----------

  /** Transforme un calage (simple ou général) en matrice 3 × 3. */
  function matriceDuCalage(calage) {
    if (!calage) throw new Error("calage absent");
    if (calage.matrice) {
      const m = calage.matrice;
      if (m.length !== 3 || m.some((l) => l.length !== 3 || l.some((v) => !Number.isFinite(v)))) {
        throw new Error("la matrice du calage doit avoir 3 lignes de 3 nombres");
      }
      return m.map((l) => l.slice());
    }
    const s = calage.px_par_m;
    const o = calage.origine_px;
    if (!(s > 0) || !Array.isArray(o) || o.length !== 2) {
      throw new Error("calage incomplet : il faut px_par_m et origine_px, ou une matrice");
    }
    return [
      [s, 0, o[0]],
      [0, -s, o[1]],
      [0, 0, 1],
    ];
  }

  /** Un point en mètres → le pixel correspondant sur l'image du plan. */
  function versPixel(m, p) {
    const u = m[0][0] * p[0] + m[0][1] * p[1] + m[0][2];
    const v = m[1][0] * p[0] + m[1][1] * p[1] + m[1][2];
    const w = m[2][0] * p[0] + m[2][1] * p[1] + m[2][2];
    if (Math.abs(w) < 1e-12) throw new Error("point hors du calage");
    return [u / w, v / w];
  }

  // ---------- Formes (en mètres) ----------

  function longueur(a, b) {
    return Math.hypot(b[0] - a[0], b[1] - a[1]);
  }

  /** Direction unitaire d'un mur, et sa normale (vers la gauche). */
  function axes(mur) {
    const l = longueur(mur.debut, mur.fin);
    const d = [(mur.fin[0] - mur.debut[0]) / l, (mur.fin[1] - mur.debut[1]) / l];
    return { l, d, n: [-d[1], d[0]] };
  }

  /** Rectangle d'un morceau de mur, de `de` à `a` mètres le long de l'axe, épaisseur `ep`. */
  function bande(mur, de, a, ep) {
    const { d, n } = axes(mur);
    const h = ep / 2;
    const p = (t, s) => [mur.debut[0] + d[0] * t + n[0] * s, mur.debut[1] + d[1] * t + n[1] * s];
    return [p(de, -h), p(a, -h), p(a, h), p(de, h)];
  }

  /** Le mur dessiné : son rectangle, rallongé d'une demi-épaisseur à chaque bout pour fermer les angles. */
  function polygoneMur(mur) {
    const { l } = axes(mur);
    const h = mur.epaisseur / 2;
    return bande(mur, -h, l + h, mur.epaisseur);
  }

  /** L'ouverture dessinée : un rectangle un peu plus épais que son mur, à sa place. */
  function polygoneOuverture(ouverture, mur) {
    return bande(mur, ouverture.position, ouverture.position + ouverture.largeur, mur.epaisseur * 1.6);
  }

  function surfacePolygone(points) {
    let total = 0;
    for (let i = 0; i < points.length; i++) {
      const [x1, y1] = points[i];
      const [x2, y2] = points[(i + 1) % points.length];
      total += x1 * y2 - x2 * y1;
    }
    return Math.abs(total) / 2;
  }

  /** Point où écrire le nom d'une pièce : le centre de son contour (centre de gravité). */
  function centrePolygone(points) {
    let a = 0, cx = 0, cy = 0;
    for (let i = 0; i < points.length; i++) {
      const [x1, y1] = points[i];
      const [x2, y2] = points[(i + 1) % points.length];
      const k = x1 * y2 - x2 * y1;
      a += k; cx += (x1 + x2) * k; cy += (y1 + y2) * k;
    }
    if (Math.abs(a) < 1e-12) {
      const n = points.length;
      return [points.reduce((s, p) => s + p[0], 0) / n, points.reduce((s, p) => s + p[1], 0) / n];
    }
    return [cx / (3 * a), cy / (3 * a)];
  }

  // ---------- Doutes ----------

  /**
   * La liste des doutes à montrer en orange.
   * Deux sources : ceux qu'Atelya a écrits dans le fichier (`doutes`), et ceux
   * que la page repère seule (confiance basse, mur très court, porte très étroite…).
   * Chaque doute : {element (id ou null), zone_px (rectangle [x, y, l, h] ou null), raison}.
   */
  function trouverDoutes(verification) {
    const lg = verification.logement;
    const doutes = [];
    const deja = new Set();
    const verifies = new Set(verification.verifies || []);
    const resolus = new Set(verification.resolus || []);
    const ajouter = (element, raison, zone_px = null, propositions = null) => {
      const cle = `${element}|${raison}`;
      if (deja.has(cle) || resolus.has(cle) || (element != null && verifies.has(element))) return;
      deja.add(cle);
      doutes.push({ cle, element, zone_px, raison, propositions: propositions || propositionsAuto(lg, element) });
    };

    const ids = new Set([...lg.murs, ...(lg.ouvertures || []), ...(lg.pieces || [])].map((e) => e.id));
    for (const d of verification.doutes || []) {
      if (d.element != null && !ids.has(d.element)) continue; // élément supprimé entre-temps
      ajouter(d.element ?? null, d.raison || "à vérifier", d.zone_px ?? null, d.propositions || null);
    }

    const murs = new Map(lg.murs.map((m) => [m.id, m]));
    const dejaEcrits = new Set((verification.doutes || []).map((d) => d.element).filter((x) => x != null));
    for (const e of [...lg.murs, ...(lg.ouvertures || []), ...(lg.pieces || [])]) {
      if (dejaEcrits.has(e.id)) continue; // Atelya a déjà expliqué son doute sur cet élément
      const c = e.confiance ?? 1;
      if (c < SEUIL_CONFIANCE) ajouter(e.id, `Atelya hésite (sûr à ${Math.round(c * 100)} %)`);
    }
    for (const m of lg.murs) {
      if (longueur(m.debut, m.fin) < MUR_COURT) ajouter(m.id, "mur très court : vrai mur ou tache ?");
    }
    for (const o of lg.ouvertures || []) {
      if (!murs.has(o.mur)) ajouter(o.id, `posée sur un mur inconnu (${o.mur})`);
      if (o.type === "porte" && o.largeur < PORTE_ETROITE) ajouter(o.id, `porte très étroite (${String(arrondi(o.largeur)).replace(".", ",")} m)`);
      if (o.largeur > OUVERTURE_LARGE) ajouter(o.id, `ouverture très large (${String(arrondi(o.largeur)).replace(".", ",")} m)`);
    }
    for (const p of lg.pieces || []) {
      if (p.surface != null && Math.abs(p.surface - surfacePolygone(p.contour)) > 0.05 * p.surface) {
        ajouter(p.id, "la surface écrite ne correspond pas au contour lu");
      }
    }
    return doutes;
  }

  /** Les propositions en un clic quand Atelya n'en a pas écrit : garder, ou supprimer ce qui est en trop. */
  function propositionsAuto(lg, element) {
    if (element == null) return [{ libelle: "Rien à corriger ici", action: { type: "resoudre" } }];
    const garder = { libelle: "C'est juste", action: { type: "confirmer", id: element } };
    if (lg.murs.some((m) => m.id === element)) {
      return [garder, { libelle: "Supprimer ce mur", action: { type: "supprimer", id: element } }];
    }
    if ((lg.ouvertures || []).some((o) => o.id === element)) {
      return [garder, { libelle: "Supprimer", action: { type: "supprimer", id: element } }];
    }
    return [garder];
  }

  // ---------- Corrections ----------
  //
  // Chaque correction prend le fichier de vérification et en renvoie une COPIE corrigée :
  // l'original n'est jamais modifié, ce qui rend le bouton « Annuler » très simple
  // (on garde les copies successives).
  //
  // Un élément touché par la personne est noté « vérifié » : il sort de la liste des doutes,
  // sa confiance passe à 1 et sa source devient « atelya+verification ».

  const NOMS_PIECES = ["Séjour", "Cuisine", "Chambre", "Salle d'eau", "Salle de bains", "WC", "Entrée",
    "Dégagement", "Placard", "Buanderie", "Bureau", "Escalier"];
  const LARGEURS = { porte: 0.83, fenetre: 1.2, porte_fenetre: 1.4 };
  const HAUTEURS = { porte: [2.04, 0], fenetre: [1.25, 0.95], porte_fenetre: [2.15, 0] };
  const PRES = 0.02; // m : deux points plus proches que ça sont « le même point »

  const copie = (v) => JSON.parse(JSON.stringify(v));

  function marquer(v, e) {
    if (!e) return;
    e.confiance = 1;
    if (e.source && !e.source.includes("verification")) e.source = `${e.source}+verification`;
    v.verifies = [...new Set([...(v.verifies || []), e.id])];
  }

  function trouver(lg, id) {
    for (const [genre, liste] of [["mur", lg.murs], ["ouverture", lg.ouvertures || []], ["piece", lg.pieces || []]]) {
      const e = liste.find((x) => x.id === id);
      if (e) return { genre, e };
    }
    return null;
  }

  function nouvelId(lg, prefixe) {
    const ids = new Set([...lg.murs, ...(lg.ouvertures || []), ...(lg.pieces || [])].map((e) => e.id));
    let k = 1;
    while (ids.has(`${prefixe}${k}`)) k++;
    return `${prefixe}${k}`;
  }

  const ar = (p) => [arrondi(p[0], 3), arrondi(p[1], 3)];

  /** Distance d'un point à un segment, et la position (en m depuis a) de son pied sur le segment. */
  function projection(p, a, b) {
    const l = longueur(a, b);
    if (l === 0) return { dist: longueur(p, a), t: 0 };
    const d = [(b[0] - a[0]) / l, (b[1] - a[1]) / l];
    const t = (p[0] - a[0]) * d[0] + (p[1] - a[1]) * d[1];
    const tt = Math.max(0, Math.min(l, t));
    return { dist: longueur(p, [a[0] + d[0] * tt, a[1] + d[1] * tt]), t, tt };
  }

  /**
   * Déplace un mur perpendiculairement à lui-même (un mur ne glisse pas dans sa longueur).
   * Suivent avec lui : les bouts des murs qui s'y accrochent et les coins des pièces qui le bordent.
   */
  function deplacerMur(v0, id, delta) {
    const v = copie(v0);
    const lg = v.logement;
    const mur = lg.murs.find((m) => m.id === id);
    if (!mur) throw new Error(`mur inconnu : ${id}`);
    const { l, n } = axes(mur);
    const k = delta[0] * n[0] + delta[1] * n[1];
    const dep = [n[0] * k, n[1] * k];
    if (Math.abs(k) < 1e-9) return v0;
    const bouge = (p) => ar([p[0] + dep[0], p[1] + dep[1]]);
    const ancien = { debut: mur.debut.slice(), fin: mur.fin.slice() };
    const touche = (p, marge) => {
      const pr = projection(p, ancien.debut, ancien.fin);
      return pr.dist <= marge && pr.t >= -marge && pr.t <= l + marge;
    };
    const dm = axes(mur).d;
    for (const m of lg.murs) {
      if (m === mur) continue;
      const { d } = axes(m);
      if (Math.abs(d[0] * dm[0] + d[1] * dm[1]) > 0.9) continue; // mur parallèle : il ne suit pas
      const marge = mur.epaisseur / 2 + m.epaisseur / 2 + PRES;
      if (touche(m.debut, marge)) {
        // Le début recule ou avance : les portes de ce mur gardent leur place réelle.
        const s = dep[0] * d[0] + dep[1] * d[1];
        for (const o of lg.ouvertures || []) if (o.mur === m.id) o.position = arrondi(Math.max(0, o.position - s), 3);
        m.debut = bouge(m.debut);
      }
      if (touche(m.fin, marge)) m.fin = bouge(m.fin);
    }
    for (const p of lg.pieces || []) {
      let change = false;
      p.contour = p.contour.map((q) => (touche(q, mur.epaisseur / 2 + PRES) ? ((change = true), bouge(q)) : q));
      if (change) delete p.surface; // la surface écrite ne correspond plus
    }
    mur.debut = bouge(mur.debut);
    mur.fin = bouge(mur.fin);
    marquer(v, mur);
    return v;
  }

  /** Donne à un mur sa vraie longueur (cote lue sur le plan) : son début reste en place, sa fin bouge. */
  function longueurMur(v0, id, nouvelle) {
    if (!(nouvelle > 0)) throw new Error("la longueur doit être positive");
    const v = copie(v0);
    const mur = v.logement.murs.find((m) => m.id === id);
    if (!mur) throw new Error(`mur inconnu : ${id}`);
    const { d } = axes(mur);
    mur.fin = ar([mur.debut[0] + d[0] * nouvelle, mur.debut[1] + d[1] * nouvelle]);
    marquer(v, mur);
    return v;
  }

  /**
   * Corrige l'échelle de tout le plan : toutes les longueurs sont multipliées par `k`
   * (ex. un mur lu à 3,90 m qui mesure 4,00 m sur la cote → k = 4,00 / 3,90).
   * Le calage suit, pour que la lecture reste posée au même endroit sur l'image.
   */
  function mettreAEchelle(v0, k) {
    if (!(k > 0)) throw new Error("le facteur d'échelle doit être positif");
    const v = copie(v0);
    const lg = v.logement;
    const fois = (p) => ar([p[0] * k, p[1] * k]);
    for (const m of lg.murs) { m.debut = fois(m.debut); m.fin = fois(m.fin); m.epaisseur = arrondi(m.epaisseur * k, 3); }
    for (const o of lg.ouvertures || []) { o.position = arrondi(o.position * k, 3); o.largeur = arrondi(o.largeur * k, 3); }
    for (const p of lg.pieces || []) { p.contour = p.contour.map(fois); if (p.surface != null) p.surface = arrondi(p.surface * k * k, 2); }
    const m = matriceDuCalage(v.calage);
    v.calage = { matrice: m.map((ligne) => [ligne[0] / k, ligne[1] / k, ligne[2]]) };
    v.echelle = { ...(v.echelle || {}), etat: "corrigee", facteur: arrondi(k * ((v0.echelle && v0.echelle.facteur) || 1), 5) };
    return v;
  }

  function ajouterMur(v0, debut, fin, epaisseur) {
    if (longueur(debut, fin) < 0.05) throw new Error("mur trop court");
    const v = copie(v0);
    const lg = v.logement;
    const mur = { id: nouvelId(lg, "M_v"), debut: ar(debut), fin: ar(fin), epaisseur, statut: "estime", source: "verification", confiance: 1 };
    lg.murs.push(mur);
    v.verifies = [...(v.verifies || []), mur.id];
    return v;
  }

  /** Ajoute une porte (ou fenêtre…) centrée sur le point du mur où l'on a cliqué. */
  function ajouterOuverture(v0, murId, type, centre, largeur = LARGEURS[type]) {
    const v = copie(v0);
    const lg = v.logement;
    const mur = lg.murs.find((m) => m.id === murId);
    if (!mur) throw new Error(`mur inconnu : ${murId}`);
    const l = longueur(mur.debut, mur.fin);
    const larg = Math.min(largeur, l);
    const position = Math.max(0, Math.min(l - larg, centre - larg / 2));
    const [hauteur, allege] = HAUTEURS[type];
    const o = { id: nouvelId(lg, "O_v"), type, mur: murId, position: arrondi(position, 3), largeur: arrondi(larg - 1e-6, 3),
      hauteur, allege, statut: "estime", source: "verification", confiance: 1 };
    lg.ouvertures = [...(lg.ouvertures || []), o];
    v.verifies = [...(v.verifies || []), o.id];
    return v;
  }

  /** Change des champs d'une ouverture (type, largeur, position) ; la hauteur suit le type. */
  function modifierOuverture(v0, id, champs) {
    const v = copie(v0);
    const o = (v.logement.ouvertures || []).find((x) => x.id === id);
    if (!o) throw new Error(`ouverture inconnue : ${id}`);
    if (champs.type && champs.type !== o.type) {
      o.type = champs.type;
      [o.hauteur, o.allege] = HAUTEURS[o.type];
    }
    if (champs.largeur != null) o.largeur = arrondi(champs.largeur, 3);
    if (champs.position != null) o.position = arrondi(champs.position, 3);
    marquer(v, o);
    return v;
  }

  function modifierMur(v0, id, champs) {
    const v = copie(v0);
    const m = v.logement.murs.find((x) => x.id === id);
    if (!m) throw new Error(`mur inconnu : ${id}`);
    if (champs.epaisseur != null) m.epaisseur = arrondi(champs.epaisseur, 3);
    marquer(v, m);
    return v;
  }

  function renommerPiece(v0, id, nom) {
    const v = copie(v0);
    const p = (v.logement.pieces || []).find((x) => x.id === id);
    if (!p) throw new Error(`pièce inconnue : ${id}`);
    if (!nom || !nom.trim()) throw new Error("le nom ne peut pas être vide");
    p.nom = nom.trim();
    marquer(v, p);
    return v;
  }

  /** Supprime un élément ; un mur emporte ses portes et fenêtres. */
  function supprimer(v0, id) {
    const v = copie(v0);
    const lg = v.logement;
    const t = trouver(lg, id);
    if (!t) throw new Error(`élément inconnu : ${id}`);
    if (t.genre === "mur") {
      if (lg.murs.length === 1) throw new Error("impossible de supprimer le dernier mur");
      lg.murs = lg.murs.filter((m) => m.id !== id);
      lg.ouvertures = (lg.ouvertures || []).filter((o) => o.mur !== id);
    } else if (t.genre === "ouverture") {
      lg.ouvertures = lg.ouvertures.filter((o) => o.id !== id);
    } else {
      lg.pieces = lg.pieces.filter((p) => p.id !== id);
    }
    return v;
  }

  function confirmer(v0, id) {
    const v = copie(v0);
    const t = trouver(v.logement, id);
    if (!t) throw new Error(`élément inconnu : ${id}`);
    marquer(v, t.e);
    return v;
  }

  function resoudre(v0, cle) {
    const v = copie(v0);
    v.resolus = [...new Set([...(v.resolus || []), cle])];
    return v;
  }

  /**
   * Applique une proposition en un clic (écrite par Atelya dans le fichier, ou proposée par la page).
   * `doute` sert pour « resoudre » : on range la clé de ce doute parmi les doutes réglés.
   */
  function appliquerAction(v, action, doute = null) {
    switch (action.type) {
      case "confirmer": return confirmer(v, action.id);
      case "supprimer": return supprimer(v, action.id);
      case "renommer": return renommerPiece(v, action.id, action.nom);
      case "ajouter_ouverture": {
        const w = ajouterOuverture(v, action.mur, action.ouverture, action.position + action.largeur / 2, action.largeur);
        return doute ? resoudre(w, doute.cle) : w;
      }
      case "resoudre": return resoudre(v, doute ? doute.cle : action.cle);
      default: throw new Error(`proposition inconnue : ${action.type}`);
    }
  }

  // ---------- Viser avec la souris ----------

  function inverse(m) {
    const [[a, b, c], [d, e, f], [g, h, i]] = m;
    const A = e * i - f * h, B = -(d * i - f * g), Cc = d * h - e * g;
    const det = a * A + b * B + c * Cc;
    if (Math.abs(det) < 1e-15) throw new Error("calage impossible à inverser");
    return [
      [A / det, -(b * i - c * h) / det, (b * f - c * e) / det],
      [B / det, (a * i - c * g) / det, -(a * f - c * d) / det],
      [Cc / det, -(a * h - b * g) / det, (a * e - b * d) / det],
    ];
  }

  function dansPolygone(p, poly) {
    let dedans = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const [xi, yi] = poly[i], [xj, yj] = poly[j];
      if ((yi > p[1]) !== (yj > p[1]) && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) dedans = !dedans;
    }
    return dedans;
  }

  /** L'élément sous un point (en m) : d'abord les ouvertures, puis les murs, puis les pièces. */
  function elementSous(lg, p, tolerance) {
    const murs = new Map(lg.murs.map((m) => [m.id, m]));
    for (const o of lg.ouvertures || []) {
      const m = murs.get(o.mur);
      if (m && dansPolygone(p, polygoneOuverture(o, m))) return { genre: "ouverture", id: o.id };
      if (m) {
        const { d } = axes(m);
        const a = [m.debut[0] + d[0] * o.position, m.debut[1] + d[1] * o.position];
        const b = [a[0] + d[0] * o.largeur, a[1] + d[1] * o.largeur];
        if (projection(p, a, b).dist <= tolerance) return { genre: "ouverture", id: o.id };
      }
    }
    let meilleur = null;
    for (const m of lg.murs) {
      const dist = projection(p, m.debut, m.fin).dist - m.epaisseur / 2;
      if (dist <= tolerance && (!meilleur || dist < meilleur.dist)) meilleur = { genre: "mur", id: m.id, dist };
    }
    if (meilleur) return { genre: "mur", id: meilleur.id };
    for (const piece of lg.pieces || []) if (dansPolygone(p, piece.contour)) return { genre: "piece", id: piece.id };
    return null;
  }

  /** Le mur le plus proche d'un point (pour poser une porte) et la position du point le long de ce mur. */
  function murLePlusProche(lg, p, tolerance) {
    let best = null;
    for (const m of lg.murs) {
      const pr = projection(p, m.debut, m.fin);
      if (pr.dist <= m.epaisseur / 2 + tolerance && (!best || pr.dist < best.dist)) best = { id: m.id, dist: pr.dist, le_long: pr.tt };
    }
    return best;
  }

  /**
   * Aimante le bout d'un nouveau mur : sur un bout de mur existant s'il est proche,
   * puis d'équerre (horizontal ou vertical) avec le point de départ.
   */
  function aimanter(lg, p, depart, rayon) {
    let q = p.slice();
    let best = rayon;
    for (const m of lg.murs) for (const b of [m.debut, m.fin]) {
      const d = longueur(p, b);
      if (d < best) { best = d; q = b.slice(); }
    }
    if (depart && best === rayon) {
      if (Math.abs(q[0] - depart[0]) > Math.abs(q[1] - depart[1])) q[1] = depart[1];
      else q[0] = depart[0];
    }
    return ar(q);
  }

  // ---------- Cohérence (mêmes règles que moteur/logement.py) ----------

  /** Les incohérences qui empêcheraient le moteur de lire le logement.json (vide si tout va bien). */
  function verifierCoherence(lg) {
    const erreurs = [];
    const tous = [...lg.murs, ...(lg.ouvertures || []), ...(lg.pieces || [])].map((e) => e.id);
    const doublons = [...new Set(tous.filter((id, i) => tous.indexOf(id) !== i))].sort();
    if (doublons.length) erreurs.push(`identifiants en double : ${doublons.join(", ")}`);
    if (!lg.murs.length) erreurs.push("aucun mur");
    const murs = new Map(lg.murs.map((m) => [m.id, m]));
    for (const m of lg.murs) {
      if (longueur(m.debut, m.fin) === 0) erreurs.push(`le mur ${m.id} a un début et une fin identiques`);
      if (!(m.epaisseur > 0)) erreurs.push(`le mur ${m.id} a une épaisseur nulle`);
    }
    for (const o of lg.ouvertures || []) {
      const m = murs.get(o.mur);
      if (!m) { erreurs.push(`l'ouverture ${o.id} désigne un mur inconnu : ${o.mur}`); continue; }
      const l = longueur(m.debut, m.fin);
      if (o.position < 0) erreurs.push(`l'ouverture ${o.id} commence avant le début du mur ${m.id}`);
      if (!(o.largeur > 0)) erreurs.push(`l'ouverture ${o.id} a une largeur nulle`);
      if (o.position + o.largeur > l + 1e-9) {
        erreurs.push(`l'ouverture ${o.id} dépasse du mur ${m.id} (${(o.position + o.largeur).toFixed(2)} m pour un mur de ${l.toFixed(2)} m)`);
      }
      const h = m.hauteur || lg.hauteur_sous_plafond;
      if (o.allege + o.hauteur > h + 1e-9) erreurs.push(`l'ouverture ${o.id} dépasse le haut du mur ${m.id}`);
    }
    for (const p of lg.pieces || []) {
      if (!p.nom || !p.nom.trim()) erreurs.push(`la pièce ${p.id} n'a pas de nom`);
      if (p.contour.length < 3) erreurs.push(`la pièce ${p.id} a moins de 3 coins`);
      if (p.surface != null && Math.abs(p.surface - surfacePolygone(p.contour)) > 0.01) {
        erreurs.push(`la pièce ${p.id} annonce ${p.surface.toFixed(2)} m² mais son contour mesure ${surfacePolygone(p.contour).toFixed(2)} m²`);
      }
    }
    return erreurs;
  }

  // ---------- Valider ----------

  const VERSION_RESULTAT = "resultat-verification/0.1";

  /**
   * Le résultat de la vérification : le logement.json corrigé, prêt pour le moteur,
   * et un petit rapport (qui a été corrigé, ce qui restait en doute).
   * Lève une erreur si le logement n'est pas lisible par le moteur.
   */
  function resultat(v, { quand = new Date().toISOString(), corrections = 0 } = {}) {
    const lg = copie(v.logement);
    const erreurs = verifierCoherence(lg);
    if (erreurs.length) throw new Error("le logement n'est pas encore cohérent : " + erreurs.join(" ; "));
    const restants = trouverDoutes(v);
    return {
      schema: VERSION_RESULTAT,
      projet_id: lg.projet_id,
      statut: restants.length ? "valide_avec_doutes" : "valide",
      logement: lg,
      rapport: {
        date: quand,
        corrections,
        elements_verifies: (v.verifies || []).length,
        doutes_restants: restants.map((d) => ({ element: d.element, raison: d.raison })),
        echelle: v.echelle || null,
      },
    };
  }

  // ---------- Lecture du fichier ----------

  /** Vérifie la forme d'un fichier de vérification et renvoie la liste des problèmes (vide si tout va bien). */
  function verifierFichier(v) {
    const erreurs = [];
    if (!v || typeof v !== "object") return ["le fichier n'est pas un objet JSON"];
    if (v.schema !== VERSION_VERIFICATION) erreurs.push(`schéma attendu « ${VERSION_VERIFICATION} »`);
    try { matriceDuCalage(v.calage); } catch (e) { erreurs.push(e.message); }
    const lg = v.logement;
    if (!lg || lg.schema !== "logement/0.1") erreurs.push("logement absent ou pas au format logement/0.1");
    else if (!Array.isArray(lg.murs) || lg.murs.length === 0) erreurs.push("le logement n'a aucun mur");
    return erreurs;
  }

  const CalculsVerif = {
    VERSION_VERIFICATION,
    SEUIL_CONFIANCE,
    arrondi,
    matriceDuCalage,
    versPixel,
    longueur,
    polygoneMur,
    polygoneOuverture,
    surfacePolygone,
    centrePolygone,
    trouverDoutes,
    verifierFichier,
    VERSION_RESULTAT,
    resultat,
    NOMS_PIECES,
    LARGEURS,
    deplacerMur,
    longueurMur,
    mettreAEchelle,
    ajouterMur,
    ajouterOuverture,
    modifierOuverture,
    modifierMur,
    renommerPiece,
    supprimer,
    confirmer,
    resoudre,
    appliquerAction,
    inverse,
    dansPolygone,
    elementSous,
    murLePlusProche,
    aimanter,
    verifierCoherence,
  };

  if (typeof module !== "undefined" && module.exports) module.exports = CalculsVerif;
  else racine.CalculsVerif = CalculsVerif;
})(this);
