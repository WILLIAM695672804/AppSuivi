import React, { useMemo, useState } from 'react';

import Panneau from '../../composants/Panneau.jsx';
import { useDonnees } from '../../services/donnees.jsx';
import {
  Button, Chip, Dialog, EmptyState, Field, Select, StatusBanner, formatTemperature,
} from '../../systeme.js';

// L'image thermique fait 640 × 480 points : les contours sont enregistrés dans
// ce repère, comme l'attend le connecteur (cahier des charges technique, 5.3).
const LARGEUR = 640;
const HAUTEUR = 480;

/** Image thermique d'exemple : des taches chaudes sur un fond froid. */
function ImageThermique({ taches }) {
  return (
    <>
      <defs>
        <linearGradient id="fond-thermique" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#1b1035" />
          <stop offset="100%" stopColor="#2d1b4e" />
        </linearGradient>
        {taches.map((tache) => (
          <radialGradient key={tache.id} id={`tache-${tache.id}`}>
            <stop offset="0%" stopColor={tache.chaude ? '#ffd899' : '#b05ac0'} />
            <stop offset="45%" stopColor={tache.chaude ? '#f2743a' : '#8244b4'} />
            <stop offset="100%" stopColor="#2d1b4e" stopOpacity="0" />
          </radialGradient>
        ))}
      </defs>
      <rect width={LARGEUR} height={HAUTEUR} fill="url(#fond-thermique)" />
      {taches.map((tache) => (
        <ellipse key={tache.id} cx={tache.x} cy={tache.y} rx={tache.rx} ry={tache.ry}
          fill={`url(#tache-${tache.id})`} />
      ))}
    </>
  );
}

function boiteEnglobante(points) {
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  return { x1: Math.min(...xs), y1: Math.min(...ys), x2: Math.max(...xs), y2: Math.max(...ys) };
}

function seChevauchent(a, b) {
  const ba = boiteEnglobante(a.points);
  const bb = boiteEnglobante(b.points);
  return ba.x1 < bb.x2 && bb.x1 < ba.x2 && ba.y1 < bb.y2 && bb.y1 < ba.y2;
}

export default function Cameras() {
  const D = useDonnees();
  const cameras = D.cameras || [];
  const [camera, setCamera] = useState(cameras[0]?.id ?? null);
  const [mode, setMode] = useState('deplacer');          // deplacer | tracer
  const [enCours, setEnCours] = useState([]);            // points du contour en cours
  const [contours, setContours] = useState({});          // par caméra
  const [choisi, setChoisi] = useState(null);
  const [aSupprimer, setASupprimer] = useState(null);

  const choisie = cameras.find((c) => c.id === camera);
  const liste = useMemo(
    () => D.equipements.filter((e) => e.camera === camera), [D.equipements, camera]);

  if (!choisie) {
    return (
      <div className="onglet-contenu">
        <EmptyState title="Aucune caméra déclarée" tone="neutral">
          Déclarez une caméra pour délimiter la zone de chacun de ses équipements.
        </EmptyState>
      </div>
    );
  }

  const tracés = contours[camera] || [];
  const sansContour = liste.filter((e) => !tracés.some((c) => c.equipement === e.id));
  const chevauchements = tracés.filter(
    (a, i) => tracés.some((b, j) => i !== j && seChevauchent(a, b)));

  // Taches chaudes d'exemple : une par équipement de la zone.
  const taches = liste.map((e, i) => ({
    id: e.id, x: 120 + (i % 3) * 200, y: 120 + Math.floor(i / 3) * 170,
    rx: 90, ry: 70, chaude: e.niveau !== 'normal',
  }));

  const pointDepuisClic = (evenement) => {
    const boite = evenement.currentTarget.getBoundingClientRect();
    const x = Math.round(((evenement.clientX - boite.left) / boite.width) * LARGEUR);
    const y = Math.round(((evenement.clientY - boite.top) / boite.height) * HAUTEUR);
    return [x, y];
  };

  const cliquerImage = (evenement) => {
    if (mode !== 'tracer') return;
    setEnCours([...enCours, pointDepuisClic(evenement)]);
  };

  const terminer = () => {
    if (enCours.length < 3) return;
    const identifiant = `C-${Date.now().toString().slice(-5)}`;
    const nouveau = { id: identifiant, equipement: sansContour[0]?.id ?? null, points: enCours };
    setContours({ ...contours, [camera]: [...tracés, nouveau] });
    setEnCours([]);
    setChoisi(identifiant);
    setMode('deplacer');
  };

  const associer = (identifiant, equipement) => setContours({
    ...contours,
    [camera]: tracés.map((c) => (c.id === identifiant ? { ...c, equipement } : c)),
  });

  const supprimer = (identifiant) => {
    setContours({ ...contours, [camera]: tracés.filter((c) => c.id !== identifiant) });
    setChoisi(null);
    setASupprimer(null);
  };

  const contourChoisi = tracés.find((c) => c.id === choisi);

  return (
    <div className="onglet-contenu">
      <div className="filtres">
        <span className="filtres-libelle">Caméra</span>
        {cameras.map((c) => (
          <Chip key={c.id} selected={camera === c.id} label={c.id}
            onClick={() => { setCamera(c.id); setEnCours([]); setChoisi(null); }} />
        ))}
      </div>

      {choisie.etat === 'muette' && (
        <StatusBanner kind="technique" title="Caméra muette">
          Aucune mesure reçue : les contours s’affichent sur la dernière image reçue.
        </StatusBanner>
      )}

      <div className="deux-colonnes deux-colonnes-large">
        <Panneau
          titre={`Image thermique · ${choisie.id}`}
          actions={(
            <div className="boutons-ligne">
              <Button variant={mode === 'deplacer' ? 'primary' : 'secondary'} size="sm"
                onClick={() => { setMode('deplacer'); setEnCours([]); }}>Déplacer</Button>
              <Button variant={mode === 'tracer' ? 'primary' : 'secondary'} size="sm"
                onClick={() => setMode('tracer')}>Tracer un contour</Button>
              <Button variant="quiet" size="sm" disabled={!enCours.length}
                onClick={() => setEnCours(enCours.slice(0, -1))}>Annuler le dernier point</Button>
              <Button variant="quiet" size="sm" disabled={!enCours.length}
                onClick={() => setEnCours([])}>Annuler le tracé</Button>
              <Button variant="secondary" size="sm" disabled={enCours.length < 3}
                onClick={terminer}>Terminer le contour</Button>
            </div>
          )}
        >
          <svg
            className={`image-thermique${mode === 'tracer' ? ' image-tracage' : ''}`}
            viewBox={`0 0 ${LARGEUR} ${HAUTEUR}`}
            onClick={cliquerImage}
            role="img"
            aria-label={`Image thermique de ${choisie.id}`}
          >
            <ImageThermique taches={taches} />

            {tracés.map((contour) => {
              const boite = boiteEnglobante(contour.points);
              return (
                <g key={contour.id}
                  className={`contour${choisi === contour.id ? ' contour-choisi' : ''}`}
                  onClick={(e) => { e.stopPropagation(); setChoisi(contour.id); }}>
                  <polygon points={contour.points.map((p) => p.join(',')).join(' ')} />
                  <text x={boite.x1 + 4} y={boite.y1 - 6}>
                    {contour.equipement || 'à associer'}
                  </text>
                </g>
              );
            })}

            {enCours.length > 0 && (
              <g className="contour contour-en-cours">
                <polyline points={enCours.map((p) => p.join(',')).join(' ')} />
                {enCours.map((p, i) => <circle key={i} cx={p[0]} cy={p[1]} r="5" />)}
              </g>
            )}
          </svg>
          <p className="note">
            Fausses couleurs de l’image : sans lien avec les niveaux d’alerte.
            {mode === 'tracer' && ' Cliquez pour poser les points, puis « Terminer le contour ».'}
          </p>
        </Panneau>

        <div>
          <Panneau titre="Caméra">
            <dl className="proprietes">
              <dt>Zone</dt><dd>Zone {choisie.zone} — {D.zones[choisie.zone]}</dd>
              <dt>Modèle</dt><dd>{choisie.modele || '—'}</dd>
              <dt>Adresse réseau</dt><dd>{choisie.adresse || '—'}</dd>
              <dt>Distance</dt><dd>{choisie.distance ? `${choisie.distance} m` : '—'}</dd>
              <dt>Émissivité</dt><dd>{choisie.emissivite ?? '—'}</dd>
              <dt>État</dt><dd>{choisie.etat}</dd>
            </dl>
          </Panneau>

          <Panneau titre="Vérifications">
            <ul className="verifications">
              <li className={chevauchements.length ? 'echec' : 'ok'}>
                {chevauchements.length
                  ? `${chevauchements.length} contour(s) se chevauchent`
                  : 'Aucun chevauchement'}
              </li>
              <li className={sansContour.length ? 'echec' : 'ok'}>
                {sansContour.length
                  ? `${sansContour.length} équipement(s) sans contour : non surveillés`
                  : `Les ${liste.length} équipements ont un contour`}
              </li>
              <li className={tracés.some((c) => !c.equipement) ? 'echec' : 'ok'}>
                {tracés.some((c) => !c.equipement)
                  ? 'Un contour n’est associé à aucun équipement'
                  : 'Chaque contour est associé à un équipement'}
              </li>
            </ul>
          </Panneau>

          {contourChoisi && (
            <Panneau titre="Contour sélectionné">
              <Field label="Équipement associé" required>
                <Select
                  value={contourChoisi.equipement || ''}
                  onChange={(e) => associer(contourChoisi.id, e.target.value || null)}
                >
                  <option value="">Choisir un équipement</option>
                  {liste.map((e) => (
                    <option key={e.id} value={e.id}>{e.id} · {e.nom}</option>
                  ))}
                </Select>
              </Field>
              <p className="note">{contourChoisi.points.length} points tracés.</p>
              <Button variant="secondary" onClick={() => setASupprimer(contourChoisi.id)}>
                Supprimer le contour
              </Button>
            </Panneau>
          )}

          <Panneau titre="Équipements de la zone"
            complement={`${tracés.length} sur ${liste.length} surveillés`}>
            <ul className="liste-simple">
              {liste.map((e) => {
                const contour = tracés.find((c) => c.equipement === e.id);
                return (
                  <li key={e.id}>
                    <span className="cellule-forte">{e.id}</span>
                    <span>{e.nom}</span>
                    <span className={contour ? 'cellule-douce' : 'cellule-relance'}>
                      {contour ? 'contour tracé' : 'sans contour'}
                    </span>
                  </li>
                );
              })}
            </ul>
          </Panneau>

          <div className="boutons-ligne">
            <Button variant="primary" disabled={!tracés.length}>Enregistrer les contours</Button>
            <Button variant="quiet" onClick={() => { setContours({ ...contours, [camera]: [] });
              setChoisi(null); }}>Annuler les modifications</Button>
          </div>
        </div>
      </div>

      <Dialog
        open={Boolean(aSupprimer)}
        title="Supprimer le contour"
        irreversible="L’équipement associé ne sera plus surveillé tant qu’un nouveau contour n’est pas tracé."
        destructive
        confirmLabel="Supprimer"
        cancelLabel="Annuler"
        onCancel={() => setASupprimer(null)}
        onConfirm={() => supprimer(aSupprimer)}
      >
        <p>Ce contour et son association seront perdus.</p>
      </Dialog>
    </div>
  );
}
