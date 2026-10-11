// Accès aux données de l'application.
//
// Deux sources, choisies automatiquement :
//   - le serveur de l'application (api/serveur.py), quand il répond ;
//   - les données d'exemple (donnees-exemple.js), sinon — mode démonstration.
//
// Les écrans ne savent pas laquelle est utilisée : ils appellent toujours les
// mêmes fonctions.

(function (global) {
  const D = global.DonneesExemple;

  function attendre(valeur) {
    return Promise.resolve(valeur);
  }

  // ------------------------------------------------------------ exemple
  const SourceExemple = {
    mode: 'exemple',

    async site() {
      return {
        site: { id: 'SIM01', nom: 'Site pilote — brasserie' },
        zones: D.zones, familles: D.familles,
      };
    },

    async equipements() {
      return D.equipements;
    },

    async alertes() {
      return { enCours: D.alertes, historique: D.historique, technique: D.alerteTechnique };
    },

    async rapport() {
      return D.rapport;
    },

    async cameras() {
      return D.cameras;
    },

    async serie(equipement, options) {
      return D.serie(equipement, options);
    },

    async action() {
      return { simule: true };
    },

    ecouter() {
      return () => {};              // aucune mise à jour en direct en mode démonstration
    },
  };

  // ------------------------------------------------------------ serveur
  function SourceServeur(base) {
    async function lire(chemin) {
      const reponse = await fetch(base + chemin);
      if (!reponse.ok) throw new Error(`${chemin} : ${reponse.status}`);
      return reponse.json();
    }

    return {
      mode: 'serveur',

      async site() {
        const s = await lire('/api/site');
        return { site: s.site, zones: s.zones, familles: s.familles, equipementsBruts: s.equipements };
      },

      async equipements() {
        const liste = await lire('/api/equipements');
        const fiches = (await lire('/api/site')).equipements;
        const parId = Object.fromEntries(fiches.map((e) => [e.id, e]));
        return liste.map((e) => {
          const f = parId[e.id] || {};
          return {
            ...e,
            plageBasse: f.plage_basse, plageHaute: f.plage_haute,
            tempsMontee: f.temps_montee_min, camera: f.camera,
            seuilInspection: f.seuil_inspection ?? (f.plage_haute + 15),
            seuilUrgence: f.seuil_urgence ?? (f.plage_haute + 30),
          };
        });
      },

      async alertes() {
        const toutes = await lire('/api/alertes');
        const convertir = (a) => ({
          id: a.id, equipement: a.equipement, niveau: a.niveau, etat: a.etat,
          debut: new Date(a.debut * 1000).getTime(),
          fin: a.fin ? new Date(a.fin * 1000).getTime() : null,
          assignee: a.assignee_a, raison: a.raison, action: a.action,
          facteurs: a.facteurs || [], justifiee: a.justifiee,
        });
        return {
          enCours: toutes.filter((a) => a.etat !== 'cloturee').map(convertir),
          historique: toutes.filter((a) => a.etat === 'cloturee').map(convertir),
          technique: null,
        };
      },

      async rapport() {
        return lire('/api/rapports/hebdomadaire');
      },

      async cameras() {
        return lire('/api/cameras');
      },

      async serie(equipement, options = {}) {
        const heures = options.heures || 24;
        const reponse = await lire(
          `/api/equipements/${equipement.id}/mesures?heures=${heures}`);
        const mesure = [];
        const attendu = [];
        (reponse.mesures || []).forEach((m) => {
          const t = new Date(m.horodatage).getTime();
          mesure.push({ t, v: m.t_max });
          if (m.t_attendue !== null && m.t_attendue !== undefined) {
            attendu.push({ t, v: m.t_attendue });
          }
        });
        return { mesure, attendu };
      },

      async action(equipement, nom, corps) {
        const reponse = await fetch(`${base}/api/alertes/${equipement}/${nom}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(corps || {}),
        });
        if (!reponse.ok) throw new Error(await reponse.text());
        return reponse.json();
      },

      ecouter(surMessage, surLiaison) {
        let prise = null;
        let vivant = true;
        const ouvrir = () => {
          if (!vivant) return;
          const protocole = location.protocol === 'https:' ? 'wss' : 'ws';
          prise = new WebSocket(`${protocole}://${location.host}/ws/temps-reel`);
          prise.onopen = () => surLiaison && surLiaison(true);
          prise.onclose = () => {
            surLiaison && surLiaison(false);
            setTimeout(ouvrir, 3000);
          };
          prise.onmessage = (evenement) => {
            try {
              surMessage(JSON.parse(evenement.data));
            } catch (erreur) {
              console.warn('Message en direct illisible', erreur);
            }
          };
        };
        ouvrir();
        return () => { vivant = false; if (prise) prise.close(); };
      },
    };
  }

  // ------------------------------------------------------------ choix
  async function choisir() {
    const demande = new URLSearchParams(location.search).get('source');
    if (demande === 'exemple' || location.protocol === 'file:') return SourceExemple;

    const serveur = SourceServeur('');
    try {
      const controle = new AbortController();
      const minuteur = setTimeout(() => controle.abort(), 2500);
      const reponse = await fetch('/api/site', { signal: controle.signal });
      clearTimeout(minuteur);
      if (!reponse.ok) throw new Error(String(reponse.status));
      return serveur;
    } catch (erreur) {
      console.info('Serveur injoignable : mode démonstration.', erreur.message);
      return SourceExemple;
    }
  }

  global.Service = {
    choisir,
    SourceExemple,
    SourceServeur,
    async tout(source) {
      const [site, equipements, alertes, rapport, cameras] = await Promise.all([
        source.site(), source.equipements(), source.alertes(),
        source.rapport().catch(() => null), source.cameras().catch(() => []),
      ]);
      const parId = Object.fromEntries(equipements.map((e) => [e.id, e]));
      alertes.enCours.forEach((a) => { if (parId[a.equipement]) parId[a.equipement].niveau = a.niveau; });
      return {
        mode: source.mode,
        zones: site.zones, familles: site.familles, nomSite: site.site.nom,
        equipements, parId,
        alertes: alertes.enCours, historique: alertes.historique,
        alerteTechnique: alertes.technique,
        rapport, cameras,
        MINUTE: 60 * 1000, HEURE: 3600 * 1000,
        MAINTENANT: source.mode === 'exemple' ? D.MAINTENANT : Date.now(),
        serie: (equipement, options) => source.serie(equipement, options),
        action: (...arguments_) => source.action(...arguments_),
        ecouter: (...arguments_) => source.ecouter(...arguments_),
      };
    },
  };
})(window);
