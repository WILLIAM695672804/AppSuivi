import React from 'react';
import { TextInput } from '../systeme.js';

export default function ChampRecherche({ valeur, surChangement, libelle = 'Rechercher' }) {
  return (
    <label className="recherche">
      <span className="recherche-libelle">{libelle}</span>
      <TextInput
        type="search"
        value={valeur}
        placeholder="Nom, identifiant, zone…"
        onChange={(evenement) => surChangement(evenement.target.value)}
      />
    </label>
  );
}
