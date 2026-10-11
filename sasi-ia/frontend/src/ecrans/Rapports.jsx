import React from 'react';

import Panneau from '../composants/Panneau.jsx';
import { useDonnees } from '../services/donnees.jsx';
import { pourcentage } from '../services/format.js';
import {
  Button, DataTable, EmptyState, LEVEL_LABEL, LevelBadge, NIVEAUX, StatCard,
} from '../systeme.js';

// Chaque niveau a sa hachure : le rapport reste lisible imprimé en noir et blanc.
const HACHURES = {
  urgence: 'hachure-urgence',
  inspection: 'hachure-inspection',
  surveillance: 'hachure-surveillance',
  information: 'hachure-information',
};

function Motifs() {
  return (
    <svg width="0" height="0" aria-hidden="true" focusable="false">
      <defs>
        <pattern id="hachure-urgence" width="6" height="6" patternUnits="userSpaceOnUse">
          <rect width="6" height="6" fill="var(--niveau-urgence-solide)" />
        </pattern>
        <pattern id="hachure-inspection" width="6" height="6" patternUnits="userSpaceOnUse"
          patternTransform="rotate(45)">
          <rect width="6" height="6" fill="var(--niveau-inspection-fond)" />
          <line x1="0" y1="0" x2="0" y2="6" stroke="var(--niveau-inspection-texte)"
            strokeWidth="3" />
        </pattern>
        <pattern id="hachure-surveillance" width="6" height="6" patternUnits="userSpaceOnUse"
          patternTransform="rotate(-45)">
          <rect width="6" height="6" fill="var(--niveau-surveillance-fond)" />
          <line x1="0" y1="0" x2="0" y2="6" stroke="var(--niveau-surveillance-texte)"
            strokeWidth="2" />
        </pattern>
        <pattern id="hachure-information" width="5" height="5" patternUnits="userSpaceOnUse">
          <rect width="5" height="5" fill="var(--niveau-information-fond)" />
          <circle cx="2.5" cy="2.5" r="1" fill="var(--niveau-information-texte)" />
        </pattern>
      </defs>
    </svg>
  );
}

function BarresParZone({ lignes }) {
  const total = (l) => NIVEAUX.reduce((somme, n) => somme + (l[n] || 0), 0);
  const maximum = Math.max(1, ...lignes.map(total));
  const largeur = 640;

  return (
    <div className="graphique-zones">
      <Motifs />
      <ul className="legende">
        {NIVEAUX.map((n) => (
          <li key={n}>
            <svg width="16" height="16" aria-hidden="true">
              <rect width="16" height="16" fill={`url(#${HACHURES[n]})`}
                stroke="var(--border-strong)" />
            </svg>
            {LEVEL_LABEL[n]}
          </li>
        ))}
      </ul>
      <svg viewBox={`0 0 ${largeur + 120} ${lignes.length * 34 + 10}`} className="barres"
        role="img" aria-label="Alertes par zone et par niveau">
        {lignes.map((ligne, index) => {
          let decalage = 90;
          return (
            <g key={ligne.zone} transform={`translate(0 ${index * 34 + 8})`}>
              <text x="0" y="16" className="barres-libelle">Zone {ligne.zone}</text>
              {NIVEAUX.map((niveau) => {
                const valeur = ligne[niveau] || 0;
                if (!valeur) return null;
                const large = (valeur / maximum) * largeur;
                const x = decalage;
                decalage += large;
                return (
                  <g key={niveau}>
                    <rect x={x} y="2" width={large} height="20"
                      fill={`url(#${HACHURES[niveau]})`} stroke="var(--border-strong)" />
                    <text x={x + large / 2} y="17" className="barres-valeur">{valeur}</text>
                  </g>
                );
              })}
              <text x={decalage + 10} y="16" className="barres-total">{total(ligne)}</text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

export default function Rapports() {
  const D = useDonnees();
  const r = D.rapport;

  if (!r || !r.alertes) {
    return (
      <div className="ecran">
        <h1>Rapports</h1>
        <EmptyState title="Aucune alerte sur la période" tone="ok">
          Le rapport reste utile : la surveillance a fonctionné et les équipements
          sont restés dans leur comportement habituel.
        </EmptyState>
      </div>
    );
  }

  const variation = r.alertes - (r.alertesPrecedentes || 0);

  return (
    <div className="ecran ecran-rapport">
      <h1>
        Rapports
        <span className="titre-compte">{r.periode}</span>
        <span className="filtres-fin">
          <Button variant="secondary" size="sm" onClick={() => window.print()}>
            Imprimer
          </Button>
        </span>
      </h1>

      <div className="compteurs">
        <StatCard label="Alertes de la semaine" size="lg" value={String(r.alertes)}
          delta={r.alertesPrecedentes
            ? { text: `${variation > 0 ? '+' : ''}${variation}`,
              direction: variation > 0 ? 'up' : 'down' } : undefined}
          caption={r.alertesPrecedentes ? `semaine précédente : ${r.alertesPrecedentes}` : undefined} />
        <StatCard label="Délai de prise en charge" size="lg"
          value={r.delaiMedian === null ? '—' : String(r.delaiMedian)} unit="min"
          caption={r.delaiMaximum ? `médiane · maximum ${r.delaiMaximum} min` : undefined} />
        <StatCard label="Alertes justifiées" size="lg"
          value={String(Math.round((r.justifiees / r.alertes) * 100))} unit="%"
          caption={`${r.justifiees} sur ${r.alertes}`} />
        <StatCard label="Disponibilité de la surveillance" size="lg"
          value={r.disponibilite === null ? '—' : r.disponibilite.toLocaleString('fr-FR',
            { minimumFractionDigits: 1 })}
          unit="%" caption="part du temps où les caméras ont mesuré" />
      </div>

      <div className="deux-colonnes">
        <Panneau titre="Alertes par zone et par niveau" complement={`${r.alertes} alertes`}>
          <BarresParZone lignes={r.parZone} />
        </Panneau>

        <Panneau titre="Équipements les plus exposés"
          complement="par nombre d’alertes, puis par gravité">
          <DataTable
            rowKey="equipement"
            rows={r.exposes}
            columns={[
              { key: 'equipement', label: 'Équipement', render: (l) => (
                <div>
                  <div className="cellule-forte">{l.equipement}</div>
                  <div className="cellule-douce">{D.parId[l.equipement]?.nom}</div>
                </div>
              ) },
              { key: 'alertes', label: 'Alertes', numeric: true, align: 'right', width: 90 },
              { key: 'niveau', label: 'Plus haut niveau', width: 170,
                render: (l) => <LevelBadge level={l.niveau} size="sm" /> },
              { key: 'duree', label: 'Durée cumulée', align: 'right', width: 140 },
            ]}
          />
        </Panneau>
      </div>

      {r.cameras?.length > 0 && (
        <Panneau titre="Disponibilité par caméra" complement="sur la période">
          <DataTable
            rowKey="camera"
            rows={r.cameras}
            columns={[
              { key: 'camera', label: 'Caméra', width: 150 },
              { key: 'disponibilite', label: 'Disponibilité', numeric: true, align: 'right',
                width: 150, render: (l) => pourcentage(l.disponibilite, 1) },
              { key: 'sansMesure', label: 'Temps sans mesure', align: 'right' },
            ]}
          />
        </Panneau>
      )}
    </div>
  );
}
