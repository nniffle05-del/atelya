// Tests des calculs de la page de saisie.
// Lancement (nécessite Node.js, pas installé sur le Mac pour l'instant) :
//   node --test outils/saisie-plan/tests/calculs.test.js
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const C = require("../calculs.js");

const proche = (a, b, tol = 1e-6) => assert.ok(Math.abs(a - b) <= tol, `${a} ≠ ${b}`);
const procheP = (p, q, tol = 1e-6) => { proche(p[0], q[0], tol); proche(p[1], q[1], tol); };

test("échelle : 800 pixels pour 8,00 m donnent 100 px/m", () => {
  proche(C.echelle([210, 145], [1010, 145], 8.0), 100);
  assert.throws(() => C.echelle([0, 0], [0, 0], 1));
  assert.throws(() => C.echelle([0, 0], [10, 0], 0));
});

test("contrôle : l'écart en % entre une cote et l'échelle", () => {
  proche(C.ecartControle([135, 760], [135, 220], 5.4, 100), 0);
  proche(C.ecartControle([0, 0], [0, 102], 1.0, 100), 2);
});

test("conversion pixels ↔ mètres : y vers le haut, origine au coin sud-ouest", () => {
  const o = [210, 760];
  assert.deepEqual(C.versMetres([200, 770], o, 100), [-0.1, -0.1]);
  assert.deepEqual(C.versMetres([1020, 210], o, 100), [8.1, 5.5]);
  procheP(C.versPixels([8.1, 5.5], o, 100), [1020, 210]);
});

test("aimant d'angle : presque horizontal ou vertical devient droit", () => {
  assert.deepEqual(C.redresser([0, 0], [100, 6]), [100, 0]);
  assert.deepEqual(C.redresser([0, 0], [5, -100]), [0, -100]);
  assert.deepEqual(C.redresser([0, 0], [100, 60]), [100, 60]); // vrai biais : on ne touche pas
});

test("aimant de point : le plus proche dans le rayon", () => {
  const c = [[0, 0], [10, 0]];
  assert.deepEqual(C.pointLePlusProche([8, 1], c, 5), [10, 0]);
  assert.equal(C.pointLePlusProche([50, 50], c, 5), null);
});

test("aimant d'alignement : x et y calés sur un point existant proche", () => {
  const r = C.aligner([203, 211], [[200, 770], [1020, 210]], 5);
  assert.deepEqual(r.point, [200, 210]);
  assert.deepEqual(C.aligner([203, 211], [[200, 770]], 5, "y").point, [203, 211]); // seul y peut bouger
  assert.deepEqual(C.aligner([230, 211], [[200, 770]], 5).point, [230, 211]); // trop loin
});

test("aimant de face : une cloison s'arrête sur la face des murs, pas sur leur axe", () => {
  // Mur sud : axe y = 770 px, 20 px d'épaisseur ; mur nord : axe y = 210 px.
  const sud = { debut: [200, 770], fin: [1020, 770], epaisseurPx: 20 };
  const nord = { debut: [1020, 210], fin: [200, 210], epaisseurPx: 20 };
  const cloison = { debut: [695, 766], fin: [695, 214], epaisseurPx: 10 };
  const r = C.accrocherAuxFaces(cloison, [sud, nord]);
  procheP(r.debut, [695, 760]); // face intérieure du mur sud (y = 0 m)
  procheP(r.fin, [695, 220]); // face intérieure du mur nord (y = 5,40 m)
});

test("aimant de face : un bout posé sur un angle n'est pas déplacé", () => {
  const sud = { debut: [200, 770], fin: [1020, 770], epaisseurPx: 20 };
  const est = { debut: [1020, 770], fin: [1020, 210], epaisseurPx: 20 };
  const r = C.accrocherAuxFaces(est, [sud]);
  procheP(r.debut, [1020, 770]);
});

test("longueur tapée : le mur suivant reste accroché", () => {
  const murs = [
    { id: "M1", debut: [0, 0], fin: [98, 0], epaisseur: 0.2 },
    { id: "M2", debut: [98, 0], fin: [98, -50], epaisseur: 0.2 },
  ];
  const r = C.appliquerLongueur(murs, 0, 1.0, 100);
  procheP(r[0].fin, [100, 0]);
  assert.equal(r[0].longueurTapee, 1.0);
  procheP(r[1].debut, [100, 0]);
  procheP(r[1].fin, [98, -50]); // l'autre bout ne bouge pas
});

test("surface d'un polygone", () => {
  proche(C.surfacePolygone([[0, 0], [4.8, 0], [4.8, 5.4], [0, 5.4]]), 25.92, 1e-9);
});

test("export : statut estimé si cliqué, mesuré si la cote est tapée", () => {
  const saisie = {
    projet_id: "ESSAI",
    hauteur_sous_plafond: 2.5,
    echelle: { pxParM: 100 },
    origine: [210, 760],
    murs: [
      { id: "M1", debut: [200, 770], fin: [1020, 770], epaisseur: 0.2, longueurTapee: null },
      { id: "M2", debut: [1020, 770], fin: [1020, 210], epaisseur: 0.2, longueurTapee: 5.6 },
    ],
  };
  const l = C.construireLogement(saisie);
  assert.equal(l.schema, "logement/0.1");
  assert.deepEqual(l.murs[0].debut, [-0.1, -0.1]);
  assert.deepEqual(l.murs[0].fin, [8.1, -0.1]);
  assert.equal(l.murs[0].statut, "estime");
  assert.equal(l.murs[0].confiance, 0.8);
  assert.equal(l.murs[1].statut, "mesure");
  assert.equal(l.murs[1].source, "cote_plan");
});

test("export refusé tant qu'il manque l'échelle, l'origine ou les murs", () => {
  const vide = { projet_id: "X", hauteur_sous_plafond: 2.5, echelle: null, origine: null, murs: [] };
  assert.equal(C.verifierSaisie(vide).length, 3);
  assert.throws(() => C.construireLogement(vide));
});

// ---------- Vérification d'une lecture automatique (étape 3e) ----------

function lectureAuto() {
  return {
    projet_id: "LU",
    hauteur_sous_plafond: 2.5,
    echelle: { pxParM: 100, lue: true, sure: true },
    origine: [210, 760],
    lecture_auto: true,
    hsp_lue: true,
    murs: [{ id: "M1", debut: [200, 770], fin: [1020, 770], epaisseur: 0.2, longueurTapee: null, source: "lecture_auto" }],
    ouvertures: [
      { id: "P1", type: "porte", mur: "M1", position: 5.2, largeur: 0.9, hauteur: 2.04, allege: 0, source: "lecture_auto", sure: true, verifie: false },
    ],
    pieces: [
      { id: "piece_1", nom: "Séjour", contour: [[210, 220], [210, 760], [690, 760], [690, 220]], surfaceEcrite: 25.92, accord: true, verifie: false },
    ],
  };
}

test("lecture sans doute : rien à vérifier, logement complet et « vérifié »", () => {
  const s = lectureAuto();
  assert.deepEqual(C.doutes(s), []);
  const l = C.construireLogement(s);
  assert.equal(l.murs[0].source, "lecture_verifiee");
  assert.equal(l.ouvertures[0].mur, "M1");
  assert.equal(l.ouvertures[0].position, 5.2);
  assert.deepEqual(l.pieces[0].contour, [[0, 5.4], [0, 0], [4.8, 0], [4.8, 5.4]]);
  assert.equal(l.pieces[0].surface, 25.92);
});

test("chaque doute bloque l'enregistrement tant qu'il n'est pas levé", () => {
  const s = lectureAuto();
  s.echelle.sure = false;
  s.hsp_lue = false;
  s.ouvertures[0].sure = false;
  s.pieces[0].nom = "";
  assert.deepEqual(C.doutes(s).map((d) => d.genre), ["echelle", "hsp", "ouverture", "piece"]);
  assert.throws(() => C.construireLogement(s), /4 points à vérifier/);
  s.echelle.verifiee = true;
  s.hsp_verifiee = true;
  s.ouvertures[0].verifie = true;
  s.pieces[0].verifie = true;
  assert.deepEqual(C.doutes(s), []);
  assert.equal(C.construireLogement(s).pieces[0].nom, "Pièce 1"); // nom par défaut
});

test("une surface écrite qui ne colle pas est signalée, et n'est pas recopiée", () => {
  const s = lectureAuto();
  s.pieces[0].surfaceEcrite = 27.5;
  s.pieces[0].accord = false;
  assert.match(C.doutes(s)[0].texte, /27,5 m² écrits, 25,92 m² mesurés/);
  s.pieces[0].verifie = true;
  assert.equal(C.construireLogement(s).pieces[0].surface, null);
});

test("une ouverture qui dépasse de son mur est refusée", () => {
  const s = lectureAuto();
  s.ouvertures[0].position = 7.8;
  assert.ok(C.verifierSaisie(s).some((e) => e.includes("dépasse du mur M1")));
});

test("outils : point dans un polygone, bouts d'une ouverture", () => {
  const carre = [[0, 0], [10, 0], [10, 10], [0, 10]];
  assert.ok(C.dansPolygone([5, 5], carre));
  assert.ok(!C.dansPolygone([15, 5], carre));
  const [a, b] = C.boutsOuverture({ position: 1, largeur: 0.5 }, { debut: [0, 0], fin: [400, 0] }, 100);
  assert.deepEqual([a, b], [[100, 0], [150, 0]]);
});
