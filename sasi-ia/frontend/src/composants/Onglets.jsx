import React from 'react';

/** Onglets d'un écran (administration). Utilisables au clavier. */
export default function Onglets({ onglets, actif, surChangement }) {
  return (
    <div className="onglets" role="tablist">
      {onglets.map(({ clef, libelle }) => (
        <button
          key={clef}
          type="button"
          role="tab"
          aria-selected={actif === clef}
          className={`onglet${actif === clef ? ' actif' : ''}`}
          onClick={() => surChangement(clef)}
        >
          {libelle}
        </button>
      ))}
    </div>
  );
}
