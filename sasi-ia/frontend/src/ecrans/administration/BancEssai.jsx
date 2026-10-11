import React, { useEffect, useState } from 'react';

import EnAttente from '../../composants/EnAttente.jsx';
import Panneau from '../../composants/Panneau.jsx';
import { useDonnees } from '../../services/donnees.jsx';
import {
  Button, EmptyState, Field, LEVEL_LABEL, LevelBadge, Select, StatCard, StatusBanner,
  TemperatureChart,
} from '../../systeme.js';

const VITESSES = [[0.5, 'lente · 0,5 °C/min'], [1, 'modérée · 1 °C/min'],
  [2, 'franche · 2 °C/min'], [5, 'rapide · 5 °C/min']];
const DUREES = [[20, '20 minutes'], [40, '40 minutes'], [90, '1 h 30'], [180, '3 heures']];

/** Banc d'essai : soumettre une situation à l'IA et regarder ce qu'elle en dit. */
export default function BancEssai() {
  const D = useDonnees();
  const [equipement, setEquipement] = useState(D.equipements[0]?.id || '');
  const [situations, setSituations] = useState([]);
  const [situation, setSituation] = useState('montee');
  const [vitesse, setVitesse] = useState('2');
  const [duree, setDuree] = useState('40');
  const [resultat, setResultat] = useState(null);
  const [enCours, setEnCours] = useState(false);
  const [erreur, setErreur] = useState(null);

  useEffect(() => {
    D.situations().then(setSituations).catch(() => setSituations([]));
  }, [D]);

  const lancer = () => {
    setEnCours(true);
    setErreur(null);
    D.essai({ equipement, situation, vitesse: Number(vitesse), duree: Number(duree) })
      .then(setResultat)
      .catch((souci) => setErreur(souci.message))
      .finally(() => setEnCours(false));
  };

  // Les instants du graphique partent de maintenant : l'essai n'a pas de date,
  // mais l'échelle de temps doit rester lisible.
  const origine = resultat ? Date.now() : 0;
  const courbes = resultat && [
    { id: 'mesuree', label: 'Température soumise',
      points: resultat.trace.map((p) => ({ t: origine + p.minute * 60000, v: p.mesuree })) },
  ];
  const attendue = resultat && {
    points: resultat.trace.map((p) => ({ t: origine + p.minute * 60000, v: p.attendue })),
  };
  const risqueMaximal = resultat
    ? Math.max(...resultat.trace.map((p) => p.risque)) : 0;
  const risqueFinal = resultat ? resultat.trace[resultat.trace.length - 1].risque : 0;

  return (
    <div className="onglet-contenu">
      <Panneau titre="Éprouver l’IA sur une situation">
        <p className="precision">
          On fabrique une situation de toutes pièces et on la soumet au modèle en
          service, minute par minute. Rien n’est publié, rien n’est enregistré :
          la surveillance en cours n’est pas touchée.
        </p>
        <div className="formulaire-ligne">
          <Field label="Équipement">
            <Select value={equipement} onChange={(e) => setEquipement(e.target.value)}>
              {D.equipements.map((eq) => (
                <option key={eq.id} value={eq.id}>{eq.nom} · {eq.id}</option>
              ))}
            </Select>
          </Field>
          <Field label="Situation">
            <Select value={situation} onChange={(e) => setSituation(e.target.value)}>
              {situations.map((s) => (
                <option key={s.clef} value={s.clef}>{s.libelle}</option>
              ))}
            </Select>
          </Field>
          <Field label="Vitesse de chauffe">
            <Select value={vitesse} onChange={(e) => setVitesse(e.target.value)}>
              {VITESSES.map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>{libelle}</option>
              ))}
            </Select>
          </Field>
          <Field label="Durée">
            <Select value={duree} onChange={(e) => setDuree(e.target.value)}>
              {DUREES.map(([valeur, libelle]) => (
                <option key={valeur} value={valeur}>{libelle}</option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="boutons-ligne">
          <Button variant="primary" onClick={lancer} disabled={enCours || !equipement}>
            {enCours ? 'Essai en cours…' : 'Lancer l’essai'}
          </Button>
        </div>
      </Panneau>

      {erreur && <StatusBanner kind="technique" title="Essai impossible">{erreur}</StatusBanner>}

      {enCours && !resultat && <EnAttente hauteur={280} libelle="Essai en cours…" />}

      {resultat && (
        <>
          <Panneau titre={`${resultat.nom} — ${resultat.libelle}`}>
            <div className="compteurs">
              <StatCard label="Risque le plus haut" value={risqueMaximal} unit="%" />
              <StatCard label="Risque à la fin" value={risqueFinal} unit="%" />
              <StatCard label="Changements de niveau"
                value={resultat.changements.length} />
              <StatCard label="Écart habituel appris"
                value={resultat.calibrage
                  ? resultat.calibrage.dispersion.toFixed(1) : '—'} unit="°C" />
            </div>
            <p className="precision">
              Plage normale {resultat.plage[0]}–{resultat.plage[1]} °C ·
              {' '}inspection {resultat.seuil_inspection} °C ·
              {' '}urgence {resultat.seuil_urgence} °C ·
              {' '}criticité {resultat.criticite}
              {!resultat.calibrage && ' · aucun calibrage appris : l’essai est plus sensible '
                + 'qu’en service'}
            </p>
          </Panneau>

          <Panneau titre="Ce que l’IA a vu">
            <TemperatureChart
              series={courbes}
              expected={attendue}
              normalRange={resultat.plage}
              thresholds={[
                { level: 'inspection', value: resultat.seuil_inspection },
                { level: 'urgence', value: resultat.seuil_urgence },
              ]}
              height={260}
            />
          </Panneau>

          <Panneau titre="Ce que l’IA a dit">
            {resultat.changements.length === 0 ? (
              <EmptyState title="Aucune alerte" tone="neutral">
                L’IA n’a rien trouvé d’anormal dans cette situation.
              </EmptyState>
            ) : (
              <ol className="historique">
                {resultat.changements.map((changement, rang) => (
                  <li key={rang}>
                    <span className="historique-heure">
                      {changement.minute.toFixed(0)} min
                    </span>
                    <span>
                      <LevelBadge level={changement.niveau} />
                      {' '}{LEVEL_LABEL[changement.niveau] || changement.niveau}
                      <br />
                      <span className="precision">{changement.raison}</span>
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </Panneau>

          <Panneau titre="Le détail, minute par minute">
            <div className="tableau-compact">
              <table>
                <thead>
                  <tr>
                    <th>Minute</th><th>Mesurée</th><th>Attendue</th>
                    <th>Écart</th><th>Risque</th><th>Niveau</th>
                  </tr>
                </thead>
                <tbody>
                  {resultat.trace
                    .filter((_, rang) => rang % 2 === 0)
                    .map((point) => (
                      <tr key={point.minute}>
                        <td>{point.minute.toFixed(1)}</td>
                        <td>{point.mesuree.toFixed(1)} °C</td>
                        <td>{point.attendue.toFixed(1)} °C</td>
                        <td>{point.ecart > 0 ? '+' : ''}{point.ecart.toFixed(1)} °C</td>
                        <td>{point.risque} %</td>
                        <td>{LEVEL_LABEL[point.niveau] || point.niveau}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </Panneau>
        </>
      )}
    </div>
  );
}
