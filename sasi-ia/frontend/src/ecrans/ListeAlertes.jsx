import React, { useState } from 'react';

import Panneau from '../composants/Panneau.jsx';
import { useDonnees } from '../services/donnees.jsx';
import { peut } from '../services/session.js';
import { duree, heure } from '../services/format.js';
import {
  Button, Chip, DataTable, EmptyState, LEVEL_LABEL, LevelBadge, NIVEAUX, STATE_LABEL,
} from '../systeme.js';

const ETATS = ['ouverte', 'acquittee', 'assignee', 'cloturee'];

function exporter(lignes, D) {
  const entetes = ['id', 'equipement', 'nom', 'zone', 'niveau', 'etat', 'debut',
    'duree', 'en_charge', 'raison'];
  const echapper = (valeur) => `"${String(valeur ?? '').replace(/"/g, '""')}"`;
  const contenu = [entetes.join(';')].concat(lignes.map((l) => [
    l.id, l.equipement, D.parId[l.equipement]?.nom, D.parId[l.equipement]?.zone,
    LEVEL_LABEL[l.niveau], STATE_LABEL[l.etat], new Date(l.debut).toISOString(),
    duree(l.debut, l.fin, D.maintenant), l.assignee || '', l.raison,
  ].map(echapper).join(';'))).join('\n');

  const lien = document.createElement('a');
  lien.href = URL.createObjectURL(new Blob([`﻿${contenu}`], { type: 'text/csv' }));
  lien.download = 'alertes.csv';
  lien.click();
  URL.revokeObjectURL(lien.href);
}

export default function ListeAlertes({ aller }) {
  const D = useDonnees();
  const [niveaux, setNiveaux] = useState([]);
  const [etats, setEtats] = useState(['ouverte', 'acquittee', 'assignee']);
  const [relance, setRelance] = useState(false);
  const [tri, setTri] = useState({ key: 'niveau', dir: 'desc' });

  const bascule = (valeur, liste, majorer) => majorer(
    liste.includes(valeur) ? liste.filter((v) => v !== valeur) : [...liste, valeur]);

  const lignes = [...D.alertes, ...D.historique].filter((a) => (
    (niveaux.length === 0 || niveaux.includes(a.niveau))
    && (etats.length === 0 || etats.includes(a.etat))
    && (!relance || a.relance)));

  const colonnes = [
    { key: 'niveau', label: 'Niveau', sortable: true, width: 150,
      render: (l) => (
        <LevelBadge level={l.niveau} size="sm"
          tone={['inspection', 'urgence'].includes(l.niveau) ? 'solid' : 'soft'} />
      ) },
    { key: 'id', label: 'Alerte', width: 100 },
    { key: 'equipement', label: 'Équipement', render: (l) => (
      <div>
        <div className="cellule-forte">{l.equipement}</div>
        <div className="cellule-douce">
          {D.parId[l.equipement]?.nom} · Zone {D.parId[l.equipement]?.zone}
        </div>
      </div>
    ) },
    { key: 'etat', label: 'État', width: 120,
      render: (l) => <span className="etat-pastille">{STATE_LABEL[l.etat]}</span> },
    { key: 'debut', label: 'Début', sortable: true, width: 110,
      render: (l) => heure(l.debut) },
    { key: 'duree', label: 'Durée', numeric: true, align: 'right', width: 90,
      render: (l) => duree(l.debut, l.fin, D.maintenant) },
    { key: 'raison', label: 'Raison', render: (l) => (
      <div>
        <div className="cellule-raison">{l.raison}</div>
        {l.relance && (
          <div className="cellule-relance">Relance envoyée · plus de 10 min</div>
        )}
      </div>
    ) },
    { key: 'assignee', label: 'En charge', width: 110, render: (l) => l.assignee || '—' },
    { key: 'actions', label: 'Actions', width: 230, render: (l) => (
      l.etat === 'cloturee' ? <span className="cellule-douce">Clôturée</span> : (
        <div className="cellule-actions">
          {l.etat === 'ouverte' && peut(D.session, 'prendre_en_charge') && (
            <Button size="sm" variant="secondary"
              onClick={(e) => { e.stopPropagation();
                D.action(l.equipement, 'acquitter', { par: D.session.nom }); }}>
              Prendre en charge
            </Button>
          )}
          {peut(D.session, 'assigner') && (
            <Button size="sm" variant="quiet"
              onClick={(e) => { e.stopPropagation();
                D.action(l.equipement, 'assigner',
                  { par: D.session.nom, a_qui: 'technicien' }); }}>
              {l.assignee ? 'Réassigner' : 'Assigner'}
            </Button>
          )}
        </div>
      )
    ) },
  ];

  return (
    <div className="ecran">
      <h1>Alertes<span className="titre-compte">{lignes.length} alertes affichées</span></h1>

      <Panneau>
        <div className="filtres">
          <span className="filtres-libelle">Niveau</span>
          {NIVEAUX.map((n) => (
            <Chip key={n} selected={niveaux.includes(n)} label={LEVEL_LABEL[n]}
              onClick={() => bascule(n, niveaux, setNiveaux)} />
          ))}
        </div>
        <div className="filtres">
          <span className="filtres-libelle">État</span>
          {ETATS.map((e) => (
            <Chip key={e} selected={etats.includes(e)} label={STATE_LABEL[e]}
              onClick={() => bascule(e, etats, setEtats)} />
          ))}
          <Chip selected={relance} label="Relance envoyée"
            onClick={() => setRelance(!relance)} />
          <span className="filtres-fin">
            <Button variant="quiet" size="sm"
              onClick={() => { setNiveaux([]); setEtats([]); setRelance(false); }}>
              Tout effacer
            </Button>
            <Button variant="secondary" size="sm" onClick={() => exporter(lignes, D)}>
              Exporter la liste filtrée
            </Button>
          </span>
        </div>
      </Panneau>

      <Panneau>
        <DataTable
          columns={colonnes}
          rows={lignes}
          rowKey="id"
          sort={tri}
          onSort={(key, dir) => setTri({ key, dir })}
          onRowOpen={(l) => aller('alerte', l.id)}
          rowClassName={(l) => (l.niveau === 'urgence' ? 'ligne-urgence' : undefined)}
          empty={(
            <EmptyState
              title="Aucune alerte ne correspond"
              tone="neutral"
              action={(
                <Button variant="secondary"
                  onClick={() => { setNiveaux([]); setEtats([]); setRelance(false); }}>
                  Effacer les filtres
                </Button>
              )}
            >
              Élargissez la période ou retirez un filtre.
            </EmptyState>
          )}
        />
      </Panneau>
    </div>
  );
}
