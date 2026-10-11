import React from 'react';

/** Bloc d'attente affiché à l'emplacement du contenu, jamais un écran vide. */
export default function EnAttente({ hauteur = 240, libelle = 'Chargement…' }) {
  return (
    <div className="en-attente" style={{ height: hauteur }} role="status">
      {libelle}
    </div>
  );
}
