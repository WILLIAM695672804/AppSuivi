import React, { useCallback, useEffect, useState } from 'react';

import EnAttente from '../../composants/EnAttente.jsx';
import Panneau from '../../composants/Panneau.jsx';
import { useDonnees } from '../../services/donnees.jsx';
import { peut } from '../../services/session.js';
import {
  Button, DataTable, EmptyState, StatCard, StatusBanner,
} from '../../systeme.js';

const PERIODE_SUIVI_MS = 2000;

const VERDICTS = {
  conforme: { libelle: 'Conforme', classe: 'verdict-conforme' },
  insensible: { libelle: 'Sans effet', classe: 'verdict-insensible' },
  'jamais observé': { libelle: 'Jamais observé', classe: 'verdict-jamais' },
  "À L'ENVERS": { libelle: 'À l’envers', classe: 'verdict-envers' },
};

const dateEtHeure = (texte) => (texte
  ? new Date(texte).toLocaleString('fr-FR',
    { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
  : '—');

/** Le raisonnement du modèle : où il se trompe, sur quoi il s'appuie, s'il raisonne juste. */
export default function Raisonnement() {
  const D = useDonnees();
  const [examen, setExamen] = useState(null);
  const [absent, setAbsent] = useState(false);
  const [travail, setTravail] = useState(null);
  const [erreur, setErreur] = useState(null);

  const administre = peut(D.session, 'administrer');

  const charger = useCallback(() => D.inspection()
    .then((resultat) => { setExamen(resultat); setAbsent(false); })
    .catch(() => setAbsent(true)), [D]);

  useEffect(() => { charger(); }, [charger]);

  useEffect(() => {
    if (!travail || travail.etat !== 'en cours') return undefined;
    const minuteur = setInterval(() => {
      D.travail(travail.id)
        .then((suite) => {
          setTravail(suite);
          if (suite && suite.etat !== 'en cours') charger();
        })
        .catch(() => {});
    }, PERIODE_SUIVI_MS);
    return () => clearInterval(minuteur);
  }, [travail, D, charger]);

  const inspecter = () => {
    setErreur(null);
    D.inspecter(D.session.nom).then(setTravail).catch((s) => setErreur(s.message));
  };

  const enCours = travail && travail.etat === 'en cours';

  const bouton = administre && (
    <div className="boutons-ligne">
      <Button variant="primary" onClick={inspecter} disabled={enCours}>
        {enCours ? 'Inspection en cours…' : 'Inspecter le modèle en service'}
      </Button>
      <span className="precision">
        L’inspection relit les mesures d’apprentissage et interroge le modèle ;
        elle ne le modifie pas.
      </span>
    </div>
  );

  if (absent && !examen) {
    return (
      <div className="onglet-contenu">
        {erreur && <StatusBanner kind="technique" title="Inspection impossible">{erreur}</StatusBanner>}
        <Panneau titre="Raisonnement du modèle">
          <EmptyState title="Aucune inspection disponible" tone="neutral">
            Le modèle en service n’a pas encore été inspecté.
          </EmptyState>
          {bouton}
          {enCours && travail && (
            <p className="precision">{travail.progression} % · {travail.etape_libelle}</p>
          )}
        </Panneau>
      </div>
    );
  }

  if (!examen) return <EnAttente hauteur={320} libelle="Lecture de l’inspection…" />;

  const resume = examen.resume || {};
  const pireErreur = Math.max(
    ...examen.par_equipement.map((l) => l.erreur_moyenne), 0.01);

  const colonnes = [
    { key: 'equipement', label: 'Équipement', width: 130 },
    { key: 'famille', label: 'Famille', width: 80 },
    { key: 'erreur_moyenne', label: 'Erreur', width: 90,
      render: (l) => `${l.erreur_moyenne.toFixed(2)} °C` },
    { key: 'erreur_etabli', label: 'En régime établi', width: 130,
      render: (l) => (l.erreur_etabli ? `${l.erreur_etabli.toFixed(2)} °C` : '—') },
    { key: 'erreur_transitoire', label: 'En transitoire', width: 120,
      render: (l) => (l.erreur_transitoire ? `${l.erreur_transitoire.toFixed(2)} °C` : '—') },
    { key: 'biais', label: 'Biais', width: 90,
      render: (l) => `${l.biais > 0 ? '+' : ''}${l.biais.toFixed(2)} °C` },
    { key: 'pire', label: 'Pire écart', width: 100,
      render: (l) => `${l.pire.toFixed(1)} °C` },
  ];

  const anomalies = examen.bon_sens.filter((c) => c.verdict === "À L'ENVERS");

  return (
    <div className="onglet-contenu">
      {erreur && <StatusBanner kind="technique" title="Inspection impossible">{erreur}</StatusBanner>}

      <Panneau titre="Contrôles de bon sens">
        <p className="precision">
          On fait varier une seule information à la fois et on vérifie que la
          température attendue évolue comme le bon sens l’exige : plus de charge
          doit donner plus chaud, une machine arrêtée depuis longtemps doit être
          plus froide.
        </p>
        <div className="compteurs">
          <StatCard label="Conformes" value={resume.conformes ?? 0} />
          <StatCard label="Sans effet" value={resume.insensibles ?? 0} />
          <StatCard label="Jamais observés" value={resume.jamais_observes ?? 0} />
          <StatCard label="À l’envers" value={resume.a_lenvers ?? 0} />
        </div>
        <p className="precision">
          Un « jamais observé » n’est pas un défaut du modèle mais un trou dans les
          données : la situation ne s’est pas présentée pendant l’apprentissage.
        </p>
        {bouton}
        {enCours && travail && (
          <p className="precision">{travail.progression} % · {travail.etape_libelle}</p>
        )}
      </Panneau>

      {anomalies.length > 0 && (
        <Panneau titre="Raisonnements à corriger">
          <ul className="liste-anomalies">
            {anomalies.map((constat, rang) => (
              <li key={rang}>
                <strong>{constat.equipement}</strong> — {constat.intitule} : le modèle
                fait l’inverse ({constat.variation > 0 ? '+' : ''}
                {constat.variation.toFixed(1)} °C).
              </li>
            ))}
          </ul>
          <p className="precision">
            Le plus souvent, les données d’apprentissage ne couvrent pas assez de
            situations. Allonger la période d’apprentissage est le premier remède.
          </p>
        </Panneau>
      )}

      <Panneau titre="Où le modèle se trompe">
        <p className="precision">
          Écart entre la température prédite et la température mesurée, en
          fonctionnement normal. Un biais franchement positif signifie que le modèle
          croit l’équipement plus froid qu’il n’est, et risque d’alerter à tort.
        </p>
        <DataTable columns={colonnes} rows={examen.par_equipement} rowKey="equipement"
          empty={<EmptyState title="Aucun équipement inspecté" tone="neutral" />} />
      </Panneau>

      <Panneau titre="Sur quoi il s’appuie">
        <p className="precision">
          Part de chaque information dans les décisions du modèle. Une entrée
          écrasante mérite qu’on vérifie qu’elle est bien mesurée sur le terrain.
        </p>
        {Object.entries(examen.poids).sort().map(([famille, couples]) => (
          <div key={famille} className="famille-poids">
            <h4>{D.familles[famille] || famille}</h4>
            {couples.length === 0 ? (
              <p className="precision">Ce modèle n’expose pas ses poids.</p>
            ) : (
              <ul className="barres">
                {couples.filter((c) => c.part >= 0.5).map((couple) => (
                  <li key={couple.entree}>
                    <span className="barres-libelle">{couple.libelle}</span>
                    <span className="barres-piste">
                      <span className="barres-valeur" style={{ width: `${couple.part}%` }} />
                    </span>
                    <span className="barres-chiffre">{couple.part.toFixed(1)} %</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </Panneau>

      <Panneau titre="Ses pires moments">
        <p className="precision">
          Les mesures que le modèle explique le plus mal, en fonctionnement normal.
          Si elles se concentrent sur un équipement ou sur un régime, la cause est là.
        </p>
        <div className="tableau-compact">
          <table>
            <thead>
              <tr>
                <th>Quand</th><th>Équipement</th><th>Régime</th>
                <th>Mesurée</th><th>Attendue</th><th>Écart</th><th>Charge</th>
              </tr>
            </thead>
            <tbody>
              {examen.pires.map((ligne, rang) => (
                <tr key={rang}>
                  <td>{dateEtHeure(ligne.horodatage)}</td>
                  <td>{ligne.equipement}</td>
                  <td>{ligne.regime}</td>
                  <td>{ligne.t_max.toFixed(1)} °C</td>
                  <td>{ligne.t_attendue.toFixed(1)} °C</td>
                  <td>{ligne.ecart > 0 ? '+' : ''}{ligne.ecart.toFixed(1)} °C</td>
                  <td>{ligne.charge_pct.toFixed(0)} %</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panneau>

      <Panneau titre="Tous les contrôles">
        <div className="tableau-compact">
          <table>
            <thead>
              <tr>
                <th>Équipement</th><th>Ce qui varie</th>
                <th>Attendu</th><th>Réponse</th><th>Verdict</th>
              </tr>
            </thead>
            <tbody>
              {examen.bon_sens.map((constat, rang) => {
                const verdict = VERDICTS[constat.verdict]
                  || { libelle: constat.verdict, classe: '' };
                return (
                  <tr key={rang}>
                    <td>{constat.equipement}</td>
                    <td>{constat.libelle}</td>
                    <td>{constat.intitule}</td>
                    <td>
                      {constat.verdict === 'jamais observé' ? '—'
                        : `${constat.variation > 0 ? '+' : ''}${constat.variation.toFixed(1)} °C`}
                    </td>
                    <td className={verdict.classe}>{verdict.libelle}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Panneau>
    </div>
  );
}
