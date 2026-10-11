import React, { useState } from 'react';

import { ROLES } from '../services/session.js';
import { Button, Field, Select, TextInput } from '../systeme.js';

/**
 * Écran de connexion. Tant que le serveur ne gère pas les comptes, le rôle est
 * choisi ici : il détermine les actions visibles dans toute l'application.
 */
export default function Connexion({ surConnexion }) {
  const [nom, setNom] = useState('');
  const [role, setRole] = useState('securite');
  const [erreur, setErreur] = useState(null);

  const valider = (evenement) => {
    evenement.preventDefault();
    if (!nom.trim()) {
      setErreur('Indiquez votre nom pour que vos actions soient tracées.');
      return;
    }
    surConnexion(nom.trim(), role);
  };

  return (
    <div className="connexion">
      <form className="panneau connexion-panneau" onSubmit={valider}>
        <div className="menu-titre">
          <span className="menu-marque" aria-hidden="true">◈</span>
          <span>SASI</span>
        </div>
        <h1>Surveillance thermique</h1>
        <p className="note">
          Chaque alerte prise en charge est enregistrée au nom de la personne connectée.
        </p>

        <Field label="Votre nom" required error={erreur || undefined}>
          <TextInput value={nom} autoFocus onChange={(e) => { setNom(e.target.value);
            setErreur(null); }} />
        </Field>

        <Field label="Votre rôle" required
          hint="Il détermine les actions qui vous sont proposées.">
          <Select value={role} onChange={(e) => setRole(e.target.value)}>
            {Object.entries(ROLES).map(([clef, valeur]) => (
              <option key={clef} value={clef}>{valeur.libelle}</option>
            ))}
          </Select>
        </Field>

        <Button type="submit" variant="primary" size="lg">Entrer</Button>
      </form>
    </div>
  );
}
