import React from 'react';
import { Button, EmptyState } from '../systeme.js';

export default function NonTrouve({ aller }) {
  return (
    <div className="ecran">
      <h1>Écran introuvable</h1>
      <EmptyState
        title="Cette adresse ne correspond à aucun écran"
        tone="neutral"
        action={<Button variant="secondary" onClick={() => aller('tableau')}>
          Revenir au tableau de bord
        </Button>}
      >
        Vérifiez le lien, ou utilisez le menu à gauche.
      </EmptyState>
    </div>
  );
}
