import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import './preparation.js';

import BancEssai from '../ecrans/administration/BancEssai.jsx';
import Raisonnement from '../ecrans/administration/Raisonnement.jsx';
import { FournisseurDonnees } from '../services/donnees.jsx';
import { DonneesExemple } from '../services/donneesExemple.js';

const ADMIN = { nom: 'Awa N.', role: 'administrateur' };
const TECHNICIEN = { nom: 'Serge M.', role: 'technicien' };

const ESSAI = {
  equipement: 'Z2-CHE-01', nom: 'La chaudière d’ébullition',
  situation: 'retour', libelle: 'chauffe, puis retour à la normale à mi-parcours',
  plage: [150, 250], seuil_inspection: 280, seuil_urgence: 300, criticite: 2,
  calibrage: { biais: 0.0, dispersion: 4.1 },
  trace: [
    { minute: 0, mesuree: 200, attendue: 200, ecart: 0, risque: 0, niveau: 'normal' },
    { minute: 4, mesuree: 208, attendue: 200, ecart: 8, risque: 79, niveau: 'surveillance' },
    { minute: 20, mesuree: 220, attendue: 200, ecart: 20, risque: 0, niveau: 'urgence' },
  ],
  changements: [
    { minute: 4, niveau: 'surveillance', raison: 'La chaudière monte de 2,00 °C par minute…' },
  ],
};

function afficher(Composant, donnees) {
  return render(
    <FournisseurDonnees donnees={donnees}><Composant /></FournisseurDonnees>,
  );
}

function base(session = ADMIN, remplacements = {}) {
  return {
    session,
    familles: DonneesExemple.familles,
    equipements: DonneesExemple.equipements,
    inspection: vi.fn().mockResolvedValue(DonneesExemple.inspection),
    situations: vi.fn().mockResolvedValue(DonneesExemple.situations),
    inspecter: vi.fn().mockResolvedValue({
      id: 'T-0002', genre: 'inspection', etat: 'en cours', etape: 'lecture',
      etape_libelle: 'Lecture des mesures de fonctionnement normal',
      progression: 0, journal: [], duree_s: 0,
    }),
    travail: vi.fn().mockResolvedValue(null),
    essai: vi.fn().mockResolvedValue(ESSAI),
    ...remplacements,
  };
}

describe('administration · raisonnement', () => {
  beforeEach(() => vi.clearAllMocks());

  it('résume les contrôles de bon sens', async () => {
    afficher(Raisonnement, base());
    expect(await screen.findByText('Contrôles de bon sens')).toBeInTheDocument();
    expect(screen.getByText('50')).toBeInTheDocument();
    expect(screen.getAllByText('6').length).toBeGreaterThan(0);
  });

  it('met en avant les raisonnements à corriger', async () => {
    afficher(Raisonnement, base());
    expect(await screen.findByText('Raisonnements à corriger')).toBeInTheDocument();
    expect(screen.getAllByText(/Z5-PAS-01/).length).toBeGreaterThan(0);
  });

  it('montre où le modèle se trompe, du pire au meilleur', async () => {
    afficher(Raisonnement, base());
    expect(await screen.findByText('0.58 °C')).toBeInTheDocument();
    expect(screen.getByText('+0.10 °C')).toBeInTheDocument();
  });

  it('traduit en clair ce sur quoi le modèle s’appuie', async () => {
    afficher(Raisonnement, base());
    expect(await screen.findAllByText('la charge des 30 dernières minutes'))
      .toHaveLength(2);
    expect(screen.getByText('51.2 %')).toBeInTheDocument();
  });

  it('ne propose l’inspection qu’à l’administrateur', async () => {
    const { unmount } = afficher(Raisonnement, base(TECHNICIEN));
    await screen.findByText('Contrôles de bon sens');
    expect(screen.queryByText('Inspecter le modèle en service')).toBeNull();
    unmount();

    afficher(Raisonnement, base(ADMIN));
    expect(await screen.findByText('Inspecter le modèle en service')).toBeInTheDocument();
  });

  it('propose de lancer une inspection quand il n’y en a pas', async () => {
    afficher(Raisonnement, base(ADMIN, {
      inspection: vi.fn().mockRejectedValue(new Error('404')),
    }));
    expect(await screen.findByText('Aucune inspection disponible')).toBeInTheDocument();
  });

  it('lance l’inspection et suit son avancement', async () => {
    const donnees = base();
    afficher(Raisonnement, donnees);
    fireEvent.click(await screen.findByText('Inspecter le modèle en service'));
    await waitFor(() => expect(donnees.inspecter).toHaveBeenCalledWith('Awa N.'));
    expect(await screen.findByText(/Lecture des mesures/)).toBeInTheDocument();
  });
});

describe('administration · banc d’essai', () => {
  beforeEach(() => vi.clearAllMocks());

  it('propose les situations venues du serveur', async () => {
    afficher(BancEssai, base());
    await waitFor(() => expect(screen.getByText(/chauffe régulière/)).toBeInTheDocument());
  });

  it('soumet la situation choisie et montre la réaction', async () => {
    const donnees = base();
    afficher(BancEssai, donnees);
    fireEvent.click(screen.getByText('Lancer l’essai'));
    await waitFor(() => expect(donnees.essai).toHaveBeenCalled());
    expect((await screen.findAllByText(/chauffe, puis retour à la normale/)).length)
      .toBeGreaterThan(0);
    expect(screen.getByText('79 %')).toBeInTheDocument();     // risque le plus haut
  });

  it('montre le retour à la normale : le risque retombe', async () => {
    const donnees = base();
    afficher(BancEssai, donnees);
    fireEvent.click(screen.getByText('Lancer l’essai'));
    await screen.findAllByText(/chauffe, puis retour/);
    expect(screen.getAllByText('0 %').length).toBeGreaterThan(0);  // risque final nul
  });

  it('annonce quand l’IA ne trouve rien', async () => {
    const donnees = base(ADMIN, {
      essai: vi.fn().mockResolvedValue({ ...ESSAI, changements: [] }),
    });
    afficher(BancEssai, donnees);
    fireEvent.click(screen.getByText('Lancer l’essai'));
    expect(await screen.findByText('Aucune alerte')).toBeInTheDocument();
  });

  it('signale un refus du serveur sans casser l’écran', async () => {
    const donnees = base(ADMIN, {
      essai: vi.fn().mockRejectedValue(new Error('Équipement inconnu')),
    });
    afficher(BancEssai, donnees);
    fireEvent.click(screen.getByText('Lancer l’essai'));
    expect(await screen.findByText(/Équipement inconnu/)).toBeInTheDocument();
  });
});
