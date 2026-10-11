// Données d'exemple de l'interface.
//
// Elles imitent ce que fournira le serveur de l'application : mêmes noms de
// champs que dans le cahier des charges technique (chapitre 8.4), mêmes
// identifiants que le site pilote (sites/brasserie.json). Rien ici ne vient du
// vrai système : c'est un jeu d'essai, remplacé plus tard par les appels au
// serveur.

(function (global) {
  const MINUTE = 60 * 1000;
  const HEURE = 60 * MINUTE;
  const MAINTENANT = new Date('2026-09-15T17:50:00Z').getTime();

  // ---------------------------------------------------------------- le site
  const zones = {
    1: 'Réception et stockage des matières premières',
    2: 'Salle de brassage',
    3: 'Cave de fermentation et de garde',
    4: 'Chaufferie et armoires électriques',
    5: 'Conditionnement',
    6: 'Station de nettoyage en place',
    7: 'Stockage CO₂ et gaz techniques',
  };

  const familles = {
    MOT: 'Moteurs et convoyeurs',
    ARM: 'Armoires électriques',
    CHD: 'Équipements chauds',
    POM: 'Pompes et compresseurs',
    RES: 'Résistances de chauffe',
  };

  // Seuils du document « Valeur normale et seuil des équipements ».
  const SEUILS = {"Z1-ELV-01": [70, 80], "Z1-VIS-01": [70, 80], "Z1-MOU-01": [35, 40], "Z2-CHE-01": [280, 300], "Z4-CHV-01": [240, 245], "Z4-ARM-01-A": [50, 65], "Z4-ARM-01-B": [50, 65], "Z4-ARM-01-C": [50, 65], "Z6-RES-01": [165, 180], "Z6-PCI-01": [100, 115], "Z7-CMP-01": [95, 110]};

  // id, nom, zone, famille, caméra, criticité, plage normale, temps de montée
  const equipements = [
    ['Z1-ELV-01', "L'élévateur à godets", 1, 'MOT', 'CAM-Z1', 2, [40, 70], 35],
    ['Z1-VIS-01', 'La vis à grain', 1, 'MOT', 'CAM-Z1', 2, [40, 70], 35],
    ['Z1-MOU-01', 'Le moulin', 1, 'MOT', 'CAM-Z1', 2, [20, 35], 25],
    ['Z2-CHE-01', "La chaudière d'ébullition", 2, 'CHD', 'CAM-Z2', 2, [150, 250], 50],
    ['Z3-GFG-01', 'Le groupe froid', 3, 'POM', 'CAM-Z3', 3, [-8, -6], 60],
    ['Z3-PTR-01', 'La pompe de transfert', 3, 'POM', 'CAM-Z3', 1, [40, 60], 22],
    ['Z4-CHV-01', 'La chaudière vapeur', 4, 'CHD', 'CAM-Z4', 3, [150, 230], 45],
    ['Z4-ARM-01-A', "La phase A de l'armoire", 4, 'ARM', 'CAM-Z4', 3, [15, 35], 15],
    ['Z4-ARM-01-B', "La phase B de l'armoire", 4, 'ARM', 'CAM-Z4', 3, [15, 35], 15],
    ['Z4-ARM-01-C', "La phase C de l'armoire", 4, 'ARM', 'CAM-Z4', 3, [15, 35], 15],
    ['Z5-ETQ-01', "L'étiqueteuse", 5, 'MOT', 'CAM-Z5', 1, [40, 45], 25],
    ['Z5-PAS-01', 'Le pasteurisateur', 5, 'CHD', 'CAM-Z5', 2, [60, 67], 50],
    ['Z5-CNV-01', 'Le convoyeur', 5, 'MOT', 'CAM-Z5', 1, [40, 45], 25],
    ['Z6-CUV-01', 'La cuve de nettoyage', 6, 'CHD', 'CAM-Z6', 2, [70, 85], 25],
    ['Z6-RES-01', 'La résistance de chauffe', 6, 'RES', 'CAM-Z6', 3, [50, 150], 15],
    ['Z6-PCI-01', 'La pompe de circulation', 6, 'POM', 'CAM-Z6', 2, [10, 90], 22],
    ['Z7-CMP-01', 'Le compresseur', 7, 'POM', 'CAM-Z7', 2, [30, 40], 30],
  ].map(([id, nom, zone, famille, camera, criticite, plage, montee]) => ({
    id, nom, zone, famille, camera, criticite,
    plageBasse: plage[0], plageHaute: plage[1], tempsMontee: montee,
    // Seuils relevés sur le terrain s'ils existent, sinon plage haute + 15 °C et + 30 °C.
    seuilInspection: (SEUILS[id] || [plage[1] + 15])[0],
    seuilUrgence: (SEUILS[id] || [null, plage[1] + 30])[1] ?? plage[1] + 30,
    niveau: 'normal',
  }));

  const parId = Object.fromEntries(equipements.map((e) => [e.id, e]));

  // ---------------------------------------------------- séries de mesures
  // Générateur simple et reproductible : une courbe plausible, pas un modèle.
  function alea(graine) {
    let etat = graine;
    return () => {
      etat = (etat * 1103515245 + 12345) % 2147483648;
      return etat / 2147483648;
    };
  }

  function serie(equipement, options = {}) {
    const { heures = 24, pas = 5 * MINUTE, derive = 0, depuis = 0 } = options;
    const tirage = alea(equipement.id.length * 7919 + equipement.zone * 104729);
    const debut = MAINTENANT - heures * HEURE;
    const centre = (equipement.plageBasse + equipement.plageHaute) / 2;
    const amplitude = (equipement.plageHaute - equipement.plageBasse) / 6;
    const mesure = [];
    const attendu = [];
    for (let t = debut; t <= MAINTENANT; t += pas) {
      const heure = new Date(t).getUTCHours() + new Date(t).getUTCMinutes() / 60;
      const marche = equipement.famille === 'POM' || (heure >= 6 && heure < 22);
      const base = marche
        ? centre + amplitude * Math.sin((t - debut) / (4 * HEURE))
        : equipement.plageBasse - (equipement.plageBasse - 28) * 0.6;
      const attendue = Math.round(base * 10) / 10;
      let mesuree = base + (tirage() - 0.5) * 0.8;
      if (derive && t >= MAINTENANT - depuis) {
        mesuree += (derive * (t - (MAINTENANT - depuis))) / HEURE;
      }
      mesure.push({ t, v: Math.round(mesuree * 10) / 10 });
      attendu.push({ t, v: attendue });
    }
    return { mesure, attendu };
  }

  // ---------------------------------------------------------------- alertes
  const alertes = [
    {
      id: 'A-1033', equipement: 'Z1-ELV-01', niveau: 'inspection', etat: 'ouverte',
      debut: MAINTENANT - 3 * HEURE - 20 * MINUTE, relance: true,
      tMesuree: 68.0, tAttendue: 50.0,
      raison: "L'élévateur à godets est 18,0 °C plus chaud que d'habitude (68,0 °C mesurés "
        + 'pour 50,0 °C attendus) pour une charge de 75 % et une ambiance de 31,2 °C, et la '
        + 'température monte encore de 0,12 °C par minute depuis 40 min.',
      facteurs: [
        'la charge des 30 dernières minutes augmente la température attendue de 13,0 °C',
        "la plage normale de l'équipement augmente la température attendue de 3,7 °C",
        "le temps écoulé depuis le démarrage augmente la température attendue de 3,6 °C",
      ],
      action: "Contrôler les roulements et la lubrification ; vérifier l'alignement et la "
        + 'tension des courroies.',
      evenements: [
        { t: MAINTENANT - 3 * HEURE - 20 * MINUTE, type: 'Alerte créée', niveau: 'surveillance' },
        { t: MAINTENANT - 2 * HEURE - 50 * MINUTE, type: 'Montée de niveau', niveau: 'inspection' },
        { t: MAINTENANT - 2 * HEURE - 40 * MINUTE, type: 'Relance envoyée', par: 'Système' },
      ],
      derive: 6,
    },
    {
      id: 'A-1034', equipement: 'Z6-RES-01', niveau: 'urgence', etat: 'assignee',
      debut: MAINTENANT - 35 * MINUTE, assignee: 'Marc T.',
      tMesuree: 162.0, tAttendue: 88.0,
      raison: 'La résistance de chauffe monte de 4,10 °C par minute, plus vite que prévu '
        + '(162,0 °C atteints) alors que la cuve est signalée vide, depuis 8 min.',
      facteurs: [
        "l'état de marche augmente la température attendue de 41,0 °C",
        'la charge augmente la température attendue de 6,2 °C',
      ],
      action: 'Vérifier immédiatement le niveau de liquide dans la cuve et couper la chauffe '
        + 'si la cuve est vide.',
      evenements: [
        { t: MAINTENANT - 35 * MINUTE, type: 'Alerte créée', niveau: 'urgence' },
        { t: MAINTENANT - 30 * MINUTE, type: 'Prise en charge', par: 'Awa N.' },
        { t: MAINTENANT - 28 * MINUTE, type: 'Assignée', par: 'Awa N.', a: 'Marc T.' },
      ],
      derive: 40,
    },
    {
      id: 'A-1035', equipement: 'Z4-ARM-01-B', niveau: 'inspection', etat: 'ouverte',
      debut: MAINTENANT - 55 * MINUTE, relance: true,
      tMesuree: 47.5, tAttendue: 34.0,
      raison: "La phase B de l'armoire est 13,5 °C plus chaude que les équipements identiques "
        + '(47,5 °C mesurés).',
      facteurs: [
        'la chaleur ambiante augmente la température attendue de 7,5 °C',
        'la charge augmente la température attendue de 2,2 °C',
      ],
      action: 'Contrôler le serrage des connexions de la phase concernée ; vérifier '
        + "l'équilibre des charges.",
      evenements: [
        { t: MAINTENANT - 55 * MINUTE, type: 'Alerte créée', niveau: 'surveillance' },
        { t: MAINTENANT - 25 * MINUTE, type: 'Montée de niveau', niveau: 'inspection' },
        { t: MAINTENANT - 15 * MINUTE, type: 'Relance envoyée', par: 'Système' },
      ],
      derive: 9,
    },
    {
      id: 'A-1036', equipement: 'Z7-CMP-01', niveau: 'surveillance', etat: 'acquittee',
      debut: MAINTENANT - 40 * MINUTE, assignee: 'Awa N.',
      tMesuree: 70.1, tAttendue: 62.1,
      raison: 'Le compresseur est 8,0 °C plus chaud que d\'habitude (70,1 °C mesurés pour '
        + '62,1 °C attendus) pour une charge de 93 % et une ambiance de 24,9 °C.',
      facteurs: ["la plage normale de l'équipement augmente la température attendue de 9,8 °C"],
      action: 'Vérifier la ventilation, les filtres et les roulements ; contrôler le niveau '
        + "d'huile.",
      evenements: [
        { t: MAINTENANT - 40 * MINUTE, type: 'Alerte créée', niveau: 'surveillance' },
        { t: MAINTENANT - 32 * MINUTE, type: 'Prise en charge', par: 'Awa N.' },
      ],
      derive: 5,
    },
    {
      id: 'A-1037', equipement: 'Z5-CNV-01', niveau: 'information', etat: 'ouverte',
      debut: MAINTENANT - 12 * MINUTE,
      tMesuree: 52.3, tAttendue: 49.8,
      raison: "Le convoyeur est 2,5 °C plus chaud que d'habitude (52,3 °C mesurés pour "
        + '49,8 °C attendus) pour une charge de 80 %.',
      facteurs: ['la charge augmente la température attendue de 4,1 °C'],
      action: "Contrôler les roulements et la lubrification ; vérifier l'alignement et la "
        + 'tension des courroies.',
      evenements: [{ t: MAINTENANT - 12 * MINUTE, type: 'Alerte créée', niveau: 'information' }],
      derive: 2,
    },
  ];

  const alerteTechnique = {
    id: 'A-1038', equipement: 'CAM-Z2', niveau: 'technique', etat: 'ouverte',
    debut: MAINTENANT - 14 * MINUTE,
    raison: 'Aucune mesure reçue de CAM-Z2 depuis 14 min. Les équipements de la zone 2 ne '
      + 'sont pas surveillés.',
    action: "Vérifier l'alimentation et le câble réseau de la caméra.",
  };

  alertes.forEach((a) => { parId[a.equipement].niveau = a.niveau; });

  // ------------------------------------------------------------ historique
  const historique = [
    { id: 'A-1021', equipement: 'Z1-MOU-01', niveau: 'inspection', etat: 'cloturee',
      debut: MAINTENANT - 30 * HEURE, fin: MAINTENANT - 28 * HEURE,
      assignee: 'Marc T.', justifiee: true,
      raison: "Le moulin est 14,2 °C plus chaud que d'habitude.",
      compteRendu: 'Roulement côté entraînement remplacé.' },
    { id: 'A-1018', equipement: 'Z3-PTR-01', niveau: 'surveillance', etat: 'cloturee',
      debut: MAINTENANT - 52 * HEURE, fin: MAINTENANT - 51 * HEURE,
      assignee: 'Awa N.', justifiee: false,
      raison: 'La pompe de transfert est 5,1 °C plus chaude que d\'habitude.',
      compteRendu: 'Fausse alerte : nettoyage en place plus long que prévu.' },
    { id: 'A-1012', equipement: 'Z5-PAS-01', niveau: 'information', etat: 'cloturee',
      debut: MAINTENANT - 74 * HEURE, fin: MAINTENANT - 73 * HEURE,
      assignee: 'Marc T.', justifiee: true,
      raison: 'Le pasteurisateur est 3,4 °C plus chaud que d\'habitude.',
      compteRendu: 'Filtre de ventilation nettoyé.' },
  ];

  // ------------------------------------------------------------- rapports
  const rapport = {
    periode: 'Semaine du 7 au 13 septembre 2026',
    alertes: 14, alertesPrecedentes: 19,
    delaiMedian: 6, delaiMaximum: 41,
    justifiees: 11, disponibilite: 99.4,
    parZone: [
      { zone: 1, urgence: 0, inspection: 2, surveillance: 1, information: 1 },
      { zone: 2, urgence: 0, inspection: 0, surveillance: 1, information: 1 },
      { zone: 4, urgence: 1, inspection: 2, surveillance: 1, information: 0 },
      { zone: 5, urgence: 0, inspection: 0, surveillance: 1, information: 2 },
      { zone: 6, urgence: 1, inspection: 0, surveillance: 0, information: 0 },
    ],
    exposes: [
      { equipement: 'Z1-ELV-01', alertes: 4, niveau: 'inspection', duree: '5 h 35' },
      { equipement: 'Z4-ARM-01-B', alertes: 3, niveau: 'inspection', duree: '3 h 10' },
      { equipement: 'Z6-RES-01', alertes: 2, niveau: 'urgence', duree: '1 h 05' },
      { equipement: 'Z7-CMP-01', alertes: 2, niveau: 'surveillance', duree: '2 h 20' },
      { equipement: 'Z5-CNV-01', alertes: 1, niveau: 'information', duree: '0 h 25' },
    ],
    cameras: [
      { camera: 'CAM-Z1', disponibilite: 99.9, sansMesure: '10 min' },
      { camera: 'CAM-Z2', disponibilite: 97.1, sansMesure: '4 h 52' },
      { camera: 'CAM-Z3', disponibilite: 99.9, sansMesure: '10 min' },
      { camera: 'CAM-Z4', disponibilite: 99.8, sansMesure: '20 min' },
      { camera: 'CAM-Z5', disponibilite: 99.9, sansMesure: '10 min' },
      { camera: 'CAM-Z6', disponibilite: 99.7, sansMesure: '30 min' },
      { camera: 'CAM-Z7', disponibilite: 99.6, sansMesure: '40 min' },
    ],
  };

  // ---------------------------------------------------------------- caméras
  const cameras = [
    { id: 'CAM-Z1', zone: 1, modele: 'FLIR A70', adresse: '10.20.3.11', distance: 9,
      emissivite: 0.95, etat: 'en service', contours: 3 },
    { id: 'CAM-Z2', zone: 2, modele: 'FLIR A70', adresse: '10.20.3.12', distance: 11,
      emissivite: 0.95, etat: 'muette', contours: 1 },
    { id: 'CAM-Z3', zone: 3, modele: 'FLIR A70', adresse: '10.20.3.13', distance: 7,
      emissivite: 0.92, etat: 'en service', contours: 2 },
    { id: 'CAM-Z4', zone: 4, modele: 'FLIR A70', adresse: '10.20.3.14', distance: 12,
      emissivite: 0.95, etat: 'en service', contours: 4 },
    { id: 'CAM-Z5', zone: 5, modele: 'FLIR A70', adresse: '10.20.3.15', distance: 10,
      emissivite: 0.95, etat: 'en service', contours: 3 },
    { id: 'CAM-Z6', zone: 6, modele: 'FLIR A70', adresse: '10.20.3.16', distance: 8,
      emissivite: 0.93, etat: 'en service', contours: 3 },
    { id: 'CAM-Z7', zone: 7, modele: 'FLIR A70', adresse: '10.20.3.17', distance: 9,
      emissivite: 0.95, etat: 'en service', contours: 1 },
  ];

  global.DonneesExemple = {
    MAINTENANT, MINUTE, HEURE,
    zones, familles, equipements, parId,
    alertes, alerteTechnique, historique, rapport, cameras,
    serie,
  };
})(window);
