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
