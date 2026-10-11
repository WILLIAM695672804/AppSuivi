// Interface SASI — sept écrans construits avec les composants du système visuel.
//
// Cette version fonctionne sur des données d'exemple (donnees-exemple.js).
// Le branchement sur le serveur de l'application viendra ensuite : seules les
// fonctions de chargement changeront, pas les écrans.

const { createElement: h, useState, useMemo, Fragment } = React;
const {
  Button, LevelBadge, AlertCard, DataTable, TemperatureChart, StatusBanner,
  Dialog, Field, Textarea, Select, EmptyState, Chip, StatCard,
  LEVEL_LABEL, STATE_LABEL, formatTemperature,
} = window.SASI;

// Données du site : remplies au démarrage par le service (serveur ou exemple).
let D = null;
const NIVEAUX = ['urgence', 'inspection', 'surveillance', 'information'];

// ---------------------------------------------------------------- chargement
function useSerie(equipement, options) {
  const [donnees, setDonnees] = useState(null);
  const clef = equipement ? `${equipement.id}|${JSON.stringify(options)}` : null;
  React.useEffect(() => {
    if (!equipement) return undefined;
    let vivant = true;
    D.serie(equipement, options).then((s) => { if (vivant) setDonnees(s); });
    return () => { vivant = false; };
  }, [clef]);
  return donnees;
}

function useSeries(liste, options) {
  const [donnees, setDonnees] = useState(null);
  const clef = liste.map((e) => e.id).join(',') + JSON.stringify(options);
  React.useEffect(() => {
    let vivant = true;
    Promise.all(liste.map((e) => D.serie(e, options)))
      .then((resultats) => { if (vivant) setDonnees(resultats); });
    return () => { vivant = false; };
  }, [clef]);
  return donnees;
}

function EnAttente({ hauteur = 240 }) {
  return h('div', { className: 'en-attente', style: { height: hauteur } }, 'Chargement…');
}

// ---------------------------------------------------------------- utilitaires
function heure(t) {
  return new Date(t).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
    .replace(':', ' h ');
}

function depuis(t) {
  const minutes = Math.round((D.MAINTENANT - t) / D.MINUTE);
  if (minutes < 60) return `il y a ${minutes} min`;
  const heures = Math.floor(minutes / 60);
  return `depuis ${heures} h ${String(minutes % 60).padStart(2, '0')}`;
}

function duree(t, fin) {
  const minutes = Math.round(((fin || D.MAINTENANT) - t) / D.MINUTE);
  return `${Math.floor(minutes / 60)} h ${String(minutes % 60).padStart(2, '0')}`;
}

function equipement(id) {
  return D.parId[id] || { id, nom: id, zone: '—', famille: '—' };
}

function titreEquipement(id) {
  return `${id} · ${equipement(id).nom}`;
}

function courbes(id, options) {
  const eq = equipement(id);
  const { mesure, attendu } = D.serie(eq, options);
  return { mesure, attendu, eq };
}

// ---------------------------------------------------------------- ossature
function MenuLateral({ ecran, aller, nbAlertes }) {
  const entrees = [
    ['tableau', 'Tableau de bord', 'grid'],
    ['suivi', 'Suivi des températures', 'chart'],
    ['alertes', 'Alertes', 'bell'],
    ['equipements', 'Équipements', 'book'],
    ['rapports', 'Rapports', 'file'],
    ['administration', 'Administration', 'settings'],
  ];
  return h('nav', { className: 'menu' },
    h('div', { className: 'menu-titre' },
      h('span', { className: 'menu-marque' }, '◈'),
      h('span', null, 'SASI')),
    h('ul', null, entrees.map(([clef, libelle]) =>
      h('li', { key: clef },
        h('button', {
          className: 'menu-entree' + (ecran === clef ? ' active' : ''),
          onClick: () => aller(clef),
          'aria-current': ecran === clef ? 'page' : undefined,
        },
          h('span', null, libelle),
          clef === 'alertes' && nbAlertes
            ? h('span', { className: 'menu-compteur' }, nbAlertes) : null)))),
    h('p', { className: 'menu-pied' }, 'Données d’exemple'));
}

function BarreHaute({ liaison, basculerTheme, theme, mode }) {
  return h('header', { className: 'barre' },
    h('span', { className: 'barre-site' },
      (D && D.nomSite ? D.nomSite : 'Site') + ' · ',
      mode === 'exemple' ? 'données d’exemple'
        : liaison ? 'Mise à jour en direct' : 'Liaison interrompue'),
    h('div', { className: 'barre-actions' },
      h(Button, { variant: 'quiet', size: 'sm', onClick: basculerTheme },
        theme === 'dark' ? 'Thème clair' : 'Thème sombre'),
      h('span', { className: 'barre-utilisateur' }, 'Responsable sécurité')));
}

// ---------------------------------------------------------- tableau de bord
function TableauDeBord({ aller }) {
  const alertes = D.alertes;
  const compte = Object.fromEntries(NIVEAUX.map((n) =>
    [n, D.equipements.filter((e) => e.niveau === n).length]));
  const normaux = D.equipements.filter((e) => e.niveau === 'normal').length;
  const plusHaut = NIVEAUX.find((n) => compte[n] > 0);

  return h('div', { className: 'ecran' },
    D.alerteTechnique ? h(StatusBanner, {
      kind: 'technique',
      title: 'Caméra muette',
      actionLabel: 'Voir la caméra',
      onAction: () => aller('administration'),
    }, D.alerteTechnique.raison) : null,

    h('div', { className: 'etat-site' },
      h('p', { className: 'etat-titre' },
        plusHaut === 'urgence' ? 'Une urgence en cours'
          : plusHaut ? 'Des alertes en cours' : 'Tout va bien'),
      h('p', { className: 'etat-detail' },
        `${normaux} équipements sur ${D.equipements.length} sont normaux · `
        + `${alertes.length} alertes en cours`)),

    h('div', { className: 'compteurs' }, NIVEAUX.map((niveau) =>
      h(StatCard, {
        key: niveau, size: 'xl', level: niveau, plain: compte[niveau] === 0,
        label: LEVEL_LABEL[niveau], value: String(compte[niveau]),
        caption: compte[niveau] ? 'équipements concernés' : 'aucun équipement',
      }))),

    h('div', { className: 'deux-colonnes' },
      h('section', { className: 'panneau' },
        h('h2', null, 'Plan du site'),
        Object.entries(D.zones).map(([numero, nom]) => {
          const liste = D.equipements.filter((e) => String(e.zone) === numero);
          return h('div', { className: 'zone', key: numero },
            h('h3', null, `Zone ${numero} — ${nom}`),
            h('div', { className: 'zone-equipements' }, liste.map((e) =>
              h('button', {
                key: e.id, className: `tuile niveau-${e.niveau}`,
                onClick: () => aller('equipement', e.id),
              },
                h(LevelBadge, { level: e.niveau, size: 'sm', iconOnly: true }),
                h('span', { className: 'tuile-nom' }, e.nom),
                h('span', { className: 'tuile-id' }, e.id)))));
        })),

      h('section', { className: 'panneau' },
        h('h2', null, 'Alertes en cours'),
        alertes.length === 0
          ? h(EmptyState, { title: 'Aucune alerte en cours', tone: 'ok' },
            'Tous les équipements sont dans leur comportement habituel.')
          : alertes.map((a) => h(AlertCard, {
            key: a.id,
            level: a.niveau,
            state: a.etat,
            equipment: titreEquipement(a.equipement),
            zone: `Zone ${equipement(a.equipement).zone}`,
            since: depuis(a.debut),
            reason: a.raison,
            measured: a.tMesuree,
            expected: a.tAttendue,
            assignee: a.assignee,
            overdue: a.relance,
            density: 'compact',
            onOpen: () => aller('alerte', a.id),
          })))));
}

// ------------------------------------------------------ suivi températures
function SuiviTemperatures() {
  const [zone, setZone] = useState('1');
  const [heures, setHeures] = useState(24);
  const [choisi, setChoisi] = useState(null);

  const liste = D.equipements.filter((e) => String(e.zone) === zone);
  const seul = liste.length === 1 || choisi;
  const cible = choisi ? equipement(choisi) : liste[0];
  const brutes = useSeries(liste.slice(0, 5), { heures });
  const donnees = useSerie(cible, { heures });
  // Libellé court : les noms complets débordent du graphique en comparaison.
  const series = (brutes || []).map((s, i) => ({
    id: liste[i].id, label: liste[i].id, points: s.mesure,
  }));

  return h('div', { className: 'ecran' },
    h('h1', null, 'Suivi des températures'),
    h('div', { className: 'filtres' },
      h('span', { className: 'filtres-libelle' }, 'Zone'),
      Object.entries(D.zones).map(([numero, nom]) =>
        h(Chip, {
          key: numero, selected: zone === numero,
          onClick: () => { setZone(numero); setChoisi(null); },
          label: `Zone ${numero}`, title: nom,
        })),
      h('span', { className: 'filtres-libelle' }, 'Période'),
      [[2, '2 h'], [24, '24 h'], [168, '7 jours']].map(([valeur, libelle]) =>
        h(Chip, {
          key: valeur, selected: heures === valeur,
          onClick: () => setHeures(valeur), label: libelle,
        }))),

    h('section', { className: 'panneau panneau-courbe' },
      h('h2', null, seul ? `${cible.nom} · ${cible.id}` : `Zone ${zone} — ${D.zones[zone]}`),
      (!donnees || (!seul && !brutes)) ? h(EnAttente, { hauteur: 420 }) : h(TemperatureChart, {
        series: seul
          ? [{ id: cible.id, label: cible.nom, points: donnees.mesure }]
          : series,
        expected: seul ? { points: donnees.attendu } : undefined,
        normalRange: seul ? [cible.plageBasse, cible.plageHaute] : undefined,
        thresholds: seul ? [
          { level: 'inspection', value: cible.seuilInspection },
          { level: 'urgence', value: cible.seuilUrgence },
        ] : undefined,
        height: 420,
        selectedId: choisi,
        onSelect: (id) => setChoisi(id === choisi ? null : id),
        caption: seul
          ? 'Température mesurée et température attendue par l’IA.'
          : 'Cliquez une courbe pour n’afficher qu’un équipement.',
      })),

    h('div', { className: 'filtres' },
      h('span', { className: 'filtres-libelle' }, 'Équipements'),
      liste.map((e) => h(Chip, {
        key: e.id, selected: choisi === e.id,
        onClick: () => setChoisi(choisi === e.id ? null : e.id),
        label: e.nom,
      }))));
}

// ---------------------------------------------------------------- alertes
function ListeAlertes({ aller }) {
  const [niveaux, setNiveaux] = useState([]);
  const [etats, setEtats] = useState(['ouverte', 'acquittee', 'assignee']);
  const [tri, setTri] = useState({ key: 'niveau', dir: 'desc' });

  const bascule = (valeur, liste, majorer) =>
    majorer(liste.includes(valeur) ? liste.filter((v) => v !== valeur) : [...liste, valeur]);

  const toutes = [...D.alertes, ...D.historique];
  const lignes = toutes.filter((a) =>
    (niveaux.length === 0 || niveaux.includes(a.niveau))
    && (etats.length === 0 || etats.includes(a.etat)));

  const colonnes = [
    { key: 'niveau', label: 'Niveau', sortable: true, width: 150,
      render: (l) => h(LevelBadge, { level: l.niveau, size: 'sm',
        tone: ['inspection', 'urgence'].includes(l.niveau) ? 'solid' : 'soft' }) },
    { key: 'id', label: 'Alerte', width: 100 },
    { key: 'equipement', label: 'Équipement',
      render: (l) => h('div', null,
        h('div', { className: 'cellule-forte' }, l.equipement),
        h('div', { className: 'cellule-douce' },
          `${equipement(l.equipement).nom} · Zone ${equipement(l.equipement).zone}`)) },
    { key: 'etat', label: 'État', width: 130,
      render: (l) => h('span', { className: 'etat-pastille' }, STATE_LABEL[l.etat]) },
    { key: 'debut', label: 'Début', sortable: true, width: 130,
      render: (l) => heure(l.debut) },
    { key: 'duree', label: 'Durée', numeric: true, align: 'right', width: 90,
      render: (l) => duree(l.debut, l.fin) },
    { key: 'raison', label: 'Raison',
      render: (l) => h('div', null,
        h('div', { className: 'cellule-raison' }, l.raison),
        l.relance ? h('div', { className: 'cellule-relance' },
          'Relance envoyée · plus de 10 min') : null) },
    { key: 'assignee', label: 'En charge', width: 110,
      render: (l) => l.assignee || '—' },
  ];

  return h('div', { className: 'ecran' },
    h('h1', null, 'Alertes',
      h('span', { className: 'titre-compte' }, `${lignes.length} alertes affichées`)),

    h('section', { className: 'panneau' },
      h('div', { className: 'filtres' },
        h('span', { className: 'filtres-libelle' }, 'Niveau'),
        NIVEAUX.map((n) => h(Chip, {
          key: n, selected: niveaux.includes(n), label: LEVEL_LABEL[n],
          onClick: () => bascule(n, niveaux, setNiveaux),
        }))),
      h('div', { className: 'filtres' },
        h('span', { className: 'filtres-libelle' }, 'État'),
        ['ouverte', 'acquittee', 'assignee', 'cloturee'].map((e) => h(Chip, {
          key: e, selected: etats.includes(e), label: STATE_LABEL[e],
          onClick: () => bascule(e, etats, setEtats),
        })),
        h('span', { className: 'filtres-fin' },
          h(Button, { variant: 'quiet', size: 'sm',
            onClick: () => { setNiveaux([]); setEtats([]); } }, 'Tout effacer')))),

    h('section', { className: 'panneau' },
      h(DataTable, {
        columns: colonnes, rows: lignes, rowKey: 'id', sort: tri,
        onSort: (key, dir) => setTri({ key, dir }),
        onRowOpen: (l) => aller('alerte', l.id),
        rowClassName: (l) => (l.niveau === 'urgence' ? 'ligne-urgence' : undefined),
        empty: h(EmptyState, {
          title: 'Aucune alerte ne correspond', tone: 'neutral',
          action: h(Button, { variant: 'secondary',
            onClick: () => { setNiveaux([]); setEtats([]); } }, 'Effacer les filtres'),
        }, 'Élargissez la période ou retirez un filtre.'),
      })));
}

function FicheAlerte({ id, aller }) {
  const [dialogue, setDialogue] = useState(false);
  const [constat, setConstat] = useState('');
  const [justifiee, setJustifiee] = useState('');
  const alerte = [...D.alertes, ...D.historique].find((a) => a.id === id) || D.alertes[0];
  const eq = equipement(alerte.equipement);
  const donnees = useSerie(eq, { heures: 24, derive: alerte.derive, depuis: 4 * D.HEURE });

  return h('div', { className: 'ecran' },
    h('button', { className: 'fil', onClick: () => aller('alertes') }, '‹ Alertes'),

    h('div', { className: 'fiche-entete' },
      h(LevelBadge, { level: alerte.niveau, size: 'lg', tone: 'solid' }),
      h('div', null,
        h('h1', null, eq.nom),
        h('p', { className: 'fiche-sous-titre' },
          `${alerte.id} · ${eq.id} · Zone ${eq.zone} · ${D.familles[eq.famille] || ''}`
          + ` · ${STATE_LABEL[alerte.etat]} · ${depuis(alerte.debut)}`))),

    h('div', { className: 'deux-colonnes' },
      h('div', null,
        h('section', { className: 'panneau' },
          h('div', { className: 'compteurs compteurs-trois' },
            h(StatCard, { label: 'Température mesurée', size: 'lg',
              value: formatTemperature(alerte.tMesuree), unit: '°C' }),
            h(StatCard, { label: 'Température attendue', size: 'lg',
              value: formatTemperature(alerte.tAttendue), unit: '°C' }),
            h(StatCard, { label: 'Écart', size: 'lg',
              value: formatTemperature(alerte.tMesuree - alerte.tAttendue), unit: '°C',
              delta: { text: `+${formatTemperature(alerte.tMesuree - alerte.tAttendue)} °C`,
                direction: 'up' } })),
          h('h2', null, 'Raison'),
          h('p', { className: 'raison' }, alerte.raison),
          alerte.facteurs
            ? h(Fragment, null,
              h('h2', null, 'Facteurs d’influence'),
              h('ul', { className: 'facteurs' },
                alerte.facteurs.map((f, i) => h('li', { key: i }, f))))
            : null,
          h('div', { className: 'action-conseillee' },
            h('h2', null, 'Action conseillée'),
            h('p', null, alerte.action))),

        h('section', { className: 'panneau' },
          h('h2', null, '24 dernières heures'),
          !donnees ? h(EnAttente, { hauteur: 320 }) : h(TemperatureChart, {
            series: [{ id: eq.id, label: eq.nom, points: donnees.mesure }],
            expected: { points: donnees.attendu },
            normalRange: [eq.plageBasse, eq.plageHaute],
            thresholds: [
              { level: 'inspection', value: eq.seuilInspection },
              { level: 'urgence', value: eq.seuilUrgence },
            ],
            periods: [{ from: alerte.debut, to: D.MAINTENANT, level: alerte.niveau }],
            height: 320,
            caption: 'Mesure en trait plein, température attendue en pointillé.',
          }))),

      h('div', null,
        h('section', { className: 'panneau' },
          h('h2', null, 'Actions'),
          h('div', { className: 'boutons-colonne' },
            alerte.etat === 'ouverte'
              ? h(Button, { variant: 'primary', size: 'lg',
                onClick: () => D.action(alerte.equipement, 'acquitter',
                  { par: 'responsable' }) }, 'Prendre en charge') : null,
            h(Button, { variant: 'secondary',
              onClick: () => D.action(alerte.equipement, 'assigner',
                { par: 'responsable', a_qui: 'technicien' }) }, 'Assigner à un technicien'),
            h(Button, { variant: 'secondary', onClick: () => setDialogue(true) }, 'Clôturer'),
            h(Button, { variant: 'quiet',
              onClick: () => aller('equipement', eq.id) }, 'Voir l’équipement'))),

        h('section', { className: 'panneau' },
          h('h2', null, 'Historique de l’alerte'),
          h('ol', { className: 'historique' }, (alerte.evenements || []).map((e, i) =>
            h('li', { key: i },
              h('span', { className: 'historique-heure' }, heure(e.t)),
              h('span', null, e.type + (e.niveau ? ` — ${LEVEL_LABEL[e.niveau]}` : '')
                + (e.par ? ` · ${e.par}` : '') + (e.a ? ` → ${e.a}` : '')))))))),

    h(Dialog, {
      open: dialogue,
      title: 'Clôturer l’alerte',
      confirmLabel: 'Clôturer',
      cancelLabel: 'Annuler',
      confirmDisabled: !constat || !justifiee,
      onCancel: () => setDialogue(false),
      onConfirm: () => {
        D.action(alerte.equipement, 'cloturer', {
          par: 'responsable', constat, justifiee: justifiee === 'oui',
        });
        setDialogue(false);
      },
    },
      h(Field, { label: 'Compte rendu de l’intervention', required: true },
        h(Textarea, { rows: 3, value: constat,
          onChange: (e) => setConstat(e.target.value) })),
      h(Field, { label: 'L’alerte était-elle justifiée ?', required: true },
        h(Select, { value: justifiee, onChange: (e) => setJustifiee(e.target.value) },
          h('option', { value: '' }, 'Choisir'),
          h('option', { value: 'oui' }, 'Oui'),
          h('option', { value: 'non' }, 'Non'))),
      h('p', { className: 'note' },
        'La clôture est impossible sans compte rendu ni réponse à cette question.')));
}

// ------------------------------------------------------------ équipements
function ListeEquipements({ aller }) {
  const colonnes = [
    { key: 'niveau', label: 'Niveau', width: 140,
      render: (e) => h(LevelBadge, { level: e.niveau, size: 'sm' }) },
    { key: 'id', label: 'Identifiant', width: 130 },
    { key: 'nom', label: 'Équipement' },
    { key: 'zone', label: 'Zone', width: 80, numeric: true, align: 'right' },
    { key: 'famille', label: 'Famille', width: 200,
      render: (e) => D.familles[e.famille] },
    { key: 'criticite', label: 'Criticité', width: 100, numeric: true, align: 'right',
      render: (e) => `${e.criticite} sur 3` },
    { key: 'plage', label: 'Plage normale', width: 150, align: 'right',
      render: (e) => `${e.plageBasse} à ${e.plageHaute} °C` },
  ];
  return h('div', { className: 'ecran' },
    h('h1', null, 'Équipements',
      h('span', { className: 'titre-compte' }, `${D.equipements.length} équipements`)),
    h('section', { className: 'panneau' },
      h(DataTable, { columns: colonnes, rows: D.equipements, rowKey: 'id',
        onRowOpen: (e) => aller('equipement', e.id) })));
}

function FicheEquipement({ id, aller }) {
  const eq = equipement(id);
  const alerte = D.alertes.find((a) => a.equipement === id);
  const donnees = useSerie(eq, { heures: 24, derive: alerte ? alerte.derive : 0,
    depuis: 4 * D.HEURE });
  const derniere = donnees && donnees.mesure.length
    ? donnees.mesure[donnees.mesure.length - 1].v : null;
  const attendue = donnees && donnees.attendu.length
    ? donnees.attendu[donnees.attendu.length - 1].v : null;
  const passees = D.historique.filter((a) => a.equipement === id);

  return h('div', { className: 'ecran' },
    h('button', { className: 'fil', onClick: () => aller('equipements') }, '‹ Équipements'),
    h('div', { className: 'fiche-entete' },
      h(LevelBadge, { level: eq.niveau, size: 'lg' }),
      h('div', null,
        h('h1', null, eq.nom),
        h('p', { className: 'fiche-sous-titre' },
          `${eq.id} · Zone ${eq.zone} · ${D.familles[eq.famille]} · ${eq.camera}`))),

    eq.niveau === 'normal'
      ? h(StatusBanner, { kind: 'apprentissage', title: 'Période d’apprentissage terminée' },
        'La plage normale est apprise depuis le 4 août 2026 (4 semaines d’observation).')
      : null,

    h('div', { className: 'deux-colonnes' },
      h('div', null,
        h('section', { className: 'panneau' },
          h('h2', null, eq.niveau === 'normal'
            ? 'Cet équipement va bien, et voici pourquoi' : 'État actuel'),
          h('div', { className: 'compteurs compteurs-trois' },
            h(StatCard, { label: 'Mesurée', size: 'lg', unit: '°C',
              value: derniere === null ? '—' : formatTemperature(derniere),
              level: eq.niveau }),
            h(StatCard, { label: 'Attendue', size: 'lg', unit: '°C',
              value: attendue === null ? '—' : formatTemperature(attendue) }),
            h(StatCard, { label: 'Écart', size: 'lg', unit: '°C',
              value: (derniere === null || attendue === null) ? '—'
                : formatTemperature(derniere - attendue),
              delta: (derniere === null || attendue === null) ? undefined : {
                text: `${derniere - attendue >= 0 ? '+' : ''}`
                  + `${formatTemperature(derniere - attendue)} °C`,
                direction: derniere - attendue >= 0 ? 'up' : 'down' } }))),

        h('section', { className: 'panneau' },
          h('h2', null, '24 dernières heures'),
          !donnees ? h(EnAttente, { hauteur: 320 }) : h(TemperatureChart, {
            series: [{ id: eq.id, label: eq.nom, points: donnees.mesure }],
            expected: { points: donnees.attendu },
            normalRange: [eq.plageBasse, eq.plageHaute],
            thresholds: [
              { level: 'inspection', value: eq.seuilInspection },
              { level: 'urgence', value: eq.seuilUrgence },
            ],
            height: 300,
          })),

        h('section', { className: 'panneau' },
          h('h2', null, 'Historique des alertes et des interventions'),
          passees.length === 0
            ? h(EmptyState, { title: 'Aucune alerte enregistrée', tone: 'ok' },
              'Cet équipement n’a jamais déclenché d’alerte.')
            : h('ul', { className: 'historique' }, passees.map((a) =>
              h('li', { key: a.id },
                h(LevelBadge, { level: a.niveau, size: 'sm' }),
                h('span', null, `${a.id} · ${duree(a.debut, a.fin)} · `
                  + `justifiée : ${a.justifiee ? 'oui' : 'non'} · ${a.compteRendu}`)))))),

      h('div', null,
        h('section', { className: 'panneau' },
          h('h2', null, 'Identité'),
          h('dl', { className: 'proprietes' },
            [['Identifiant', eq.id], ['Zone', `Zone ${eq.zone}`],
             ['Famille', D.familles[eq.famille]], ['Criticité', `${eq.criticite} sur 3`],
             ['Caméra', eq.camera], ['Temps de mise en température', `${eq.tempsMontee} min`]]
              .map(([clef, valeur]) => h(Fragment, { key: clef },
                h('dt', null, clef), h('dd', null, valeur))))),

        h('section', { className: 'panneau' },
          h('h2', null, 'Plage normale et seuils'),
          h('dl', { className: 'proprietes' },
            h('dt', null, 'Plage normale'),
            h('dd', null, `${eq.plageBasse} à ${eq.plageHaute} °C`),
            h('dt', null, 'Seuil d’inspection'),
            h('dd', null, `${eq.seuilInspection} °C`),
            h('dt', null, 'Seuil d’urgence'),
            h('dd', null, `${eq.seuilUrgence} °C`)),
          h('p', { className: 'note' },
            'Seuils relevés sur le terrain ; à défaut, plage haute + 15 °C et + 30 °C.')),

        h('section', { className: 'panneau' },
          h('h2', null, 'Actions'),
          h('div', { className: 'boutons-colonne' },
            h(Button, { variant: 'primary' }, 'Ouvrir le suivi des températures'),
            h(Button, { variant: 'secondary' }, 'Mettre en maintenance'))))));
}

// ---------------------------------------------------------------- rapports
function Rapports() {
  const r = D.rapport;
  if (!r) {
    return h('div', { className: 'ecran' },
      h('h1', null, 'Rapports'),
      h(EmptyState, { title: 'Aucun rapport disponible', tone: 'neutral' },
        'Le rapport hebdomadaire sera produit dès que le système aura une semaine de mesures.'));
  }
  const variation = r.alertes - r.alertesPrecedentes;
  return h('div', { className: 'ecran' },
    h('h1', null, 'Rapports',
      h('span', { className: 'titre-compte' }, r.periode)),

    h('div', { className: 'compteurs' },
      h(StatCard, { label: 'Alertes de la semaine', size: 'lg', value: String(r.alertes),
        delta: { text: `${variation > 0 ? '+' : ''}${variation}`,
          direction: variation > 0 ? 'up' : 'down' },
        caption: `semaine précédente : ${r.alertesPrecedentes}` }),
      h(StatCard, { label: 'Délai de prise en charge', size: 'lg',
        value: String(r.delaiMedian), unit: 'min',
        caption: `médiane · maximum ${r.delaiMaximum} min` }),
      h(StatCard, { label: 'Alertes justifiées', size: 'lg',
        value: String(Math.round((r.justifiees / r.alertes) * 100)), unit: '%',
        caption: `${r.justifiees} sur ${r.alertes}` }),
      h(StatCard, { label: 'Disponibilité de la surveillance', size: 'lg',
        value: r.disponibilite.toLocaleString('fr-FR', { minimumFractionDigits: 1 }),
        unit: '%', caption: 'part du temps où les caméras ont mesuré' })),

    h('div', { className: 'deux-colonnes' },
      h('section', { className: 'panneau' },
        h('h2', null, 'Alertes par zone et par niveau'),
        h(DataTable, {
          rowKey: 'zone',
          columns: [
            { key: 'zone', label: 'Zone', width: 90, render: (l) => `Zone ${l.zone}` },
            ...NIVEAUX.map((n) => ({ key: n, label: LEVEL_LABEL[n], numeric: true,
              align: 'right', render: (l) => l[n] || '—' })),
            { key: 'total', label: 'Total', numeric: true, align: 'right',
              render: (l) => NIVEAUX.reduce((s, n) => s + (l[n] || 0), 0) },
          ],
          rows: r.parZone,
        })),

      h('section', { className: 'panneau' },
        h('h2', null, 'Équipements les plus exposés'),
        h(DataTable, {
          rowKey: 'equipement',
          columns: [
            { key: 'equipement', label: 'Équipement',
              render: (l) => h('div', null,
                h('div', { className: 'cellule-forte' }, l.equipement),
                h('div', { className: 'cellule-douce' }, equipement(l.equipement).nom)) },
            { key: 'alertes', label: 'Alertes', numeric: true, align: 'right', width: 90 },
            { key: 'niveau', label: 'Plus haut niveau', width: 160,
              render: (l) => h(LevelBadge, { level: l.niveau, size: 'sm' }) },
            { key: 'duree', label: 'Durée cumulée', align: 'right', width: 130 },
          ],
          rows: r.exposes,
        }))),

    h('section', { className: 'panneau' },
      h('h2', null, 'Disponibilité par caméra'),
      h(DataTable, {
        rowKey: 'camera',
        columns: [
          { key: 'camera', label: 'Caméra', width: 140 },
          { key: 'disponibilite', label: 'Disponibilité', numeric: true, align: 'right',
            width: 140, render: (l) => `${l.disponibilite.toLocaleString('fr-FR',
              { minimumFractionDigits: 1 })} %` },
          { key: 'sansMesure', label: 'Temps sans mesure', align: 'right' },
        ],
        rows: r.cameras,
      })));
}

// ---------------------------------------------------------- administration
function Administration() {
  const cameras = D.cameras && D.cameras.length ? D.cameras : [];
  const [camera, setCamera] = useState(cameras.length ? cameras[0].id : null);
  const choisie = cameras.find((c) => c.id === camera);
  if (!choisie) {
    return h('div', { className: 'ecran' },
      h('h1', null, 'Administration'),
      h(EmptyState, { title: 'Aucune caméra déclarée', tone: 'neutral' },
        'Déclarez une caméra pour délimiter les zones de ses équipements.'));
  }
  const liste = D.equipements.filter((e) => e.camera === camera);
  const sansContour = Math.max(liste.length - choisie.contours, 0);

  return h('div', { className: 'ecran' },
    h('h1', null, 'Administration',
      h('span', { className: 'titre-compte' }, 'Caméras et zones')),

    h('div', { className: 'filtres' },
      h('span', { className: 'filtres-libelle' }, 'Caméra'),
      cameras.map((c) => h(Chip, {
        key: c.id, selected: camera === c.id, onClick: () => setCamera(c.id),
        label: c.id,
      }))),

    choisie.etat === 'muette'
      ? h(StatusBanner, { kind: 'technique', title: 'Caméra muette' },
        'Aucune mesure reçue depuis 14 min : les contours s’affichent sur la dernière '
        + 'image reçue.')
      : null,

    h('div', { className: 'deux-colonnes' },
      h('section', { className: 'panneau' },
        h('h2', null, `Image thermique · ${choisie.id}`),
        h('div', { className: 'image-thermique' },
          h('p', null, 'Zone de tracé des contours'),
          h('p', { className: 'note' },
            'L’outil de dessin sera branché sur l’image réelle de la caméra. '
            + 'Fausses couleurs : sans lien avec les niveaux d’alerte.')),
        h('div', { className: 'boutons-ligne' },
          h(Button, { variant: 'primary' }, 'Tracer un contour'),
          h(Button, { variant: 'secondary' }, 'Annuler le dernier point'),
          h(Button, { variant: 'quiet' }, 'Annuler le tracé'))),

      h('div', null,
        h('section', { className: 'panneau' },
          h('h2', null, 'Caméra'),
          h('dl', { className: 'proprietes' },
            [['Zone', `Zone ${choisie.zone} — ${D.zones[choisie.zone]}`],
             ['Modèle', choisie.modele], ['Adresse réseau', choisie.adresse],
             ['Distance', `${choisie.distance} m`], ['Émissivité', String(choisie.emissivite)],
             ['État', choisie.etat]].map(([clef, valeur]) =>
              h(Fragment, { key: clef }, h('dt', null, clef), h('dd', null, valeur))))),

        h('section', { className: 'panneau' },
          h('h2', null, 'Équipements de la zone'),
          h('p', { className: 'note' },
            `${choisie.contours} contour(s) tracé(s) sur ${liste.length} équipements.`),
          sansContour > 0
            ? h(StatusBanner, { kind: 'technique', title: 'Équipement sans contour' },
              `${sansContour} équipement(s) de cette zone ne sont pas surveillés.`)
            : null,
          h('ul', { className: 'liste-simple' }, liste.map((e) =>
            h('li', { key: e.id },
              h('span', { className: 'cellule-forte' }, e.id),
              h('span', null, e.nom))))))));
}

// ---------------------------------------------------------------- ossature
function lireAdresse() {
  // #alerte/A-1033 → { ecran: 'alerte', cible: 'A-1033' }
  const [ecran, cible] = (window.location.hash || '#tableau').slice(1).split('/');
  return { ecran: ecran || 'tableau', cible: cible || null };
}

function Application() {
  const depart = lireAdresse();
  const [ecran, setEcran] = useState(depart.ecran);
  const [cible, setCible] = useState(depart.cible);
  const [theme, setTheme] = useState(
    new URLSearchParams(window.location.search).get('theme') || 'light');
  const [pret, setPret] = useState(false);
  const [erreur, setErreur] = useState(null);
  const [liaison, setLiaison] = useState(false);
  const [rafraichir, setRafraichir] = useState(0);

  React.useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  // Chargement initial : serveur si disponible, sinon données d'exemple.
  React.useEffect(() => {
    let vivant = true;
    let arreter = () => {};
    Service.choisir()
      .then((source) => Service.tout(source))
      .then((donnees) => {
        if (!vivant) return;
        D = donnees;
        setPret(true);
        setLiaison(donnees.mode === 'serveur');
        arreter = donnees.ecouter(
          (message) => {
            // Une mesure ou une alerte vient d'arriver : on réaffiche.
            if (message.type === 'niveaux') {
              Object.entries(message.niveaux || {}).forEach(([id, niveau]) => {
                if (D.parId[id]) D.parId[id].niveau = niveau;
              });
            }
            if (message.type === 'alerte' && message.alerte) {
              const existante = D.alertes.findIndex((a) => a.id === message.alerte.id);
              if (existante >= 0) D.alertes[existante] = message.alerte;
              else D.alertes.unshift(message.alerte);
            }
            setRafraichir((n) => n + 1);
          },
          (etat) => setLiaison(etat));
      })
      .catch((e) => { if (vivant) setErreur(e.message || String(e)); });
    return () => { vivant = false; arreter(); };
  }, []);

  const aller = (nom, id = null) => {
    setEcran(nom); setCible(id);
    window.location.hash = id ? `${nom}/${id}` : nom;
    window.scrollTo(0, 0);
  };
  const basculer = () => setTheme(theme === 'light' ? 'dark' : 'light');

  if (erreur) {
    return h('div', { className: 'application application-simple' },
      h(StatusBanner, { kind: 'technique', title: 'Données indisponibles' }, erreur));
  }
  if (!pret) {
    return h('div', { className: 'application application-simple' },
      h(EnAttente, { hauteur: 200 }));
  }

  const contenu = {
    tableau: () => h(TableauDeBord, { aller }),
    suivi: () => h(SuiviTemperatures, null),
    alertes: () => h(ListeAlertes, { aller }),
    alerte: () => h(FicheAlerte, { id: cible, aller }),
    equipements: () => h(ListeEquipements, { aller }),
    equipement: () => h(FicheEquipement, { id: cible, aller }),
    rapports: () => h(Rapports, null),
    administration: () => h(Administration, null),
  }[ecran] || (() => h(TableauDeBord, { aller }));

  return h('div', { className: 'application', key: rafraichir },
    h(MenuLateral, {
      ecran: ecran === 'alerte' ? 'alertes' : ecran === 'equipement' ? 'equipements' : ecran,
      aller, nbAlertes: D.alertes.length,
    }),
    h('main', null,
      h(BarreHaute, { liaison, basculerTheme: basculer, theme, mode: D.mode }),
      D.mode === 'exemple'
        ? h(StatusBanner, { kind: 'demonstration', title: 'Mode démonstration' },
          'Le serveur n’est pas joignable : les écrans affichent des données d’exemple.')
        : null,
      contenu()));
}

ReactDOM.createRoot(document.getElementById('racine')).render(h(Application));
