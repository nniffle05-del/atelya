// Tests des calculs de l'écran de vérification.
// Lancement (nécessite Node.js) : node --test outils/verification-plan/tests/verif.test.js
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../calculs-verif.js");

const proche = (a, b, tol = 1e-6) => assert.ok(Math.abs(a - b) <= tol, `${a} ≠ ${b}`);
const procheP = (p, q, tol = 1e-6) => { proche(p[0], q[0], tol); proche(p[1], q[1], tol); };

const murs = [
  { id: "M1", debut: [0, 0], fin: [4, 0], epaisseur: 0.2, statut: "estime", source: "atelya" },
  { id: "M2", debut: [4, 0], fin: [4, 3], epaisseur: 0.2, statut: "estime", source: "atelya" },
];
const fichier = (extra = {}) => ({
  schema: "verification/0.1",
  calage: { px_par_m: 100, origine_px: [210, 760] },
  logement: { schema: "logement/0.1", projet_id: "T", unites: "m", hauteur_sous_plafond: 2.5, murs, ouvertures: [], pieces: [] },
  ...extra,
});

test("calage simple : l'origine tombe sur son pixel, le nord monte sur l'image", () => {
  const m = C.matriceDuCalage({ px_par_m: 100, origine_px: [210, 760] });
  procheP(C.versPixel(m, [0, 0]), [210, 760]);
  procheP(C.versPixel(m, [8, 5.4]), [1010, 220]); // coin nord-est du cas test n°0
});

test("calage par matrice : une photo de biais (perspective) est prise en compte", () => {
  const m = C.matriceDuCalage({ matrice: [[100, 0, 10], [0, -100, 500], [0, 0.1, 1]] });
  procheP(C.versPixel(m, [0, 0]), [10, 500]);
  procheP(C.versPixel(m, [1, 1]), [110 / 1.1, 400 / 1.1]);
  assert.throws(() => C.matriceDuCalage({ matrice: [[1, 0], [0, 1]] }));
  assert.throws(() => C.matriceDuCalage({ px_par_m: 0, origine_px: [0, 0] }));
});

test("mur dessiné : rallongé d'une demi-épaisseur aux deux bouts pour fermer les angles", () => {
  const p = C.polygoneMur(murs[0]);
  procheP(p[0], [-0.1, -0.1]);
  procheP(p[2], [4.1, 0.1]);
});

test("ouverture dessinée : à sa place le long du mur", () => {
  const p = C.polygoneOuverture({ position: 1, largeur: 0.9 }, murs[1]);
  const ys = p.map((q) => q[1]);
  proche(Math.min(...ys), 1);
  proche(Math.max(...ys), 1.9);
});

test("surface et centre d'une pièce", () => {
  const c = [[0, 0], [4, 0], [4, 3], [0, 3]];
  proche(C.surfacePolygone(c), 12);
  procheP(C.centrePolygone(c), [2, 1.5]);
  const l = [[0, 0], [2, 0], [2, 1], [1, 1], [1, 2], [0, 2]]; // une pièce en L
  proche(C.surfacePolygone(l), 3);
});

test("doutes : confiance basse, mur très court, porte étroite, doutes écrits par Atelya", () => {
  const v = fichier({ doutes: [{ zone_px: [0, 0, 10, 10], raison: "tache" }] });
  v.logement.murs = [...murs, { id: "M3", debut: [1, 1], fin: [1.2, 1], epaisseur: 0.1, statut: "estime", source: "atelya" }];
  v.logement.ouvertures = [{ id: "O1", type: "porte", mur: "M1", position: 1, largeur: 0.4, hauteur: 2, statut: "estime", source: "atelya" }];
  v.logement.pieces = [{ id: "p1", nom: "Bureau", contour: [[0, 0], [4, 0], [4, 3], [0, 3]], statut: "estime", source: "atelya", confiance: 0.55 }];
  const d = C.trouverDoutes(v);
  const ids = d.map((x) => x.element);
  assert.deepEqual(ids, [null, "p1", "M3", "O1"]);
  assert.match(d[1].raison, /55 %/);
});

test("doutes : rien à signaler quand Atelya est sûr de tout", () => {
  assert.deepEqual(C.trouverDoutes(fichier()), []);
});

test("fichier : les erreurs de forme sont expliquées", () => {
  assert.deepEqual(C.verifierFichier(fichier()), []);
  assert.equal(C.verifierFichier(fichier({ schema: "autre" })).length, 1);
  assert.equal(C.verifierFichier(fichier({ calage: {} })).length, 1);
  assert.ok(C.verifierFichier(null).length > 0);
});

test("l'exemple livré est un fichier valide, avec ses 4 doutes", () => {
  const v = require("../exemples/exemple-cas-test-00.verification.json");
  assert.deepEqual(C.verifierFichier(v), []);
  assert.equal(C.trouverDoutes(v).length, 4);
});

// ---------- Étape B : corrections ----------

const exemple = () => JSON.parse(JSON.stringify(require("../exemples/exemple-cas-test-00.verification.json")));
const mur = (v, id) => v.logement.murs.find((m) => m.id === id);

test("une correction ne touche jamais l'original (c'est ce qui permet « Annuler »)", () => {
  const v = exemple();
  const avant = JSON.stringify(v);
  C.renommerPiece(v, "chambre", "Chambre");
  C.deplacerMur(v, "C_sejour", [0.2, 0]);
  C.supprimer(v, "M_tache");
  assert.equal(JSON.stringify(v), avant);
});

test("propositions en un clic : la porte oubliée est ajoutée et le doute disparaît", () => {
  let v = exemple();
  const d = C.trouverDoutes(v).find((x) => x.element === null);
  v = C.appliquerAction(v, d.propositions[0].action, d);
  const o = v.logement.ouvertures.find((x) => x.mur === "C_sdb");
  assert.equal(o.type, "porte");
  proche(o.position, 0.4, 1e-3);
  proche(o.largeur, 0.8, 1e-3);
  assert.equal(o.source, "verification");
  assert.ok(!C.trouverDoutes(v).some((x) => x.element === null));
});

test("renommer la pièce douteuse : elle sort des doutes, confiance 1, trace de la vérification", () => {
  let v = exemple();
  const d = C.trouverDoutes(v).find((x) => x.element === "chambre");
  assert.equal(d.propositions[0].libelle, "Chambre");
  v = C.appliquerAction(v, d.propositions[0].action, d);
  const p = v.logement.pieces.find((x) => x.id === "chambre");
  assert.equal(p.nom, "Chambre");
  assert.equal(p.confiance, 1);
  assert.equal(p.source, "atelya+verification");
  assert.ok(!C.trouverDoutes(v).some((x) => x.element === "chambre"));
});

test("tous les doutes de l'exemple se règlent en 4 clics, et le logement reste cohérent", () => {
  let v = exemple();
  for (let i = 0; i < 4; i++) {
    const d = C.trouverDoutes(v)[0];
    v = C.appliquerAction(v, d.propositions[0].action, d);
  }
  assert.deepEqual(C.trouverDoutes(v), []);
  assert.deepEqual(C.verifierCoherence(v.logement), []);
});

test("déplacer une cloison : les murs et les pièces qui la touchent suivent", () => {
  const v = C.deplacerMur(exemple(), "C_sdb", [0.3, 0.05]); // la composante le long du mur est ignorée
  procheP(mur(v, "C_sdb").debut, [6.55, 0]);
  procheP(mur(v, "C_sdb").fin, [6.55, 2.1]);
  const sdb = v.logement.pieces.find((p) => p.id === "sdb");
  proche(C.surfacePolygone(sdb.contour), 1.4 * 2.1, 1e-6); // 1,70 → 1,40 m de large
  const entree = v.logement.pieces.find((p) => p.id === "entree");
  proche(C.surfacePolygone(entree.contour), 1.6 * 2.1, 1e-6);
  // Le mur sud (parallèle à rien ici, perpendiculaire) ne bouge pas : la cloison ne s'y accroche que par un bout.
  procheP(mur(v, "M_sud").debut, [-0.1, -0.1]);
  assert.deepEqual(C.verifierCoherence(v.logement), []);
});

test("déplacer un mur dont un autre part : les portes de l'autre gardent leur place réelle", () => {
  // C_chambre part du mur C_sejour (x = 4,85) ; sa porte est à 0,30 m de son début.
  const v0 = exemple();
  const avant = v0.logement.ouvertures.find((o) => o.id === "P_chambre");
  const v = C.deplacerMur(v0, "C_sejour", [-0.25, 0]);
  const apres = v.logement.ouvertures.find((o) => o.id === "P_chambre");
  procheP(mur(v, "C_chambre").debut, [4.65, 2.15]);
  proche(apres.position, avant.position + 0.25, 1e-6);
});

test("corriger une cote : ce mur seulement, ou l'échelle de tout le plan", () => {
  const v1 = C.longueurMur(exemple(), "M_sud", 8.5);
  proche(C.longueur(mur(v1, "M_sud").debut, mur(v1, "M_sud").fin), 8.5, 1e-3);

  const v0 = exemple();
  const k = 8.2 / 8.0;
  const v2 = C.mettreAEchelle(v0, k);
  proche(C.longueur(mur(v2, "M_sud").debut, mur(v2, "M_sud").fin), 8.2 * k, 2e-3);
  const sej0 = v0.logement.pieces[0], sej2 = v2.logement.pieces[0];
  proche(C.surfacePolygone(sej2.contour), C.surfacePolygone(sej0.contour) * k * k, 1e-2);
  // Sur l'image, rien ne bouge : un coin du logement retombe sur le même pixel.
  const pt = mur(v0, "M_est").fin;
  procheP(C.versPixel(C.matriceDuCalage(v2.calage), mur(v2, "M_est").fin), C.versPixel(C.matriceDuCalage(v0.calage), pt), 0.5);
  assert.equal(v2.echelle.etat, "corrigee");
});

test("ajouter un mur et des ouvertures ; supprimer un mur emporte ses portes", () => {
  let v = C.ajouterMur(exemple(), [1, 1], [3, 1], 0.1);
  const id = v.logement.murs.at(-1).id;
  assert.equal(id, "M_v1");
  v = C.ajouterOuverture(v, id, "porte", 1.0);
  const o = v.logement.ouvertures.at(-1);
  proche(o.position, 1.0 - 0.83 / 2, 1e-3);
  assert.equal(o.hauteur, 2.04);
  v = C.ajouterOuverture(v, id, "fenetre", 0.1); // trop près du bout : elle est ramenée dans le mur
  assert.equal(v.logement.ouvertures.at(-1).position, 0);
  v = C.modifierOuverture(v, o.id, { type: "porte_fenetre" });
  assert.equal(v.logement.ouvertures.find((x) => x.id === o.id).hauteur, 2.15);
  assert.deepEqual(C.verifierCoherence(v.logement), []);
  v = C.supprimer(v, id);
  assert.ok(!v.logement.ouvertures.some((x) => x.mur === id));
  assert.throws(() => C.supprimer(v, "inconnu"));
});

test("cohérence : une porte qui dépasse de son mur est signalée, comme dans moteur/logement.py", () => {
  const v = C.modifierOuverture(exemple(), "P_entree", { largeur: 5 });
  assert.match(C.verifierCoherence(v.logement)[0], /dépasse du mur M_sud/);
  assert.throws(() => C.renommerPiece(exemple(), "sejour", "  "));
});

test("viser : la souris trouve la porte, puis le mur, puis la pièce", () => {
  const lg = exemple().logement;
  assert.deepEqual(C.elementSous(lg, [5.65, -0.1], 0.05), { genre: "ouverture", id: "P_entree" });
  assert.deepEqual(C.elementSous(lg, [2, -0.1], 0.05), { genre: "mur", id: "M_sud" });
  assert.deepEqual(C.elementSous(lg, [2, 2], 0.05), { genre: "piece", id: "sejour" });
  const m = C.murLePlusProche(lg, [6.27, 0.8], 0.05);
  assert.equal(m.id, "C_sdb");
  proche(m.le_long, 0.8);
  const inv = C.inverse(C.matriceDuCalage(exemple().calage));
  procheP(C.versPixel(inv, [210, 760]), [0, 0]);
  procheP(C.aimanter(lg, [7.6, 2.3], [4.9, 2.15], 0.1), [7.6, 2.15]); // remis d'équerre
  procheP(C.aimanter(lg, [8.05, 2.2], [4.9, 2.15], 0.1), [8, 2.15]); // accroché au bout d'un mur
});

// ---------- Étape C : valider ----------

test("valider : le résultat contient le logement corrigé et le rapport", () => {
  let v = exemple();
  for (let i = 0; i < 4; i++) {
    const d = C.trouverDoutes(v)[0];
    v = C.appliquerAction(v, d.propositions[0].action, d);
  }
  const r = C.resultat(v, { quand: "2026-10-31T12:00:00Z", corrections: 4 });
  assert.equal(r.schema, "resultat-verification/0.1");
  assert.equal(r.statut, "valide");
  assert.equal(r.logement.schema, "logement/0.1");
  assert.equal(r.logement.pieces.find((p) => p.id === "chambre").nom, "Chambre");
  assert.equal(r.rapport.corrections, 4);
  assert.deepEqual(r.rapport.doutes_restants, []);
  // Le logement rendu ne garde que les champs du format logement/0.1 (rien de propre à l'écran).
  assert.deepEqual(Object.keys(r.logement).sort(), ["hauteur_sous_plafond", "murs", "ouvertures", "pieces", "projet_id", "schema", "unites"]);
});

test("valider : avec des doutes restants, c'est noté ; avec une incohérence, c'est refusé", () => {
  const r = C.resultat(exemple());
  assert.equal(r.statut, "valide_avec_doutes");
  assert.equal(r.rapport.doutes_restants.length, 4);
  const casse = C.modifierOuverture(exemple(), "P_entree", { largeur: 9 });
  assert.throws(() => C.resultat(casse), /pas encore cohérent/);
});
