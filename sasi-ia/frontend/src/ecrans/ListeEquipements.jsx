import React from 'react';

import Panneau from '../composants/Panneau.jsx';
import { useDonnees } from '../services/donnees.jsx';
import { DataTable, LevelBadge } from '../systeme.js';

export default function ListeEquipements({ aller }) {
  const D = useDonnees();
  const colonnes = [
    { key: 'niveau', label: 'Niveau', width: 140,
      render: (e) => <LevelBadge level={e.niveau} size="sm" /> },
    { key: 'id', label: 'Identifiant', width: 140 },
    { key: 'nom', label: 'Équipement' },
    { key: 'zone', label: 'Zone', width: 80, numeric: true, align: 'right' },
    { key: 'famille', label: 'Famille', width: 200, render: (e) => D.familles[e.famille] },
    { key: 'criticite', label: 'Criticité', width: 100, numeric: true, align: 'right',
      render: (e) => `${e.criticite} sur 3` },
    { key: 'plage', label: 'Plage normale', width: 160, align: 'right',
      render: (e) => `${e.plageBasse} à ${e.plageHaute} °C` },
  ];
  return (
    <div className="ecran">
      <h1>Équipements
        <span className="titre-compte">{D.equipements.length} équipements</span>
      </h1>
      <Panneau>
        <DataTable columns={colonnes} rows={D.equipements} rowKey="id"
          onRowOpen={(e) => aller('equipement', e.id)} />
      </Panneau>
    </div>
  );
}
