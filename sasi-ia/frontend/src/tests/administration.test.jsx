import { fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import { describe, expect, it, vi } from 'vitest';

import Cameras from '../ecrans/administration/Cameras.jsx';
import Equipements from '../ecrans/administration/Equipements.jsx';
import Utilisateurs from '../ecrans/administration/Utilisateurs.jsx';
import { FournisseurDonnees } from '../services/donnees.jsx';
import { chargerTout, SourceExemple } from '../services/service.js';

async function afficher(Composant) {
  const donnees = await chargerTout(SourceExemple);
  const rendu = render(
    <FournisseurDonnees donnees={{ ...donnees, action: vi.fn(),
      session: { nom: 'Admin', role: 'administrateur' } }}>
      <Composant />
    </FournisseurDonnees>,
  );
  return { ...rendu, donnees };
}

describe('administration · caméras et zones', () => {
  it('signale les équipements sans contour', async () => {
    await afficher(Cameras);
    expect(screen.getByText(/équipement\(s\) sans contour/)).toBeInTheDocument();
  });

  it('trace un contour et l’associe à un équipement', async () => {
    await afficher(Cameras);
    fireEvent.click(screen.getByText('Tracer un contour'));

    const image = screen.getByRole('img', { name: /Image thermique/ });
    image.getBoundingClientRect = () => ({ left: 0, top: 0, width: 640, height: 480 });
    [[100, 100], [200, 100], [200, 200]].forEach(([clientX, clientY]) => {
      fireEvent.click(image, { clientX, clientY });
    });

    fireEvent.click(screen.getByText('Terminer le contour'));
    expect(screen.getByText('Contour sélectionné')).toBeInTheDocument();
    expect(screen.getByText('3 points tracés.')).toBeInTheDocument();
  });

  it('demande confirmation avant de supprimer un contour', async () => {
    await afficher(Cameras);
    fireEvent.click(screen.getByText('Tracer un contour'));
    const image = screen.getByRole('img', { name: /Image thermique/ });
    image.getBoundingClientRect = () => ({ left: 0, top: 0, width: 640, height: 480 });
    [[10, 10], [60, 10], [60, 60]].forEach(([clientX, clientY]) => {
      fireEvent.click(image, { clientX, clientY });
    });
    fireEvent.click(screen.getByText('Terminer le contour'));
    fireEvent.click(screen.getByText('Supprimer le contour'));
    expect(screen.getByRole('dialog', { name: 'Supprimer le contour' })).toBeInTheDocument();
  });
});

describe('administration · équipements', () => {
  it('filtre par recherche', async () => {
    await afficher(Equipements);
    fireEvent.change(screen.getByRole('searchbox'), { target: { value: 'moulin' } });
    expect(screen.getByText('Le moulin')).toBeInTheDocument();
    expect(screen.queryByText('Le compresseur')).toBeNull();
  });

  it('refuse un seuil d’urgence inférieur au seuil d’inspection', async () => {
    await afficher(Equipements);
    fireEvent.click(screen.getAllByText('Modifier')[0]);
    const champs = screen.getAllByRole('spinbutton');
    fireEvent.change(champs[1], { target: { value: '10' } });
    expect(screen.getByRole('alert')).toHaveTextContent(/supérieur au seuil d’inspection/);
    expect(screen.getByText('Enregistrer')).toBeDisabled();
  });
});

describe('administration · utilisateurs', () => {
  it('liste les comptes et leurs rôles', async () => {
    await afficher(Utilisateurs);
    expect(screen.getAllByText('Awa N.').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Technicien').length).toBeGreaterThan(0);
  });

  it('prévient avant de désactiver un compte', async () => {
    await afficher(Utilisateurs);
    fireEvent.click(screen.getAllByText('Désactiver')[0]);
    expect(screen.getByRole('dialog', { name: 'Désactiver le compte' })).toBeInTheDocument();
  });
});
