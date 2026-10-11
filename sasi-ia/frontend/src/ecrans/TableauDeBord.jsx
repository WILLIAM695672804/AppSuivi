import React from 'react';

import Panneau from '../composants/Panneau.jsx';
import { useDonnees } from '../services/donnees.jsx';
import { depuis } from '../services/format.js';
import {
  AlertCard, EmptyState, LevelBadge, NIVEAUX, StatCard, StatusBanner, LEVEL_LABEL,
} from '../systeme.js';

export default function TableauDeBord({ aller }) {
  const D = useDonnees();
  const compte = Object.fromEntries(
    NIVEAUX.map((n) => [n, D.equipements.filter((e) => e.niveau === n).length]));
  const normaux = D.equipements.filter((e) => e.niveau === 'normal').length;
  const plusHaut = NIVEAUX.find((n) => compte[n] > 0);

  return (
    <div className="ecran">
      {D.alerteTechnique && (
        <StatusBanner
          kind="technique"
          title="Caméra muette"
          actionLabel="Voir la caméra"
          onAction={() => aller('administration')}
        >
          {D.alerteTechnique.raison}
        </StatusBanner>
      )}

      <div className="etat-site">
        <p className="etat-titre">
          {plusHaut === 'urgence' ? 'Une urgence en cours'
            : plusHaut ? 'Des alertes en cours' : 'Tout va bien'}
        </p>
        <p className="etat-detail">
          {normaux} équipements sur {D.equipements.length} sont normaux
          {' · '}{D.alertes.length} alertes en cours
        </p>
      </div>

      <div className="compteurs">
        {NIVEAUX.map((niveau) => (
          <StatCard
            key={niveau}
            size="xl"
            level={niveau}
            plain={compte[niveau] === 0}
            label={LEVEL_LABEL[niveau]}
            value={String(compte[niveau])}
            caption={compte[niveau] ? 'équipements concernés' : 'aucun équipement'}
          />
        ))}
      </div>

      <div className="deux-colonnes">
        <Panneau titre="Plan du site">
          {Object.entries(D.zones).map(([numero, nom]) => (
            <div className="zone" key={numero}>
              <h3>Zone {numero} — {nom}</h3>
              <div className="zone-equipements">
                {D.equipements.filter((e) => String(e.zone) === String(numero)).map((e) => (
                  <button
                    type="button"
                    key={e.id}
                    className={`tuile niveau-${e.niveau}`}
                    onClick={() => aller('equipement', e.id)}
                  >
                    <LevelBadge level={e.niveau} size="sm" iconOnly />
                    <span className="tuile-nom">{e.nom}</span>
                    <span className="tuile-id">{e.id}</span>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </Panneau>

        <Panneau titre="Alertes en cours">
          {D.alertes.length === 0 ? (
            <EmptyState title="Aucune alerte en cours" tone="ok">
              Tous les équipements sont dans leur comportement habituel.
            </EmptyState>
          ) : D.alertes.map((a) => (
            <AlertCard
              key={a.id}
              level={a.niveau}
              state={a.etat}
              equipment={`${a.equipement} · ${D.parId[a.equipement]?.nom ?? ''}`}
              zone={`Zone ${D.parId[a.equipement]?.zone ?? '—'}`}
              since={depuis(a.debut, D.maintenant)}
              reason={a.raison}
              measured={a.tMesuree}
              expected={a.tAttendue}
              assignee={a.assignee}
              overdue={a.relance}
              density="compact"
              onOpen={() => aller('alerte', a.id)}
            />
          ))}
        </Panneau>
      </div>
    </div>
  );
}
