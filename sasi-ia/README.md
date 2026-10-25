# Projet SASI — IA version 0

Première étape du projet : valider la méthode de détection sur des données publiques,
sans matériel, sans jumeau numérique et sans partenaire.

**En service depuis le 25/10/2026 sur `https://sasi.the7ing.site`.** Les
commandes du serveur — connexion, état, mise à jour, pannes courantes — sont
dans **`MEMENTO.md`**, une ligne par commande. L'installation complète est dans
`DEPLOIEMENT.md`, les décisions et les pannes rencontrées dans `JOURNAL.md`.

## Ce que fait le programme

1. Télécharge deux jeux de données publics (SKAB et NAB).
2. Apprend la **température normale** d'un équipement à partir de son contexte de
   fonctionnement (courant, tension, pression, débit, heure).
3. Signale les écarts persistants, selon les règles du cahier des charges technique
   (chapitre 6) : trois signaux, un score, quatre niveaux, confirmation et hystérésis.
4. Compare ses alertes aux pannes réellement connues et écrit un rapport chiffré.

## Installation (à faire une seule fois)

```bash
cd "/home/william/Documents/project de surveillance/sasi-ia"

# 1. Environnement Python isolé
python3 -m venv venv

# 2. Bibliothèques indispensables (environ 30 Mo)
#    --timeout 300 : indispensable sur une connexion lente
./venv/bin/pip install --timeout 300 --retries 20 numpy
./venv/bin/pip install --timeout 300 --retries 20 pandas

# 3. Jeux de données (environ 20 à 30 Mo)
python3 outils/telecharger_donnees.py
```

### Plus tard, quand la connexion le permet (facultatif)

LightGBM rend le modèle plus précis, mais il entraîne scipy (35 Mo). Sans lui, le
programme bascule tout seul sur un modèle de repli.

```bash
./venv/bin/pip install --timeout 300 --retries 20 lightgbm
```

Si le téléchargement échoue encore, récupérer le fichier avec `wget -c`, qui reprend
là où il s'est arrêté :

```bash
# la commande affiche l'adresse exacte du fichier à télécharger
./venv/bin/pip download --no-deps --timeout 300 -d paquets scipy
# en cas d'échec, reprendre le téléchargement interrompu :
wget -c <adresse affichée> -P paquets/
./venv/bin/pip install paquets/*.whl
```

## Où consigner quoi

`JOURNAL.md` est le carnet de bord, écrit à la main : décisions, essais
abandonnés, avis d'un professionnel du site. Rien ne l'écrase.

Les fichiers de `resultats/` sont **régénérés à chaque exécution** : n'y écrivez
jamais de note, elle serait perdue au prochain `lancer_site.py`.

## Utilisation

```bash
# 1. Tous les tests
python3 tests/lancer_tests.py            # 138 tests, sans rien installer
./venv/bin/python tests/lancer_tests.py  # 152 tests, entraînement compris

# 1 bis. Chaîne complète en un seul programme, sans serveur de messages ni base
python3 outils/verifier_chaine.py        # 21 contrôles : connecteur → IA → alertes → écrans

# 2. Produire les données d'un site (mini jumeau numérique)
./venv/bin/python outils/simulateur.py              # site par défaut : brasserie
./venv/bin/python outils/simulateur.py minoterie    # un autre secteur
# → lot A (30 jours sains), lots B et C (30 jours, 60 pannes chacun, tirages différents)

# 2 bis. Composer un autre catalogue de pannes
./venv/bin/python outils/scenarios.py brasserie --jours 30 --pannes 60
./venv/bin/python outils/scenarios.py --montrer          # sans rien écrire

# 3. Chaîne complète : entraînement, détection, évaluation, rapport
./venv/bin/python lancer_site.py
./venv/bin/python lancer_site.py minoterie
./venv/bin/python lancer_site.py brasserie C      # second lot d'essai, tirage indépendant

# 3 bis. Éprouver l'IA sur une situation que vous choisissez
./venv/bin/python outils/essayer.py Z2-CHE-01 --situation montee --vitesse 2
./venv/bin/python outils/essayer.py Z2-CHE-01 --toutes

# 3 ter. Inspecter le raisonnement de l'IA (également depuis l'interface : Administration › Modèle)
./venv/bin/python outils/inspecter.py brasserie
./venv/bin/python outils/inspecter.py brasserie --sans heure   # éprouver une correction

# 4. Scénario « départ de feu d'une chaudière » (SPE-AI-ENG-042) : 150 feux, 150 marches saines
./venv/bin/python lancer_chaudiere.py

# 5. Contrôle sur les jeux publics (facultatif)
./venv/bin/python lancer.py
```

Les rapports sont écrits dans `resultats/`.

## Valeurs normales et seuils

Les plages et les seuils du site pilote viennent du document « Valeur normale et
seuil des équipements » (22/09/2026). Chaque équipement peut porter ses propres
seuils (`seuil_inspection`, `seuil_urgence`) ; sinon la règle par défaut s'applique
(plage haute + 15 °C et + 30 °C). Les valeurs douteuses portent une `remarque`
dans `sites/brasserie.json`.

## Changer de site ou de secteur

Aucune modification du code n'est nécessaire : tout est décrit dans un fichier du
dossier `sites/`. Deux exemples sont livrés, `brasserie.json` (17 équipements,
7 zones) et `minoterie.json` (12 équipements, 4 zones).

Un fichier de site contient : les zones, les familles, le planning de production,
le climat local, la liste des équipements (plage normale, temps de mise en
température, criticité, action conseillée) et des pannes d'exemple. Le fichier est
vérifié au chargement : un champ manquant ou une valeur incohérente est refusée
avec un message clair.

## Résultats obtenus (20/09/2026)

Entraînement sur 14 jours de fonctionnement normal, test sur 6 jours jamais vus
contenant 12 pannes :

| Indicateur | Résultat | Objectif |
|---|---|---|
| Pannes détectées (brasserie) | 12 / 12 (100 %) | ≥ 80 % |
| Pannes détectées (minoterie) | 6 / 6 (100 %) | ≥ 80 % |
| Fausses alertes | 5 épisodes en 6 jours, pour 17 zones | aucune référence encore |
| Délai médian de détection | 34 minutes | — |
| Erreur de prédiction | 0,29 à 0,40 °C selon la famille | ≤ 1,5 °C |

Chaque alerte est accompagnée de sa raison en français, des facteurs qui expliquent
la température attendue et d'une action conseillée.

Les données étant simulées par nos soins, ces chiffres prouvent que la chaîne
fonctionne, pas que l'IA réussira sur site.

### Jeux publics : un enseignement utile

SKAB et NAB ne conviennent pas à notre cas : dans SKAB les anomalies sont
hydrauliques et **refroidissent** souvent l'équipement, et NAB ne fournit aucune
donnée de contexte. Ils restent utiles comme contrôle de méthode, mais pas comme
mesure de performance.

## L'interface

Deux versions coexistent :

| Version | Pour quoi | Installation |
|---|---|---|
| `frontend/` | **Le vrai projet** : React, JSX, un fichier par écran, session et rôles, tests Vitest, ESLint | `npm install` (≈ 250 Mo) |
| `web/` | Démonstration immédiate, sans rien installer | aucune |

```bash
cd frontend
npm install          # une seule fois
npm run dev          # http://localhost:5173
npm run build        # produit dist/ pour la mise en production
```

Deux contrôles restent possibles sans rien installer :

```bash
python3 outils/verifier_jsx.py frontend/src      # structure des fichiers JSX
node outils/verifier_services.mjs                # logique des services (28 contrôles)
```

## Voir la démonstration sans installation

Sept écrans construits avec le système visuel SASI, sur des données d'exemple :

```bash
# aucun serveur nécessaire
google-chrome "web/index.html"        # ou firefox, ou double-clic
```

L'interface choisit sa source toute seule : le serveur de l'application s'il répond,
sinon les données d'exemple, avec un bandeau « Mode démonstration ». Pour forcer
l'exemple : `?source=exemple`.

Chaque écran a son adresse : `web/index.html#alertes`, `#alerte/A-1033`,
`#equipement/Z1-ELV-01`, `#suivi`, `#rapports`, `#administration`.
Le thème sombre se règle par le bouton en haut à droite, ou par `?theme=dark`.

Le système visuel (jetons, composants, bundle) est importé depuis l'artefact de
design ; pour le mettre à jour :

```bash
python3 outils/importer_systeme.py <dossier project/ du système>
```

## Administrer le modèle depuis l'interface

Trois onglets, tous réservés au droit administrateur :

| Onglet | Ce qu'on y fait |
|---|---|
| **Modèle** | version en service, erreur par famille, évaluation, réentraînement, historique des versions |
| **Raisonnement** | contrôles de bon sens, où le modèle se trompe, sur quoi il s'appuie, ses pires moments |
| **Banc d'essai** | soumettre une situation (montée, palier, retour à la normale, démarrage) et voir la réaction pas à pas |

Les mêmes calculs restent accessibles en ligne de commande — `outils/inspecter.py`
et `outils/essayer.py` — pour qui préfère le terminal.


`Administration › Modèle` (droit administrateur) montre la version en service, son
erreur par famille, ce que le modèle regarde et sa dernière évaluation. Le bouton
**Réentraîner** lance le travail en arrière-plan : la surveillance continue, l'écran
suit l'avancement étape par étape, et la nouvelle version **n'entre pas en service
d'elle-même**. C'est une décision humaine, prise au vu de la comparaison :

| Version | Erreur | Détection |
|---|---|---|
| v3 | 0,35 °C | 12/12 pannes · 7 fausses |
| v2 | 0,35 °C | 12/12 pannes · 7 fausses |
| v1 | 0,35 °C | non évaluée |

La mise en service copie les fichiers de la version choisie et publie une demande
de rechargement sur `sasi/<site>/modele` : le service IA reprend les modèles sans
interruption, et les alertes en cours sont conservées. Revenir à la version
précédente se fait de la même façon.

## Conserver l'historique : la base de données

Sans base, tout vit en mémoire et disparaît à l'arrêt des services. Avec elle,
mesures, prédictions, alertes et comptes rendus sont conservés, et l'application
les relit au démarrage.

```bash
# PostgreSQL seul : suffit pour développer, 80 Mo si l'image n'est pas déjà là
docker compose --profile legere up -d base-legere
export SASI_BASE="postgresql://sasi:sasi@localhost:5434/sasi"

# verser la description du site : sans elle, aucune mesure ne peut entrer
./venv/bin/python outils/initialiser_base.py
./venv/bin/python outils/initialiser_base.py --verifier   # compter sans rien écrire

# puis démarrer comme d'habitude : la base est détectée toute seule
./outils/demonstration.sh
```

`TimescaleDB` (service `base`, 550 Mo) reste la cible pour la production : elle
découpe les tables de mesures, les compresse après sept jours et les purge après
un an. Le schéma s'adapte à ce qui est installé et le dit au démarrage.

La base ne doit jamais empêcher d'alerter : si une écriture échoue, l'incident est
noté dans le journal et la chaîne continue.

## Mettre le système en service (quand les outils seront installés)

Tout est écrit et prêt. Il reste à installer la pile prévue au cahier des charges :

```bash
# une seule commande démarre l'ensemble
docker compose up -d

# puis, dans une autre fenêtre : produire des mesures en direct
./venv/bin/python outils/direct.py brasserie --panne 300
```

L'application s'ouvre ensuite sur http://localhost:8000 et la documentation des
services sur http://localhost:8000/docs. L'adresse `/api/etat` indique à quoi le
serveur est relié (serveur de messages, base) : c'est le premier endroit à
regarder au démarrage.

### Qui parle à qui

| Sujet du serveur de messages | Émetteur | Destinataire |
|---|---|---|
| `sasi/<site>/<camera>/mesures` | jumeau numérique, caméras | connecteur |
| `sasi/<site>/contexte` | jumeau numérique | connecteur, service IA |
| `sasi/<site>/interne/mesures_validees` | connecteur | service IA |
| `sasi/<site>/interne/niveaux` | service IA | service des alertes |
| `sasi/<site>/alertes` | service des alertes | application (écrans) |
| `sasi/<site>/niveaux` | service des alertes | application (écrans) |
| `sasi/<site>/commandes` | application | service des alertes |
| `sasi/<site>/interne/alertes_techniques` | connecteur | application (écrans) |

Le service des alertes décide seul : il ouvre, escalade et clôture. Le serveur de
l'application en garde une copie pour répondre vite aux écrans et lui transmet les
actions des équipes (prise en charge, assignation, clôture, mise en maintenance).
Sans serveur de messages, l'application applique ces actions localement : la
démonstration reste utilisable.

### Où en est la détection

| Jeu d'essai | Pannes | Détectées | Fausses alertes | Délai médian |
|---|---|---|---|---|
| Brasserie, lot B (30 jours) | 60 | **60** | 19 | 39 min |
| Brasserie, lot C (30 jours, autre tirage) | 60 | **60** | 28 | 38 min |
| Minoterie, lot B (14 jours) | 36 | **36** | 0 | 56 min |
| Chaudière, spécification SPE-AI-ENG-042 | 150 | **150** | 0 sur 150 marches saines | 33 min d'anticipation |

L'écart entre les lots B et C — 19 fausses alertes contre 28, sur des jeux
équivalents — est l'enseignement de ce second tirage : une mesure faite sur un
seul jeu de données ne dit pas grand-chose. C'est pour cela que le lot C existe.

**Deux précautions**, apprises à nos dépens (voir `JOURNAL.md`) :

- l'intensité d'une panne doit avoir un plancher physique, sans quoi les
  équipements à plage étroite reçoivent des pannes de trois degrés que personne
  ne pourrait voir ;
- le catalogue doit couvrir la durée du **lot d'essai**, pas celle de
  l'apprentissage : une panne datée au-delà n'apparaît dans aucune mesure et
  compte ensuite comme manquée. Le simulateur le signale désormais.

### Les scénarios de panne

Dix signatures thermiques, décrites dans `sites/<site>.json` et reproduites par
`outils/simulateur.py`. Les quatre dernières reprennent le journal des incidents
du guide d'audit terrain (AUD-IA-BRASS-01, fiche REL-DATA-04) :

| Type | Ce qui se passe | Étiquette du document |
|---|---|---|
| `derive_lente` | montée régulière sur plusieurs heures | — |
| `montee_brutale` | bond de température en quelques minutes | — |
| `point_chaud_phase` | une phase d'armoire chauffe plus que ses jumelles | — |
| `chauffe_a_vide` | résistance immergée sans liquide : plus de refroidissement | — |
| `defaut_refroidissement` | palier haut installé | — |
| `derive_froid` | un groupe froid qui ne tient plus sa consigne | — |
| `colmatage_filtre` | dérive qui s'aggrave : moins d'air, moins de refroidissement | 0,5 — dérive lente |
| `surchauffe_bruleur` | montée sévère en vingt minutes, puis palier | 1 — anomalie sévère |
| `rupture_calorifuge` | la paroi perd son isolation : bond en deux minutes | 2 — départ d'incident |
| `friction_roulement` | la friction produit la chaleur qui l'aggrave | — |

### Voir les écrans bouger

```bash
./outils/demonstration.sh                 # remise à zéro, démarrage, flux en direct
./outils/demonstration.sh brasserie 180   # une panne toutes les trois minutes
```

Le script arrête les services, les relance (leur mémoire repart vide : détecteurs,
alertes, courbes), puis lance `outils/direct.py`, un jumeau qui produit les mesures
en temps réel et déclenche une panne à intervalle régulier. L'interface montre
alors la température monter, l'alerte apparaître, puis tout rentrer dans l'ordre.

Deux sources de mesures, à ne pas confondre :

| Programme | Ce qu'il fait | Quand l'employer |
|---|---|---|
| `outils/direct.py` | produit les mesures à l'heure courante, sans fichier | démonstration, mise au point |
| `outils/rejeu.py` | rediffuse un lot enregistré (`donnees/`) | comparer deux versions sur les mêmes données |

`rejeu.py --maintenant` redate le lot pour qu'il se termine à l'instant présent :
sans cela, les courbes de l'interface, qui n'affichent que les dernières heures,
resteraient vides. Le rejeu accéléré ne convient pas au direct : ses horodatages
prendraient de l'avance sur l'horloge, et le connecteur les écarterait.

Sans base de données, le serveur garde en mémoire les dernières heures de mesures
jugées (sujet `interne/jugements`) : les courbes fonctionnent dès le premier
démarrage, mais rien n'est conservé à l'arrêt.

Sans Docker, les mêmes composants se lancent à la main :

```bash
sudo apt install mosquitto mosquitto-clients        # serveur de messages
./venv/bin/pip install -r requirements-app.txt      # paho-mqtt, psycopg, fastapi…
psql -U sasi -d sasi -f base/schema.sql             # tables TimescaleDB

./venv/bin/python -m connecteur.main                # réception et contrôles
./venv/bin/python -m ia.service                     # IA en continu
./venv/bin/python -m alertes.service                # alertes, escalade, SMS
./venv/bin/uvicorn api.serveur:app --port 8000      # application
```

## Organisation des fichiers

```
sasi-ia/
├── ia/
│   ├── detection.py      signaux, score, niveaux d'alerte (Python seul)
│   ├── chaine.py         chaîne complète sur les lots A et B
│   ├── site.py           lecture et vérification d'un fichier de site
│   ├── explication.py    raison de l'alerte, facteurs, action conseillée
│   ├── controles.py      mesures aberrantes, caméras muettes ou figées
│   ├── donnees.py        chargement des jeux publics, mise au format commun
│   ├── entrainement.py   modèle LightGBM de température attendue, calibrage
│   └── evaluation.py     taux de détection, fausses alertes, délais
├── outils/
│   ├── simulateur.py     mini jumeau numérique (lots A et B)
│   └── telecharger_donnees.py
├── tests/
│   ├── lancer_tests.py     lance tous les tests
│   ├── test_site.py        12 tests
│   ├── test_detection.py   9 tests
│   ├── test_explication.py 11 tests
│   ├── test_controles.py   15 tests
│   ├── test_evaluation.py  9 tests
│   ├── test_simulateur.py  11 tests
│   ├── test_connecteur.py  8 tests
│   ├── test_moteur_alertes.py 16 tests
│   └── test_entrainement.py 6 tests (nécessite numpy et pandas)
├── donnees/              jeux téléchargés
├── modeles/              modèles entraînés
├── resultats/            rapports
├── connecteur/           réception des mesures, contrôles, écriture en base
│   ├── main.py           porte d'entrée (MQTT)
│   ├── depot.py          écriture dans PostgreSQL / TimescaleDB
│   └── adaptateurs/      jumeau, Modbus (vraies caméras)
├── alertes/
│   ├── moteur.py         vie d'une alerte, escalade, anti-rafale
│   └── service.py        notifications et SMS
├── api/
│   ├── serveur.py        services de l'application (FastAPI, WebSocket)
│   └── registre.py       copie de l'état, commandes vers le service des alertes
├── integration/          kit remis à l'équipe du jumeau numérique
│   ├── README.md         le contrat : sujets, messages, règles, vérifications
│   ├── contrat.py        le même contrat, exécutable (Python seul)
│   ├── verificateur.py   écoute un émetteur et dit ce qui cloche
│   ├── emetteur_reference.py  publie un flux conforme, à comparer au sien
│   ├── referentiel.py    liste de référence des équipements, source unique
│   └── schemas/          les six messages en JSON Schema (autres langages)
├── ia/risque.py          probabilité d'atteindre le seuil dangereux, et son explication
├── ia/retours.py         corrections du terrain : fausses alertes, échauffements manqués
├── ia/travaux.py         entraînements lancés depuis l'application, en arrière-plan
├── ia/modeles_en_service.py  versions des modèles, mise en service, retour arrière
├── frontend/             projet React (Vite) : 9 écrans, tests, linting
│   ├── src/ecrans/       un fichier par écran + administration/ (6 onglets)
│   ├── src/composants/   menu, barre, panneau, attente, règle, onglets, erreurs
│   ├── src/services/     serveur ou exemple, routeur, session et droits, format
│   ├── src/tests/        tests Vitest des services et des écrans
│   └── public/systeme/   système visuel SASI (jetons, bundle)
├── web/                  démonstration sans installation (mêmes écrans, sans compilation)
│   ├── index.html        page unique
│   ├── app.js            les écrans, avec les composants du système visuel
│   ├── service.js        source des données : serveur ou exemple
│   ├── donnees-exemple.js jeu d'essai (17 équipements, 5 alertes, rapports)
│   ├── application.css   mise en page (aucune couleur en dur)
│   └── systeme/          système visuel SASI importé (jetons, bundle, React)
├── base/schema.sql       tables PostgreSQL + TimescaleDB
├── config/               mosquitto.conf, Dockerfile, réglages des caméras
├── docker-compose.yml    démarrage de tout le système
├── sites/                description des sites (brasserie.json, minoterie.json)
├── lancer_site.py        chaîne complète sur un site simulé
├── outils/rejeu.py       rejoue un lot comme s'il venait des caméras
├── outils/verifier_chaine.py  chaîne complète dans un seul programme
├── outils/inspecter.py   justesse du raisonnement (erreurs, appuis, bon sens)
├── outils/essayer.py     banc d'essai : une situation, la réaction de l'IA pas à pas
├── outils/scenarios.py   compose le catalogue de pannes d'un site
├── outils/initialiser_base.py  verse la description d'un site dans la base
├── outils/direct.py      jumeau numérique en direct (mesures en temps réel)
├── outils/demonstration.sh  remise à zéro, démarrage, flux en direct
├── lancer.py             contrôle sur les jeux publics
└── requirements.txt
```

## Points de conception

- **`detection.py` n'utilise que Python.** Il tournera tel quel sur le boîtier du site,
  et ses tests s'exécutent sans rien installer.
- **La température passée n'est jamais une entrée du modèle** : il recopierait la dérive
  au lieu de la détecter.
- **Découpage chronologique** des données : on teste toujours sur des périodes jamais vues.
- **La vitesse de montée n'est prise en compte que si la température dépasse déjà
  l'attendu**, sinon un simple démarrage de machine déclencherait une alerte.
- **Réglages de la détection** : en tête de `ia/detection.py` (seuils, confirmation,
  hystérésis, criticité).
- **Les confirmations sont exprimées en durée**, jamais en nombre de mesures : le
  comportement reste le même à 10 secondes ou à la minute.
- **La vitesse de montée est comparée à la vitesse attendue** : une chaudière qui
  monte normalement de 8 °C/min ne déclenche rien.
- **Le calibrage n'utilise que des mesures jamais vues à l'entraînement**, sinon les
  écarts tolérés seraient trop serrés et le système alerterait à tort.

## État d'avancement

| Composant | État |
|---|---|
| Détection, explications, contrôles | Écrit et testé |
| Simulateur, chaîne d'entraînement et d'évaluation | Écrit et exécuté |
| Moteur d'alertes | Écrit et testé (16 tests) |
| Connecteur | Écrit et testé (8 tests, sans serveur de messages) |
| Service IA en continu, service des alertes | Écrits, **jamais exécutés** (attendent MQTT) |
| Base de données et serveur d'application | Écrits, **jamais exécutés** (attendent PostgreSQL et FastAPI) |
| Interface : 7 écrans | Écrite et **vérifiée à l'écran** ; branchée sur le serveur, avec repli sur les données d'exemple |

## Étape suivante

Quand le lot A du jumeau numérique sera livré : reprendre le même code, en remplaçant
`ia/donnees.py` par la lecture des fichiers du cahier des scénarios, avec un modèle
par famille d'équipements.
