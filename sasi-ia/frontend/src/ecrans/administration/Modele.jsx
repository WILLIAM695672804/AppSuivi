import React, { useCallback, useEffect, useRef, useState } from 'react';

import EnAttente from '../../composants/EnAttente.jsx';
import Panneau from '../../composants/Panneau.jsx';
import { useDonnees } from '../../services/donnees.jsx';
import { peut } from '../../services/session.js';
import {
  Button, DataTable, Dialog, EmptyState, StatCard, StatusBanner,
} from '../../systeme.js';

const PERIODE_SUIVI_MS = 2000;      // pendant un entraînement, on demande l'avancement

const GENRES_RETOUR = {
  fausse_alerte: 'Fausse alerte',
  manque: 'Échauffement manqué',
  confirme: 'Alerte confirmée',
};

const NOMS_ENTREES = {
  charge_pct: 'la charge',
  charge_moy_30min: 'la charge des 30 dernières minutes',
  etat_marche: 'l’état de marche',
  t_ambiante: 'la chaleur ambiante',
  minutes_depuis_demarrage: 'le temps écoulé depuis le démarrage',
  minutes_depuis_arret: 'le temps écoulé depuis l’arrêt',
  fraction_chauffe: 'la montée en température en cours',
  fraction_refroidissement: 'le refroidissement en cours',
  heure: 'l’heure de la journée',
  jour_semaine: 'le jour de la semaine',
  plage_basse: 'le bas de la plage normale',
  plage_haute: 'le haut de la plage normale',
};

const dateEtHeure = (texte) => (texte
  ? new Date(texte).toLocaleString('fr-FR',
    { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  : '—');

const duree = (secondes) => (secondes == null ? '—'
  : secondes >= 3600 ? `${Math.floor(secondes / 3600)} h ${Math.round((secondes % 3600) / 60)}`
    : `${Math.round(secondes / 60)} min`);

/** Administration du modèle : ce qu'il vaut, le réentraîner, revenir en arrière. */
export default function Modele() {
  const D = useDonnees();
  const [fiche, setFiche] = useState(null);
  const [travail, setTravail] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [confirmation, setConfirmation] = useState(null);   // version à mettre en service
  const minuteur = useRef(null);

  const administre = peut(D.session, 'administrer');

  const charger = useCallback(() => D.modele()
    .then((resultat) => {
      setFiche(resultat);
      if (resultat.travail && resultat.travail.id) setTravail(resultat.travail);
      return resultat;
    })
    .catch((souci) => setErreur(souci.message)), [D]);

  useEffect(() => { charger(); }, [charger]);

  // Pendant un entraînement, on demande l'avancement régulièrement ; dès qu'il
  // est fini, on relit la fiche pour voir la nouvelle version.
  useEffect(() => {
    if (!travail || travail.etat !== 'en cours') return undefined;
    minuteur.current = setInterval(() => {
      D.travail(travail.id)
        .then((suite) => {
          setTravail(suite);
          if (suite && suite.etat !== 'en cours') charger();
        })
        .catch(() => {});
    }, PERIODE_SUIVI_MS);
    return () => clearInterval(minuteur.current);
  }, [travail, D, charger]);

  const lancer = () => {
    setErreur(null);
    D.entrainer(D.session.nom)
      .then(setTravail)
      .catch((souci) => setErreur(souci.message));
  };

  const mettreEnService = (version) => {
    setConfirmation(null);
    setErreur(null);
    D.mettreEnService(version, D.session.nom)
      .then(charger)
      .catch((souci) => setErreur(souci.message));
  };

  if (!fiche) return <EnAttente hauteur={320} libelle="Lecture du modèle…" />;

  const service = fiche.en_service;
  const erreurs = Object.entries(service?.erreurs || {}).sort();
  const pireErreur = Math.max(...erreurs.map(([, valeur]) => valeur), 0.01);
  const evaluation = service?.evaluation;
  const enCours = travail && travail.etat === 'en cours';

  const colonnes = [
    { key: 'version', label: 'Version', width: 90, render: (l) => (
      <span className="version-nom">{l.version}</span>
    ) },
    { key: 'entraine_le', label: 'Entraînée le', width: 150,
      render: (l) => dateEtHeure(l.entraine_le) },
    { key: 'periode', label: 'Apprise sur', width: 190, render: (l) => l.periode || '—' },
    { key: 'erreur_moyenne', label: 'Erreur', width: 90,
      render: (l) => (l.erreur_moyenne ? `${l.erreur_moyenne.toFixed(2)} °C` : '—') },
    { key: 'evaluation', label: 'Détection', width: 150, render: (l) => (l.evaluation
      ? `${l.evaluation.pannes_detectees}/${l.evaluation.pannes} pannes · `
        + `${l.evaluation.fausses_alertes} fausses`
      : 'non évaluée') },
    { key: 'etat', label: '', width: 170, render: (l) => (l.en_service
      ? <span className="version-en-service">● en service</span>
      : administre && (
        <Button size="sm" variant="secondary" onClick={() => setConfirmation(l)}>
          Mettre en service
        </Button>
      )) },
  ];

  return (
    <div className="onglet-contenu">
      {erreur && (
        <StatusBanner kind="technique" title="Action impossible">{erreur}</StatusBanner>
      )}

      <Panneau titre="Modèle en service">
        {!service ? (
          <EmptyState title="Aucun modèle entraîné" tone="neutral">
            Lancez un premier entraînement pour que la surveillance devienne possible.
          </EmptyState>
        ) : (
          <>
            <div className="compteurs">
              <StatCard label="Version" value={service.version} />
              <StatCard label="Entraînée le" value={dateEtHeure(service.entraine_le)} />
              <StatCard label="Erreur moyenne"
                value={service.erreur_moyenne ? service.erreur_moyenne.toFixed(2) : '—'}
                unit="°C" />
              <StatCard label="Mesures apprises"
                value={service.mesures ? service.mesures.toLocaleString('fr-FR') : '—'} />
            </div>
            {service.periode && (
              <p className="precision">Période d’apprentissage : {service.periode}.</p>
            )}
          </>
        )}

        {administre && (
          <div className="boutons-ligne">
            <Button variant="primary" onClick={lancer} disabled={enCours}>
              {enCours ? 'Entraînement en cours…' : 'Réentraîner le modèle'}
            </Button>
            <span className="precision">
              L’entraînement dure quelques minutes. La surveillance continue pendant ce
              temps, et la nouvelle version n’entre en service que si vous le décidez.
            </span>
          </div>
        )}
      </Panneau>

      {travail && (
        <Panneau titre={enCours ? 'Entraînement en cours' : `Entraînement ${travail.id}`}>
          <div className="progression" role="progressbar" aria-valuenow={travail.progression}
            aria-valuemin={0} aria-valuemax={100}>
            <div className="progression-barre" style={{ width: `${travail.progression}%` }} />
          </div>
          <p className="precision">
            {travail.progression} % · {travail.etape_libelle}
            {travail.duree_s ? ` · ${travail.duree_s} s écoulées` : ''}
            {travail.etat === 'echec' && ' · échec'}
          </p>
          <ol className="historique">
            {travail.journal.map((ligne, rang) => (
              <li key={rang}>
                <span className="historique-heure">
                  {new Date(ligne.instant).toLocaleTimeString('fr-FR',
                    { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                </span>
                <span>{ligne.detail}</span>
              </li>
            ))}
          </ol>
        </Panneau>
      )}

      {service && erreurs.length > 0 && (
        <Panneau titre="Erreur de prédiction par famille">
          <p className="precision">
            Écart moyen entre la température prédite et la température mesurée, en
            fonctionnement normal. Plus il est faible, plus une chauffe anormale ressort.
          </p>
          <ul className="barres">
            {erreurs.map(([famille, valeur]) => (
              <li key={famille}>
                <span className="barres-libelle">{D.familles[famille] || famille}</span>
                <span className="barres-piste">
                  <span className="barres-valeur"
                    style={{ width: `${Math.round((valeur / pireErreur) * 100)}%` }} />
                </span>
                <span className="barres-chiffre">{valeur.toFixed(2)} °C</span>
              </li>
            ))}
          </ul>
        </Panneau>
      )}

      {evaluation && (
        <Panneau titre="Dernière évaluation">
          <div className="compteurs">
            <StatCard label="Pannes détectées"
              value={`${evaluation.pannes_detectees}/${evaluation.pannes}`} />
            <StatCard label="Fausses alertes" value={evaluation.fausses_alertes} />
            <StatCard label="Délai médian" value={duree(evaluation.delai_median_s)} />
            <StatCard label="Familles" value={(service.familles || []).length} />
          </div>
          <p className="precision">
            Évaluation menée sur des mesures que le modèle n’avait jamais vues.
          </p>
        </Panneau>
      )}

      {fiche.retours && (
        <Panneau titre="Ce que le terrain a corrigé">
          <p className="precision">
            Chaque alerte clôturée « non justifiée » devient une période de
            fonctionnement normal à réapprendre ; chaque échauffement signalé après coup
            sort des données d’apprentissage, pour que le modèle ne l’apprenne pas
            comme normal. Ces corrections sont prises en compte au prochain entraînement.
          </p>
          <div className="compteurs">
            <StatCard label="Fausses alertes signalées"
              value={fiche.retours.fausses_alertes} />
            <StatCard label="Échauffements manqués" value={fiche.retours.manques} />
            <StatCard label="Alertes confirmées" value={fiche.retours.confirmes} />
            <StatCard label="En attente d’entraînement" value={fiche.retours.en_attente} />
          </div>
          {fiche.retours.derniers && fiche.retours.derniers.length > 0 && (
            <ol className="historique">
              {fiche.retours.derniers.map((retour) => (
                <li key={retour.id}>
                  <span className="historique-heure">
                    {dateEtHeure(retour.enregistre_le)}
                  </span>
                  <span>
                    {GENRES_RETOUR[retour.genre] || retour.genre} · {retour.equipement}
                    {' — '}{retour.motif}
                    {retour.par && ` · ${retour.par}`}
                    {!retour.pris_en_compte_le && ' · pas encore appris'}
                  </span>
                </li>
              ))}
            </ol>
          )}
        </Panneau>
      )}

      <Panneau titre="Ce que le modèle regarde">
        <ul className="liste-entrees">
          {(fiche.entrees || []).map((entree) => (
            <li key={entree}>{NOMS_ENTREES[entree] || entree}</li>
          ))}
        </ul>
      </Panneau>

      <Panneau titre="Versions">
        <DataTable columns={colonnes} rows={fiche.versions || []} rowKey="version"
          empty={<EmptyState title="Aucune version enregistrée" tone="neutral" />} />
      </Panneau>

      <Dialog
        open={Boolean(confirmation)}
        title="Mettre cette version en service"
        confirmLabel="Mettre en service"
        cancelLabel="Annuler"
        onCancel={() => setConfirmation(null)}
        onConfirm={() => mettreEnService(confirmation.version)}
      >
        <p>
          La version {confirmation?.version} remplacera celle en service. Les alertes en
          cours sont conservées ; seules les mesures suivantes seront jugées par le
          nouveau modèle.
        </p>
      </Dialog>
    </div>
  );
}
