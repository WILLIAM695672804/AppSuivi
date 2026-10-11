// Routeur minimal, fondé sur l'adresse (#ecran/cible).
//
// Pas de bibliothèque : l'application a huit écrans et deux niveaux. Les
// adresses restent partageables et le retour du navigateur fonctionne.

export const ROUTES = {
  tableau: { titre: 'Tableau de bord', parent: null },
  suivi: { titre: 'Suivi des températures', parent: null },
  alertes: { titre: 'Alertes', parent: null },
  alerte: { titre: 'Fiche d’alerte', parent: 'alertes' },
  equipements: { titre: 'Équipements', parent: null },
  equipement: { titre: 'Fiche équipement', parent: 'equipements' },
  rapports: { titre: 'Rapports', parent: null },
  administration: { titre: 'Administration', parent: null },
};

export const ROUTE_PAR_DEFAUT = 'tableau';

/** Transforme « #alerte/A-1033 » en { ecran, cible }. */
export function lireAdresse(adresse = window.location.hash) {
  const [ecran, cible] = String(adresse || '').replace(/^#/, '').split('/');
  return {
    ecran: ROUTES[ecran] ? ecran : (ecran ? 'introuvable' : ROUTE_PAR_DEFAUT),
    cible: cible ? decodeURIComponent(cible) : null,
  };
}

/** Transforme { ecran, cible } en « #alerte/A-1033 ». */
export function ecrireAdresse(ecran, cible = null) {
  return cible ? `#${ecran}/${encodeURIComponent(cible)}` : `#${ecran}`;
}

/** Entrée de menu à mettre en évidence pour un écran donné. */
export function entreeMenu(ecran) {
  return ROUTES[ecran]?.parent || ecran;
}

/** Titre de l'onglet du navigateur. */
export function titrePage(ecran, cible) {
  const titre = ROUTES[ecran]?.titre || 'Écran introuvable';
  return cible ? `${titre} · ${cible} — SASI` : `${titre} — SASI`;
}
