// Session : rôle de la personne connectée et droits associés.
//
// Règle du système visuel : on affiche seulement les actions permises au rôle,
// on ne grise pas ce qui est interdit (voir « Interaction et accessibilité »).

export const ROLES = {
  technicien: {
    libelle: 'Technicien',
    droits: ['voir', 'prendre_en_charge', 'cloturer'],
  },
  securite: {
    libelle: 'Responsable sécurité',
    droits: ['voir', 'prendre_en_charge', 'cloturer', 'assigner', 'rapports',
      'maintenance', 'abonnements'],
  },
  direction: {
    libelle: 'Direction',
    droits: ['voir', 'rapports'],
  },
  administrateur: {
    libelle: 'Administrateur',
    droits: ['voir', 'administrer', 'abonnements', 'maintenance'],
  },
};

const CLEF = 'sasi.session';

export function lireSession() {
  try {
    const brut = localStorage.getItem(CLEF);
    if (!brut) return null;
    const session = JSON.parse(brut);
    return ROLES[session.role] ? session : null;
  } catch (erreur) {
    return null;
  }
}

export function ouvrirSession(nom, role) {
  const session = { nom, role, depuis: Date.now() };
  try { localStorage.setItem(CLEF, JSON.stringify(session)); } catch (erreur) { /* mode privé */ }
  return session;
}

export function fermerSession() {
  try { localStorage.removeItem(CLEF); } catch (erreur) { /* mode privé */ }
}

export function peut(session, droit) {
  if (!session) return false;
  return (ROLES[session.role]?.droits || []).includes(droit);
}

export function libelleRole(session) {
  return session ? ROLES[session.role]?.libelle ?? session.role : '';
}
