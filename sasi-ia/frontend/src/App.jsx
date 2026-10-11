// Ossature de l'application : session, navigation, chargement des données, direct.

import React, { useCallback, useEffect, useRef, useState } from 'react';

import BarreHaute from './composants/BarreHaute.jsx';
import EnAttente from './composants/EnAttente.jsx';
import LimiteErreur from './composants/LimiteErreur.jsx';
import MenuLateral from './composants/MenuLateral.jsx';
import Administration from './ecrans/administration/index.jsx';
import Connexion from './ecrans/Connexion.jsx';
import FicheAlerte from './ecrans/FicheAlerte.jsx';
import FicheEquipement from './ecrans/FicheEquipement.jsx';
import ListeAlertes from './ecrans/ListeAlertes.jsx';
import ListeEquipements from './ecrans/ListeEquipements.jsx';
import NonTrouve from './ecrans/NonTrouve.jsx';
import Rapports from './ecrans/Rapports.jsx';
import SuiviTemperatures from './ecrans/SuiviTemperatures.jsx';
import TableauDeBord from './ecrans/TableauDeBord.jsx';
import { FournisseurDonnees } from './services/donnees.jsx';
import { ecrireAdresse, entreeMenu, lireAdresse, titrePage } from './services/routeur.js';
import { chargerTout, choisirSource, convertirAlerte } from './services/service.js';
import { fermerSession, lireSession, ouvrirSession } from './services/session.js';
import { StatusBanner } from './systeme.js';

const DELAI_AFFICHAGE_MS = 250;

const ECRANS = {
  tableau: TableauDeBord,
  suivi: SuiviTemperatures,
  alertes: ListeAlertes,
  alerte: FicheAlerte,
  equipements: ListeEquipements,
  equipement: FicheEquipement,
  rapports: Rapports,
  administration: Administration,
  introuvable: NonTrouve,
};

export default function App() {
  const depart = lireAdresse();
  const [ecran, setEcran] = useState(depart.ecran);
  const [cible, setCible] = useState(depart.cible);
  const [session, setSession] = useState(() => lireSession());
  const [theme, setTheme] = useState(
    new URLSearchParams(window.location.search).get('theme') || 'light');
  const [donnees, setDonnees] = useState(null);
  const [erreur, setErreur] = useState(null);
  const [liaison, setLiaison] = useState(false);
  const [version, setVersion] = useState(0);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  useEffect(() => {
    document.title = titrePage(ecran, cible);
  }, [ecran, cible]);

  // Le bouton « retour » du navigateur doit fonctionner.
  useEffect(() => {
    const surRetour = () => {
      const adresse = lireAdresse();
      setEcran(adresse.ecran);
      setCible(adresse.cible);
    };
    window.addEventListener('hashchange', surRetour);
    return () => window.removeEventListener('hashchange', surRetour);
  }, []);

  // Le direct peut envoyer plusieurs messages par seconde : on ne réaffiche
  // qu'au rythme de l'œil, sans quoi le navigateur passe son temps à dessiner.
  const attenteAffichage = useRef(null);
  const rafraichir = useCallback(() => {
    if (attenteAffichage.current) return;
    attenteAffichage.current = setTimeout(() => {
      attenteAffichage.current = null;
      setVersion((n) => n + 1);
    }, DELAI_AFFICHAGE_MS);
  }, []);

  useEffect(() => () => clearTimeout(attenteAffichage.current), []);

  // Chargement des données : serveur si disponible, sinon exemple.
  useEffect(() => {
    if (!session) return undefined;
    let vivant = true;
    let arreter = () => {};
    choisirSource()
      .then(chargerTout)
      .then((chargees) => {
        if (!vivant) return;
        setDonnees(chargees);
        setLiaison(chargees.mode === 'serveur');
        const seDesabonner = chargees.abonner(rafraichir);
        const arreterDirect = chargees.ecouter(
          (message) => {
            if (message.type === 'niveaux') chargees.appliquerNiveaux(message.niveaux);
            if (message.type === 'alerte' && message.alerte) {
              chargees.appliquerAlerte(convertirAlerte(message.alerte));
            }
            if (message.type === 'technique' && message.alerte) {
              chargees.alerteTechnique = message.alerte;
            }
            if (message.type === 'erreur') chargees.derniereErreur = message.message;
            rafraichir();
          },
          (etat) => setLiaison(etat));
        arreter = () => { seDesabonner(); arreterDirect(); };
      })
      .catch((e) => { if (vivant) setErreur(e.message || String(e)); });
    return () => { vivant = false; arreter(); };
  }, [session, rafraichir]);

  const aller = useCallback((nom, identifiant = null) => {
    setEcran(nom);
    setCible(identifiant);
    window.location.hash = ecrireAdresse(nom, identifiant);
    window.scrollTo(0, 0);
  }, []);

  if (!session) {
    return (
      <Connexion surConnexion={(nom, role) => setSession(ouvrirSession(nom, role))} />
    );
  }

  if (erreur) {
    return (
      <div className="application application-simple">
        <StatusBanner kind="technique" title="Données indisponibles">{erreur}</StatusBanner>
      </div>
    );
  }
  if (!donnees) {
    return (
      <div className="application application-simple">
        <EnAttente hauteur={200} libelle="Chargement des données du site…" />
      </div>
    );
  }

  const Ecran = ECRANS[ecran] || NonTrouve;

  return (
    <FournisseurDonnees donnees={{ ...donnees, session, version }}>
      {/* Surtout pas de « key » variable ici : elle remonterait tout l'arbre à
          chaque mesure reçue, et les écrans rechargeraient leurs courbes sans fin. */}
      <div className="application">
        <MenuLateral ecran={entreeMenu(ecran)} aller={aller} session={session}
          nbAlertes={donnees.alertes.length} />
        <main>
          <BarreHaute
            nomSite={donnees.nomSite}
            mode={donnees.mode}
            liaison={liaison}
            theme={theme}
            session={session}
            basculerTheme={() => setTheme(theme === 'light' ? 'dark' : 'light')}
            seDeconnecter={() => { fermerSession(); setSession(null); setDonnees(null); }}
          />
          {donnees.mode === 'exemple' && (
            <StatusBanner kind="demonstration" title="Mode démonstration">
              Le serveur n’est pas joignable : les écrans affichent des données d’exemple.
            </StatusBanner>
          )}
          <LimiteErreur key={ecran + (cible || '')}>
            <Ecran id={cible} aller={aller} />
          </LimiteErreur>
        </main>
      </div>
    </FournisseurDonnees>
  );
}
