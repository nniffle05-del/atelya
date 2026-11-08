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
 *
 * 08/11/2026 : le doute « plusieurs_niveaux » (moteur/doutes.py 0.2.0 : l'image dessine plusieurs niveaux
 * ou logements, un seul a été lu) devient le PREMIER point à vérifier, avant même l'échelle, avec les parties
 * non lues entourées (`blocs_px`, en pixels de l'image). Sans lui, rien ne disait qu'un étage manquait.
 */
(function (racine) {
  "use strict";

  const VERSION_VERIFICATION = "verification/0.1";
  const SEUIL_CONFIANCE = 0.7; // en dessous, Atelya hésite : l'élément passe en orange
  const MUR_COURT = 0.3; // m
  const PORTE_ETROITE = 0.55; // m
  const OUVERTURE_LARGE = 3.0; // m
  const RECOUVREMENT_TOLERE = 0.01; // m : même tolérance que moteur/geometrie.py entre deux ouvertures voisines

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
    const ajouter = (element, raison, zone_px = null, propositions = null, origine = null) => {
      const cle = `${element}|${raison}`;
      if (deja.has(cle) || resolus.has(cle) || (element != null && verifies.has(element))) return;
      deja.add(cle);
      const doute = { cle, element, zone_px, raison, propositions: propositions || propositionsAuto(lg, element) };
      if (origine && origine.code) doute.code = origine.code;
      if (origine && origine.gravite) doute.gravite = origine.gravite;
      if (origine && Array.isArray(origine.blocs_px)) doute.blocs_px = origine.blocs_px;
      doutes.push(doute);
    };

    const ids = new Set([...lg.murs, ...(lg.ouvertures || []), ...(lg.pieces || [])].map((e) => e.id));
    for (const d of verification.doutes || []) {
      if (d.element != null && !ids.has(d.element)) continue; // élément supprimé entre-temps
      ajouter(d.element ?? null, d.raison || "à vérifier", d.zone_px ?? null, d.propositions || null, d);
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
    // Ce qu'Atelya avait supposé d'après l'ancien nom (sol, plinthes, portes de placard) est oublié : il le supposera de nouveau
    // d'après le nouveau nom (un « Bureau » devenu « Salle d'eau » n'a pas de parquet). Ce que la personne a choisi reste.
    for (const k of ["sol", "plinthes", "placard"]) if (p[k] && p[k].statut === "ajoute") delete p[k];
    marquer(v, p);
    return v;
  }

  const CHOIX_PLINTHES = ["bois", "carrelage", "aucune"];

  /** Les plinthes d'une pièce, choisies par la personne (B2) : « bois », « carrelage » ou « aucune ». */
  function reglerPlinthes(v0, id, choix) {
    if (!CHOIX_PLINTHES.includes(choix)) throw new Error(`plinthes inconnues : ${choix}`);
    const v = copie(v0);
    const p = (v.logement.pieces || []).find((x) => x.id === id);
    if (!p) throw new Error(`pièce inconnue : ${id}`);
    p.plinthes = { choix, statut: "mesure", source: "verification", confiance: 1 };
    marquer(v, p);
    return v;
  }

  // B2-3 : les sols qu'Atelya sait poser (même liste, même ordre que moteur/matieres.py ; un test le vérifie).
  const SOLS = {
    parquet_chene_lames: "Parquet chêne, lames droites",
    parquet_batons_rompus: "Parquet bâtons rompus",
    point_de_hongrie: "Parquet point de Hongrie",
    stratifie: "Stratifié",
    carrelage_interieur: "Carrelage beige",
    carreaux_ciment: "Carreaux de ciment",
    tomettes: "Tomettes",
    damier_pierre: "Damier de pierre",
    pierre_beige: "Dalles de pierre beige",
  };

  /** Le sol d'une pièce, choisi par la personne. */
  function reglerSol(v0, id, matiere) {
    if (!(matiere in SOLS)) throw new Error(`sol inconnu : ${matiere}`);
    const v = copie(v0);
    const p = (v.logement.pieces || []).find((x) => x.id === id);
    if (!p) throw new Error(`pièce inconnue : ${id}`);
    p.sol = { matiere, statut: "mesure", source: "verification", confiance: 1 };
    marquer(v, p);
    return v;
  }

  const CHOIX_PLACARD = ["coulissantes", "battantes", "aucune"];
  // Même règle que moteur/habillage.py (est_placard) : le nom dit placard, et c'est petit (un grand dressing est une pièce).
  const MOTS_PLACARD = /placard|rangement|dressing|penderie/;
  const PLACARD_MAX = 4.0; // m²

  function sansAccents(texte) {
    return texte.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  }

  /** Cette pièce est-elle un placard (portes à choisir) ? */
  function estPlacard(p) {
    return !!p.placard || (MOTS_PLACARD.test(sansAccents(p.nom || "")) && surfacePolygone(p.contour) <= PLACARD_MAX);
  }

  /** Les portes d'un placard, choisies par la personne (B2-2) : « coulissantes », « battantes » ou « aucune ». */
  function reglerPlacard(v0, id, choix) {
    if (!CHOIX_PLACARD.includes(choix)) throw new Error(`portes de placard inconnues : ${choix}`);
    const v = copie(v0);
    const p = (v.logement.pieces || []).find((x) => x.id === id);
    if (!p) throw new Error(`pièce inconnue : ${id}`);
    p.placard = { choix, statut: "mesure", source: "verification", confiance: 1 };
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

  // ---------- Réunir des morceaux de pièce ----------

  const CELLULE_FUSION = 0.04; // m : finesse du calcul de la forme réunie
  const FERMETURE_FUSION = 2; // cellules : petits trous bouchés entre deux morceaux
  const TOLERANCE_CONTOUR = 0.06; // m : un contour réuni garde ses vrais angles, pas ses dents de scie

  function simplifier(points, tolerance) {
    if (points.length < 3) return points;
    let iMax = 0, dMax = 0;
    const a = points[0], b = points[points.length - 1];
    for (let i = 1; i < points.length - 1; i++) {
      const d = projection(points[i], a, b).dist;
      if (d > dMax) { dMax = d; iMax = i; }
    }
    if (dMax <= tolerance) return [a, b];
    return [...simplifier(points.slice(0, iMax + 1), tolerance).slice(0, -1), ...simplifier(points.slice(iMax), tolerance)];
  }

  /** Le contour extérieur de plusieurs polygones qui se touchent, calculé sur une grille fine. */
  function contourReuni(contours) {
    const tous = contours.flat();
    const x0 = Math.min(...tous.map((q) => q[0])), y0 = Math.min(...tous.map((q) => q[1]));
    const x1 = Math.max(...tous.map((q) => q[0])), y1 = Math.max(...tous.map((q) => q[1]));
    const c = Math.max(CELLULE_FUSION, Math.max(x1 - x0, y1 - y0) / 500);
    const marge = FERMETURE_FUSION + 2;
    const l = Math.ceil((x1 - x0) / c) + 2 * marge, h = Math.ceil((y1 - y0) / c) + 2 * marge;
    const X = (i) => x0 + (i - marge) * c, Y = (j) => y0 + (j - marge) * c;
    let grille = new Uint8Array(l * h);
    for (const contour of contours) {
      const ys = contour.map((q) => q[1]);
      const jMin = Math.max(0, Math.floor((Math.min(...ys) - y0) / c) + marge - 1), jMax = Math.min(h - 1, Math.ceil((Math.max(...ys) - y0) / c) + marge + 1);
      for (let j = jMin; j <= jMax; j++) {
        const yc = Y(j + 0.5), coupes = [];
        for (let k = 0, n = contour.length; k < n; k++) {
          const [xa, ya] = contour[k], [xb, yb] = contour[(k + 1) % n];
          if ((ya > yc) !== (yb > yc)) coupes.push(xa + ((yc - ya) * (xb - xa)) / (yb - ya));
        }
        coupes.sort((u, v) => u - v);
        for (let k = 0; k + 1 < coupes.length; k += 2) {
          const iA = Math.max(0, Math.round((coupes[k] - x0) / c) + marge), iB = Math.min(l, Math.round((coupes[k + 1] - x0) / c) + marge);
          grille.fill(1, j * l + iA, j * l + iB);
        }
      }
    }
    for (let k = 0; k < FERMETURE_FUSION; k++) grille = voisinageGrille(grille, l, h, 1);
    for (let k = 0; k < FERMETURE_FUSION; k++) grille = voisinageGrille(grille, l, h, 0);
    return bordDeLaGrille(grille, l, h, X, Y);
  }

  /** Étend (valeur 1) ou rétrécit (valeur 0) d'une cellule ce qui est plein dans la grille. */
  function voisinageGrille(entree, l, h, valeur) {
    const sortie = new Uint8Array(l * h);
    for (let j = 0; j < h; j++) for (let i = 0; i < l; i++) {
      let v = valeur === 0 ? 1 : 0;
      for (let dj = -1; dj <= 1 && v !== valeur; dj++) for (let di = -1; di <= 1; di++) {
        const u = i + di, w = j + dj;
        const e = u >= 0 && w >= 0 && u < l && w < h ? entree[w * l + u] : 0;
        if (e === valeur) { v = valeur; break; }
      }
      sortie[j * l + i] = v;
    }
    return sortie;
  }

  /** Le contour extérieur, simplifié, de ce qui est plein dans la grille (en mètres, grâce à X et Y). */
  function bordDeLaGrille(grille, l, h, X, Y) {
    // Le bord : chaque côté de cellule pleine qui touche une cellule vide, relié au suivant.
    const suivants = new Map();
    const lien = (a, b) => { if (!suivants.has(a)) suivants.set(a, []); suivants.get(a).push(b); };
    const P = (i, j) => j * (l + 1) + i;
    const plein = (i, j) => i >= 0 && j >= 0 && i < l && j < h && grille[j * l + i] === 1;
    for (let j = 0; j < h; j++) for (let i = 0; i < l; i++) {
      if (!plein(i, j)) continue;
      if (!plein(i, j - 1)) lien(P(i, j), P(i + 1, j));
      if (!plein(i + 1, j)) lien(P(i + 1, j), P(i + 1, j + 1));
      if (!plein(i, j + 1)) lien(P(i + 1, j + 1), P(i, j + 1));
      if (!plein(i - 1, j)) lien(P(i, j + 1), P(i, j));
    }
    let meilleure = [];
    while (suivants.size) {
      const depart = suivants.keys().next().value;
      const boucle = [];
      let q = depart;
      while (suivants.has(q)) {
        boucle.push(q);
        const liste = suivants.get(q);
        const r = liste.shift();
        if (!liste.length) suivants.delete(q);
        q = r;
        if (q === depart) break;
      }
      if (boucle.length > meilleure.length) meilleure = boucle;
    }
    const brut = meilleure.map((q) => [X(q % (l + 1)), Y(Math.floor(q / (l + 1)))]);
    if (brut.length < 3) throw new Error("ces pièces ne peuvent pas être réunies");
    // Pour simplifier une boucle fermée : on la coupe en deux au point le plus loin de son départ.
    let loin = 0;
    brut.forEach((q, i) => { if (longueur(q, brut[0]) > longueur(brut[loin], brut[0])) loin = i; });
    const moitie1 = simplifier(brut.slice(0, loin + 1), TOLERANCE_CONTOUR);
    const moitie2 = simplifier([...brut.slice(loin), brut[0]], TOLERANCE_CONTOUR);
    return [...moitie1.slice(0, -1), ...moitie2.slice(0, -1)].map(ar);
  }

  /** Réunit des pièces en une seule, qui garde le nom donné (par défaut, celui de la plus grande). */
  function fusionnerPieces(v0, ids, nom = null) {
    const v = copie(v0);
    const lg = v.logement;
    const pieces = (lg.pieces || []).filter((p) => ids.includes(p.id));
    if (pieces.length < 2) throw new Error("il faut au moins deux pièces à réunir");
    pieces.sort((a, b) => surfacePolygone(b.contour) - surfacePolygone(a.contour));
    const garde = pieces[0];
    garde.contour = contourReuni(pieces.map((p) => p.contour));
    delete garde.surface;
    if (nom && nom.trim()) garde.nom = nom.trim();
    lg.pieces = lg.pieces.filter((p) => p === garde || !ids.includes(p.id));
    marquer(v, garde);
    return v;
  }

  const CONTACT_MAX = 0.18; // m : deux morceaux de pièce à moins de ça, sans mur entre eux, se touchent
  const CONTACT_MIN = 0.4; // m : un contact plus court (un coin) ne compte pas

  function presDUnMur(lg, p) {
    return lg.murs.some((m) => projection(p, m.debut, m.fin).dist <= m.epaisseur / 2 + 0.005);
  }

  /** Longueur (m) le long de laquelle deux pièces se touchent sans qu'un mur les sépare. */
  function contactSansMur(lg, a, b) {
    const boite = (c) => [Math.min(...c.map((q) => q[0])), Math.min(...c.map((q) => q[1])), Math.max(...c.map((q) => q[0])), Math.max(...c.map((q) => q[1]))];
    const A = boite(a.contour), B = boite(b.contour);
    if (A[0] > B[2] + CONTACT_MAX || B[0] > A[2] + CONTACT_MAX || A[1] > B[3] + CONTACT_MAX || B[1] > A[3] + CONTACT_MAX) return 0;
    const contacts = [];
    for (let i = 0, n = a.contour.length; i < n; i++) {
      const q = a.contour[i], r = a.contour[(i + 1) % n];
      const pas = Math.max(1, Math.ceil(longueur(q, r) / 0.1));
      for (let k = 0; k < pas; k++) {
        const s = [q[0] + ((r[0] - q[0]) * k) / pas, q[1] + ((r[1] - q[1]) * k) / pas];
        let best = null;
        for (let j = 0, m = b.contour.length; j < m; j++) {
          const u = b.contour[j], w = b.contour[(j + 1) % m];
          const pr = projection(s, u, w);
          if (!best || pr.dist < best.dist) {
            const l = longueur(u, w) || 1;
            best = { dist: pr.dist, pied: [u[0] + ((w[0] - u[0]) * pr.tt) / l, u[1] + ((w[1] - u[1]) * pr.tt) / l] };
          }
        }
        if (best.dist <= CONTACT_MAX && !presDUnMur(lg, [(s[0] + best.pied[0]) / 2, (s[1] + best.pied[1]) / 2])) contacts.push(s);
      }
    }
    if (contacts.length < 2) return 0;
    const b2 = boite(contacts);
    return Math.hypot(b2[2] - b2[0], b2[3] - b2[1]);
  }

  /** Les groupes de pièces (2 ou plus) qui semblent n'être qu'une seule pièce : aucun mur ne les sépare. */
  function morceauxDePieces(lg) {
    const pieces = lg.pieces || [];
    const parent = pieces.map((_, i) => i);
    const racineDe = (i) => (parent[i] === i ? i : (parent[i] = racineDe(parent[i])));
    for (let i = 0; i < pieces.length; i++) for (let j = i + 1; j < pieces.length; j++) {
      if (contactSansMur(lg, pieces[i], pieces[j]) >= CONTACT_MIN) parent[racineDe(i)] = racineDe(j);
    }
    const groupes = new Map();
    pieces.forEach((p, i) => { const r = racineDe(i); if (!groupes.has(r)) groupes.set(r, []); groupes.get(r).push(p.id); });
    return [...groupes.values()].filter((g) => g.length >= 2);
  }

  // ---------- Retoucher les murs ----------

  /** Change un bout de mur de place. Les portes et fenêtres gardent leur place réelle sur le plan. */
  function deplacerBout(v0, id, bout, point) {
    const v = copie(v0);
    const mur = v.logement.murs.find((m) => m.id === id);
    if (!mur) throw new Error(`mur inconnu : ${id}`);
    const { d } = axes(mur);
    const places = (v.logement.ouvertures || []).filter((o) => o.mur === id).map((o) => ({
      o, depart: [mur.debut[0] + d[0] * o.position, mur.debut[1] + d[1] * o.position],
    }));
    mur[bout] = ar(point);
    const l = longueur(mur.debut, mur.fin);
    if (l < 0.05) throw new Error("ce mur serait trop court");
    const n = axes(mur).d;
    for (const { o, depart } of places) {
      const t = (depart[0] - mur.debut[0]) * n[0] + (depart[1] - mur.debut[1]) * n[1];
      if (t < -0.02 || t + o.largeur > l + 0.02) throw new Error("une porte ou une fenêtre empêche de raccourcir ce mur autant : déplacez-la ou supprimez-la d'abord");
      o.position = arrondi(Math.max(0, Math.min(l - o.largeur - 1e-3, t)), 3);
    }
    marquer(v, mur);
    return v;
  }

  /**
   * Où poser un bout de mur que l'on fait glisser près du point `p` (m). Par ordre de préférence : sur le bout d'un
   * autre mur ; là où le mur prolongé tout droit rencontre un autre mur ; sur le côté d'un autre mur ; tout droit.
   * Rend {point, accroche} ; `accroche` : ce qui a retenu le bout (null si rien).
   */
  function accrocherBout(lg, id, bout, p, rayon) {
    const mur = lg.murs.find((m) => m.id === id);
    const fixe = bout === "fin" ? mur.debut : mur.fin;
    const vers = bout === "fin" ? mur.fin : mur.debut;
    const l = longueur(fixe, vers) || 1;
    const dir = [(vers[0] - fixe[0]) / l, (vers[1] - fixe[1]) / l];
    const autres = lg.murs.filter((m) => m.id !== id);
    let meilleur = null, dist = rayon;
    for (const m of autres) for (const b of [m.debut, m.fin]) {
      const e = longueur(p, b);
      if (e < dist) { dist = e; meilleur = b; }
    }
    if (meilleur) return { point: ar(meilleur), accroche: "bout" };
    dist = rayon * 1.5;
    for (const m of autres) {
      const e = [m.fin[0] - m.debut[0], m.fin[1] - m.debut[1]];
      const croix = dir[0] * e[1] - dir[1] * e[0];
      if (Math.abs(croix) < 0.05) continue;
      const w = [m.debut[0] - fixe[0], m.debut[1] - fixe[1]];
      const t = (w[0] * e[1] - w[1] * e[0]) / croix;
      const u = (w[0] * dir[1] - w[1] * dir[0]) / croix;
      const marge = m.epaisseur / (longueur(m.debut, m.fin) || 1);
      if (t <= 0.05 || u < -marge || u > 1 + marge) continue;
      const q = [fixe[0] + dir[0] * t, fixe[1] + dir[1] * t];
      const ecart = longueur(p, q);
      if (ecart < dist) { dist = ecart; meilleur = q; }
    }
    if (meilleur) return { point: ar(meilleur), accroche: "mur" };
    dist = rayon;
    for (const m of autres) {
      const pr = projection(p, m.debut, m.fin);
      if (pr.dist < dist) {
        const lm = longueur(m.debut, m.fin) || 1;
        dist = pr.dist;
        meilleur = [m.debut[0] + ((m.fin[0] - m.debut[0]) * pr.tt) / lm, m.debut[1] + ((m.fin[1] - m.debut[1]) * pr.tt) / lm];
      }
    }
    if (meilleur) return { point: ar(meilleur), accroche: "mur" };
    const t = (p[0] - fixe[0]) * dir[0] + (p[1] - fixe[1]) * dir[1];
    const q = [fixe[0] + dir[0] * t, fixe[1] + dir[1] * t];
    if (t > 0 && longueur(p, q) <= t * Math.tan((6 * Math.PI) / 180)) return { point: ar(q), accroche: null }; // il reste bien droit
    return { point: ar(p), accroche: null };
  }

  const pointSurMur = (m, t) => { const { d } = axes(m); return ar([m.debut[0] + d[0] * t, m.debut[1] + d[1] * t]); };

  /**
   * Une position le long d'un mur, au centimètre, retenue près d'un repère utile : le bord d'une porte ou d'une fenêtre,
   * ou l'endroit où un autre mur arrive. Rend {t, repere}.
   */
  function aimanterSurMur(lg, id, t, rayon) {
    const mur = lg.murs.find((m) => m.id === id);
    const { l, d } = axes(mur);
    const reperes = [];
    for (const o of lg.ouvertures || []) if (o.mur === id) reperes.push(o.position, o.position + o.largeur);
    for (const m of lg.murs) {
      if (m.id === id) continue;
      for (const b of [m.debut, m.fin]) {
        const pr = projection(b, mur.debut, mur.fin);
        if (pr.dist <= mur.epaisseur / 2 + m.epaisseur / 2 + PRES) reperes.push((b[0] - mur.debut[0]) * d[0] + (b[1] - mur.debut[1]) * d[1]);
      }
    }
    let meilleur = null, dist = rayon;
    for (const r of reperes) if (r > 0 && r < l && Math.abs(r - t) < dist) { dist = Math.abs(r - t); meilleur = r; }
    return meilleur === null ? { t: arrondi(Math.max(0, Math.min(l, t)), 2), repere: false } : { t: arrondi(meilleur, 3), repere: true };
  }

  /** Coupe un mur en deux à `t` mètres de son début : chaque morceau peut ensuite se retoucher ou se supprimer à part. */
  function couperMur(v0, id, t) {
    const v = copie(v0);
    const lg = v.logement;
    const mur = lg.murs.find((m) => m.id === id);
    if (!mur) throw new Error(`mur inconnu : ${id}`);
    const l = longueur(mur.debut, mur.fin);
    if (t < 0.03 || t > l - 0.03) throw new Error("trop près du bout du mur pour le couper");
    const ouvertures = (lg.ouvertures || []).filter((o) => o.mur === id);
    if (ouvertures.some((o) => o.position < t && o.position + o.largeur > t)) throw new Error("cet endroit tombe sur une porte ou une fenêtre : coupez à côté");
    const coupe = pointSurMur(mur, t);
    const second = { ...copie(mur), id: nouvelId(lg, "M_v"), debut: coupe };
    mur.fin = coupe;
    lg.murs.splice(lg.murs.indexOf(mur) + 1, 0, second);
    for (const o of ouvertures) if (o.position >= t) { o.mur = second.id; o.position = arrondi(o.position - t, 3); }
    marquer(v, mur);
    marquer(v, second);
    return v;
  }

  /** Enlève le morceau de mur entre `a` et `b` (m depuis son début), ainsi que les portes et fenêtres qui s'y trouvent. */
  function enleverMorceau(v0, id, a, b) {
    const t0 = Math.min(a, b), t1 = Math.max(a, b);
    if (t1 - t0 < 0.03) throw new Error("le morceau à enlever est trop petit");
    const mur0 = v0.logement.murs.find((m) => m.id === id);
    if (!mur0) throw new Error(`mur inconnu : ${id}`);
    const l = longueur(mur0.debut, mur0.fin);
    const coupeFin = t1 <= l - 0.03, coupeDebut = t0 >= 0.03;
    const dedans = (o) => o.position + o.largeur > t0 && o.position < t1;
    const traverse = (o) => (o.position < t0 && o.position + o.largeur > t0) || (o.position < t1 && o.position + o.largeur > t1);
    if ((v0.logement.ouvertures || []).some((o) => o.mur === id && traverse(o))) throw new Error("ce morceau coupe une porte ou une fenêtre : commencez ou finissez à côté");
    let v = copie(v0);
    v.logement.ouvertures = (v.logement.ouvertures || []).filter((o) => o.mur !== id || !dedans(o));
    if (!coupeDebut && !coupeFin) return supprimer(v, id);
    if (!coupeDebut) return deplacerBout(v, id, "debut", pointSurMur(mur0, t1));
    if (!coupeFin) return deplacerBout(v, id, "fin", pointSurMur(mur0, t0));
    v = couperMur(v, id, t1);
    return deplacerBout(v, id, "fin", pointSurMur(mur0, t0));
  }

  /** Relie deux bouts de murs : ils se prolongent jusqu'à se rejoindre, ou un petit mur comble le trou s'ils sont alignés. */
  function relierMurs(v0, idA, boutA, idB, boutB) {
    if (idA === idB) throw new Error("choisissez les bouts de deux murs différents");
    const A = v0.logement.murs.find((m) => m.id === idA), B = v0.logement.murs.find((m) => m.id === idB);
    if (!A || !B) throw new Error("mur inconnu");
    const pA = A[boutA], pB = B[boutB];
    const ecart = longueur(pA, pB);
    if (ecart < 0.005) throw new Error("ces deux bouts sont déjà reliés");
    const da = axes(A).d, db = axes(B).d;
    const croix = da[0] * db[1] - da[1] * db[0];
    if (Math.abs(croix) >= 0.1) {
      const w = [pB[0] - pA[0], pB[1] - pA[1]];
      const t = (w[0] * db[1] - w[1] * db[0]) / croix;
      const I = ar([pA[0] + da[0] * t, pA[1] + da[1] * t]);
      if (longueur(I, pA) + longueur(I, pB) <= 2 * ecart + 0.5) return deplacerBout(deplacerBout(v0, idA, boutA, I), idB, boutB, I);
    }
    return ajouterMur(v0, pA, pB, Math.min(A.epaisseur, B.epaisseur));
  }

  /** Le bout de mur le plus proche d'un point : {id, bout, point}, ou null. */
  function boutLePlusProche(lg, p, rayon, sauf = null) {
    let best = null, dist = rayon;
    for (const m of lg.murs) for (const bout of ["debut", "fin"]) {
      if (sauf && m.id === sauf) continue;
      const e = longueur(p, m[bout]);
      if (e < dist) { dist = e; best = { id: m.id, bout, point: m[bout] }; }
    }
    return best;
  }

  // ---------- Refaire les pièces à partir des murs ----------

  const PIECE_MIN = 0.25; // m² : plus petit, ce n'est pas une pièce mais un vide entre deux murs

  /**
   * Les pièces, déduites des murs : chaque espace entièrement fermé par des murs devient une pièce, qui garde le nom de
   * la pièce qu'elle recouvre le plus. Une ancienne pièce qui n'est plus fermée (il manque un mur) reste telle quelle et
   * est signalée dans `ouvertes`. Rend {pieces, ouvertes, reunies, nouvelles}.
   */
  function piecesDepuisMurs(lg) {
    const tous = lg.murs.flatMap((m) => polygoneMur(m));
    const x0 = Math.min(...tous.map((q) => q[0])), y0 = Math.min(...tous.map((q) => q[1]));
    const x1 = Math.max(...tous.map((q) => q[0])), y1 = Math.max(...tous.map((q) => q[1]));
    const c = Math.max(CELLULE_FUSION, Math.max(x1 - x0, y1 - y0) / 700);
    const marge = 3;
    const l = Math.ceil((x1 - x0) / c) + 2 * marge, h = Math.ceil((y1 - y0) / c) + 2 * marge;
    const X = (i) => x0 + (i - marge) * c, Y = (j) => y0 + (j - marge) * c;
    const remplir = (grille, contour, valeur = 1) => {
      const ys = contour.map((q) => q[1]);
      const jMin = Math.max(0, Math.floor((Math.min(...ys) - y0) / c) + marge - 1), jMax = Math.min(h - 1, Math.ceil((Math.max(...ys) - y0) / c) + marge + 1);
      for (let j = jMin; j <= jMax; j++) {
        const yc = Y(j + 0.5), coupes = [];
        for (let k = 0, n = contour.length; k < n; k++) {
          const [xa, ya] = contour[k], [xb, yb] = contour[(k + 1) % n];
          if ((ya > yc) !== (yb > yc)) coupes.push(xa + ((yc - ya) * (xb - xa)) / (yb - ya));
        }
        coupes.sort((u, v) => u - v);
        for (let k = 0; k + 1 < coupes.length; k += 2) {
          const iA = Math.max(0, Math.floor((coupes[k] - x0) / c) + marge), iB = Math.min(l, Math.ceil((coupes[k + 1] - x0) / c) + marge);
          grille.fill(valeur, j * l + iA, j * l + iB);
        }
      }
    };
    let murs = new Uint8Array(l * h);
    for (const m of lg.murs) remplir(murs, polygoneMur(m));
    murs = voisinageGrille(murs, l, h, 1); // bouche les jours minuscules entre deux murs qui se touchent presque

    // Numérote les espaces vides ; celui qui touche le bord de la grille est l'extérieur.
    const etiquettes = new Int32Array(l * h).fill(-1);
    const espaces = [];
    for (let depart = 0; depart < l * h; depart++) {
      if (murs[depart] || etiquettes[depart] >= 0) continue;
      const pile = [depart], cellules = [];
      etiquettes[depart] = espaces.length;
      let exterieur = false;
      while (pile.length) {
        const q = pile.pop();
        cellules.push(q);
        const i = q % l, j = (q - i) / l;
        if (i === 0 || j === 0 || i === l - 1 || j === h - 1) { exterieur = true; continue; }
        for (const r of [q - 1, q + 1, q - l, q + l]) if (!murs[r] && etiquettes[r] < 0) { etiquettes[r] = espaces.length; pile.push(r); }
      }
      espaces.push({ cellules, exterieur });
    }

    const anciennes = lg.pieces || [];
    const recouvrement = anciennes.map((p) => {
      const g = new Uint8Array(l * h);
      remplir(g, p.contour);
      const parEspace = new Map();
      for (let q = 0; q < l * h; q++) if (g[q] && etiquettes[q] >= 0) parEspace.set(etiquettes[q], (parEspace.get(etiquettes[q]) || 0) + 1);
      return parEspace;
    });
    const pieces = [], gardees = new Set();
    let idsPris = { murs: lg.murs, ouvertures: lg.ouvertures, pieces: [] };
    espaces.forEach((e, k) => {
      if (e.exterieur || e.cellules.length * c * c < PIECE_MIN) return;
      // L'ancienne pièce qui a le plus de surface dans cet espace donne son nom ; la plus grande en cas de morceaux.
      let meilleure = null, plus = 0;
      anciennes.forEach((p, i) => { const n = recouvrement[i].get(k) || 0; if (n > plus) { plus = n; meilleure = p; } });
      const grille = new Uint8Array(l * h);
      for (const q of e.cellules) grille[q] = 1;
      const contour = bordDeLaGrille(voisinageGrille(grille, l, h, 1), l, h, X, Y); // rend la cellule prise par le rebouchage
      const piece = meilleure && !gardees.has(meilleure.id)
        ? { ...copie(meilleure), contour }
        : { id: null, nom: meilleure ? meilleure.nom : "Pièce", contour, statut: "estime", source: "verification", confiance: 1 };
      if (meilleure) gardees.add(meilleure.id);
      delete piece.surface;
      if (!piece.id) { idsPris.pieces = [...anciennes, ...pieces]; piece.id = nouvelId(idsPris, "P_v"); }
      pieces.push(piece);
    });
    // Une ancienne pièce sans espace fermé à elle : il manque sans doute un mur, on ne la perd pas sans le dire.
    const ouvertes = anciennes.filter((p, i) => {
      if (gardees.has(p.id)) return false;
      let ferme = 0, total = 0;
      recouvrement[i].forEach((n, k) => { total += n; if (!espaces[k].exterieur && n * c * c >= 0) ferme += n; });
      return total === 0 || ferme / total < 0.5;
    });
    const reunies = anciennes.length - gardees.size - ouvertes.length;
    return { pieces: [...pieces, ...ouvertes.map(copie)], ouvertes: ouvertes.map((p) => p.nom), reunies,
      nouvelles: pieces.filter((x) => !anciennes.some((a) => a.id === x.id)).length,
      fuites: ouvertes.map((p) => fuiteDePiece(lg, p)) };
  }

  const FUITE_MIN = 0.25; // m : un passage plus court le long d'un contour n'est pas un trou dans les murs
  const FUITE_LIBRE = 0.15; // m : plus loin que ça d'un mur, le contour n'est plus bordé par un mur

  /**
   * Où une pièce n'est pas fermée : le plus long passage de son contour qu'aucun mur ne borde, de préférence celui qui
   * donne sur l'extérieur du logement. Rend {piece, nom, a, b, longueur, mur} ; `mur` : le mur qui fermerait ce trou,
   * d'un bout de mur voisin à l'autre, s'il y en a ; a et b sont null si le passage n'a pas pu être situé.
   */
  function fuiteDePiece(lg, piece) {
    const contour = piece.contour;
    const prochDUnMur = (q, marge) => lg.murs.some((m) => projection(q, m.debut, m.fin).dist <= m.epaisseur / 2 + marge);
    const passages = [];
    let courant = null;
    const fermer = () => { if (courant && longueur(courant.a, courant.b) >= FUITE_MIN) passages.push(courant); courant = null; };
    for (let i = 0, n = contour.length; i < n; i++) {
      const q = contour[i], r = contour[(i + 1) % n];
      const l = longueur(q, r);
      const pas = Math.max(1, Math.ceil(l / 0.05));
      for (let k = 0; k <= pas; k++) {
        const s0 = [q[0] + ((r[0] - q[0]) * k) / pas, q[1] + ((r[1] - q[1]) * k) / pas];
        if (prochDUnMur(s0, FUITE_LIBRE)) { fermer(); continue; }
        if (!courant) courant = { a: s0, b: s0, cote: [q, r] };
        else courant.b = s0;
      }
      fermer();
    }
    const tous = lg.murs.flatMap((m) => [m.debut, m.fin]);
    const x0 = Math.min(...tous.map((q) => q[0])) - 1, x1 = Math.max(...tous.map((q) => q[0])) + 1;
    const y0 = Math.min(...tous.map((q) => q[1])) - 1, y1 = Math.max(...tous.map((q) => q[1])) + 1;
    const donneDehors = (f) => {
      const m = [(f.a[0] + f.b[0]) / 2, (f.a[1] + f.b[1]) / 2];
      const lf = longueur(f.cote[0], f.cote[1]) || 1;
      let n = [-(f.cote[1][1] - f.cote[0][1]) / lf, (f.cote[1][0] - f.cote[0][0]) / lf];
      if (dansPolygone([m[0] + n[0] * 0.05, m[1] + n[1] * 0.05], contour)) n = [-n[0], -n[1]];
      for (let t = 0.05; t < 60; t += 0.1) {
        const q = [m[0] + n[0] * t, m[1] + n[1] * t];
        if (q[0] < x0 || q[0] > x1 || q[1] < y0 || q[1] > y1) return true;
        if (prochDUnMur(q, 0)) return false;
      }
      return true;
    };
    const classes = passages.map((f) => ({ f, l: longueur(f.a, f.b), dehors: donneDehors(f) }));
    classes.sort((u, w) => (w.dehors - u.dehors) || (w.l - u.l));
    if (!classes.length) return { piece: piece.id, nom: piece.nom, a: null, b: null, longueur: 0, mur: null };
    const { f, l } = classes[0];
    const a = ar(f.a), b = ar(f.b);
    const boutProche = (q, sauf) => {
      let best = null, d = 0.7;
      for (const m of lg.murs) for (const c of [m.debut, m.fin]) {
        if (sauf && longueur(c, sauf.point) < 0.2) continue;
        const e = longueur(q, c);
        if (e < d) { d = e; best = { point: c, epaisseur: m.epaisseur }; }
      }
      return best;
    };
    const u = boutProche(a, null);
    const w = u && boutProche(b, u);
    const mur = u && w ? { debut: u.point, fin: w.point, epaisseur: Math.max(u.epaisseur, w.epaisseur) } : null;
    return { piece: piece.id, nom: piece.nom, a, b, longueur: arrondi(l), mur };
  }

  /** Remplace les pièces par celles que dessinent les murs. Le détail reste calculable par piecesDepuisMurs. */
  function recalculerPieces(v0) {
    const v = copie(v0);
    const r = piecesDepuisMurs(v.logement);
    const ids = new Set(r.pieces.map((p) => p.id));
    v.logement.pieces = r.pieces;
    v.verifies = [...new Set([...(v.verifies || []), ...ids])];
    return v;
  }

  // ---------- Les points à vérifier, un par un ----------
  //
  // Les doutes restent ceux d'Atelya, sans aucun seuil changé : on les présente seulement autrement.
  // Ce qui revient au même (morceaux d'une pièce, morceaux de mur voisins, petites hésitations) forme un seul point.

  const REGROUPER_ZONE_M = 0.6; // m : deux doutes de mur plus proches que ça sont le même endroit du plan
  const CODES_ZONE = new Set(["carte", "epaisseur", "zone_douteuse"]);
  const fr = (v, d = 2) => v.toFixed(d).replace(".", ",");

  function boitePixels(points) {
    const xs = points.map((q) => q[0]), ys = points.map((q) => q[1]);
    const x = Math.min(...xs), y = Math.min(...ys);
    return [x, y, Math.max(...xs) - x, Math.max(...ys) - y];
  }

  function unirBoites(boites) {
    return boitePixels(boites.flatMap(([x, y, l, h]) => [[x, y], [x + l, y + h]]));
  }

  function nomSimple(lg, id) {
    const t = trouver(lg, id);
    if (!t) return "cet élément";
    if (t.genre === "piece") return `« ${t.e.nom} »`;
    if (t.genre === "ouverture") return { porte: "cette porte", fenetre: "cette fenêtre", porte_fenetre: "cette porte-fenêtre" }[t.e.type];
    return "ce mur";
  }

  /** Remplace, dans une phrase écrite par Atelya, les codes internes (chambre_1) par les noms des pièces. */
  function phraseLisible(lg, raison) {
    let t = raison;
    for (const p of lg.pieces || []) t = t.split(p.id).join(`« ${p.nom} »`);
    return t.charAt(0).toUpperCase() + t.slice(1);
  }

  function pointSeul(lg, d) {
    const t = trouver(lg, d.element);
    const garder = (libelle) => ({ libelle, action: { type: "regler" }, principal: false });
    const enlever = (libelle) => ({ libelle, action: { type: "supprimer_tout" }, danger: true });
    let titre = "À vérifier", texte = phraseLisible(lg, d.raison), actions = [garder("C'est juste")];
    if (t && t.genre === "ouverture") {
      const genre = { porte: ["Porte", "La"], fenetre: ["Fenêtre", "La"], porte_fenetre: ["Porte-fenêtre", "La"] }[t.e.type];
      titre = genre[0];
      actions = [garder(`${genre[1]} garder`), enlever(`${genre[1]} supprimer`)];
      if (d.code === "largeur_porte" || d.code === "largeur_fenetre") {
        const cm = /(\d+)\s*cm/.exec(d.raison);
        const largeur = cm ? `${cm[1]} cm` : `${fr(t.e.largeur)} m`;
        texte = `${nomSimple(lg, d.element).replace(/^c/, "C")} fait ${largeur} de large : cela paraît ${t.e.largeur < 0.6 ? "très étroit" : "inhabituel"}.`;
      } else if (d.code === "fenetre_interieure") {
        texte = `${nomSimple(lg, d.element).replace(/^c/, "C")} semble donner à l'intérieur du logement, pas vers l'extérieur.`;
      }
    } else if (t && t.genre === "piece") {
      const surface = surfacePolygone(t.e.contour);
      titre = `Pièce ${t.e.nom}`;
      actions = [garder("La garder"), enlever("La supprimer")];
      if (d.code === "surface") texte = `Cette pièce ne ferait que ${fr(surface)} m² : cela paraît ${surface < 2 ? "très petit" : "inhabituel"}.`;
      if (d.code === "sans_acces") {
        texte = `Aucune porte ni passage trouvés pour entrer dans cette pièce.`;
        actions = [{ libelle: "Ajouter une porte", action: { type: "outil", outil: "porte" }, principal: true }, garder("C'est normal")];
      }
      if (d.code === "type_hesitant") actions = [garder("Le nom est bon")];
    } else if (t && t.genre === "mur") {
      titre = "Mur";
      actions = [garder("Il est juste"), enlever("Le supprimer")];
    } else if (d.code === "coloriage_douteux") {
      titre = "Lecture difficile";
      texte = "Ce plan a été difficile à lire : regardez-le avec un peu plus d'attention.";
      actions = [garder("Compris")];
    }
    return { cle: `seul|${d.cle}`, genre: "element", titre, texte, elements: d.element ? [d.element] : [], doutes: [d], zone_px: d.zone_px || null, actions };
  }

  /** Tout ce que la personne doit regarder, dans l'ordre, chaque point étant expliqué en français. */
  function pointsAVerifier(v, options = {}) {
    const lg = v.logement;
    const enDetail = new Set(options.detail || []); // les doutes que la personne veut voir un par un
    const m = matriceDuCalage(v.calage);
    const px = (q) => versPixel(m, q);
    const murs = new Map(lg.murs.map((x) => [x.id, x]));
    const verifies = new Set(v.verifies || []);
    const resolus = new Set(v.resolus || []);
    const points = [];
    let doutes = trouverDoutes(v);
    // 0. Un niveau entier non lu, avant tout le reste : le reste ne sert à rien si la moitié du logement manque.
    //    Le texte est la phrase d'Atelya telle quelle (déjà écrite pour la personne, sans code de pièce).
    for (const d of doutes.filter((x) => x.code === "plusieurs_niveaux")) {
      points.push({ cle: `niveaux|${d.cle}`, genre: "niveaux", titre: "Plusieurs niveaux sur cette image",
        texte: d.raison, elements: [], doutes: [d], zone_px: d.zone_px || null, zones_px: d.blocs_px || null,
        actions: [{ libelle: "Compris, je continue", action: { type: "regler" }, principal: true }] });
    }
    doutes = doutes.filter((x) => x.code !== "plusieurs_niveaux");
    if (options.fermeture) {
      // Après un recalcul des pièces : ce qui n'est pas fermé, montré à son endroit exact, avant tout le reste.
      for (const f of piecesDepuisMurs(lg).fuites) {
        const cle = `fuite|${f.piece}`;
        if (resolus.has(cle)) continue;
        const situe = f.a !== null;
        const taille = situe ? `${fr(f.longueur)} m` : "";
        points.push({ cle, genre: "fuite", titre: `« ${f.nom} » n'est pas fermée`, doutes: [],
          texte: situe
            ? `Aucun mur ne ferme cette pièce à l'endroit marqué en rouge, sur ${taille}. Atelya ne peut donc pas la calculer. S'il y a une porte d'entrée à cet endroit, fermez avec un mur, puis ajoutez la porte dessus.`
            : "Cette pièce touche l'extérieur, mais Atelya ne trouve pas où. Regardez son contour et ajoutez le mur manquant.",
          elements: [f.piece], trait_m: situe ? [f.a, f.b] : null, mur_propose: f.mur,
          zone_px: situe ? boitePixels([px(f.a), px(f.b)]) : boitePixels(trouver(lg, f.piece).e.contour.map(px)),
          actions: [...(f.mur ? [{ libelle: "Ajouter le mur manquant", action: { type: "fermer", ...f.mur }, principal: true }] : []),
            { libelle: "C'est normal (balcon, ouvert)", action: { type: "regler" } }] });
      }
      for (const n of (lg.pieces || []).filter((x) => x.nom === "Pièce" && !resolus.has(`nouvelle|${x.id}`))) {
        points.push({ cle: `nouvelle|${n.id}`, genre: "nouvelle", titre: "Nouvelle pièce", doutes: [],
          texte: `Les murs ferment un nouvel espace de ${fr(surfacePolygone(n.contour))} m², entouré en orange. Donnez-lui un nom, ou corrigez les murs si c'est une erreur.`,
          elements: [n.id], zone_px: boitePixels(n.contour.map(px)),
          actions: [{ libelle: "C'est une vraie pièce, garder ce nom", action: { type: "regler" } }] });
      }
    }

    const zoneDe = (id, d = null) => {
      if (d && d.zone_px) return d.zone_px;
      const t = trouver(lg, id);
      if (!t) return null;
      if (t.genre === "mur") return boitePixels(polygoneMur(t.e).map(px));
      if (t.genre === "piece") return boitePixels(t.e.contour.map(px));
      return murs.has(t.e.mur) ? boitePixels(polygoneOuverture(t.e, murs.get(t.e.mur)).map(px)) : null;
    };

    // 1. L'échelle d'abord : une erreur d'échelle ne se voit pas sur le dessin, puisqu'il reste posé sur le plan.
    const etatEchelle = (v.echelle || {}).etat;
    const doutesEchelle = doutes.filter((d) => d.code === "echelle");
    doutes = doutes.filter((d) => d.code !== "echelle");
    const grande = [...(lg.pieces || [])].sort((a, b) => surfacePolygone(b.contour) - surfacePolygone(a.contour))[0];
    const mesure = grande ? (() => {
      const xs = grande.contour.map((q) => q[0]), ys = grande.contour.map((q) => q[1]);
      return { piece: grande.id, nom: grande.nom, x: arrondi(Math.max(...xs) - Math.min(...xs)), y: arrondi(Math.max(...ys) - Math.min(...ys)) };
    })() : null;
    if (etatEchelle === "a_verifier" && !resolus.has("echelle")) {
      points.push({ cle: "echelle", genre: "echelle", titre: "Les mesures sont à contrôler",
        texte: mesure
          ? `Atelya n'a pas pu lire l'échelle : ses mesures sont approximatives. Il voit « ${mesure.nom} » à ${fr(mesure.x)} × ${fr(mesure.y)} m. Quelle est sa vraie taille d'après le plan ?`
          : "Atelya n'a pas pu lire l'échelle : ses mesures sont approximatives. Cliquez sur un mur dont le plan donne la longueur, puis tapez cette longueur.",
        elements: mesure ? [mesure.piece] : [], doutes: doutesEchelle, zone_px: null, mesure,
        actions: [...(mesure ? [{ libelle: "Je donne la vraie mesure", action: { type: "mesurer" }, principal: true }] : []), { libelle: "Les mesures sont bonnes", action: { type: "regler" } }] });
    } else if (etatEchelle !== "corrigee" && !resolus.has("controle-echelle") && mesure) {
      points.push({ cle: "controle-echelle", genre: "echelle", titre: "Vérifiez une mesure",
        texte: `Atelya lit « ${mesure.nom} » à ${fr(mesure.x)} × ${fr(mesure.y)} m. Est-ce bien ce que dit le plan ?`,
        elements: [mesure.piece], doutes: doutesEchelle, zone_px: null, mesure,
        actions: [{ libelle: "Oui, c'est bon", action: { type: "regler" }, principal: true }, { libelle: "Non, je corrige", action: { type: "mesurer" } }] });
    }

    // 1 bis. Deux ouvertures l'une sur l'autre : le moteur ne saura pas construire, il faut en supprimer une.
    const parMur = new Map();
    for (const o of lg.ouvertures || []) { if (!parMur.has(o.mur)) parMur.set(o.mur, []); parMur.get(o.mur).push(o); }
    for (const liste of parMur.values()) {
      liste.sort((a, b) => a.position - b.position);
      for (let i = 1; i < liste.length; i++) {
        const a = liste[i - 1], b = liste[i];
        if (a.position + a.largeur - b.position <= 0.01 || resolus.has(`recouvrement|${a.id}+${b.id}`)) continue;
        const nomA = nomSimple(lg, a.id).replace(/^cette /, ""), nomB = nomSimple(lg, b.id).replace(/^cette /, "");
        points.push({ cle: `recouvrement|${a.id}+${b.id}`, genre: "recouvrement", titre: "Deux ouvertures l'une sur l'autre",
          texte: `Une ${nomA} de ${fr(a.largeur)} m et une ${nomB} de ${fr(b.largeur)} m se chevauchent sur le même mur. Le plan n'en a sûrement qu'une : laquelle garder ?`,
          elements: [a.id, b.id], doutes: doutes.filter((d) => d.element === a.id || d.element === b.id), zone_px: unirBoites([zoneDe(a.id), zoneDe(b.id)].filter(Boolean)),
          actions: [{ libelle: `Garder la ${nomA} (${fr(a.largeur)} m)`, action: { type: "garder_une", garder: a.id, supprimer: b.id }, principal: a.largeur >= b.largeur },
            { libelle: `Garder la ${nomB} (${fr(b.largeur)} m)`, action: { type: "garder_une", garder: b.id, supprimer: a.id }, principal: b.largeur > a.largeur }] });
      }
    }

    // 2. Les pièces coupées en morceaux.
    const dansUnGroupe = new Set();
    for (const groupe of morceauxDePieces(lg)) {
      if (groupe.every((id) => verifies.has(id))) continue;
      groupe.forEach((id) => dansUnGroupe.add(id));
      const pieces = groupe.map((id) => trouver(lg, id).e);
      const liste = pieces.map((p) => `${p.nom} (${fr(surfacePolygone(p.contour), 1)} m²)`).join(", ");
      points.push({ cle: `morceaux|${[...groupe].sort().join("+")}`, genre: "morceaux", titre: "Une seule pièce ?",
        texte: `Aucun mur ne sépare ces ${groupe.length} morceaux : ${liste}. S'il s'agit d'une seule pièce, réunissez-les.`,
        elements: groupe, doutes: doutes.filter((d) => groupe.includes(d.element)), zone_px: unirBoites(groupe.map((id) => zoneDe(id))),
        actions: [{ libelle: "Les réunir", action: { type: "fusionner" }, principal: true }, { libelle: "Ce sont des pièces séparées", action: { type: "regler" } }] });
    }
    doutes = doutes.filter((d) => !dansUnGroupe.has(d.element));

    // 3. Les petites hésitations : un seul point, à la fin (sauf si la personne a demandé à les voir une par une).
    const legers = doutes.filter((d) => d.gravite === "faible" && !enDetail.has(d.cle));
    doutes = doutes.filter((d) => d.gravite !== "faible" || enDetail.has(d.cle));

    // 4. Les doutes sur les murs et les zones : ceux qui sont au même endroit ne font qu'un point.
    const estZone = (d) => !enDetail.has(d.cle) && (CODES_ZONE.has(d.code) || (d.element && murs.has(d.element)));
    const zones = doutes.filter(estZone);
    const seuls = doutes.filter((d) => !estZone(d));
    for (const d of seuls) {
      const point = pointSeul(lg, d);
      if (!point.zone_px && d.element) point.zone_px = zoneDe(d.element);
      if (d.code === "carte" && d.element) point.texte = `Atelya n'est pas sûr de ${nomSimple(lg, d.element)}. Existe-t-il vraiment sur le plan ?`;
      if (d.code === "epaisseur" && d.element) point.texte = `L'épaisseur de ${nomSimple(lg, d.element)} paraît inhabituelle.`;
      points.push(point);
    }
    const a = px([0, 0]), b = px([1, 0]), c = px([0, 1]);
    const pxParM = (Math.hypot(b[0] - a[0], b[1] - a[1]) + Math.hypot(c[0] - a[0], c[1] - a[1])) / 2;
    const seuil = REGROUPER_ZONE_M * pxParM;
    const boites = zones.map((d) => zoneDe(d.element, d));
    const parent = zones.map((_, i) => i);
    const racineDe = (i) => (parent[i] === i ? i : (parent[i] = racineDe(parent[i])));
    for (let i = 0; i < zones.length; i++) for (let j = i + 1; j < zones.length; j++) {
      const A = boites[i], B = boites[j];
      if (!A || !B) continue;
      if (A[0] <= B[0] + B[2] + seuil && B[0] <= A[0] + A[2] + seuil && A[1] <= B[1] + B[3] + seuil && B[1] <= A[1] + A[3] + seuil) parent[racineDe(i)] = racineDe(j);
    }
    const paquets = new Map();
    zones.forEach((d, i) => { const r = racineDe(i); if (!paquets.has(r)) paquets.set(r, []); paquets.get(r).push(i); });
    const pointsZones = [...paquets.values()].map((indices) => {
      const ds = indices.map((i) => zones[i]);
      const elements = [...new Set(ds.map((d) => d.element).filter(Boolean))];
      const nb = elements.length;
      let texte, actions;
      if (!nb) {
        texte = "Atelya n'est pas sûr de ce qu'il voit à cet endroit. Regardez s'il manque quelque chose.";
        actions = [{ libelle: "Rien à corriger", action: { type: "regler" }, principal: true }];
      } else if (nb === 1) {
        const d = ds.find((x) => x.element);
        const t = trouver(lg, d.element);
        texte = d.code === "epaisseur" ? `L'épaisseur de ${nomSimple(lg, d.element)} paraît inhabituelle.` : `Atelya n'est pas sûr de ${nomSimple(lg, d.element)}. Existe-t-il vraiment sur le plan ?`;
        if (t && t.genre === "mur" && longueur(t.e.debut, t.e.fin) < MUR_COURT) texte = "Ce mur est très court : vrai mur, ou simple tache ?";
        actions = [{ libelle: "C'est juste", action: { type: "regler" } }, { libelle: "Le supprimer", action: { type: "supprimer_tout" }, danger: true }];
      } else {
        texte = `Atelya n'est pas sûr de ces ${nb} morceaux, tous à cet endroit. Existent-ils vraiment sur le plan ?`;
        actions = [{ libelle: "Tout est juste", action: { type: "regler" } }, { libelle: "Non : les voir un par un", action: { type: "detail" } }, { libelle: "Tout supprimer", action: { type: "supprimer_tout" }, danger: true }];
      }
      return { cle: `zone|${ds.map((d) => d.cle).sort().join("+")}`, genre: "zone", titre: nb === 1 ? "Mur douteux" : nb ? "Zone douteuse" : "Zone douteuse", texte,
        elements, doutes: ds, zone_px: unirBoites(indices.map((i) => boites[i]).filter(Boolean)), actions };
    });
    pointsZones.sort((x, y) => y.elements.length - x.elements.length);
    points.push(...pointsZones);

    if (legers.length) {
      const elements = [...new Set(legers.map((d) => d.element).filter(Boolean))];
      const boitesL = legers.map((d) => zoneDe(d.element, d)).filter(Boolean);
      points.push({ cle: "legers", genre: "legers", titre: "Petites hésitations",
        texte: `Atelya hésite un peu sur ${legers.length > 1 ? `ces ${legers.length} éléments, entourés en orange` : "cet élément, entouré en orange"}. Si cela vous paraît juste, vous pouvez passer.`,
        elements, doutes: legers, zone_px: boitesL.length ? unirBoites(boitesL) : null,
        actions: [{ libelle: "Tout est juste", action: { type: "regler" }, principal: true }, ...(legers.length > 1 ? [{ libelle: "Non : les voir un par un", action: { type: "detail" } }] : [])] });
    }
    return points;
  }

  /** Applique le choix fait sur un point. Renvoie une copie corrigée. */
  function reglerPoint(v0, point, action, nom = null) {
    let v = v0;
    if (action.type === "fusionner") return fusionnerPieces(v, point.elements, nom);
    if (action.type === "fermer") return recalculerPieces(ajouterMur(v, action.debut, action.fin, action.epaisseur));
    if (action.type === "garder_une") {
      v = confirmer(supprimer(v, action.supprimer), action.garder);
      v = copie(v);
      v.resolus = [...new Set([...(v.resolus || []), point.cle])];
      return v;
    }
    if (action.type === "supprimer_tout") {
      for (const id of point.elements) if (trouver(v.logement, id)) v = supprimer(v, id);
    } else if (action.type === "regler") {
      for (const id of point.elements) if (trouver(v.logement, id)) v = confirmer(v, id);
    } else throw new Error(`choix inconnu : ${action.type}`);
    v = copie(v);
    v.resolus = [...new Set([...(v.resolus || []), point.cle, ...point.doutes.filter((d) => d.element == null).map((d) => d.cle)])];
    return v;
  }

  // ---------- Reprendre un travail ----------

  const VERSION_TRAVAIL = "travail-verification/0.1";

  /** Tout ce qu'il faut pour reprendre une vérification plus tard (l'image du plan n'y est pas : elle reste à part). */
  function travail(v, { detail = [], fermeture = false, murs_calcules = null, quand = new Date().toISOString() } = {}) {
    return { schema: VERSION_TRAVAIL, date: quand, projet_id: v.logement.projet_id, verification: v, detail: [...detail], fermeture, murs_calcules };
  }

  /**
   * Repart d'un fichier enregistré : un travail, un résultat de vérification, ou un simple logement.json corrigé.
   * Ce dernier n'a ni calage ni liste de ce qui a été vérifié : on les retrouve à partir de la lecture de départ (`base`) ;
   * si l'échelle a été corrigée, les murs qui existent des deux côtés donnent la correction.
   */
  function reprendreTravail(base, contenu) {
    if (!contenu || typeof contenu !== "object") throw new Error("ce fichier n'est pas un travail de vérification");
    const projet = base.logement.projet_id;
    const mauvaisPlan = (id) => new Error(`ce fichier concerne le plan « ${id} », pas « ${projet} »`);
    if (contenu.schema === VERSION_TRAVAIL) {
      if (contenu.projet_id !== projet) throw mauvaisPlan(contenu.projet_id);
      const erreurs = verifierFichier(contenu.verification);
      if (erreurs.length) throw new Error(erreurs.join(" ; "));
      return { v: copie(contenu.verification), detail: contenu.detail || [], fermeture: !!contenu.fermeture, murs_calcules: contenu.murs_calcules || null };
    }
    const lg = contenu.schema === VERSION_RESULTAT ? contenu.logement : contenu;
    if (!lg || lg.schema !== "logement/0.1" || !Array.isArray(lg.murs) || !lg.murs.length) throw new Error("ce fichier n'est pas un travail de vérification");
    if (lg.projet_id !== projet) throw mauvaisPlan(lg.projet_id);
    const v = copie(base);
    v.logement = copie(lg);
    const anciens = new Map(base.logement.murs.map((m) => [m.id, m]));
    const rapports = lg.murs.filter((m) => anciens.has(m.id) && longueur(anciens.get(m.id).debut, anciens.get(m.id).fin) > 0.5)
      .map((m) => longueur(m.debut, m.fin) / longueur(anciens.get(m.id).debut, anciens.get(m.id).fin)).sort((a, b) => a - b);
    const k = rapports.length ? rapports[Math.floor(rapports.length / 2)] : 1;
    if (Math.abs(k - 1) > 1e-4) {
      const m = matriceDuCalage(v.calage);
      v.calage = { matrice: m.map((ligne) => [ligne[0] / k, ligne[1] / k, ligne[2]]) };
      v.echelle = { ...(v.echelle || {}), etat: "corrigee", facteur: arrondi(k, 5) };
    }
    const touches = [...lg.murs, ...(lg.ouvertures || []), ...(lg.pieces || [])].filter((e) => e.source && e.source.includes("verification"));
    v.verifies = touches.map((e) => e.id);
    delete v.resolus;
    return { v, detail: [], fermeture: true, murs_calcules: null }; // montre tout de suite ce qui n'est pas fermé
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
    // Deux ouvertures qui se chevauchent sur le même mur : le moteur refuse de construire (moteur/geometrie.py).
    const parMur = new Map();
    for (const o of lg.ouvertures || []) { if (!parMur.has(o.mur)) parMur.set(o.mur, []); parMur.get(o.mur).push(o); }
    for (const liste of parMur.values()) {
      liste.sort((a, b) => a.position - b.position);
      for (let i = 1; i < liste.length; i++) {
        const a = liste[i - 1], b = liste[i];
        const recouvrement = a.position + a.largeur - b.position;
        if (recouvrement > RECOUVREMENT_TOLERE) erreurs.push(`les ouvertures ${a.id} et ${b.id} se chevauchent de ${Math.round(recouvrement * 100)} cm sur le mur ${a.mur}`);
      }
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
    reglerPlinthes,
    CHOIX_PLINTHES,
    reglerSol,
    SOLS,
    reglerPlacard,
    CHOIX_PLACARD,
    estPlacard,
    supprimer,
    confirmer,
    resoudre,
    appliquerAction,
    travail,
    reprendreTravail,
    fusionnerPieces,
    deplacerBout,
    accrocherBout,
    aimanterSurMur,
    couperMur,
    enleverMorceau,
    relierMurs,
    boutLePlusProche,
    piecesDepuisMurs,
    recalculerPieces,
    morceauxDePieces,
    pointsAVerifier,
    reglerPoint,
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
