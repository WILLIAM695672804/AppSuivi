import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import './preparation.js';

import Modele from '../ecrans/administration/Modele.jsx';
import { FournisseurDonnees } from '../services/donnees.jsx';
import { DonneesExemple } from '../services/donneesExemple.js';

const SESSION_ADMIN = { nom: 'Awa N.', role: 'administrateur' };
const SESSION_TECHNICIEN = { nom: 'Serge M.', role: 'technicien' };

function afficher(donnees) {
  return render(
    <FournisseurDonnees donnees={donnees}>
      <Modele />
    </FournisseurDonnees>,
  );
}

function donneesDeBase(session = SESSION_ADMIN, remplacements = {}) {
  return {
    session,
    familles: DonneesExemple.familles,
    modele: vi.fn().mockResolvedValue(DonneesExemple.modele),
    travail: vi.fn().mockResolvedValue(null),
    entrainer: vi.fn().mockResolvedValue({
      id: 'T-0001', etat: 'en cours', etape: 'lecture',
      etape_libelle: 'Lecture des mesures de fonctionnement normal',
      progression: 0, journal: [], duree_s: 0,
    }),
    mettreEnService: vi.fn().mockResolvedValue({ version: 'v1', en_service: true }),
    ...remplacements,
  };
}

describe('administration · modèle', () => {
  beforeEach(() => vi.clearAllMocks());

  it('montre la version en service et ce qu’elle vaut', async () => {
    afficher(donneesDeBase());
    expect((await screen.findAllByText('v2')).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/05\/01\/2026 au 19\/01\/2026/).length).toBeGreaterThan(0);
    expect(screen.getByText('12/12')).toBeInTheDocument();
  });

  it('détaille l’erreur de chaque famille', async () => {
    afficher(donneesDeBase());
    expect(await screen.findByText('0.50 °C')).toBeInTheDocument();
    expect(screen.getByText('0.28 °C')).toBeInTheDocument();
  });

  it('explique en clair ce que le modèle regarde', async () => {
    afficher(donneesDeBase());
    expect(await screen.findByText('la charge des 30 dernières minutes')).toBeInTheDocument();
    expect(screen.getByText('la chaleur ambiante')).toBeInTheDocument();
  });

  it('ne propose le réentraînement qu’à l’administrateur', async () => {
    const { unmount } = afficher(donneesDeBase(SESSION_TECHNICIEN));
    await screen.findAllByText('v2');
    expect(screen.queryByText('Réentraîner le modèle')).toBeNull();
    unmount();

    afficher(donneesDeBase(SESSION_ADMIN));
    expect(await screen.findByText('Réentraîner le modèle')).toBeInTheDocument();
  });

  it('lance un entraînement et affiche son avancement', async () => {
    const donnees = donneesDeBase();
    afficher(donnees);
    fireEvent.click(await screen.findByText('Réentraîner le modèle'));
    await waitFor(() => expect(donnees.entrainer).toHaveBeenCalledWith('Awa N.'));
    expect(await screen.findByText(/Lecture des mesures/)).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '0');
  });

  it('signale le refus du serveur sans casser l’écran', async () => {
    const donnees = donneesDeBase(SESSION_ADMIN, {
      entrainer: vi.fn().mockRejectedValue(new Error('Un entraînement est déjà en cours.')),
    });
    afficher(donnees);
    fireEvent.click(await screen.findByText('Réentraîner le modèle'));
    expect(await screen.findByText(/déjà en cours/)).toBeInTheDocument();
  });

  it('demande confirmation avant de changer la version en service', async () => {
    const donnees = donneesDeBase();
    afficher(donnees);
    fireEvent.click((await screen.findAllByText('Mettre en service'))[0]);
    const dialogue = await screen.findByRole('dialog');
    expect(donnees.mettreEnService).not.toHaveBeenCalled();

    const boutons = Array.from(dialogue.querySelectorAll('button'));
    fireEvent.click(boutons.find((b) => b.textContent === 'Mettre en service'));
    await waitFor(() => expect(donnees.mettreEnService).toHaveBeenCalledWith('v1', 'Awa N.'));
  });

  it('propose un premier entraînement quand aucun modèle n’existe', async () => {
    afficher(donneesDeBase(SESSION_ADMIN, {
      modele: vi.fn().mockResolvedValue({ en_service: null, versions: [], entrees: [] }),
    }));
    expect(await screen.findByText('Aucun modèle entraîné')).toBeInTheDocument();
  });
});
