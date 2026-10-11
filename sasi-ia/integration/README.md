# Kit d'intégration du jumeau numérique

À l'usage de la personne chargée du jumeau numérique. Objectif : publier un flux
que SASI accepte sans retouche, et le vérifier soi-même avant toute mise en
commun.

Contrat **1.1**. Il prolonge le document *Conventions jumeau numérique SASI* 1.0
du 19/09/2026, dont il corrige les écarts relevés à l'implantation (voir la
dernière section).

## En trois commandes

```bash
# 1. récupérer la liste de référence des équipements
curl http://localhost:8000/api/referentiel > referentiel.json

# 2. voir à quoi ressemble un flux conforme (ici 5 min simulées en 3 s)
./venv/bin/python integration/emetteur_reference.py --duree-min 5 --facteur 100

# 3. vérifier son propre jumeau pendant deux minutes
./venv/bin/python integration/verificateur.py --duree 120
```

Le vérificateur sort avec le code 0 si rien ne cloche, 1 sinon : il s'emploie
tel quel dans une chaîne d'intégration continue.

## Ce qui circule

Serveur de messages MQTT, port 1883, `qos=1`. `<site>` est l'identifiant du site
— `SIM01` pour le site pilote. Charges utiles en JSON, encodage UTF-8.

| Sens | Sujet | Cadence |
|---|---|---|
| jumeau → SASI | `sasi/<site>/<camera>/mesures` | 10 s par caméra |
| jumeau → SASI | `sasi/<site>/contexte` | à chaque changement, au moins 60 s |
| jumeau → SASI | `sasi/<site>/jumeau/pannes` | un message au début, un à la fin |
| jumeau → SASI | `sasi/<site>/jumeau/horloge` | au lancement d'un scénario |
| SASI → jumeau | `sasi/<site>/alertes` | à chaque création ou changement d'état |
| SASI → jumeau | `sasi/<site>/niveaux` | à chaque changement de niveau |

Les sujets `sasi/<site>/interne/…` sont le trafic interne de SASI : ne rien y
publier, ne rien en attendre.

### Mesures

```json
{ "site": "SIM01", "camera": "CAM-Z1", "horodatage": "2026-09-19T14:30:10Z",
  "source": "jumeau",
  "zones": [ { "equipement": "Z1-ELV-01", "t_max": 52.4, "t_moy": 45.0, "t_min": 38.1 } ] }
```

`source` vaut `jumeau` ou `camera` : une mesure simulée ne doit jamais pouvoir
passer pour une mesure réelle. La caméra du message et celle du sujet doivent
coïncider. `t_max` est la seule valeur exploitée par l'IA ; `t_moy` et `t_min`
sont conservées pour l'affichage.

### Contexte

```json
{ "site": "SIM01", "horodatage": "2026-09-19T14:30:10Z",
  "equipements": [ { "equipement": "Z1-ELV-01", "etat": "marche", "charge_pct": 75 } ],
  "ambiance": [ { "zone": 1, "t_ambiante": 31.5, "humidite_pct": 78 } ] }
```

Sans ce flux, aucun écart n'est interprétable : une armoire à 45 °C est normale à
pleine charge et anormale à l'arrêt. `etat` vaut `marche` ou `arret`.

### Journal des pannes

```json
{ "id_panne": "P-0042", "equipement": "Z1-ELV-01", "type": "derive_lente",
  "evenement": "debut", "horodatage": "2026-09-19T15:00:00Z", "intensite": 8.0,
  "description": "Roulement usé : +0,3 °C par minute" }
```

C'est la vérité de référence du contrôle automatique : sans elle, impossible de
dire si l'IA a détecté une panne ou si elle a crié dans le vide. Le connecteur
rapproche le début et la fin de même `id_panne` et écrit
`donnees/<site>/journal_jumeau.csv`, directement exploitable par l'évaluation.
Une panne commencée sans fin n'y figure pas : sa fenêtre n'existe pas encore.

Signatures reconnues : `derive_lente`, `montee_brutale`, `point_chaud_phase`,
`chauffe_a_vide`, `defaut_refroidissement`, `friction_roulement`,
`colmatage_filtre`, `surchauffe_bruleur`, `rupture_calorifuge`, `derive_froid`.
Une signature inconnue est acceptée, mais comptée à part.

### Horloge

```json
{ "site": "SIM01", "mode": "accelere", "facteur": 168,
  "scenario": "normal-4-semaines", "debut_scenario": "2026-09-19T06:00:00Z" }
```

`mode` vaut `reel` ou `accelere`. **Les horodatages des messages portent toujours
l'heure simulée, jamais celle de l'ordinateur** : le connecteur s'aligne sur
l'horloge des données dès qu'elle s'écarte de plus d'une heure de la sienne,
sans quoi toutes les caméras seraient déclarées muettes.

### Alertes et niveaux, en retour

```json
{ "id": "A-0107", "equipement": "Z1-ELV-01", "niveau": "inspection",
  "etat": "ouverte", "debut": 1789000000.0, "t_mesuree": 68.0, "t_attendue": 50.0,
  "raison": "18 °C de plus que d'habitude à ce régime, en hausse depuis 40 min" }
```

```json
{ "niveaux": { "Z1-ELV-01": "inspection", "Z1-VIS-01": "normal" } }
```

Niveaux, du plus calme au plus grave : `normal`, `information`, `surveillance`,
`inspection`, `urgence` — couleurs conseillées sur la maquette : vert, bleu,
jaune, orange, rouge. États d'une alerte :
`ouverte` → `acquittee` → `assignee` → `cloturee`.

## Règles qui font échouer un message

| Règle | Défaut signalé |
|---|---|
| Identifiant `Z<zone>-<CODE>-<nn>`, lettre finale pour les sous-zones (`Z4-ARM-01-A`) | `equipement_hors_nomenclature` |
| Équipement présent dans la liste de référence | `equipement_inconnu` |
| Heure universelle `2026-09-19T14:30:10Z` — les secondes Unix sont acceptées | `horodatage_mal_forme` |
| Température entre −30 et 1000 °C, une décimale, point décimal | `valeur_hors_plage` |
| `t_min ≤ t_moy ≤ t_max` | `temperatures_incoherentes` |
| Valeur absente à `null`, **jamais à 0** — un zéro passerait pour une mesure | `valeur_illisible` |
| `etat` parmi `marche`, `arret` | `etat_inconnu` |
| Caméra du message identique à celle du sujet | `camera_incoherente` |

Au-delà de 10 min sans mesure, une caméra est déclarée muette ; au-delà de
30 min sans la moindre variation, figée. Une mesure en avance de plus d'une
minute sur l'horloge est rejetée ; en retard de plus de 5 min, acceptée mais
signalée.

## Vérifications communes

| N° | Vérification | Résultat attendu |
|---|---|---|
| V-01 | Une heure de mesures sur les 7 caméras | Les 17 équipements apparaissent, aucun nom inconnu |
| V-02 | Scénario « normal-4-semaines » | Moins d'une alerte injustifiée sur dix |
| V-03 | Scénario « pannes-mixtes » | Au moins 8 pannes sur 10 détectées, délai mesuré |
| V-04 | Une alerte est créée dans l'application | L'équipement change de couleur sur la maquette |
| V-05 | Un même scénario lancé deux fois | Données identiques |
| V-06 | Une mesure contient un champ à `null` | Aucune erreur, valeur ignorée |
| V-07 | Le jumeau est arrêté puis relancé | L'application signale l'interruption, puis reprend |

V-01, V-05 et V-06 sont vérifiées automatiquement par `tests/test_integration.py`.

## Contenu du kit

| Fichier | Rôle |
|---|---|
| `contrat.py` | Le contrat sous forme exécutable : nomenclature, bornes, codes de défaut |
| `verificateur.py` | Écoute un émetteur et dit précisément ce qui cloche |
| `emetteur_reference.py` | Publie un flux conforme, à copier ou à comparer |
| `referentiel.py` | Charge la liste de référence : service HTTP, fichier, ou site local |
| `referentiel_SIM01.json` | La liste du site pilote, exportée |

`contrat.py` n'utilise que la bibliothèque standard : il se copie tel quel dans
un autre projet. Les tests vérifient qu'il ne s'écarte pas du code — les sujets,
les bornes de température et les signatures de panne y sont comparés aux
constantes réelles du connecteur, de la détection et du générateur de scénarios.
Un contrat qui dérive de l'implantation est pire qu'un contrat absent : il fait
chercher la panne du mauvais côté.

Hors ligne, sans serveur de messages :

```bash
./venv/bin/python integration/emetteur_reference.py --duree-min 5 --facteur 1000 \
    --sortie flux.jsonl
./venv/bin/python integration/verificateur.py --fichier flux.jsonl
```

## Écarts avec le document *Conventions* 1.0

| Point | Document 1.0 | Contrat 1.1 — ce que le code fait |
|---|---|---|
| Nombre d'équipements | 15 | **17** : les armoires `Z4-ARM-01` comptent trois phases (`-A`, `-B`, `-C`) |
| Identifiant d'alerte | `id_alerte` | `id` — `id_alerte` reste accepté en lecture |
| `debut` d'une alerte | ISO 8601 | **secondes Unix** ; les mesures restent en ISO |
| Horodatage des mesures | ISO 8601 | ISO 8601 **ou** secondes Unix |
| `sasi/<site>/niveaux` | avec `horodatage` | sans `horodatage`, champ facultatif |
| Signatures de panne | 5 | **10**, le générateur en produit dix |

Toute modification de ce contrat passe par une nouvelle version de ce fichier et
des tests correspondants.
