// Contrôle des services de l'interface sans installer de bibliothèque.
//
// Les vrais tests tournent avec Vitest (npm test) ; ce programme vérifie la
// logique pure (routeur, session, mise en forme, données d'exemple) avec le
// seul Node, en remplaçant les objets du navigateur.
//
//     node outils/verifier_services.mjs

import assert from 'node:assert/strict';

const memoire = new Map();
globalThis.window = {
  location: { hash: '', search: '', protocol: 'file:' },
  addEventListener() {}, removeEventListener() {},
};
globalThis.localStorage = {
  getItem: (clef) => (memoire.has(clef) ? memoire.get(clef) : null),
  setItem: (clef, valeur) => memoire.set(clef, String(valeur)),
  removeItem: (clef) => memoire.delete(clef),
  clear: () => memoire.clear(),
};
globalThis.location = globalThis.window.location;

const { lireAdresse, ecrireAdresse, entreeMenu, titrePage } =
  await import('../frontend/src/services/routeur.js');
const { ouvrirSession, lireSession, fermerSession, peut, libelleRole } =
  await import('../frontend/src/services/session.js');
const { depuis, duree, pourcentage, signe } =
  await import('../frontend/src/services/format.js');
const { SourceExemple, chargerTout, convertirAlerte } =
  await import('../frontend/src/services/service.js');

const controles = [];
const controle = (nom, fonction) => controles.push([nom, fonction]);

// ---------------------------------------------------------------- routeur
controle('routeur : écran simple', () => {
  assert.deepEqual(lireAdresse('#alertes'), { ecran: 'alertes', cible: null });
});
controle('routeur : écran avec cible', () => {
  assert.deepEqual(lireAdresse('#alerte/A-1033'), { ecran: 'alerte', cible: 'A-1033' });
});
controle('routeur : adresse vide', () => assert.equal(lireAdresse('').ecran, 'tableau'));
controle('routeur : adresse inconnue', () => assert.equal(lireAdresse('#zzz').ecran, 'introuvable'));
controle('routeur : écriture', () => {
  assert.equal(ecrireAdresse('equipement', 'Z1-ELV-01'), '#equipement/Z1-ELV-01');
  assert.equal(ecrireAdresse('rapports'), '#rapports');
});
controle('routeur : entrée de menu parente', () => assert.equal(entreeMenu('alerte'), 'alertes'));
controle('routeur : titre de page', () => {
  assert.equal(titrePage('alerte', 'A-1033'), 'Fiche d’alerte · A-1033 — SASI');
});

// ---------------------------------------------------------------- session
controle('session : ouverture et relecture', () => {
  localStorage.clear();
  ouvrirSession('Awa N.', 'securite');
  assert.equal(lireSession().nom, 'Awa N.');
});
controle('session : fermeture', () => {
  ouvrirSession('Awa N.', 'securite');
  fermerSession();
  assert.equal(lireSession(), null);
});
controle('session : rôle inconnu refusé', () => {
  localStorage.setItem('sasi.session', JSON.stringify({ nom: 'X', role: 'pirate' }));
  assert.equal(lireSession(), null);
});
controle('droits : technicien', () => {
  const s = { role: 'technicien' };
  assert.equal(peut(s, 'prendre_en_charge'), true);
  assert.equal(peut(s, 'assigner'), false);
  assert.equal(peut(s, 'administrer'), false);
});
controle('droits : responsable sécurité', () => {
  const s = { role: 'securite' };
  assert.equal(peut(s, 'assigner'), true);
  assert.equal(peut(s, 'rapports'), true);
});
controle('droits : administrateur', () => {
  assert.equal(peut({ role: 'administrateur' }, 'administrer'), true);
  assert.equal(peut({ role: 'direction' }, 'administrer'), false);
});
controle('droits : libellé', () => {
  assert.equal(libelleRole({ role: 'securite' }), 'Responsable sécurité');
});

// ---------------------------------------------------------------- format
controle('format : durées écoulées', () => {
  const t = 1_000_000_000;
  assert.equal(depuis(t - 12 * 60000, t), 'il y a 12 min');
  assert.equal(depuis(t - 200 * 60000, t), 'depuis 3 h 20');
});
controle('format : durée entre deux instants', () => {
  assert.equal(duree(0, 200 * 60000), '3 h 20');
});
controle('format : pourcentage', () => {
  assert.equal(pourcentage(99.4, 1), '99,4 %');
  assert.equal(pourcentage(null), '—');
});
controle('format : écart signé', () => {
  assert.equal(signe(18), '+18,0');
  assert.equal(signe(-2.5), '−2,5');
});

// ---------------------------------------------------------------- données
controle('données : site complet', async () => {
  const d = await chargerTout(SourceExemple);
  assert.equal(d.mode, 'exemple');
  assert.equal(d.equipements.length, 17);
  assert.equal(Object.keys(d.zones).length, 7);
  assert.ok(d.alertes.length > 0);
});
controle('données : niveau reporté sur l’équipement', async () => {
  const d = await chargerTout(SourceExemple);
  const alerte = d.alertes[0];
  assert.equal(d.parId[alerte.equipement].niveau, alerte.niveau);
});
controle('données : seuils du terrain', async () => {
  const d = await chargerTout(SourceExemple);
  const moulin = d.parId['Z1-MOU-01'];
  assert.deepEqual([moulin.plageBasse, moulin.plageHaute], [20, 35]);
  assert.deepEqual([moulin.seuilInspection, moulin.seuilUrgence], [35, 40]);
});
controle('données : série de mesures', async () => {
  const d = await chargerTout(SourceExemple);
  const serie = await d.serie(d.parId['Z1-ELV-01'], { heures: 2 });
  assert.ok(serie.mesure.length > 10);
  assert.equal(serie.mesure.length, serie.attendu.length);
  assert.ok('t' in serie.mesure[0] && 'v' in serie.mesure[0]);
});

// ------------------------------------------------- liaison avec le serveur
controle('liaison : conversion d’une fiche du serveur', () => {
  const fiche = convertirAlerte({
    id: 'A-1', equipement: 'Z1-ELV-01', niveau: 'inspection', etat: 'ouverte',
    debut: 1767600000, fin: null, assignee_a: 'technicien',
    evenements: [{ t: 1767600060, type: 'ouverture' }],
  });
  assert.equal(fiche.debut, 1767600000000);
  assert.equal(fiche.assignee, 'technicien');
  assert.equal(fiche.evenements[0].t, 1767600060000);
});

controle('liaison : une alerte reçue en direct remplace l’ancienne', async () => {
  const d = await chargerTout(SourceExemple);
  const avant = d.alertes.length;
  const fiche = { ...d.alertes[0], niveau: 'urgence' };
  d.appliquerAlerte(fiche);
  assert.equal(d.alertes.length, avant);
  assert.equal(d.alertes[0].niveau, 'urgence');
  assert.equal(d.parId[fiche.equipement].niveau, 'urgence');
});

controle('liaison : une clôture bascule dans l’historique', async () => {
  const d = await chargerTout(SourceExemple);
  const fiche = { ...d.alertes[0], etat: 'cloturee', fin: Date.now() };
  const avant = d.historique.length;
  d.appliquerAlerte(fiche);
  assert.equal(d.historique.length, avant + 1);
  assert.ok(!d.alertes.some((a) => a.id === fiche.id));
  assert.equal(d.parId[fiche.equipement].niveau, 'normal');
});

controle('liaison : les changements préviennent l’interface', async () => {
  const d = await chargerTout(SourceExemple);
  let appels = 0;
  const seDesabonner = d.abonner(() => { appels += 1; });
  d.appliquerNiveaux({ 'Z1-ELV-01': 'surveillance' });
  seDesabonner();
  d.appliquerNiveaux({ 'Z1-ELV-01': 'normal' });
  assert.equal(appels, 1);
});

controle('liaison : une action change l’écran sans attendre le serveur', async () => {
  const d = await chargerTout(SourceExemple);
  const alerte = d.alertes.find((a) => a.etat === 'ouverte') || d.alertes[0];
  await d.action(alerte.equipement, 'acquitter', { par: 'Awa N.' });
  assert.equal(d.alertes.find((a) => a.id === alerte.id).etat, 'acquittee');
  await d.action(alerte.equipement, 'assigner', { par: 'Awa N.', a_qui: 'Serge M.' });
  assert.equal(d.alertes.find((a) => a.id === alerte.id).assignee, 'Serge M.');
});

controle('liaison : un refus du serveur rétablit l’affichage', async () => {
  const source = {
    ...SourceExemple,
    async action() { throw new Error('Une clôture exige un compte rendu.'); },
  };
  const d = await chargerTout(source);
  const alerte = d.alertes[0];
  await d.action(alerte.equipement, 'cloturer', { par: 'Awa N.', constat: '' });
  assert.equal(d.alertes.find((a) => a.id === alerte.id).etat, alerte.etat);
  assert.match(d.derniereErreur, /compte rendu/);
});

let echecs = 0;
for (const [nom, fonction] of controles) {
  try {
    await fonction();
    console.log(`  OK    ${nom}`);
  } catch (erreur) {
    echecs += 1;
    console.log(`  ECHEC ${nom} : ${erreur.message}`);
  }
}
console.log(`\n${controles.length - echecs}/${controles.length} contrôles réussis`);
process.exit(echecs ? 1 : 0);
