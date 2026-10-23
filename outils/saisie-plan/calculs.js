/*
 * Calculs de la page de saisie : échelle, conversions, aimants, export.
 *
 * Aucun dessin ici, seulement des calculs : on peut donc les tester seuls
 * (voir tests/calculs.test.js).
 *
 * Deux repères :
 * - les PIXELS de l'image du plan : x vers la droite, y vers le BAS ;
 * - les MÈTRES du logement : x vers l'est, y vers le NORD (vers le haut),
 *   origine au coin intérieur sud-ouest (convention de l'étape 1).
 * Pendant la saisie tout est gardé en pixels ; on ne passe en mètres
 * qu'au moment d'écrire logement.json.
 */
(function (racine) {
  "use strict";

  const VERSION_LOGEMENT = "logement/0.1";
  const VERSION_SAISIE = "saisie/0.2"; // 0.2 : ouvertures et pièces, lecture automatique
  const VERSIONS_LUES = ["saisie/0.1", "saisie/0.2"];
  const CONFIANCE_CLIC = 0.8; // confiance d'une longueur obtenue en cliquant
  const CONFIANCE_VERIFIEE = 0.9; // lecture automatique relue et validée par un humain
  const TOLERANCE_SURFACE = 0.01; // m², la même que le moteur (moteur/logement.py)

  // Hauteurs courantes en France (m) : celles que met la lecture automatique.
  const HAUTEURS = {
    porte: { hauteur: 2.04, allege: 0 },
    porte_fenetre: { hauteur: 2.15, allege: 0 },
    fenetre: { hauteur: 1.35, allege: 0.95 },
  };
  const NOMS_TYPES = { porte: "porte", porte_fenetre: "porte-fenêtre", fenetre: "fenêtre" };

  function distance(a, b) {
    return Math.hypot(b[0] - a[0], b[1] - a[1]);
  }

  function arrondi(valeur, decimales = 3) {
    const f = 10 ** decimales;
    return Math.round(valeur * f) / f + 0; // + 0 : évite d'écrire « -0 »
  }

  /** Nombre de pixels par mètre, à partir de deux points et de la cote réelle. */
  function echelle(p1, p2, longueurM) {
    const d = distance(p1, p2);
    if (!(longueurM > 0)) throw new Error("la longueur réelle doit être positive");
    if (d === 0) throw new Error("les deux points sont confondus");
    return d / longueurM;
  }

  /** Écart (en %) entre une cote contrôlée et ce que donne l'échelle. */
  function ecartControle(p1, p2, longueurM, pxParM) {
    const mesuree = distance(p1, p2) / pxParM;
    return ((mesuree - longueurM) / longueurM) * 100;
  }

  function versMetres(p, origine, pxParM) {
    return [arrondi((p[0] - origine[0]) / pxParM), arrondi((origine[1] - p[1]) / pxParM)];
  }

  function versPixels(m, origine, pxParM) {
    return [origine[0] + m[0] * pxParM, origine[1] - m[1] * pxParM];
  }

  /** Aimant d'angle : un segment presque horizontal ou vertical est redressé. */
  function redresser(debut, fin, toleranceDeg = 8) {
    const dx = fin[0] - debut[0];
    const dy = fin[1] - debut[1];
    const angle = (Math.atan2(Math.abs(dy), Math.abs(dx)) * 180) / Math.PI;
    if (angle <= toleranceDeg) return [fin[0], debut[1]];
    if (angle >= 90 - toleranceDeg) return [debut[0], fin[1]];
    return [fin[0], fin[1]];
  }

  /** Aimant de point : le candidat le plus proche à moins de `rayon`, sinon null. */
  function pointLePlusProche(p, candidats, rayon) {
    let meilleur = null;
    let dMin = rayon;
    for (const c of candidats) {
      const d = distance(p, c);
      if (d <= dMin) {
        dMin = d;
        meilleur = [c[0], c[1]];
      }
    }
    return meilleur;
  }

  /**
   * Aimant d'alignement : cale le x (ou le y) du point sur celui d'un point
   * existant, s'il en est tout proche. C'est ce qui permet de fermer un
   * logement avec des angles parfaitement droits.
   * axes : "xy", "x" ou "y" (les coordonnées qu'on a le droit de bouger).
   */
  function aligner(p, references, rayon, axes = "xy") {
    const q = [p[0], p[1]];
    const guides = [];
    for (const k of [0, 1]) {
      if (!axes.includes(k === 0 ? "x" : "y")) continue;
      let dMin = rayon;
      for (const r of references) {
        const d = Math.abs(r[k] - p[k]);
        if (d <= dMin) {
          dMin = d;
          q[k] = r[k];
          guides[k] = r;
        }
      }
    }
    return { point: q, guides };
  }

  function memePoint(a, b) {
    return distance(a, b) < 1e-6;
  }

  function direction(debut, fin) {
    const l = distance(debut, fin);
    return [(fin[0] - debut[0]) / l, (fin[1] - debut[1]) / l];
  }

  /**
   * Aimant de face. Un mur qui s'arrête contre un autre mur (une cloison
   * contre un mur extérieur, par exemple) doit s'arrêter sur la FACE de ce
   * mur, pas sur son axe. On fait glisser chaque bout libre jusqu'à la face
   * tournée vers l'autre bout. Seuls les murs perpendiculaires sont concernés.
   *
   * murs : [{debut, fin, epaisseurPx}] en pixels. Renvoie {debut, fin} corrigés.
   */
  function accrocherAuxFaces(mur, autres, tolerancePx = 0) {
    const u = direction(mur.debut, mur.fin);
    const bouts = [mur.debut.slice(), mur.fin.slice()];
    for (let i = 0; i < 2; i++) {
      const bout = bouts[i];
      const autreBout = bouts[1 - i];
      const surUnAngle = autres.some((w) => memePoint(bout, w.debut) || memePoint(bout, w.fin));
      if (surUnAngle) continue;
      for (const w of autres) {
        const uw = direction(w.debut, w.fin);
        if (Math.abs(u[0] * uw[0] + u[1] * uw[1]) > 0.05) continue; // pas perpendiculaire
        const nw = [-uw[1], uw[0]];
        const lw = distance(w.debut, w.fin);
        const rel = [bout[0] - w.debut[0], bout[1] - w.debut[1]];
        const le_long = rel[0] * uw[0] + rel[1] * uw[1];
        const ecart = rel[0] * nw[0] + rel[1] * nw[1];
        const demi = w.epaisseurPx / 2;
        if (le_long < -demi || le_long > lw + demi) continue;
        if (Math.abs(ecart) > demi + tolerancePx) continue;
        const relAutre = [autreBout[0] - w.debut[0], autreBout[1] - w.debut[1]];
        const cote = Math.sign(relAutre[0] * nw[0] + relAutre[1] * nw[1]) || 1;
        const cible = cote * demi;
        const pas = (cible - ecart) / (u[0] * nw[0] + u[1] * nw[1]);
        bouts[i] = [bout[0] + u[0] * pas, bout[1] + u[1] * pas];
        break;
      }
    }
    return { debut: bouts[0], fin: bouts[1] };
  }

  /**
   * Donne au mur n° `index` une longueur tapée (cote du plan), en gardant son
   * début et sa direction. Les bouts des autres murs qui touchaient l'ancienne
   * fin suivent, pour que les angles restent fermés.
   */
  function appliquerLongueur(murs, index, longueurM, pxParM) {
    if (!(longueurM > 0)) throw new Error("la longueur doit être positive");
    const mur = murs[index];
    const u = direction(mur.debut, mur.fin);
    const ancienneFin = mur.fin;
    const nouvelleFin = [mur.debut[0] + u[0] * longueurM * pxParM, mur.debut[1] + u[1] * longueurM * pxParM];
    return murs.map((m, i) => {
      if (i === index) return { ...m, fin: nouvelleFin, longueurTapee: longueurM };
      return {
        ...m,
        debut: memePoint(m.debut, ancienneFin) ? nouvelleFin.slice() : m.debut,
        fin: memePoint(m.fin, ancienneFin) ? nouvelleFin.slice() : m.fin,
      };
    });
  }

  /** Coins des faces autour de chaque bout de mur : candidats pour placer l'origine. */
  function coinsDesFaces(murs) {
    const coins = [];
    for (const m of murs) {
      const e = m.epaisseurPx / 2;
      for (const p of [m.debut, m.fin]) {
        for (const sx of [-1, 1]) for (const sy of [-1, 1]) coins.push([p[0] + sx * e, p[1] + sy * e]);
      }
    }
    return coins;
  }

  /** Surface d'un polygone (formule du lacet), dans l'unité au carré de ses points. */
  function surfacePolygone(points) {
    let total = 0;
    for (let i = 0; i < points.length; i++) {
      const [x1, y1] = points[i];
      const [x2, y2] = points[(i + 1) % points.length];
      total += x1 * y2 - x2 * y1;
    }
    return Math.abs(total) / 2;
  }

  /** Le point p est-il dans le polygone ? (méthode du rayon) */
  function dansPolygone(p, points) {
    let dedans = false;
    for (let i = 0, j = points.length - 1; i < points.length; j = i++) {
      const [xi, yi] = points[i];
      const [xj, yj] = points[j];
      if (yi > p[1] !== yj > p[1] && p[0] < ((xj - xi) * (p[1] - yi)) / (yj - yi) + xi) dedans = !dedans;
    }
    return dedans;
  }

  /** Les deux bouts d'une ouverture, en pixels, à partir de son mur. */
  function boutsOuverture(o, mur, pxParM) {
    const u = direction(mur.debut, mur.fin);
    const a = [mur.debut[0] + u[0] * o.position * pxParM, mur.debut[1] + u[1] * o.position * pxParM];
    return [a, [a[0] + u[0] * o.largeur * pxParM, a[1] + u[1] * o.largeur * pxParM]];
  }

  /**
   * Ce qu'un humain doit encore regarder dans une lecture automatique.
   * Chaque doute : {genre, index, texte}. La liste se vide au fur et à mesure
   * des corrections et des « C'est bon ».
   */
  function doutes(saisie) {
    const liste = [];
    const e = saisie.echelle;
    if (e && e.lue && !e.sure && !e.verifiee) {
      liste.push({ genre: "echelle", index: null, texte: "Échelle lue sur une seule cote : à contrôler" });
    }
    if (saisie.lecture_auto && !saisie.hsp_lue && !saisie.hsp_verifiee) {
      liste.push({ genre: "hsp", index: null, texte: "Hauteur sous plafond absente du plan : 2,50 m mis par défaut" });
    }
    (saisie.ouvertures || []).forEach((o, i) => {
      if (o.sure === false && !o.verifie) {
        liste.push({ genre: "ouverture", index: i, texte: `${o.id} : dessin peu clair, type à confirmer (${NOMS_TYPES[o.type]} ?)` });
      }
    });
    (saisie.pieces || []).forEach((p, i) => {
      if (p.verifie) return;
      if (!p.nom) liste.push({ genre: "piece", index: i, texte: `${p.id} : pièce sans nom` });
      else if (p.accord === false) {
        const calculee = saisie.echelle ? surfacePolygone(p.contour) / saisie.echelle.pxParM ** 2 : 0;
        liste.push({
          genre: "piece",
          index: i,
          texte: `${p.nom} : ${String(p.surfaceEcrite).replace(".", ",")} m² écrits, ${calculee.toFixed(2).replace(".", ",")} m² mesurés`,
        });
      }
    });
    return liste;
  }

  /** Liste des problèmes qui empêchent d'écrire logement.json (vide si tout va bien). */
  function verifierSaisie(saisie) {
    const erreurs = [];
    if (!saisie.echelle) erreurs.push("l'échelle n'est pas calée");
    if (!saisie.origine) erreurs.push("l'origine n'est pas placée");
    if (!(saisie.hauteur_sous_plafond > 0)) erreurs.push("la hauteur sous plafond doit être positive");
    if (!saisie.projet_id) erreurs.push("le nom du projet est vide");
    if (saisie.murs.length === 0) erreurs.push("aucun mur n'est tracé");
    const vus = new Set();
    for (const m of saisie.murs) {
      if (vus.has(m.id)) erreurs.push(`identifiant en double : ${m.id}`);
      vus.add(m.id);
      if (distance(m.debut, m.fin) === 0) erreurs.push(`le mur ${m.id} a une longueur nulle`);
      if (!(m.epaisseur > 0)) erreurs.push(`le mur ${m.id} a une épaisseur nulle`);
    }
    for (const o of saisie.ouvertures || []) {
      const mur = saisie.murs.find((m) => m.id === o.mur);
      if (!mur) erreurs.push(`l'ouverture ${o.id} est sur un mur qui n'existe plus`);
      else if (saisie.echelle && o.position + o.largeur > distance(mur.debut, mur.fin) / saisie.echelle.pxParM + 1e-6) {
        erreurs.push(`l'ouverture ${o.id} dépasse du mur ${mur.id}`);
      }
    }
    const reste = doutes(saisie).length;
    if (reste) erreurs.push(`il reste ${reste} point${reste > 1 ? "s" : ""} à vérifier (liste « À vérifier »)`);
    return erreurs;
  }

  /** Construit le contenu de logement.json (format logement/0.1) à partir de la saisie. */
  function construireLogement(saisie) {
    const erreurs = verifierSaisie(saisie);
    if (erreurs.length) throw new Error(erreurs.join(" ; "));
    const s = saisie.echelle.pxParM;
    const o = saisie.origine;
    return {
      schema: VERSION_LOGEMENT,
      projet_id: saisie.projet_id,
      unites: "m",
      hauteur_sous_plafond: saisie.hauteur_sous_plafond,
      murs: saisie.murs.map((m) => {
        const tapee = m.longueurTapee != null;
        const lu = m.source === "lecture_auto";
        return {
          id: m.id,
          debut: versMetres(m.debut, o, s),
          fin: versMetres(m.fin, o, s),
          epaisseur: m.epaisseur,
          statut: tapee ? "mesure" : "estime",
          source: tapee ? "cote_plan" : lu ? "lecture_verifiee" : "saisie_plan",
          confiance: tapee ? 1 : lu ? CONFIANCE_VERIFIEE : CONFIANCE_CLIC,
        };
      }),
      // On n'arrive ici qu'une fois tous les doutes levés : la lecture est « vérifiée ».
      ouvertures: (saisie.ouvertures || []).map((ou) => ({
        id: ou.id,
        type: ou.type,
        mur: ou.mur,
        position: arrondi(ou.position),
        largeur: arrondi(ou.largeur),
        hauteur: ou.hauteur,
        allege: ou.allege,
        statut: "estime",
        source: ou.source === "lecture_auto" ? "lecture_verifiee" : ou.source || "saisie_plan",
        confiance: CONFIANCE_VERIFIEE,
      })),
      pieces: (saisie.pieces || []).map((p, i) => {
        const contour = p.contour.map((q) => versMetres(q, o, s));
        const calculee = surfacePolygone(contour);
        const ecrite = p.surfaceEcrite;
        return {
          id: p.id,
          nom: p.nom || `Pièce ${i + 1}`,
          contour,
          // La surface écrite n'est gardée que si elle colle au contour (le moteur le vérifie aussi).
          surface: ecrite != null && Math.abs(ecrite - calculee) <= TOLERANCE_SURFACE ? ecrite : null,
          statut: "estime",
          source: "lecture_verifiee",
          confiance: CONFIANCE_VERIFIEE,
        };
      }),
    };
  }

  const Calculs = {
    VERSION_LOGEMENT,
    VERSION_SAISIE,
    VERSIONS_LUES,
    HAUTEURS,
    NOMS_TYPES,
    distance,
    arrondi,
    echelle,
    ecartControle,
    versMetres,
    versPixels,
    redresser,
    pointLePlusProche,
    aligner,
    accrocherAuxFaces,
    appliquerLongueur,
    coinsDesFaces,
    surfacePolygone,
    dansPolygone,
    boutsOuverture,
    doutes,
    verifierSaisie,
    construireLogement,
  };

  if (typeof module !== "undefined" && module.exports) module.exports = Calculs;
  else racine.Calculs = Calculs;
})(this);
