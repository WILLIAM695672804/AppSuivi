// Accès aux données depuis les écrans : contexte React et crochets de chargement.

import React, { createContext, useContext, useEffect, useState } from 'react';

const Contexte = createContext(null);

// Le serveur n'envoie aux écrans que les changements de niveau : les courbes,
// elles, se redemandent à intervalle régulier pour avancer avec les mesures.
const PERIODE_RAFRAICHISSEMENT_MS = 10000;

export function FournisseurDonnees({ donnees, children }) {
  return <Contexte.Provider value={donnees}>{children}</Contexte.Provider>;
}

export function useDonnees() {
  const donnees = useContext(Contexte);
  if (!donnees) throw new Error('Les données du site ne sont pas chargées.');
  return donnees;
}

/** Équipement par identifiant, avec un repli lisible si l'identifiant est inconnu. */
export function useEquipement(identifiant) {
  const D = useDonnees();
  return D.parId[identifiant] || { id: identifiant, nom: identifiant, zone: '—', famille: '—' };
}

/** Série de mesures d'un équipement. Renvoie null tant qu'elle n'est pas arrivée.
 *
 * La série se redemande toutes les dix secondes : la courbe avance donc avec
 * les mesures, sans jamais repasser par l'écran d'attente.
 */
export function useSerie(equipement, options) {
  const D = useDonnees();
  const [serie, setSerie] = useState(null);
  const clef = equipement ? `${equipement.id}|${JSON.stringify(options)}` : null;
  useEffect(() => {
    if (!equipement) return undefined;
    let vivant = true;
    setSerie(null);
    const demander = () => D.serie(equipement, options)
      .then((resultat) => { if (vivant) setSerie(resultat); })
      .catch(() => { if (vivant) setSerie((ancienne) => ancienne || { mesure: [], attendu: [] }); });
    demander();
    const minuteur = setInterval(demander, PERIODE_RAFRAICHISSEMENT_MS);
    return () => { vivant = false; clearInterval(minuteur); };
  }, [clef]);
  return serie;
}

/** Séries de plusieurs équipements, dans l'ordre de la liste. Rafraîchies de même. */
export function useSeries(liste, options) {
  const D = useDonnees();
  const [series, setSeries] = useState(null);
  const clef = liste.map((e) => e.id).join(',') + JSON.stringify(options);
  useEffect(() => {
    let vivant = true;
    setSeries(null);
    const demander = () => Promise.all(
      liste.map((e) => D.serie(e, options).catch(() => ({ mesure: [], attendu: [] }))),
    ).then((resultats) => { if (vivant) setSeries(resultats); });
    demander();
    const minuteur = setInterval(demander, PERIODE_RAFRAICHISSEMENT_MS);
    return () => { vivant = false; clearInterval(minuteur); };
  }, [clef]);
  return series;
}
