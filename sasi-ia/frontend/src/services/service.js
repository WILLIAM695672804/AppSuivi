// Source des données de l'interface.
//
// Deux sources, choisies automatiquement :
//   - le serveur de l'application (api/serveur.py), quand il répond ;
//   - les données d'exemple, sinon — mode démonstration.
//
// Les écrans appellent toujours les mêmes fonctions et ignorent laquelle sert.

import { DonneesExemple as D_EXEMPLE } from './donneesExemple.js';

const DELAI_CONTROLE_MS = 2500;

/** Fiche d'alerte du serveur → forme attendue par les écrans (temps en millisecondes). */
export function convertirAlerte(a) {
  return {
    id: a.id, equipement: a.equipement, niveau: a.niveau, etat: a.etat,
    debut: a.debut ? a.debut * 1000 : null,
    fin: a.fin ? a.fin * 1000 : null,
    assignee: a.assignee_a ?? a.assignee ?? null,
    raison: a.raison, action: a.action,
    facteurs: a.facteurs || [], justifiee: a.justifiee,
    tMesuree: a.t_mesuree ?? a.tMesuree ?? null,
    tAttendue: a.t_attendue ?? a.tAttendue ?? null,
    score: a.score ?? null,
    risque: a.risque ?? null,
    risqueHorizon: a.risque_horizon_min ?? null,
    risqueMinutes: a.risque_minutes_avant_seuil ?? null,
    risqueSeuil: a.risque_seuil ?? null,
    risqueRaison: a.risque_raison ?? null,
    // le serveur date en secondes et nomme la clé « secondes » ; les écrans
    // travaillent en millisecondes, sous le nom « t ».
    evenements: (a.evenements || []).map((e) => {
      const instant = e.t ?? e.secondes;
      return { ...e, t: instant ? instant * 1000 : null, a: e.a ?? e.a_qui ?? null };
    }),
  };
}

// ------------------------------------------------------------------ exemple
export const SourceExemple = {
  mode: 'exemple',
  async site() {
    return { site: { id: 'SIM01', nom: 'Site pilote — brasserie' },
      zones: D_EXEMPLE.zones, familles: D_EXEMPLE.familles };
  },
  async equipements() { return D_EXEMPLE.equipements; },
  async alertes() {
    return { enCours: D_EXEMPLE.alertes, historique: D_EXEMPLE.historique,
      technique: D_EXEMPLE.alerteTechnique };
  },
  async rapport() { return D_EXEMPLE.rapport; },
  async cameras() { return D_EXEMPLE.cameras; },
  async serie(equipement, options) { return D_EXEMPLE.serie(equipement, options); },
  async action() { return { simule: true }; },
  async modele() { return D_EXEMPLE.modele; },
  async signalerManque() {
    throw new Error('Mode démonstration : le serveur de l’application est nécessaire.');
  },
  async travail() { return null; },
  async inspection() { return D_EXEMPLE.inspection; },
  async situations() { return D_EXEMPLE.situations; },
  async inspecter() {
    throw new Error('Mode démonstration : le serveur de l’application est nécessaire.');
  },
  async essai() {
    throw new Error('Mode démonstration : le serveur de l’application est nécessaire.');
  },
  async entrainer() {
    throw new Error('Mode démonstration : le serveur de l’application est nécessaire.');
  },
  async mettreEnService() {
    throw new Error('Mode démonstration : le serveur de l’application est nécessaire.');
  },
  ecouter() { return () => {}; },
};

// ------------------------------------------------------------------ serveur
export function SourceServeur(base = '') {
  async function lire(chemin) {
    const reponse = await fetch(base + chemin);
    if (!reponse.ok) throw new Error(`${chemin} : ${reponse.status}`);
    return reponse.json();
  }

  async function envoyer(chemin, corps) {
    const reponse = await fetch(base + chemin, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corps || {}),
    });
    if (!reponse.ok) throw new Error((await reponse.text()) || String(reponse.status));
    return reponse.json();
  }

  return {
    mode: 'serveur',

    async site() {
      const s = await lire('/api/site');
      return { site: s.site, zones: s.zones, familles: s.familles };
    },

    async equipements() {
      const [liste, description] = await Promise.all([
        lire('/api/equipements'), lire('/api/site')]);
      const fiches = Object.fromEntries(description.equipements.map((e) => [e.id, e]));
      return liste.map((e) => {
        const f = fiches[e.id] || {};
        return {
          ...e,
          plageBasse: f.plage_basse, plageHaute: f.plage_haute,
          tempsMontee: f.temps_montee_min, camera: f.camera,
          seuilInspection: f.seuil_inspection ?? f.plage_haute + 15,
          seuilUrgence: f.seuil_urgence ?? f.plage_haute + 30,
          remarque: f.remarque,
        };
      });
    },

    async alertes() {
      const [toutes, techniques] = await Promise.all([
        lire('/api/alertes'), lire('/api/alertes/techniques').catch(() => [])]);
      return {
        enCours: toutes.filter((a) => a.etat !== 'cloturee').map(convertirAlerte),
        historique: toutes.filter((a) => a.etat === 'cloturee').map(convertirAlerte),
        technique: techniques[0] || null,
      };
    },

    async rapport() { return lire('/api/rapports/hebdomadaire'); },
    async cameras() { return lire('/api/cameras'); },

    async serie(equipement, options = {}) {
      const heures = options.heures || 24;
      const reponse = await lire(`/api/equipements/${equipement.id}/mesures?heures=${heures}`);
      const mesure = [];
      const attendu = [];
      (reponse.mesures || []).forEach((m) => {
        const t = new Date(m.horodatage).getTime();
        mesure.push({ t, v: m.t_max });
        if (m.t_attendue !== null && m.t_attendue !== undefined) attendu.push({ t, v: m.t_attendue });
      });
      return { mesure, attendu };
    },

    async modele() { return lire('/api/modele'); },
    async signalerManque(equipement, corps) {
      return envoyer(`/api/equipements/${equipement}/manque`, corps);
    },
    async travail(identifiant) { return lire(`/api/modele/travaux/${identifiant}`); },
    async inspection() { return lire('/api/modele/inspection'); },
    async situations() { return lire('/api/modele/situations'); },
    async inspecter(par) { return envoyer('/api/modele/inspecter', { par }); },
    async essai(demande) { return envoyer('/api/modele/essai', demande); },

    async entrainer(par) {
      return envoyer('/api/modele/entrainer', { par });
    },

    async mettreEnService(version, par) {
      return envoyer(`/api/modele/versions/${version}/en-service`, { par });
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
        prise.onopen = () => surLiaison?.(true);
        prise.onclose = () => { surLiaison?.(false); setTimeout(ouvrir, 3000); };
        prise.onmessage = (evenement) => {
          try { surMessage(JSON.parse(evenement.data)); }
          catch (erreur) { console.warn('Message en direct illisible', erreur); }
        };
      };
      ouvrir();
      return () => { vivant = false; prise?.close(); };
    },
  };
}

// ------------------------------------------------------------------ choix
export async function choisirSource() {
  const demande = new URLSearchParams(location.search).get('source');
  if (demande === 'exemple' || location.protocol === 'file:') return SourceExemple;
  try {
    const controle = new AbortController();
    const minuteur = setTimeout(() => controle.abort(), DELAI_CONTROLE_MS);
    const reponse = await fetch('/api/site', { signal: controle.signal });
    clearTimeout(minuteur);
    if (!reponse.ok) throw new Error(String(reponse.status));
    return SourceServeur();
  } catch (erreur) {
    console.info('Serveur injoignable : mode démonstration.', erreur.message);
    return SourceExemple;
  }
}

export async function chargerTout(source) {
  const [site, equipements, alertes, rapport, cameras] = await Promise.all([
    source.site(), source.equipements(), source.alertes(),
    source.rapport().catch(() => null), source.cameras().catch(() => []),
  ]);
  const parId = Object.fromEntries(equipements.map((e) => [e.id, e]));
  alertes.enCours.forEach((a) => { if (parId[a.equipement]) parId[a.equipement].niveau = a.niveau; });

  const auditeurs = new Set();
  const signaler = () => auditeurs.forEach((f) => f());

  const D = {
    mode: source.mode,
    nomSite: site.site.nom, zones: site.zones, familles: site.familles,
    equipements, parId,
    alertes: alertes.enCours, historique: alertes.historique,
    alerteTechnique: alertes.technique,
    rapport, cameras,
    maintenant: source.mode === 'exemple' ? D_EXEMPLE.MAINTENANT : Date.now(),
    derniereErreur: null,
    serie: (equipement, options) => source.serie(equipement, options),
    ecouter: (...arguments_) => source.ecouter(...arguments_),
    modele: () => source.modele(),
    signalerManque: (equipement, corps) => source.signalerManque(equipement, corps),
    travail: (identifiant) => source.travail(identifiant),
    inspection: () => source.inspection(),
    situations: () => source.situations(),
    inspecter: (par) => source.inspecter(par),
    essai: (demande) => source.essai(demande),
    entrainer: (par) => source.entrainer(par),
    mettreEnService: (version, par) => source.mettreEnService(version, par),

    /** Prévient l'interface qu'il faut réafficher. Renvoie de quoi se désabonner. */
    abonner(fonction) {
      auditeurs.add(fonction);
      return () => auditeurs.delete(fonction);
    },

    /** Range une alerte arrivée du serveur : en cours, ou déplacée dans l'historique. */
    appliquerAlerte(fiche) {
      if (!fiche || !fiche.id) return;
      D.alertes = D.alertes.filter((a) => a.id !== fiche.id);
      D.historique = D.historique.filter((a) => a.id !== fiche.id);
      if (fiche.etat === 'cloturee') D.historique = [fiche, ...D.historique];
      else D.alertes = [fiche, ...D.alertes];
      if (parId[fiche.equipement]) {
        parId[fiche.equipement].niveau = fiche.etat === 'cloturee' ? 'normal' : fiche.niveau;
      }
      signaler();
    },

    /** Range un changement de niveau arrivé du serveur. */
    appliquerNiveaux(niveaux) {
      Object.entries(niveaux || {}).forEach(([identifiant, niveau]) => {
        if (parId[identifiant]) parId[identifiant].niveau = niveau;
      });
      signaler();
    },

    /** Action d'une équipe : l'écran change tout de suite, le serveur confirme ensuite.
     *
     * Le serveur des alertes reste seul juge : s'il refuse, son message corrige
     * l'affichage. En mode démonstration, seule la mise à jour locale a lieu.
     */
    async action(equipement, nom, corps = {}) {
      const index = D.alertes.findIndex((a) => a.equipement === equipement);
      const avant = index >= 0 ? D.alertes[index] : null;
      if (avant) D.appliquerAlerte(appliquerAction(avant, nom, corps));
      try {
        return await source.action(equipement, nom, corps);
      } catch (erreur) {
        if (avant) D.appliquerAlerte(avant);          // le serveur a refusé : on revient
        D.derniereErreur = erreur.message || String(erreur);
        signaler();
        return null;
      }
    },
  };
  return D;
}

/** Effet immédiat d'une action sur une alerte, en attendant la réponse du serveur. */
function appliquerAction(alerte, nom, corps) {
  const maintenant = Date.now();
  const evenement = { t: maintenant, type: nom, par: corps.par, a: corps.a_qui };
  const evenements = [...(alerte.evenements || []), evenement];
  if (nom === 'acquitter') return { ...alerte, etat: 'acquittee', evenements };
  if (nom === 'assigner') {
    return { ...alerte, etat: alerte.etat === 'ouverte' ? 'acquittee' : alerte.etat,
      assignee: corps.a_qui, evenements };
  }
  if (nom === 'cloturer') {
    return { ...alerte, etat: 'cloturee', fin: maintenant,
      justifiee: corps.justifiee, constat: corps.constat, evenements };
  }
  return alerte;
}
