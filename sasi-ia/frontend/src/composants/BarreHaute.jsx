import React from 'react';

import { libelleRole } from '../services/session.js';
import { Button } from '../systeme.js';

export default function BarreHaute({
  nomSite, mode, liaison, theme, session, basculerTheme, seDeconnecter,
}) {
  const etat = mode === 'exemple'
    ? 'données d’exemple'
    : liaison ? 'Mise à jour en direct' : 'Liaison interrompue';
  return (
    <header className="barre">
      <span className="barre-site">{nomSite} · {etat}</span>
      <div className="barre-actions">
        <Button variant="quiet" size="sm" onClick={basculerTheme}>
          {theme === 'dark' ? 'Thème clair' : 'Thème sombre'}
        </Button>
        <span className="barre-utilisateur">
          {session?.nom} · {libelleRole(session)}
        </span>
        <Button variant="quiet" size="sm" onClick={seDeconnecter}>Se déconnecter</Button>
      </div>
    </header>
  );
}
