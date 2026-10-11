import { describe, expect, it } from 'vitest';

import { chargerTout, convertirAlerte, SourceExemple } from '../services/service.js';

describe('source d’exemple', () => {
  it('charge un site complet', async () => {
    const donnees = await chargerTout(SourceExemple);
    expect(donnees.mode).toBe('exemple');
    expect(donnees.equipements).toHaveLength(17);
    expect(Object.keys(donnees.zones)).toHaveLength(7);
    expect(donnees.alertes.length).toBeGreaterThan(0);
  });

  it('reporte le niveau des alertes sur les équipements', async () => {
    const donnees = await chargerTout(SourceExemple);
    const enAlerte = donnees.alertes[0];
    expect(donnees.parId[enAlerte.equipement].niveau).toBe(enAlerte.niveau);
  });

  it('applique les seuils relevés sur le terrain', async () => {
    const donnees = await chargerTout(SourceExemple);
    const moulin = donnees.parId['Z1-MOU-01'];
    expect([moulin.plageBasse, moulin.plageHaute]).toEqual([20, 35]);
    expect([moulin.seuilInspection, moulin.seuilUrgence]).toEqual([35, 40]);
  });

  it('produit une série de mesures et sa température attendue', async () => {
    const donnees = await chargerTout(SourceExemple);
    const serie = await donnees.serie(donnees.parId['Z1-ELV-01'], { heures: 2 });
    expect(serie.mesure.length).toBeGreaterThan(10);
    expect(serie.mesure).toHaveLength(serie.attendu.length);
    expect(serie.mesure[0]).toHaveProperty('t');
    expect(serie.mesure[0]).toHaveProperty('v');
  });
});

describe('liaison avec le serveur', () => {
  it('convertit une fiche d’alerte du serveur', () => {
    const fiche = convertirAlerte({
      id: 'A-1', equipement: 'Z1-ELV-01', niveau: 'inspection', etat: 'ouverte',
      debut: 1767600000, fin: null, assignee_a: 'technicien',
      evenements: [{ t: 1767600060, type: 'ouverture' }],
    });
    expect(fiche.debut).toBe(1767600000000);
    expect(fiche.assignee).toBe('technicien');
    expect(fiche.evenements[0].t).toBe(1767600060000);
  });

  it('remplace une alerte reçue en direct sans la dupliquer', async () => {
    const donnees = await chargerTout(SourceExemple);
    const avant = donnees.alertes.length;
    donnees.appliquerAlerte({ ...donnees.alertes[0], niveau: 'urgence' });
    expect(donnees.alertes).toHaveLength(avant);
    expect(donnees.alertes[0].niveau).toBe('urgence');
  });

  it('bascule une alerte clôturée dans l’historique', async () => {
    const donnees = await chargerTout(SourceExemple);
    const fiche = { ...donnees.alertes[0], etat: 'cloturee', fin: Date.now() };
    const avant = donnees.historique.length;
    donnees.appliquerAlerte(fiche);
    expect(donnees.historique).toHaveLength(avant + 1);
    expect(donnees.alertes.some((a) => a.id === fiche.id)).toBe(false);
    expect(donnees.parId[fiche.equipement].niveau).toBe('normal');
  });

  it('prévient l’interface à chaque changement, puis cesse après désabonnement', async () => {
    const donnees = await chargerTout(SourceExemple);
    let appels = 0;
    const seDesabonner = donnees.abonner(() => { appels += 1; });
    donnees.appliquerNiveaux({ 'Z1-ELV-01': 'surveillance' });
    seDesabonner();
    donnees.appliquerNiveaux({ 'Z1-ELV-01': 'normal' });
    expect(appels).toBe(1);
  });

  it('change l’écran dès l’action, sans attendre le serveur', async () => {
    const donnees = await chargerTout(SourceExemple);
    const alerte = donnees.alertes.find((a) => a.etat === 'ouverte') || donnees.alertes[0];
    await donnees.action(alerte.equipement, 'acquitter', { par: 'Awa N.' });
    expect(donnees.alertes.find((a) => a.id === alerte.id).etat).toBe('acquittee');
    await donnees.action(alerte.equipement, 'assigner', { par: 'Awa N.', a_qui: 'Serge M.' });
    expect(donnees.alertes.find((a) => a.id === alerte.id).assignee).toBe('Serge M.');
  });

  it('rétablit l’affichage quand le serveur refuse', async () => {
    const source = {
      ...SourceExemple,
      async action() { throw new Error('Une clôture exige un compte rendu.'); },
    };
    const donnees = await chargerTout(source);
    const alerte = donnees.alertes[0];
    await donnees.action(alerte.equipement, 'cloturer', { par: 'Awa N.', constat: '' });
    expect(donnees.alertes.find((a) => a.id === alerte.id).etat).toBe(alerte.etat);
    expect(donnees.derniereErreur).toMatch(/compte rendu/);
  });
});
