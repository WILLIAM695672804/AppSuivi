import React, { useState } from 'react';

import Onglets from '../../composants/Onglets.jsx';
import Cameras from './Cameras.jsx';
import Equipements from './Equipements.jsx';
import BancEssai from './BancEssai.jsx';
import Modele from './Modele.jsx';
import Raisonnement from './Raisonnement.jsx';
import Utilisateurs from './Utilisateurs.jsx';

const ONGLETS = [
  { clef: 'cameras', libelle: 'Caméras et zones', composant: Cameras },
  { clef: 'equipements', libelle: 'Équipements', composant: Equipements },
  { clef: 'utilisateurs', libelle: 'Utilisateurs', composant: Utilisateurs },
  { clef: 'modele', libelle: 'Modèle', composant: Modele },
  { clef: 'raisonnement', libelle: 'Raisonnement', composant: Raisonnement },
  { clef: 'essai', libelle: 'Banc d’essai', composant: BancEssai },
];

export default function Administration({ id }) {
  const depart = ONGLETS.some((o) => o.clef === id) ? id : 'cameras';
  const [onglet, setOnglet] = useState(depart);
  const Contenu = (ONGLETS.find((o) => o.clef === onglet) || ONGLETS[0]).composant;

  return (
    <div className="ecran">
      <h1>Administration</h1>
      <Onglets onglets={ONGLETS} actif={onglet} surChangement={setOnglet} />
      <Contenu />
    </div>
  );
}
