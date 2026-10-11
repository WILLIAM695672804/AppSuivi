import React, { useState } from 'react';

import EnAttente from '../composants/EnAttente.jsx';
import Panneau from '../composants/Panneau.jsx';
import ReglageSeuils from '../composants/ReglageSeuils.jsx';
import { useDonnees, useSerie } from '../services/donnees.jsx';
import { date, duree, signe } from '../services/format.js';
import { peut } from '../services/session.js';
import {
  Button, Dialog, EmptyState, Field, LevelBadge, Select, StatCard, StatusBanner,
  TemperatureChart, Textarea, formatTemperature,
} from '../systeme.js';

// Depuis combien de temps l'échauffement manqué durait-il ? Une durée suffit :
// personne ne relève l'heure exacte d'un défaut constaté à la ronde.
const DEPUIS = [[1, 'la dernière heure'], [4, 'les 4 dernières heures'],
  [12, 'les 12 dernières heures'], [24, 'les 24 dernières heures']];

export default function FicheEquipement({ id, aller }) {
  const D = useDonnees();
  const [signalement, setSignalement] = useState(false);
  const [constat, setConstat] = useState('');
  const [heures, setHeures] = useState('4');
  const [retour, setRetour] = useState(null);
  const eq = D.parId[id];
  // Les crochets React s'appellent toujours, même quand l'équipement est inconnu.
  const alerte = D.alertes.find((a) => a.equipement === id);
  const donnees = useSerie(eq, { heures: 24, derive: alerte?.derive ?? 0,
    depuis: 4 * 3600 * 1000 });

  if (!eq) {
    return (
      <div className="ecran">
        <h1>Équipement introuvable</h1>
        <EmptyState title="Cet équipement n’existe pas" tone="neutral">
          Vérifiez son identifiant dans la liste des équipements.
        </EmptyState>
      </div>
    );
  }

  const derniere = donnees?.mesure.length ? donnees.mesure[donnees.mesure.length - 1].v : null;
  const attendue = donnees?.attendu.length ? donnees.attendu[donnees.attendu.length - 1].v : null;
  const ecart = (derniere !== null && attendue !== null) ? derniere - attendue : null;
  const passees = D.historique.filter((a) => a.equipement === id);
  const bonEtat = eq.niveau === 'normal';

  return (
    <div className="ecran">
      <button type="button" className="fil" onClick={() => aller('equipements')}>
        ‹ Équipements
      </button>

      <div className="fiche-entete">
        <LevelBadge level={eq.niveau} size="lg" />
        <div>
          <h1>{eq.nom}</h1>
          <p className="fiche-sous-titre">
            {eq.id} · Zone {eq.zone} · {D.familles[eq.famille]} · {eq.camera}
          </p>
        </div>
      </div>

      {eq.enApprentissage ? (
        <StatusBanner kind="apprentissage" title="Période d’apprentissage en cours">
          Le système observe cet équipement depuis {eq.joursApprentissage ?? 0} jours sur 28.
          Seuls les seuils fixes le protègent d’ici là.
        </StatusBanner>
      ) : (
        <StatusBanner kind="apprentissage" title="Période d’apprentissage terminée">
          La plage normale est apprise (4 semaines d’observation).
          {eq.finApprentissage && ` Terminée le ${date(eq.finApprentissage)}.`}
        </StatusBanner>
      )}

      <div className="deux-colonnes">
        <div>
          <Panneau titre={bonEtat ? 'Cet équipement va bien, et voici pourquoi' : 'État actuel'}>
            <div className="compteurs compteurs-trois">
              <StatCard label="Mesurée" size="lg" unit="°C" level={eq.niveau}
                value={derniere === null ? '—' : formatTemperature(derniere)} />
              <StatCard label="Attendue" size="lg" unit="°C"
                value={attendue === null ? '—' : formatTemperature(attendue)} />
              <StatCard label="Écart" size="lg" unit="°C"
                value={ecart === null ? '—' : formatTemperature(ecart)}
                delta={ecart === null ? undefined
                  : { text: `${signe(ecart)} °C`, direction: ecart >= 0 ? 'up' : 'down' }} />
            </div>
            <ReglageSeuils equipement={eq} mesuree={derniere} attendue={attendue} />
          </Panneau>

          <Panneau titre="24 dernières heures">
            {!donnees ? <EnAttente hauteur={300} /> : (
              <TemperatureChart
                series={[{ id: eq.id, label: eq.nom, points: donnees.mesure }]}
                expected={{ points: donnees.attendu }}
                normalRange={[eq.plageBasse, eq.plageHaute]}
                thresholds={[
                  { level: 'inspection', value: eq.seuilInspection },
                  { level: 'urgence', value: eq.seuilUrgence },
                ]}
                height={300}
              />
            )}
          </Panneau>

          <Panneau titre="Historique des alertes et des interventions">
            {passees.length === 0 ? (
              <EmptyState title="Aucune alerte enregistrée" tone="ok">
                Cet équipement n’a jamais déclenché d’alerte.
              </EmptyState>
            ) : (
              <ul className="historique">
                {passees.map((a) => (
                  <li key={a.id}>
                    <LevelBadge level={a.niveau} size="sm" />
                    <span>
                      {a.id} · {duree(a.debut, a.fin, D.maintenant)}
                      {' · '}justifiée : {a.justifiee ? 'oui' : 'non'} · {a.compteRendu}
                    </span>
                    <Button size="sm" variant="quiet"
                      onClick={() => aller('suivi')}>Revoir les 24 h</Button>
                  </li>
                ))}
              </ul>
            )}
          </Panneau>
        </div>

        <div>
          <Panneau titre="Identité">
            <dl className="proprietes">
              <dt>Identifiant</dt><dd>{eq.id}</dd>
              <dt>Zone</dt><dd>Zone {eq.zone}</dd>
              <dt>Famille</dt><dd>{D.familles[eq.famille]}</dd>
              <dt>Criticité</dt><dd>{eq.criticite} sur 3</dd>
              <dt>Caméra</dt><dd>{eq.camera}</dd>
              <dt>Mise en température</dt><dd>{eq.tempsMontee} min</dd>
            </dl>
          </Panneau>

          <Panneau titre="Plage normale et seuils">
            <dl className="proprietes">
              <dt>Plage normale</dt><dd>{eq.plageBasse} à {eq.plageHaute} °C</dd>
              <dt>Seuil d’inspection</dt><dd>{eq.seuilInspection} °C</dd>
              <dt>Seuil d’urgence</dt><dd>{eq.seuilUrgence} °C</dd>
            </dl>
            {eq.remarque && <p className="note">{eq.remarque}</p>}
          </Panneau>

          <Panneau titre="Actions">
            <div className="boutons-colonne">
              <Button variant="primary" onClick={() => aller('suivi')}>
                Ouvrir le suivi des températures
              </Button>
              {peut(D.session, 'maintenance') && (
                <Button variant="secondary">Mettre en maintenance</Button>
              )}
              <Button variant="quiet" onClick={() => setSignalement(true)}>
                Signaler un échauffement non détecté
              </Button>
            </div>
            {retour && <p className="note">{retour}</p>}
          </Panneau>
        </div>
      </div>

      <Dialog
        open={signalement}
        title="Signaler un échauffement non détecté"
        confirmLabel="Signaler"
        cancelLabel="Annuler"
        confirmDisabled={!constat}
        onCancel={() => setSignalement(false)}
        onConfirm={() => {
          const fin = Date.now() / 1000;
          D.signalerManque(eq.id, {
            par: D.session.nom, motif: constat,
            debut: fin - Number(heures) * 3600, fin,
          })
            .then(() => setRetour('Signalement enregistré : il sera pris en compte au '
              + 'prochain entraînement du modèle.'))
            .catch((souci) => setRetour(`Signalement impossible : ${souci.message}`));
          setSignalement(false);
          setConstat('');
        }}
      >
        <p>
          Vous avez constaté une chauffe anormale que le système n’a pas signalée.
          Le modèle apprendra à ne plus considérer cette période comme normale.
        </p>
        <Field label="Ce qui a été constaté" required>
          <Textarea rows={3} value={constat}
            onChange={(e) => setConstat(e.target.value)} />
        </Field>
        <Field label="Sur quelle période ?" required>
          <Select value={heures} onChange={(e) => setHeures(e.target.value)}>
            {DEPUIS.map(([valeur, libelle]) => (
              <option key={valeur} value={valeur}>{libelle}</option>
            ))}
          </Select>
        </Field>
      </Dialog>
    </div>
  );
}
