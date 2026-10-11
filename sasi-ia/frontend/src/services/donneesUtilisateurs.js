// Utilisateurs et abonnements d'exemple (écran Administration · utilisateurs).

export const utilisateurs = [
  { identifiant: 'awa.n', nom: 'Awa N.', role: 'securite', telephone: '+237 6 99 00 11 22',
    actif: true },
  { identifiant: 'marc.t', nom: 'Marc T.', role: 'technicien', telephone: '+237 6 77 55 33 11',
    actif: true },
  { identifiant: 'lea.b', nom: 'Léa B.', role: 'technicien', telephone: '+237 6 90 12 34 56',
    actif: true },
  { identifiant: 'dir.site', nom: 'Direction du site', role: 'direction', telephone: '',
    actif: true },
  { identifiant: 'admin', nom: 'Administrateur', role: 'administrateur', telephone: '',
    actif: true },
  { identifiant: 'paul.k', nom: 'Paul K.', role: 'technicien', telephone: '+237 6 55 44 33 22',
    actif: false },
];

export const abonnements = [
  { id: 1, utilisateur: 'marc.t', zone: null, niveauMin: 'surveillance',
    heureDebut: 6, heureFin: 22, ordre: 1 },
  { id: 2, utilisateur: 'lea.b', zone: null, niveauMin: 'inspection',
    heureDebut: 22, heureFin: 6, ordre: 1 },
  { id: 3, utilisateur: 'awa.n', zone: null, niveauMin: 'inspection',
    heureDebut: 0, heureFin: 24, ordre: 2 },
  { id: 4, utilisateur: 'dir.site', zone: null, niveauMin: 'urgence',
    heureDebut: 0, heureFin: 24, ordre: 3 },
];
