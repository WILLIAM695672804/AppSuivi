import { fireEvent, render, screen, within } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';

import ListeAlertes from '../ecrans/ListeAlertes.jsx';
import ListeEquipements from '../ecrans/ListeEquipements.jsx';
import Rapports from '../ecrans/Rapports.jsx';
import TableauDeBord from '../ecrans/TableauDeBord.jsx';
import { FournisseurDonnees } from '../services/donnees.jsx';
import { chargerTout, SourceExemple } from '../services/service.js';

async function afficher(Composant, { role = 'securite', aller = vi.fn(), ...reste } = {}) {
  const donnees = await chargerTout(SourceExemple);
  const action = vi.fn().mockResolvedValue({});
  const rendu = render(
    <FournisseurDonnees donnees={{ ...donnees, action, session: { nom: 'Awa N.', role } }}>
      <Composant aller={aller} {...reste} />
    </FournisseurDonnees>,
  );
  return { ...rendu, donnees, action, aller };
}

describe('tableau de bord', () => {
  it('annonce l’état du site et compte les équipements normaux', async () => {
    await afficher(TableauDeBord);
    expect(screen.getAllByText(/urgence en cours|alertes en cours|Tout va bien/).length)
      .toBeGreaterThan(0);
    expect(screen.getByText(/12 équipements sur 17 sont normaux/)).toBeInTheDocument();
  });

  it('affiche les sept zones du site', async () => {
    await afficher(TableauDeBord);
    expect(screen.getByText(/Zone 1 —/)).toBeInTheDocument();
    expect(screen.getByText(/Zone 7 —/)).toBeInTheDocument();
  });

  it('ouvre la fiche d’un équipement au clic', async () => {
    const { aller } = await afficher(TableauDeBord);
    fireEvent.click(screen.getByText('Le moulin'));
    expect(aller).toHaveBeenCalledWith('equipement', 'Z1-MOU-01');
  });
});

describe('liste des alertes', () => {
  it('affiche les alertes en cours', async () => {
    await afficher(ListeAlertes);
    expect(screen.getByText('A-1033')).toBeInTheDocument();
    expect(screen.getByText('Z6-RES-01')).toBeInTheDocument();
  });

  it('propose la prise en charge au technicien', async () => {
    await afficher(ListeAlertes, { role: 'technicien' });
    expect(screen.getAllByText('Prendre en charge').length).toBeGreaterThan(0);
    expect(screen.queryByText('Assigner')).toBeNull();
  });

  it('propose l’assignation au responsable sécurité', async () => {
    const { action } = await afficher(ListeAlertes, { role: 'securite' });
    fireEvent.click(screen.getAllByText('Assigner')[0]);
    expect(action).toHaveBeenCalled();
    expect(action.mock.calls[0][1]).toBe('assigner');
  });

  it('n’affiche aucune action à la direction', async () => {
    await afficher(ListeAlertes, { role: 'direction' });
    expect(screen.queryByText('Prendre en charge')).toBeNull();
    expect(screen.queryByText('Assigner')).toBeNull();
  });

  it('filtre par niveau', async () => {
    await afficher(ListeAlertes);
    fireEvent.click(screen.getByText('Urgence'));
    const tableau = screen.getByRole('table');
    expect(within(tableau).getByText('Z6-RES-01')).toBeInTheDocument();
    expect(within(tableau).queryByText('Z1-ELV-01')).toBeNull();
  });
});

describe('liste des équipements', () => {
  it('affiche les 17 équipements', async () => {
    await afficher(ListeEquipements);
    const lignes = screen.getAllByRole('row');
    expect(lignes).toHaveLength(18);           // 17 équipements + l'en-tête
  });
});

describe('rapports', () => {
  it('affiche les indicateurs de la semaine', async () => {
    await afficher(Rapports);
    expect(screen.getByText('Alertes de la semaine')).toBeInTheDocument();
    expect(screen.getByText(/Équipements les plus exposés/)).toBeInTheDocument();
  });
});
