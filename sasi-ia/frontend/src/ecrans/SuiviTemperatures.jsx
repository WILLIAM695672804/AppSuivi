import React, { useState } from 'react';

import EnAttente from '../composants/EnAttente.jsx';
import Panneau from '../composants/Panneau.jsx';
import { useDonnees, useSerie, useSeries } from '../services/donnees.jsx';
import { Chip, TemperatureChart } from '../systeme.js';

const PERIODES = [[2, '2 h'], [24, '24 h'], [168, '7 jours'], [720, '30 jours']];

export default function SuiviTemperatures() {
  const D = useDonnees();
  const [zone, setZone] = useState(Object.keys(D.zones)[0]);
  const [heures, setHeures] = useState(24);
  const [choisi, setChoisi] = useState(null);

  const liste = D.equipements.filter((e) => String(e.zone) === String(zone));
  const seul = liste.length === 1 || Boolean(choisi);
  const cible = choisi ? D.parId[choisi] : liste[0];

  const brutes = useSeries(seul ? [] : liste.slice(0, 5), { heures });
  const donnees = useSerie(cible, { heures });

  // Libellé court : les noms complets débordent du graphique en comparaison.
  const series = (brutes || []).map((s, i) => ({
    id: liste[i].id, label: liste[i].id, points: s.mesure,
  }));

  return (
    <div className="ecran">
      <h1>Suivi des températures</h1>

      <div className="filtres">
        <span className="filtres-libelle">Zone</span>
        {Object.entries(D.zones).map(([numero, nom]) => (
          <Chip
            key={numero}
            selected={String(zone) === numero}
            title={nom}
            label={`Zone ${numero}`}
            onClick={() => { setZone(numero); setChoisi(null); }}
          />
        ))}
        <span className="filtres-libelle">Période</span>
        {PERIODES.map(([valeur, libelle]) => (
          <Chip key={valeur} selected={heures === valeur} label={libelle}
            onClick={() => setHeures(valeur)} />
        ))}
      </div>

      <Panneau
        className="panneau-courbe"
        titre={seul ? `${cible?.nom} · ${cible?.id}` : `Zone ${zone} — ${D.zones[zone]}`}
      >
        {(seul ? !donnees : !brutes) ? <EnAttente hauteur={420} /> : (
          <TemperatureChart
            series={seul
              ? [{ id: cible.id, label: cible.nom, points: donnees.mesure }]
              : series}
            expected={seul ? { points: donnees.attendu } : undefined}
            normalRange={seul ? [cible.plageBasse, cible.plageHaute] : undefined}
            thresholds={seul ? [
              { level: 'inspection', value: cible.seuilInspection },
              { level: 'urgence', value: cible.seuilUrgence },
            ] : undefined}
            height={420}
            selectedId={choisi}
            onSelect={(id) => setChoisi(id === choisi ? null : id)}
            caption={seul
              ? 'Température mesurée en trait plein, température attendue en pointillé.'
              : 'Cliquez une courbe pour n’afficher qu’un équipement.'}
            emptyMessage="Aucune mesure sur cette période. Choisissez une autre période."
          />
        )}
      </Panneau>

      <div className="filtres">
        <span className="filtres-libelle">Équipements</span>
        {liste.map((e) => (
          <Chip key={e.id} selected={choisi === e.id} label={e.nom}
            onClick={() => setChoisi(choisi === e.id ? null : e.id)} />
        ))}
      </div>
    </div>
  );
}
