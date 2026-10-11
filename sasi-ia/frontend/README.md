# Interface SASI

Projet React (Vite) de l'interface de surveillance thermique : neuf écrans
construits avec le système visuel SASI.

## Installation (une seule fois, environ 250 Mo)

```bash
cd frontend
npm install
```

## Commandes

```bash
npm run dev        # http://localhost:5173, rechargement à chaud
npm test           # tests d'interface (Vitest)
npm run lint       # contrôle du code (ESLint)
npm run build      # produit dist/ pour la mise en production
npm run verifier   # lint + tests + build, avant de livrer
```

Sans rien installer, deux contrôles restent possibles depuis la racine du projet :

```bash
python3 outils/verifier_jsx.py frontend/src      # structure des fichiers JSX
node outils/verifier_services.mjs                # logique des services
```

## Organisation

```
src/
├── App.jsx              ossature : session, navigation, chargement, direct
├── main.jsx             point d'entrée ; fournit React au bundle du système
├── systeme.js           accès unique aux composants du système visuel
├── application.css      mise en page (aucune couleur en dur : que des jetons)
├── composants/          MenuLateral, BarreHaute, Panneau, EnAttente,
│                        ReglageSeuils, Onglets, ChampRecherche, LimiteErreur
├── ecrans/              un fichier par écran
│   ├── TableauDeBord.jsx      état du site, plan, alertes en cours
│   ├── SuiviTemperatures.jsx  courbes par zone et par équipement
│   ├── ListeAlertes.jsx       filtres, tri, actions en ligne, export
│   ├── FicheAlerte.jsx        raison, facteurs, action, courbe, clôture
│   ├── ListeEquipements.jsx   liste triable
│   ├── FicheEquipement.jsx    état, règle graduée, historique
│   ├── Rapports.jsx           indicateurs, graphique hachuré, impression
│   ├── Connexion.jsx          nom et rôle
│   ├── NonTrouve.jsx          adresse inconnue
│   └── administration/        onglets caméras, équipements, utilisateurs
├── services/            service (serveur ou exemple), routeur, session,
│                        mise en forme, données d'exemple
└── tests/               tests Vitest + composants simplifiés du système
```

## Source des données

L'interface interroge le serveur de l'application (`/api`, `/ws`). S'il ne répond
pas, elle bascule sur les données d'exemple et affiche un bandeau « Mode
démonstration ». Pour forcer la démonstration : `?source=exemple`.

En développement, `vite.config.js` transmet `/api` et `/ws` à
`http://localhost:8000` (le serveur FastAPI).

## Rôles

Le rôle choisi à la connexion détermine les actions proposées : technicien
(prendre en charge, clôturer), responsable sécurité (assigner, rapports,
astreintes), direction (rapports), administrateur (caméras, équipements,
utilisateurs). Les actions interdites ne sont pas affichées, jamais grisées.

## Le système visuel

`public/systeme/` contient les jetons, la feuille de style et le bundle des
composants, importés depuis l'artefact de design :

```bash
python3 ../outils/importer_systeme.py <dossier project/ du système>
cp ../web/systeme/{tokens.css,bundle.css,bundle.js} public/systeme/
```

Le bundle est un script classique qui attend `window.React` : `main.jsx` le
fournit avant de le charger.
