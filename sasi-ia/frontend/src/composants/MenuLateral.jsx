import React from 'react';

import { peut } from '../services/session.js';

const ENTREES = [
  ['tableau', 'Tableau de bord', null],
  ['suivi', 'Suivi des températures', null],
  ['alertes', 'Alertes', null],
  ['equipements', 'Équipements', null],
  ['rapports', 'Rapports', 'rapports'],
  ['administration', 'Administration', 'administrer'],
];

/** Menu principal. Les entrées interdites au rôle ne sont pas affichées. */
export default function MenuLateral({ ecran, aller, nbAlertes, session }) {
  const entrees = ENTREES.filter(([, , droit]) => !droit || peut(session, droit));
  return (
    <nav className="menu" aria-label="Navigation principale">
      <div className="menu-titre">
        <span className="menu-marque" aria-hidden="true">◈</span>
        <span>SASI</span>
      </div>
      <ul>
        {entrees.map(([clef, libelle]) => (
          <li key={clef}>
            <button
              type="button"
              className={`menu-entree${ecran === clef ? ' active' : ''}`}
              aria-current={ecran === clef ? 'page' : undefined}
              onClick={() => aller(clef)}
            >
              <span>{libelle}</span>
              {clef === 'alertes' && nbAlertes > 0 && (
                <span className="menu-compteur">{nbAlertes}</span>
              )}
            </button>
          </li>
        ))}
      </ul>
      <p className="menu-pied">Version 1 — température</p>
    </nav>
  );
}
