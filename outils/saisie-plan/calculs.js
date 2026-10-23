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
  const VERSION_SAISIE = "saisie/0.1";
  const CONFIANCE_CLIC = 0.8; // confiance d'une longueur obtenue en cliquant

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
        return {
          id: m.id,
          debut: versMetres(m.debut, o, s),
          fin: versMetres(m.fin, o, s),
          epaisseur: m.epaisseur,
          statut: tapee ? "mesure" : "estime",
          source: tapee ? "cote_plan" : "saisie_plan",
          confiance: tapee ? 1 : CONFIANCE_CLIC,
        };
      }),
      ouvertures: [],
      pieces: [],
    };
  }

  const Calculs = {
    VERSION_LOGEMENT,
    VERSION_SAISIE,
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
    verifierSaisie,
    construireLogement,
  };

  if (typeof module !== "undefined" && module.exports) module.exports = Calculs;
  else racine.Calculs = Calculs;
})(this);
