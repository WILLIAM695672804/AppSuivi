import { describe, expect, it } from 'vitest';

import { ecrireAdresse, entreeMenu, lireAdresse, titrePage } from '../services/routeur.js';

describe('routeur', () => {
  it('lit un écran simple', () => {
    expect(lireAdresse('#alertes')).toEqual({ ecran: 'alertes', cible: null });
  });

  it('lit un écran avec sa cible', () => {
    expect(lireAdresse('#alerte/A-1033')).toEqual({ ecran: 'alerte', cible: 'A-1033' });
  });

  it('revient au tableau de bord quand l’adresse est vide', () => {
    expect(lireAdresse('').ecran).toBe('tableau');
  });

  it('signale une adresse inconnue', () => {
    expect(lireAdresse('#nimporte').ecran).toBe('introuvable');
  });

  it('écrit une adresse partageable', () => {
    expect(ecrireAdresse('equipement', 'Z1-ELV-01')).toBe('#equipement/Z1-ELV-01');
    expect(ecrireAdresse('rapports')).toBe('#rapports');
  });

  it('met en évidence l’entrée de menu parente', () => {
    expect(entreeMenu('alerte')).toBe('alertes');
    expect(entreeMenu('suivi')).toBe('suivi');
  });

  it('compose le titre de la page', () => {
    expect(titrePage('alerte', 'A-1033')).toBe('Fiche d’alerte · A-1033 — SASI');
  });
});
