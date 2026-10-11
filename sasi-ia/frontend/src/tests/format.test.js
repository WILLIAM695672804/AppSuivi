import { describe, expect, it } from 'vitest';

import { depuis, duree, pourcentage, signe } from '../services/format.js';

const MINUTE = 60000;

describe('mise en forme', () => {
  it('écrit les durées écoulées en français', () => {
    const maintenant = 1_000_000_000;
    expect(depuis(maintenant - 12 * MINUTE, maintenant)).toBe('il y a 12 min');
    expect(depuis(maintenant - 200 * MINUTE, maintenant)).toBe('depuis 3 h 20');
  });

  it('écrit une durée entre deux instants', () => {
    expect(duree(0, 200 * MINUTE)).toBe('3 h 20');
  });

  it('écrit les pourcentages avec l’espace avant le signe', () => {
    expect(pourcentage(99.4, 1)).toBe('99,4 %');
    expect(pourcentage(null)).toBe('—');
  });

  it('signe les écarts', () => {
    expect(signe(18)).toBe('+18,0');
    expect(signe(-2.5)).toBe('−2,5');
  });
});
