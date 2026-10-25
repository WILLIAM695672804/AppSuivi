# Projet SASI — Carnet de bord de l'IA

Ce fichier est écrit **à la main**. Rien ne l'écrase, contrairement aux rapports
de `resultats/`, régénérés à chaque exécution.

On y consigne ce qu'aucun programme ne peut deviner : pourquoi une décision a été
prise, ce qu'un professionnel du site a dit d'un seuil, ce qu'on a essayé et
abandonné. Les chiffres, eux, restent dans les rapports.

## Où écrire quoi

| Ce que vous voulez noter | Où | Qui l'écrit |
|---|---|---|
| « cette alerte était fausse, c'était un nettoyage à la vapeur » | l'application, à la clôture de l'alerte | l'équipe, depuis l'écran |
| « le système a raté cet échauffement du 12 mars » | fiche de l'équipement, bouton « Signaler un échauffement non détecté » | l'équipe, depuis l'écran |
| « pourquoi on a changé les seuils », « ce que le chaudiériste a dit » | **ce fichier** | vous |
| erreur du modèle, pannes détectées, délais | `resultats/rapport_<site>.md` | le programme, à chaque `lancer_site.py` |
| ce sur quoi le modèle s'appuie, où il se trompe | `resultats/inspection_<site>.md` | le programme, à chaque `outils/inspecter.py` |
| versions du modèle, laquelle est en service | `modeles/<site>/versions.json` | le programme, à chaque entraînement |
| corrections venues du terrain | `retours/<site>.json` | le programme, d'après les clôtures |

Une remarque de ce carnet ne modifie rien toute seule : elle explique. Pour qu'une
correction atteigne le modèle, il faut passer par l'application (clôture ou
signalement) ou par un fichier de réglage (`sites/<site>.json`, `ia/detection.py`).

## Comment écrire une entrée

Une date, un titre, ce qui a été constaté, ce qui a été décidé, et par qui.
Les plus récentes en haut.

---

## 25/10/2026 — Première mise en service : trois pannes, une seule famille

**Constaté.** La pile de production, validée statiquement — 222 tests, deux
compositions relues par `docker compose config`, compatibilité ARM64 vérifiée
composant par composant — n'avait jamais été **exécutée**. Son premier
démarrage sur le VPS Netcup a révélé trois pannes, toutes dans le quart d'heure.

| Panne | Cause | Ce qui la rendait invisible |
|---|---|---|
| `sasi-ia` : `No module named 'lightgbm'` | la ligne était commentée dans `requirements.txt` | le commentaire annonçait un repli automatique, qui existe à l'entraînement et non au chargement des modèles en service |
| `sasi-jumeau` : `Connection refused` | `--serveur` avait pour défaut `localhost` | ce défaut l'emportait sur `SASI_MQTT=mosquitto` ; le jumeau cherchait le serveur de messages dans son propre conteneur |
| `sasi-ia` : `libgomp.so.1: cannot open shared object file` | LightGBM est compilé avec OpenMP | la roue installée par pip ne déclare pas cette bibliothèque, qui n'est pas un paquet Python ; l'image `slim` ne la porte pas |

**Ce qu'elles ont en commun.** Aucune n'est une erreur de logique, et aucune
n'était détectable par un test : ce sont trois hypothèses sur l'environnement,
vraies sur le poste de développement, fausses dans un conteneur. Une
bibliothèque installée depuis longtemps dans le `venv` et qu'on a crue
optionnelle. Un défaut d'argument commode en local. Une dépendance système que
la machine de développement portait déjà, pour une autre raison.

**Décidé.** Deux tests verrouillent ce qui peut l'être : aucun outil n'impose
plus `localhost` en défaut sur `--serveur`, et `outils/deployer.sh` refuse un
`SASI_SITE` qui ne corresponde pas à un fichier `sites/<nom>.json`. Le reste
tient aux images, désormais exactes.

**Aussi.** Le relevé d'état mentait : `curl -f` tenait le `401` du mot de passe
pour un échec et annonçait « pas encore de réponse » alors que le certificat
était obtenu. Un contrôle qui se trompe sur un succès est pire qu'une absence
de contrôle — il aurait envoyé chercher une panne ailleurs.

**La leçon tient.** « Un code qui n'a jamais tourné contre une vraie base ne
fonctionne pas : il attend seulement de rencontrer ses erreurs. » Trois pannes
annoncées, trois pannes rencontrées, un quart d'heure pour les lever. La réserve
avait été dite avant le départ ; c'est ce qui a rendu la séance tranquille.

## 23/09/2026 — Prévision du risque : le seuil visé

**Constaté.** La probabilité d'atteindre le seuil d'**urgence** ne devançait
jamais la détection par l'écart : sur 881 280 mesures, elle n'a pas haussé un
seul niveau que le score n'avait pas déjà atteint.

**Essayé.** Viser le seuil d'**inspection** plutôt que celui d'urgence.

| Seuil visé | Pannes | Fausses alertes | Délai médian |
|---|---|---|---|
| Urgence | 12/12 | 7 | 38 min |
| Inspection | 12/12 | 9 | 24 min |

**Décidé.** On vise le seuil d'inspection (`CIBLE_RISQUE` dans `ia/detection.py`).
Quatorze minutes gagnées valent deux fausses alertes de plus. À revoir quand les
équipes diront si ces deux alertes les gênent.

## 23/09/2026 — La prévision ne part qu'après une anomalie constatée

**Constaté.** En extrapolant toute montée de température, chaque démarrage de
chaudière était annoncé comme un emballement : **70 fausses alertes au lieu de 7**.

**Décidé.** Le risque ne se calcule qu'à partir d'une anomalie constatée — écart
anormal, ou température de sécurité déjà franchie. D'abord constater, ensuite
prévoir. Retour immédiat à 7 fausses alertes.

## 23/09/2026 — L'horizon de prévision ne dépend pas du niveau d'alerte

**Constaté.** Faire dépendre l'horizon du niveau en cours créait une boucle : le
niveau dépend de la probabilité, qui dépendrait de l'horizon, qui dépendrait du
niveau. Le chiffre se mettait à osciller sans qu'aucune température ne bouge.

**Décidé.** L'horizon ne tient compte que de l'inertie de l'équipement et de sa
criticité. La température et la distance au seuil agissent déjà à l'intérieur du
calcul.

## 23/09/2026 — Deux lots d'essai valent mieux qu'un

**Constaté.** Sur deux jeux équivalents produits par le même générateur, les
fausses alertes passent de 14 (lot B) à 27 (lot C). Une mesure faite sur un seul
jeu ne dit pas grand-chose.

**Décidé.** Le simulateur produit désormais un lot C, à évaluer systématiquement :
`./venv/bin/python lancer_site.py brasserie C`.

## 23/09/2026 — La chaudière vapeur reste mal prédite

**Constaté.** `Z4-CHV-01` est l'équipement le plus mal prédit du site : erreur
moyenne 0,58 °C contre 0,26 à 0,33 ailleurs, et un pire écart de +69 °C en
fonctionnement normal. C'est aussi le seul équipement dont une panne a échappé à
la détection (P-13, colmatage de filtre) : sa dispersion calibrée est si large
qu'une dérive lente s'y noie.

**À faire.** Comprendre d'où vient cette erreur. Piste : le régime de la chaudière
vapeur dépend d'une consigne que le modèle ne connaît pas (allure du brûleur,
consigne vapeur en bar — voir la fiche REL-CHAUD-01 du guide d'audit).

## 22/09/2026 — Seuils du relevé terrain à faire valider

**Constaté.** Trois valeurs du document *VALEUR NORMALE ET SEUIL DES ÉQUIPEMENTS*
paraissent douteuses au regard du climat de Douala :

- moulin à malt : 20–35 °C avec seuil à 35 °C, alors que l'ambiance dépasse
  souvent 32 °C — trois fausses alertes s'expliquent par là ;
- armoires électriques : 15–35 °C, impossible dans une chaufferie ;
- pompes de transfert : −7 °C, valeur probablement recopiée de la jaquette glycol.

**À faire.** Faire confirmer ou corriger par un professionnel du site. Tant que ce
n'est pas tranché, les chiffres restent ceux du document.

## 23/09/2026 — Un mois de données, soixante pannes

**Fait.** Les lots passent de 10 à **30 jours**, et le catalogue de 24 à
**60 pannes** couvrant les dix signatures et les dix-sept équipements
(`outils/scenarios.py`, nouveau). Volume : 802 Mo pour la brasserie seule.

**Premier résultat.** 54/60 détectées (90 %), 19 fausses alertes sur 93 épisodes.
La proportion de fausses alertes tombe de 35 % à **20 %** : plus le modèle
apprend longtemps, mieux il distingue le normal de l'anormal.

**Constaté ensuite.** Cinq des six pannes manquées frappaient le même
équipement, le pasteurisateur `Z5-PAS-01`. Ce n'était pas une faiblesse de l'IA
mais du générateur de scénarios : l'intensité était calculée en proportion de la
plage normale, et le pasteurisateur travaille entre 60 et 67 °C. Une
« surchauffe de brûleur » y valait 3 °C — moins que l'écart habituel de
l'équipement. Personne n'aurait rien vu, et surtout pas une machine.

**Décidé.** Chaque signature de panne porte désormais un **plancher physique** :
une surchauffe de brûleur fait au moins 25 °C, une rupture de calorifuge 15 °C,
un défaut de refroidissement 10 °C. La proportion ne s'applique qu'au-delà.

**Résultat après correction.** **60/60 pannes détectées (100 %)**, 19 fausses
alertes, délai médian ramené de 70 à **39 min**. Les six pannes manquées
n'étaient donc pas manquées : elles n'existaient pas vraiment.

| Étape | Pannes | Détectées | Fausses | Délai médian |
|---|---|---|---|---|
| 10 jours, 24 pannes | 24 | 23 | 14 (35 %) | 42 min |
| 30 jours, 60 pannes, intensités proportionnelles | 60 | 54 | 19 (20 %) | 70 min |
| 30 jours, 60 pannes, intensités planchées | 60 | **60** | 19 (20 %) | **39 min** |

**Second piège, sur la minoterie.** 24 pannes sur 36 seulement. Les douze
manquées étaient les douze dernières du catalogue : il couvrait 20 jours alors
que le lot d'essai n'en fait que 14. Ces pannes n'apparaissaient dans aucune
mesure. Catalogue régénéré sur 14 jours : **36/36, aucune fausse alerte**. Le
simulateur signale désormais toute panne datée après la fin du lot.

**Leçon à retenir.** Un jeu d'essai mal construit mesure ses propres défauts et
non ceux du système. Avant de conclure qu'une IA rate une panne, il faut vérifier
que la panne était détectable — et qu'elle a bien eu lieu.

## 11/10/2026 — La persistance, et trois défauts qu'elle a révélés

**Fait.** Le projet est en ligne (github.com/WILLIAM695672804/AppSuivi) et la
base de données fonctionne. Mesures, prédictions, contexte, alertes, événements
et comptes rendus sont conservés ; l'application les relit au démarrage.

**Décidé en chemin.** L'image TimescaleDB (550 Mo) ne passait pas sur la
connexion : le téléchargement a échoué deux fois. Le schéma accepte désormais
PostgreSQL seul — sans compression ni purge automatique, mais tout le reste
fonctionne. TimescaleDB reste la cible pour la production.

**Trois défauts, tous invisibles sans base réelle.**

1. Le dépôt ne savait pas convertir un horodatage en secondes, alors que le
   moteur d'alertes ne produit que cela. Le service des alertes plantait à la
   première alerte — silencieusement, puisque l'exception remontait dans la
   bibliothèque MQTT.
2. Cette erreur d'écriture interrompait le traitement de l'alerte. Prévenir une
   équipe passe avant conserver un historique : les écritures sont maintenant
   tentées sans jamais bloquer, et l'échec est noté.
3. Après un redémarrage, la numérotation repartait à `A-0001` et **écrasait en
   base l'alerte de la veille** portant ce numéro. Elle reprend désormais après
   le dernier numéro enregistré.

**Leçon.** Un code qui n'a jamais tourné contre une vraie base ne fonctionne
pas : il attend seulement de rencontrer ses erreurs.

## 11/10/2026 — Le kit du jumeau, et deux promesses non tenues

**Fait.** L'équipe du jumeau numérique dispose désormais de tout ce qu'il lui
faut pour travailler sans nous : un contrat exécutable, un vérificateur qu'elle
lance contre son propre jumeau, un émetteur de référence à comparer au sien, et
les six messages en JSON Schema si elle travaille en C# ou en JavaScript.

**Constaté en l'écrivant.** Le document *Conventions* annonçait deux sujets que
personne n'écoutait : `jumeau/pannes` et `jumeau/horloge`. Le journal des pannes
— la vérité de référence du contrôle automatique — ne pouvait venir que d'un
fichier produit par notre propre simulateur. Autrement dit, nous savions
contrôler l'IA sur nos données, pas sur les leurs.

**Décidé.** Les deux messages sont reçus. Les deux publications du jumeau (un
début, une fin) sont rapprochées en `donnees/<site>/journal_jumeau.csv`, au
format que l'évaluation lit déjà. Le service `/api/referentiel` est devenu
conforme au chapitre 6.6 : les noms n'ont plus qu'une source.

**Décidé aussi.** Les tests comparent le contrat aux constantes réelles du
connecteur, de la détection et du générateur de scénarios. Ajouter une signature
de panne sans mettre le contrat à jour fait désormais échouer les tests.

**Leçon.** Un contrat qui s'éloigne de l'implantation est pire qu'un contrat
absent : il fait chercher la panne du mauvais côté. Les écarts assumés avec le
document 1.0 sont consignés en fin de `integration/README.md` — dix-sept
équipements et non quinze, `debut` en secondes, dix signatures de panne.
