import { beforeEach, describe, expect, it } from 'vitest';

import { fermerSession, libelleRole, lireSession, ouvrirSession, peut }
  from '../services/session.js';

describe('session et droits', () => {
  beforeEach(() => { localStorage.clear(); });

  it('retient la session ouverte', () => {
    ouvrirSession('Awa N.', 'securite');
    expect(lireSession()).toMatchObject({ nom: 'Awa N.', role: 'securite' });
  });

  it('oublie la session fermée', () => {
    ouvrirSession('Awa N.', 'securite');
    fermerSession();
    expect(lireSession()).toBeNull();
  });

  it('refuse un rôle inconnu', () => {
    localStorage.setItem('sasi.session', JSON.stringify({ nom: 'X', role: 'pirate' }));
    expect(lireSession()).toBeNull();
  });

  it('donne au technicien la prise en charge mais pas l’assignation', () => {
    const session = { nom: 'Marc T.', role: 'technicien' };
    expect(peut(session, 'prendre_en_charge')).toBe(true);
    expect(peut(session, 'assigner')).toBe(false);
    expect(peut(session, 'administrer')).toBe(false);
  });

  it('donne au responsable sécurité l’assignation et les rapports', () => {
    const session = { nom: 'Awa N.', role: 'securite' };
    expect(peut(session, 'assigner')).toBe(true);
    expect(peut(session, 'rapports')).toBe(true);
  });

  it('réserve l’administration à l’administrateur', () => {
    expect(peut({ role: 'administrateur' }, 'administrer')).toBe(true);
    expect(peut({ role: 'direction' }, 'administrer')).toBe(false);
  });

  it('libelle le rôle', () => {
    expect(libelleRole({ role: 'securite' })).toBe('Responsable sécurité');
  });
});
