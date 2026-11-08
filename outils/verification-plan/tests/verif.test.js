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

test("plinthes choisies à l'écran : la pièce les garde, marquées « mesure » (vu par la personne)", () => {
  const v = exemple();
  const w = C.reglerPlinthes(v, "chambre", "aucune");
  const p = w.logement.pieces.find((x) => x.id === "chambre");
  assert.deepEqual(p.plinthes, { choix: "aucune", statut: "mesure", source: "verification", confiance: 1 });
  assert.ok(w.verifies.includes("chambre"));
  assert.equal(v.logement.pieces.find((x) => x.id === "chambre").plinthes, undefined); // l'original ne bouge pas
  assert.throws(() => C.reglerPlinthes(v, "chambre", "marbre"));
  assert.throws(() => C.reglerPlinthes(v, "inconnue", "bois"));
});

test("portes de placard choisies à l'écran ; un placard se reconnaît à son nom et à sa petite taille", () => {
  const v = exemple();
  const w = C.reglerPlacard(v, "chambre", "battantes");
  const p = w.logement.pieces.find((x) => x.id === "chambre");
  assert.deepEqual(p.placard, { choix: "battantes", statut: "mesure", source: "verification", confiance: 1 });
  assert.ok(C.estPlacard(p)); // un choix écrit suffit
  assert.throws(() => C.reglerPlacard(v, "chambre", "miroir"));
  const carre = (c) => [[0, 0], [c, 0], [c, c], [0, c]];
  assert.ok(C.estPlacard({ nom: "Placard 1", contour: carre(1) }));
  assert.ok(C.estPlacard({ nom: "Pièce 4 (rangement)", contour: carre(1) }));
  assert.ok(!C.estPlacard({ nom: "Dressing", contour: carre(3) })); // 9 m² : une vraie pièce
  assert.ok(!C.estPlacard({ nom: "Chambre", contour: carre(1) }));
});

test("sol choisi à l'écran ; un changement de nom oublie seulement ce qu'Atelya avait supposé", () => {
  const v = exemple();
  const w = C.reglerSol(v, "chambre", "tomettes");
  assert.deepEqual(w.logement.pieces.find((x) => x.id === "chambre").sol,
    { matiere: "tomettes", statut: "mesure", source: "verification", confiance: 1 });
  assert.throws(() => C.reglerSol(v, "chambre", "moquette"));
  const suppose = { matiere: "parquet_chene_lames", statut: "ajoute", source: "regle_par_defaut", confiance: 0.5 };
  v.logement.pieces.find((x) => x.id === "sejour").sol = suppose;
  const r = C.renommerPiece(C.reglerSol(v, "chambre", "tomettes"), "sejour", "Salle d'eau");
  assert.equal(r.logement.pieces.find((x) => x.id === "sejour").sol, undefined);
  const r2 = C.renommerPiece(C.reglerSol(v, "chambre", "tomettes"), "chambre", "Bureau");
  assert.equal(r2.logement.pieces.find((x) => x.id === "chambre").sol.matiere, "tomettes");
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
  let v = C.ajouterMur(exemple(), [1, 1], [4, 1], 0.1);
  const id = v.logement.murs.at(-1).id;
  assert.equal(id, "M_v1");
  v = C.ajouterOuverture(v, id, "porte", 2.5);
  const o = v.logement.ouvertures.at(-1);
  proche(o.position, 2.5 - 0.83 / 2, 1e-3);
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

// ---------- Points à vérifier et pièces réunies ----------

const rectangle = (x0, y0, x1, y1) => [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
const fichierPieces = (pieces, mursEnPlus = [], extra = {}) => fichier({
  echelle: { etat: "corrigee" },
  logement: { schema: "logement/0.1", projet_id: "T", unites: "m", hauteur_sous_plafond: 2.5, murs: [...murs, ...mursEnPlus], ouvertures: [], pieces },
  ...extra,
});

test("morceaux d'une pièce : sans mur entre eux, ils sont groupés ; avec un mur, non", () => {
  const pieces = [
    { id: "a", nom: "Chambre", contour: rectangle(0, 0, 2, 3) },
    { id: "b", nom: "Chambre 2", contour: rectangle(2, 0, 4, 3) },
  ];
  assert.deepEqual(C.morceauxDePieces(fichierPieces(pieces).logement), [["a", "b"]]);
  const cloison = { id: "C", debut: [2, 0], fin: [2, 3], epaisseur: 0.1, statut: "estime", source: "atelya" };
  const separees = [{ ...pieces[0], contour: rectangle(0, 0, 1.95, 3) }, { ...pieces[1], contour: rectangle(2.05, 0, 4, 3) }];
  assert.deepEqual(C.morceauxDePieces(fichierPieces(separees, [cloison]).logement), []);
});

test("réunir deux pièces : une seule reste, avec la bonne surface et le nom choisi", () => {
  const v = fichierPieces([
    { id: "a", nom: "Chambre", contour: rectangle(0, 0, 2, 3) },
    { id: "b", nom: "Séjour 2", contour: rectangle(2, 0, 4, 3) },
  ]);
  const w = C.fusionnerPieces(v, ["a", "b"], "Chambre 1");
  assert.equal(w.logement.pieces.length, 1);
  assert.equal(w.logement.pieces[0].nom, "Chambre 1");
  proche(C.surfacePolygone(w.logement.pieces[0].contour), 12, 0.3);
  assert.ok(w.logement.pieces[0].contour.length <= 6, `${w.logement.pieces[0].contour.length} coins`);
  assert.equal(v.logement.pieces.length, 2); // l'original n'est pas touché
  assert.deepEqual(C.verifierCoherence(w.logement), []);
});

test("réunir des morceaux en L garde la forme en L", () => {
  const v = fichierPieces([
    { id: "a", nom: "Cuisine", contour: rectangle(0, 0, 4, 2) },
    { id: "b", nom: "Coin", contour: rectangle(0, 2, 2, 4) },
  ]);
  const w = C.fusionnerPieces(v, ["a", "b"]);
  assert.equal(w.logement.pieces[0].nom, "Cuisine"); // sans nom donné : celui de la plus grande
  proche(C.surfacePolygone(w.logement.pieces[0].contour), 12, 0.3);
});

test("les doutes voisins sur des murs ne font qu'un point ; les légers sont réunis à la fin", () => {
  const ms = [0, 1, 2].map((i) => ({ id: `Z${i}`, debut: [10 + i * 0.5, 0], fin: [10.4 + i * 0.5, 0], epaisseur: 0.1, statut: "estime", source: "atelya" }));
  const v = fichierPieces([], ms, { doutes: [
    { element: "Z0", code: "carte", gravite: "fort", raison: "mur Z0 : hésite" },
    { element: "Z1", code: "carte", gravite: "fort", raison: "mur Z1 : hésite" },
    { element: "Z2", code: "carte", gravite: "fort", raison: "mur Z2 : hésite" },
    { element: "M1", code: "carte", gravite: "faible", raison: "mur M1 : hésite un peu" },
    { element: "M2", code: "carte", gravite: "faible", raison: "mur M2 : hésite un peu" },
  ] });
  const points = C.pointsAVerifier(v);
  assert.deepEqual(points.map((p) => p.genre), ["zone", "legers"]);
  assert.equal(points[0].elements.length, 3);
  assert.equal(points[1].elements.length, 2);
  assert.equal(C.trouverDoutes(v).length, 5); // les doutes eux-mêmes ne changent pas
});

test("régler un point le fait disparaître, et rien n'est perdu pour le rapport", () => {
  const v = fichierPieces([], [], { doutes: [
    { element: "M1", code: "carte", gravite: "fort", raison: "mur M1 : hésite" },
    { element: null, code: "zone_douteuse", gravite: "fort", raison: "zone", zone_px: [0, 0, 10, 10] },
  ] });
  let w = v;
  for (const point of C.pointsAVerifier(v)) w = C.reglerPoint(w, point, point.actions[0].action);
  assert.equal(C.pointsAVerifier(w).length, 0);
  assert.equal(C.resultat(w).statut, "valide");
  assert.equal(C.resultat(v).statut, "valide_avec_doutes");
});

test("échelle lue : on demande de contrôler une mesure ; une fois corrigée, plus de question", () => {
  const pieces = [{ id: "a", nom: "Séjour", contour: rectangle(0, 0, 5, 4) }];
  const lue = fichierPieces(pieces, [], { echelle: { etat: "lue", source: "cotes" } });
  const [point] = C.pointsAVerifier(lue);
  assert.equal(point.cle, "controle-echelle");
  assert.match(point.texte, /5,00 × 4,00/);
  assert.equal(C.pointsAVerifier(C.reglerPoint(lue, point, point.actions[0].action)).length, 0);
  assert.equal(C.pointsAVerifier(C.mettreAEchelle(lue, 1.1)).length, 0);
  const absente = fichierPieces(pieces, [], { echelle: { etat: "a_verifier" } });
  assert.equal(C.pointsAVerifier(absente)[0].cle, "echelle");
});

test("plusieurs niveaux sur l'image : premier point, avant l'échelle, parties non lues entourées ; réglé, il disparaît", () => {
  const pieces = [{ id: "a", nom: "Séjour", contour: rectangle(0, 0, 5, 4) }];
  const doute = { element: null, code: "plusieurs_niveaux", gravite: "fort", zone_px: [900, 100, 300, 400],
    blocs_px: [[900, 100, 300, 400]], raison: "Cette image contient plusieurs niveaux ou logements : un seul a été lu. Vérifiez qu'aucun niveau ne manque." };
  const v = fichierPieces(pieces, [], { echelle: { etat: "a_verifier" }, doutes: [doute] });
  const points = C.pointsAVerifier(v);
  assert.equal(points[0].genre, "niveaux");
  assert.equal(points[1].cle, "echelle");
  assert.match(points[0].texte, /plusieurs niveaux ou logements/);
  assert.deepEqual(points[0].zone_px, [900, 100, 300, 400]);
  assert.deepEqual(points[0].zones_px, [[900, 100, 300, 400]]);
  assert.equal(points[0].elements.length, 0);
  assert.equal(points.filter((p) => p.genre === "niveaux").length, 1, "un seul point, pas aussi un point « À vérifier »");
  const w = C.reglerPoint(v, points[0], points[0].actions[0].action);
  assert.ok(!C.pointsAVerifier(w).some((p) => p.genre === "niveaux"));
  assert.ok(!C.pointsAVerifier(fichierPieces(pieces, [], { echelle: { etat: "a_verifier" } })).some((p) => p.genre === "niveaux"));
});

test("les textes ne montrent jamais les codes internes", () => {
  const pieces = [{ id: "chambre_1", nom: "Chambre", contour: rectangle(0, 0, 2, 2) }, { id: "chambre_2", nom: "Bureau", contour: rectangle(5, 5, 7, 7) }];
  const v = fichierPieces(pieces, [], { doutes: [{ element: "chambre_1", code: "chevauchement", gravite: "fort", raison: "les pièces chambre_1 et chambre_2 se chevauchent" }] });
  const [point] = C.pointsAVerifier(v);
  assert.ok(!/chambre_\d/.test(point.texte), point.texte);
  assert.match(point.texte, /« Chambre » et « Bureau »/);
});

// ---------- Retoucher les murs ----------

const logementCarre = () => {
  const mur = (id, debut, fin) => ({ id, debut, fin, epaisseur: 0.2, statut: "estime", source: "atelya" });
  return fichier({
    echelle: { etat: "corrigee" },
    logement: {
      schema: "logement/0.1", projet_id: "T", unites: "m", hauteur_sous_plafond: 2.5,
      murs: [mur("S", [0, 0], [6, 0]), mur("E", [6, 0], [6, 4]), mur("N", [6, 4], [0, 4]), mur("O", [0, 4], [0, 0]), mur("C", [3, 0], [3, 4])],
      ouvertures: [{ id: "P", type: "porte", mur: "S", position: 1, largeur: 0.8, hauteur: 2.04, allege: 0, statut: "estime", source: "atelya" }],
      pieces: [{ id: "a", nom: "Séjour", contour: rectangle(0.1, 0.1, 2.9, 3.9), statut: "estime", source: "atelya" }, { id: "b", nom: "Chambre", contour: rectangle(3.1, 0.1, 5.9, 3.9), statut: "estime", source: "atelya" }],
    },
  });
};
const murDe = (v, id) => v.logement.murs.find((m) => m.id === id);

test("rallonger un mur par son début : la porte garde sa vraie place", () => {
  const v = C.deplacerBout(logementCarre(), "S", "debut", [-1, 0]);
  assert.deepEqual(murDe(v, "S").debut, [-1, 0]);
  proche(v.logement.ouvertures[0].position, 2, 1e-3);
  assert.deepEqual(C.verifierCoherence(v.logement), []);
  assert.throws(() => C.deplacerBout(logementCarre(), "S", "fin", [1.2, 0]), /porte ou une fenêtre/);
});

test("un bout de mur s'accroche : au bout voisin, puis au mur rencontré en allant tout droit, sinon reste droit", () => {
  const v = logementCarre();
  const lg = C.deplacerBout(v, "C", "fin", [3, 3]).logement; // la cloison s'arrête à 1 m du mur nord
  assert.deepEqual(C.accrocherBout(lg, "C", "fin", [3.05, 3.9], 0.3), { point: [3, 4], accroche: "mur" });
  assert.deepEqual(C.accrocherBout(lg, "S", "fin", [6.1, 0.1], 0.3), { point: [6, 0], accroche: "bout" });
  const libre = C.accrocherBout(lg, "C", "fin", [3.05, 3.3], 0.1);
  assert.equal(libre.accroche, null);
  assert.deepEqual(libre.point, [3, 3.3]);
});

test("couper un mur en deux : chaque porte suit son morceau ; on ne coupe pas à travers une porte", () => {
  const v = C.couperMur(logementCarre(), "S", 0.5);
  assert.equal(v.logement.murs.length, 6);
  const o = v.logement.ouvertures[0];
  assert.notEqual(o.mur, "S");
  proche(o.position, 0.5, 1e-3);
  assert.deepEqual(C.verifierCoherence(v.logement), []);
  assert.throws(() => C.couperMur(logementCarre(), "S", 1.3), /porte ou une fenêtre/);
});

test("enlever un morceau de mur : deux morceaux restent, la porte du morceau part avec", () => {
  const v = C.enleverMorceau(logementCarre(), "S", 0.5, 2.5);
  assert.equal(v.logement.murs.length, 6);
  assert.equal(v.logement.ouvertures.length, 0);
  assert.deepEqual(murDe(v, "S").fin, [0.5, 0]);
  assert.deepEqual(C.verifierCoherence(v.logement), []);
  const bout = C.enleverMorceau(logementCarre(), "N", 0, 2);
  assert.deepEqual(murDe(bout, "N").debut, [4, 4]);
  assert.equal(C.enleverMorceau(logementCarre(), "C", 0, 4).logement.murs.length, 4);
  assert.throws(() => C.enleverMorceau(logementCarre(), "S", 1.2, 3), /porte ou une fenêtre/);
});

test("relier deux bouts : en angle, ils se rejoignent ; alignés, un petit mur comble le trou", () => {
  const base = logementCarre();
  base.logement.murs = [{ ...murDe(base, "E"), debut: [6, 1], fin: [6, 4] }, { ...murDe(base, "S"), fin: [5, 0] }];
  base.logement.ouvertures = [];
  base.logement.pieces = [];
  const coin = C.relierMurs(base, "E", "debut", "S", "fin");
  assert.deepEqual(murDe(coin, "E").debut, [6, 0]);
  assert.deepEqual(murDe(coin, "S").fin, [6, 0]);
  const alignes = fichier({ logement: { ...base.logement, murs: [{ ...murDe(base, "S"), id: "A", debut: [0, 0], fin: [2, 0] }, { ...murDe(base, "S"), id: "B", debut: [3, 0], fin: [5, 0] }] } });
  const comble = C.relierMurs(alignes, "A", "fin", "B", "debut");
  assert.equal(comble.logement.murs.length, 3);
  assert.deepEqual(comble.logement.murs[2].debut, [2, 0]);
  assert.deepEqual(comble.logement.murs[2].fin, [3, 0]);
  assert.throws(() => C.relierMurs(base, "S", "debut", "S", "fin"), /deux murs différents/);
});

test("recalculer les pièces : deux espaces fermés, les noms sont gardés, les surfaces viennent des murs", () => {
  const v = C.recalculerPieces(logementCarre());
  assert.deepEqual(v.logement.pieces.map((p) => p.nom).sort(), ["Chambre", "Séjour"]);
  for (const p of v.logement.pieces) proche(C.surfacePolygone(p.contour), 2.8 * 3.8, 0.6);
  assert.deepEqual(C.verifierCoherence(v.logement), []);
});

test("recalculer après avoir supprimé la cloison : une seule pièce, au nom de la plus grande", () => {
  const sans = C.supprimer(logementCarre(), "C");
  const r = C.piecesDepuisMurs(sans.logement);
  assert.equal(r.pieces.length, 1);
  assert.equal(r.reunies, 1);
  proche(C.surfacePolygone(r.pieces[0].contour), 5.8 * 3.8, 0.8);
});

test("recalculer avec un trou dans les murs : les pièces ouvertes ne sont pas perdues et sont signalées", () => {
  const troue = C.enleverMorceau(logementCarre(), "N", 1, 3); // trou dans le mur nord, côté chambre
  const r = C.piecesDepuisMurs(troue.logement);
  assert.deepEqual(r.ouvertes, ["Chambre"]);
  assert.equal(r.pieces.length, 2);
  assert.deepEqual(r.pieces.find((p) => p.nom === "Chambre").contour, rectangle(3.1, 0.1, 5.9, 3.9));
});

test("une nouvelle cloison dans une pièce : deux espaces, le second reçoit un identifiant libre", () => {
  const v = C.ajouterMur(logementCarre(), [0, 2], [3, 2], 0.1);
  const w = C.recalculerPieces(v);
  assert.equal(w.logement.pieces.length, 3);
  assert.equal(new Set(w.logement.pieces.map((p) => p.id)).size, 3);
  assert.deepEqual(C.verifierCoherence(w.logement), []);
});

test("couper au centimètre, avec arrêt sur le bord d'une porte et sur un mur qui arrive", () => {
  const lg = logementCarre().logement;
  assert.deepEqual(C.aimanterSurMur(lg, "S", 2.5271, 0.03), { t: 2.53, repere: false });
  assert.deepEqual(C.aimanterSurMur(lg, "S", 1.81, 0.03), { t: 1.8, repere: true }); // le bord de la porte
  assert.deepEqual(C.aimanterSurMur(lg, "S", 3.02, 0.03), { t: 3, repere: true }); // là où arrive la cloison
});

test("répondre non : le point de mesure propose de corriger, les points groupés se voient un par un", () => {
  const pieces = [{ id: "a", nom: "Séjour", contour: rectangle(0, 0, 5, 5.58) }];
  const [point] = C.pointsAVerifier(fichierPieces(pieces, [], { echelle: { etat: "lue" } }));
  assert.deepEqual(point.actions.map((a) => a.action.type), ["regler", "mesurer"]);
  assert.deepEqual(point.mesure, { piece: "a", nom: "Séjour", x: 5, y: 5.58 });

  const ms = [0, 1, 2].map((i) => ({ id: `Z${i}`, debut: [10 + i * 0.5, 0], fin: [10.4 + i * 0.5, 0], epaisseur: 0.1, statut: "estime", source: "atelya" }));
  const v = fichierPieces([], ms, { doutes: ms.map((m) => ({ element: m.id, code: "carte", gravite: "fort", raison: `mur ${m.id} : hésite` })) });
  const groupe = C.pointsAVerifier(v);
  assert.equal(groupe.length, 1);
  assert.ok(groupe[0].actions.some((a) => a.action.type === "detail"));
  const detail = C.pointsAVerifier(v, { detail: groupe[0].doutes.map((d) => d.cle) });
  assert.equal(detail.length, 3);
  assert.ok(detail.every((x) => x.elements.length === 1 && x.zone_px));
  assert.ok(!/Z\d/.test(detail[0].texte), detail[0].texte);
});

test("une pièce non fermée : l'écran montre le trou et propose le mur qui le ferme", () => {
  const troue = C.enleverMorceau(logementCarre(), "N", 1, 3); // trou de 2 m dans le mur nord, côté chambre
  const [f] = C.piecesDepuisMurs(troue.logement).fuites;
  assert.equal(f.piece, "b");
  proche(f.a[1], 3.9, 0.01);
  assert.ok(f.longueur > 1.2 && f.longueur < 2.2, `${f.longueur}`);
  assert.ok(f.mur, "un mur proposé");
  const points = C.pointsAVerifier(troue, { fermeture: true });
  const point = points.find((x) => x.genre === "fuite");
  assert.equal(point.cle, "fuite|b");
  assert.equal(point.trait_m.length, 2);
  assert.ok(point.zone_px[2] > 0);
  assert.ok(!/\bb\b/.test(point.titre));
  assert.ok(!C.pointsAVerifier(troue).some((x) => x.genre === "fuite"), "seulement après un recalcul");
  const ferme = C.reglerPoint(troue, point, point.actions[0].action);
  assert.deepEqual(C.piecesDepuisMurs(ferme.logement).ouvertes, []);
  assert.deepEqual(C.verifierCoherence(ferme.logement), []);
  assert.ok(!C.pointsAVerifier(ferme, { fermeture: true }).some((x) => x.genre === "fuite"));
});

test("une pièce vraiment ouverte peut rester ouverte, et un nouvel espace est signalé", () => {
  const troue = C.enleverMorceau(logementCarre(), "N", 1, 3);
  const point = C.pointsAVerifier(troue, { fermeture: true }).find((x) => x.genre === "fuite");
  const garde = C.reglerPoint(troue, point, { type: "regler" });
  assert.ok(!C.pointsAVerifier(garde, { fermeture: true }).some((x) => x.genre === "fuite"));
  const cloison = C.recalculerPieces(C.ajouterMur(logementCarre(), [3, 2], [6, 2], 0.1));
  const noms = cloison.logement.pieces.map((x) => x.nom);
  assert.equal(noms.length, 3);
  assert.deepEqual(C.pointsAVerifier(cloison, { fermeture: true }).filter((x) => x.genre === "fuite"), []);
});

// ---------- Reprendre un travail ----------

test("reprendre un travail : tout revient, y compris ce qui a été vérifié et les doutes vus un par un", () => {
  const base = logementCarre();
  const corrige = C.confirmer(C.supprimer(base, "C"), "S");
  const t = C.travail(corrige, { detail: ["x"], fermeture: true, murs_calcules: "abc", quand: "2026-11-04" });
  const r = C.reprendreTravail(base, JSON.parse(JSON.stringify(t)));
  assert.deepEqual(r.v, corrige);
  assert.deepEqual(r.detail, ["x"]);
  assert.equal(r.fermeture, true);
  assert.equal(r.murs_calcules, "abc");
});

test("reprendre un logement.json enregistré : le calage et la correction d'échelle sont retrouvés", () => {
  const base = logementCarre();
  const corrige = C.supprimer(C.mettreAEchelle(base, 1.1), "C");
  const r = C.reprendreTravail(base, JSON.parse(JSON.stringify(corrige.logement)));
  assert.deepEqual(r.v.logement, corrige.logement);
  const a = C.matriceDuCalage(r.v.calage), b = C.matriceDuCalage(corrige.calage);
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) proche(a[i][j], b[i][j], 1e-3);
  assert.equal(r.v.echelle.etat, "corrigee");
  const resultat = C.resultat(C.renommerPiece(base, "a", "Salon"));
  const r2 = C.reprendreTravail(base, resultat);
  assert.deepEqual(r2.v.verifies, ["a"].filter((id) => resultat.logement.pieces.find((x) => x.id === id).source.includes("verification")));
  assert.equal(r2.v.echelle.etat, "corrigee"); // celle de logementCarre, inchangée
});

test("reprendre : un fichier d'un autre plan ou sans rapport est refusé", () => {
  const base = logementCarre();
  const autre = JSON.parse(JSON.stringify(base.logement));
  autre.projet_id = "Autre";
  assert.throws(() => C.reprendreTravail(base, autre), /concerne le plan « Autre »/);
  assert.throws(() => C.reprendreTravail(base, { a: 1 }), /pas un travail/);
  assert.throws(() => C.reprendreTravail(base, C.travail({ ...base, logement: autre })), /concerne le plan/);
});

test("deux ouvertures l'une sur l'autre : incohérence pour le moteur, et un point qui propose d'en garder une", () => {
  const v = logementCarre();
  v.logement.ouvertures.push({ id: "F", type: "fenetre", mur: "S", position: 1.5, largeur: 1.0, hauteur: 1.2, allege: 0.9, statut: "estime", source: "atelya" });
  assert.ok(C.verifierCoherence(v.logement).some((e) => /chevauchent de 30 cm/.test(e)));
  const point = C.pointsAVerifier(v).find((p) => p.genre === "recouvrement");
  assert.deepEqual(point.elements, ["P", "F"]);
  assert.match(point.texte, /porte de 0,80 m et une fenêtre de 1,00 m/);
  const w = C.reglerPoint(v, point, point.actions[1].action); // garder la fenêtre
  assert.deepEqual(w.logement.ouvertures.map((o) => o.id), ["F"]);
  assert.deepEqual(C.verifierCoherence(w.logement), []);
  assert.ok(!C.pointsAVerifier(w).some((p) => p.genre === "recouvrement"));
});
