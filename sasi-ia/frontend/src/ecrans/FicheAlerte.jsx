import React, { useState } from 'react';

import EnAttente from '../composants/EnAttente.jsx';
import Panneau from '../composants/Panneau.jsx';
import { useDonnees, useSerie } from '../services/donnees.jsx';
import { depuis, heure, signe } from '../services/format.js';
import { peut } from '../services/session.js';
import {
  Button, Dialog, Field, LEVEL_LABEL, LevelBadge, STATE_LABEL, Select, StatCard,
  TemperatureChart, Textarea, formatTemperature,
} from '../systeme.js';

// Les types d'événements viennent du moteur d'alertes ; on les écrit en clair.
const LIBELLES_EVENEMENT = {
  creation: 'Alerte ouverte',
  montee_de_niveau: 'Montée de niveau',
  acquittement: 'Prise en charge',
  assignation: 'Assignation',
  cloture: 'Clôture',
  escalade: 'Relance',
};

/** Couleur de la jauge : les paliers qui commandent les niveaux d'alerte. */
function niveauDuRisque(pourcentage) {
  if (pourcentage >= 90) return 'urgence';
  if (pourcentage >= 75) return 'inspection';
  if (pourcentage >= 50) return 'surveillance';
  if (pourcentage >= 25) return 'information';
  return 'normal';
}

export default function FicheAlerte({ id, aller }) {
  const D = useDonnees();
  const [dialogue, setDialogue] = useState(false);
  const [constat, setConstat] = useState('');
  const [justifiee, setJustifiee] = useState('');

  const alerte = [...D.alertes, ...D.historique].find((a) => a.id === id) || D.alertes[0];
  // Les crochets React s'appellent toujours, même quand l'alerte est introuvable.
  const eq = alerte
    ? D.parId[alerte.equipement] || { id: alerte.equipement, nom: alerte.equipement }
    : null;
  const donnees = useSerie(eq, { heures: 24, derive: alerte?.derive, depuis: 4 * 3600 * 1000 });

  if (!alerte) {
    return <div className="ecran"><h1>Alerte introuvable</h1></div>;
  }
  const ecart = (alerte.tMesuree ?? 0) - (alerte.tAttendue ?? 0);

  return (
    <div className="ecran">
      <button type="button" className="fil" onClick={() => aller('alertes')}>‹ Alertes</button>

      <div className="fiche-entete">
        <LevelBadge level={alerte.niveau} size="lg" tone="solid" />
        <div>
          <h1>{eq.nom}</h1>
          <p className="fiche-sous-titre">
            {alerte.id} · {eq.id} · Zone {eq.zone} · {D.familles[eq.famille] || ''}
            {' · '}{STATE_LABEL[alerte.etat]} · {depuis(alerte.debut, D.maintenant)}
          </p>
        </div>
      </div>

      <div className="deux-colonnes">
        <div>
          <Panneau titre="Raison">
            <div className="compteurs compteurs-trois">
              <StatCard label="Température mesurée" size="lg" unit="°C"
                value={formatTemperature(alerte.tMesuree)} />
              <StatCard label="Température attendue" size="lg" unit="°C"
                value={formatTemperature(alerte.tAttendue)} />
              <StatCard label="Écart" size="lg" unit="°C"
                value={formatTemperature(ecart)}
                delta={{ text: `${signe(ecart)} °C`, direction: ecart >= 0 ? 'up' : 'down' }} />
            </div>
            <p className="raison">{alerte.raison}</p>
            {alerte.facteurs?.length > 0 && (
              <>
                <h3>Facteurs d’influence</h3>
                <ul className="facteurs">
                  {alerte.facteurs.map((f, i) => <li key={i}>{f}</li>)}
                </ul>
              </>
            )}
            <div className="action-conseillee">
              <h3>Action conseillée</h3>
              <p>{alerte.action}</p>
            </div>
          </Panneau>

          <Panneau titre="24 dernières heures">
            {!donnees ? <EnAttente hauteur={320} /> : (
              <TemperatureChart
                series={[{ id: eq.id, label: eq.nom, points: donnees.mesure }]}
                expected={{ points: donnees.attendu }}
                normalRange={[eq.plageBasse, eq.plageHaute]}
                thresholds={[
                  { level: 'inspection', value: eq.seuilInspection },
                  { level: 'urgence', value: eq.seuilUrgence },
                ]}
                periods={[{ from: alerte.debut, to: alerte.fin || D.maintenant,
                  level: alerte.niveau }]}
                height={320}
                caption="Mesure en trait plein, température attendue en pointillé."
              />
            )}
          </Panneau>
        </div>

        <div>
          <Panneau titre="Actions">
            <div className="boutons-colonne">
              {alerte.etat === 'ouverte' && peut(D.session, 'prendre_en_charge') && (
                <Button variant="primary" size="lg"
                  onClick={() => D.action(alerte.equipement, 'acquitter',
                    { par: D.session.nom })}>
                  Prendre en charge
                </Button>
              )}
              {peut(D.session, 'assigner') && (
                <Button variant="secondary"
                  onClick={() => D.action(alerte.equipement, 'assigner',
                    { par: D.session.nom, a_qui: 'technicien' })}>
                  Assigner à un technicien
                </Button>
              )}
              {peut(D.session, 'cloturer') && (
                <Button variant="secondary" onClick={() => setDialogue(true)}>Clôturer</Button>
              )}
              <Button variant="quiet" onClick={() => aller('equipement', eq.id)}>
                Voir l’équipement
              </Button>
            </div>
          </Panneau>

          {alerte.risque !== null && alerte.risque !== undefined && (
            <Panneau titre="Prévision">
              <div className="jauge-risque">
                <div className="jauge-piste">
                  <div className={`jauge-valeur jauge-${niveauDuRisque(alerte.risque)}`}
                    style={{ width: `${alerte.risque}%` }} />
                </div>
                <strong className="jauge-chiffre">{alerte.risque} %</strong>
              </div>
              <p className="precision">
                {alerte.risqueRaison
                  || `Probabilité d’atteindre ${alerte.risqueSeuil} °C dans les `
                     + `${Math.round(alerte.risqueHorizon)} prochaines minutes.`}
              </p>
              {alerte.risqueMinutes != null && (
                <p className="precision">
                  Au rythme actuel, ce seuil serait atteint dans
                  {' '}{Math.round(alerte.risqueMinutes)} minutes.
                </p>
              )}
            </Panneau>
          )}

          <Panneau titre="Historique de l’alerte">
            <ol className="historique">
              {(alerte.evenements || []).map((e, i) => (
                <li key={i}>
                  <span className="historique-heure">{heure(e.t)}</span>
                  <span>
                    {LIBELLES_EVENEMENT[e.type] || e.type}
                    {e.niveau && ` — ${LEVEL_LABEL[e.niveau]}`}
                    {e.par && ` · ${e.par === 'systeme' ? 'système' : e.par}`}
                    {e.a && ` → ${e.a}`}
                  </span>
                </li>
              ))}
            </ol>
          </Panneau>
        </div>
      </div>

      <Dialog
        open={dialogue}
        title="Clôturer l’alerte"
        confirmLabel="Clôturer"
        cancelLabel="Annuler"
        confirmDisabled={!constat || !justifiee}
        onCancel={() => setDialogue(false)}
        onConfirm={() => {
          D.action(alerte.equipement, 'cloturer', {
            par: D.session.nom, constat, justifiee: justifiee === 'oui',
          });
          setDialogue(false);
        }}
      >
        <Field label="Compte rendu de l’intervention" required>
          <Textarea rows={3} value={constat} onChange={(e) => setConstat(e.target.value)} />
        </Field>
        <Field label="L’alerte était-elle justifiée ?" required>
          <Select value={justifiee} onChange={(e) => setJustifiee(e.target.value)}>
            <option value="">Choisir</option>
            <option value="oui">Oui</option>
            <option value="non">Non</option>
          </Select>
        </Field>
        <p className="note">
          La clôture est impossible sans compte rendu ni réponse à cette question.
        </p>
      </Dialog>
    </div>
  );
}
