# Projet SASI — Inspection du raisonnement : Site pilote — brasserie

Date : 23/09/2026 12:44

Ce rapport ne mesure pas la détection des pannes (voir `rapport_sim01.md`) mais la justesse du raisonnement : sur quoi le modèle s'appuie, où il se trompe, et s'il raisonne dans le bon sens.

## 1. Où le modèle se trompe-t-il ?

L'erreur est l'écart entre la température prédite et la température réellement mesurée, en fonctionnement normal. Plus elle est faible, plus l'écart anormal ressort nettement le jour d'une panne.

| Famille | Erreur moyenne |
|---|---|
| ARM | 0.28 °C |
| CHD | 0.47 °C |
| MOT | 0.28 °C |
| POM | 0.34 °C |
| RES | 0.31 °C |

### Par équipement, du plus mal prédit au mieux prédit

| Équipement | Erreur | En régime établi | En transitoire | Biais | Pire écart |
|---|---|---|---|---|---|
| Z4-CHV-01 | 0.58 °C | 0.39 °C | 3.79 °C | +0.10 °C | 69.3 °C |
| Z2-CHE-01 | 0.50 °C | 0.37 °C | 2.71 °C | +0.05 °C | 40.3 °C |
| Z6-PCI-01 | 0.45 °C | 0.37 °C | 1.80 °C | +0.14 °C | 15.7 °C |
| Z3-GFG-01 | 0.37 °C | 0.37 °C | 0.31 °C | -0.22 °C | 7.7 °C |
| Z6-CUV-01 | 0.30 °C | 0.28 °C | 0.72 °C | -0.01 °C | 8.9 °C |
| Z5-PAS-01 | 0.29 °C | 0.27 °C | 0.64 °C | -0.01 °C | 5.9 °C |
| Z6-RES-01 | 0.29 °C | 0.27 °C | 0.53 °C | -0.00 °C | 13.7 °C |
| Z3-PTR-01 | 0.28 °C | 0.27 °C | 0.54 °C | -0.01 °C | 8.3 °C |
| Z1-ELV-01 | 0.28 °C | 0.28 °C | 0.36 °C | +0.00 °C | 3.5 °C |
| Z1-VIS-01 | 0.28 °C | 0.27 °C | 0.37 °C | -0.00 °C | 3.3 °C |
| Z4-ARM-01-C | 0.28 °C | 0.28 °C | 0.25 °C | -0.00 °C | 3.9 °C |
| Z4-ARM-01-B | 0.27 °C | 0.28 °C | 0.25 °C | +0.00 °C | 4.3 °C |
| Z7-CMP-01 | 0.27 °C | 0.27 °C | 0.26 °C | +0.01 °C | 2.0 °C |
| Z1-MOU-01 | 0.27 °C | 0.27 °C | 0.28 °C | -0.00 °C | 1.5 °C |
| Z4-ARM-01-A | 0.27 °C | 0.27 °C | 0.24 °C | -0.00 °C | 2.7 °C |
| Z5-CNV-01 | 0.26 °C | 0.26 °C | 0.29 °C | +0.00 °C | 1.6 °C |
| Z5-ETQ-01 | 0.26 °C | 0.26 °C | 0.29 °C | -0.00 °C | 2.1 °C |

Un **biais** franchement positif signifie que le modèle sous-estime cet équipement : il le croit plus froid qu'il n'est, et risque donc d'alerter à tort. Un biais négatif est l'inverse, et retarde la détection.

Une erreur bien plus forte **en transitoire** qu'en régime établi est normale : la montée en température est le moment le plus difficile à prédire. C'est pourquoi le calibrage distingue les deux régimes.

## 2. Sur quoi s'appuie-t-il ?

Part de chaque information dans les décisions du modèle. Une entrée à 0 % ne sert à rien ; une entrée écrasante mérite qu'on vérifie qu'elle est bien mesurée sur le terrain.

**ARM**

- la charge des 30 dernières minutes : 34.7 %
- la chaleur ambiante : 22.7 %
- l'heure de la journée : 16.1 %
- la charge : 14.0 %
- le temps écoulé depuis l'arrêt : 4.6 %
- le temps écoulé depuis le démarrage : 4.2 %
- le jour de la semaine : 1.4 %
- la montée en température en cours : 1.4 %
- le refroidissement en cours : 0.8 %

**CHD**

- la chaleur ambiante : 39.5 %
- la charge des 30 dernières minutes : 23.9 %
- le bas de la plage normale de l'équipement : 15.2 %
- le temps écoulé depuis le démarrage : 6.0 %
- le temps écoulé depuis l'arrêt : 4.6 %
- l'heure de la journée : 3.6 %
- la charge : 3.1 %
- le haut de la plage normale de l'équipement : 2.0 %
- le refroidissement en cours : 1.1 %
- la montée en température en cours : 0.7 %

**MOT**

- la charge des 30 dernières minutes : 50.6 %
- la chaleur ambiante : 17.8 %
- le temps écoulé depuis le démarrage : 10.1 %
- l'heure de la journée : 7.2 %
- le bas de la plage normale de l'équipement : 5.1 %
- le haut de la plage normale de l'équipement : 3.8 %
- le temps écoulé depuis l'arrêt : 2.4 %
- la charge : 1.6 %
- la montée en température en cours : 0.8 %

**POM**

- la chaleur ambiante : 41.8 %
- le bas de la plage normale de l'équipement : 29.9 %
- la charge : 9.9 %
- la charge des 30 dernières minutes : 8.9 %
- le temps écoulé depuis le démarrage : 3.8 %
- l'heure de la journée : 2.7 %
- le temps écoulé depuis l'arrêt : 2.0 %
- le haut de la plage normale de l'équipement : 0.5 %

**RES**

- l'heure de la journée : 46.9 %
- la chaleur ambiante : 36.5 %
- le temps écoulé depuis l'arrêt : 6.6 %
- le temps écoulé depuis le démarrage : 5.0 %
- la charge des 30 dernières minutes : 2.7 %
- la charge : 1.6 %

## 3. Raisonne-t-il dans le bon sens ?

On fait varier une seule information à la fois, toutes choses égales par ailleurs, et on regarde si la température attendue évolue comme le bon sens l'exige. Un « À L'ENVERS » est une anomalie à corriger : le modèle a appris une relation fausse, souvent faute de données variées.

| Équipement | Ce qui varie | Attendu | Réponse du modèle | Verdict |
|---|---|---|---|---|
| Z1-ELV-01 | la charge | plus la machine est chargée, plus elle doit chauffer | 59.9 °C → 65.8 °C (+5.9) | conforme |
| Z1-ELV-01 | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | 60.1 °C → 57.9 °C (-2.2) | À L'ENVERS |
| Z1-ELV-01 | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 57.2 °C → 61.3 °C (+4.1) | conforme |
| Z1-ELV-01 | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 57.4 °C → 50.1 °C (-7.3) | conforme |
| Z1-VIS-01 | la charge | plus la machine est chargée, plus elle doit chauffer | 59.9 °C → 65.8 °C (+5.9) | conforme |
| Z1-VIS-01 | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | 60.1 °C → 57.9 °C (-2.2) | À L'ENVERS |
| Z1-VIS-01 | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 57.2 °C → 61.3 °C (+4.1) | conforme |
| Z1-VIS-01 | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 57.4 °C → 50.1 °C (-7.3) | conforme |
| Z1-MOU-01 | la charge | plus la machine est chargée, plus elle doit chauffer | 32.0 °C → 33.8 °C (+1.7) | conforme |
| Z1-MOU-01 | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | 31.4 °C → 32.2 °C (+0.8) | conforme |
| Z1-MOU-01 | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 31.5 °C → 31.8 °C (+0.3) | conforme |
| Z1-MOU-01 | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 31.4 °C → 31.5 °C (+0.1) | insensible |
| Z2-CHE-01 | la charge | plus la machine est chargée, plus elle doit chauffer | 218.8 °C → 235.0 °C (+16.2) | conforme |
| Z2-CHE-01 | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | 182.7 °C → 214.6 °C (+32.0) | conforme |
| Z2-CHE-01 | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 175.7 °C → 211.9 °C (+36.2) | conforme |
| Z2-CHE-01 | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 182.8 °C → 151.1 °C (-31.6) | conforme |
| Z3-GFG-01 | la charge | plus la machine est chargée, plus elle doit chauffer | 19.3 °C → 34.0 °C (+14.7) | conforme |
| Z3-GFG-01 | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | situation absente des données | jamais observé |
| Z3-GFG-01 | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 31.8 °C → 32.8 °C (+1.0) | conforme |
| Z3-GFG-01 | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 31.8 °C → 28.2 °C (-3.5) | conforme |
| Z3-PTR-01 | la charge | plus la machine est chargée, plus elle doit chauffer | 41.3 °C → 44.3 °C (+3.0) | conforme |
| Z3-PTR-01 | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | situation absente des données | jamais observé |
| Z3-PTR-01 | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 37.0 °C → 39.9 °C (+2.9) | conforme |
| Z3-PTR-01 | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 37.1 °C → 33.0 °C (-4.0) | conforme |
| Z4-CHV-01 | la charge | plus la machine est chargée, plus elle doit chauffer | 97.2 °C → 199.6 °C (+102.4) | conforme |
| Z4-CHV-01 | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | 205.2 °C → 202.4 °C (-2.8) | À L'ENVERS |
| Z4-CHV-01 | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 142.6 °C → 178.2 °C (+35.6) | conforme |
| Z4-CHV-01 | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 148.8 °C → 126.5 °C (-22.3) | conforme |
| Z4-ARM-01-A | la charge | plus la machine est chargée, plus elle doit chauffer | 33.2 °C → 35.1 °C (+1.9) | conforme |
| Z4-ARM-01-A | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | 34.0 °C → 34.7 °C (+0.6) | conforme |
| Z4-ARM-01-A | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 32.8 °C → 33.4 °C (+0.6) | conforme |
| Z4-ARM-01-A | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 33.1 °C → 33.0 °C (-0.1) | insensible |
| Z4-ARM-01-B | la charge | plus la machine est chargée, plus elle doit chauffer | 33.2 °C → 35.1 °C (+1.9) | conforme |
| Z4-ARM-01-B | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | 34.0 °C → 34.7 °C (+0.6) | conforme |
| Z4-ARM-01-B | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 32.8 °C → 33.4 °C (+0.6) | conforme |
| Z4-ARM-01-B | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 33.1 °C → 33.0 °C (-0.1) | insensible |
| Z4-ARM-01-C | la charge | plus la machine est chargée, plus elle doit chauffer | 33.2 °C → 35.1 °C (+1.9) | conforme |
| Z4-ARM-01-C | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | 34.0 °C → 34.7 °C (+0.6) | conforme |
| Z4-ARM-01-C | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 32.8 °C → 33.4 °C (+0.6) | conforme |
| Z4-ARM-01-C | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 33.1 °C → 33.0 °C (-0.1) | insensible |
| Z5-ETQ-01 | la charge | plus la machine est chargée, plus elle doit chauffer | 43.6 °C → 44.5 °C (+0.9) | conforme |
| Z5-ETQ-01 | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | 43.2 °C → 44.4 °C (+1.2) | conforme |
| Z5-ETQ-01 | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 43.1 °C → 44.1 °C (+1.0) | conforme |
| Z5-ETQ-01 | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 43.0 °C → 42.8 °C (-0.3) | insensible |
| Z5-PAS-01 | la charge | plus la machine est chargée, plus elle doit chauffer | 65.0 °C → 66.7 °C (+1.7) | conforme |
| Z5-PAS-01 | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | 62.7 °C → 65.0 °C (+2.3) | conforme |
| Z5-PAS-01 | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 68.3 °C → 64.6 °C (-3.6) | À L'ENVERS |
| Z5-PAS-01 | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 70.7 °C → 48.6 °C (-22.1) | conforme |
| Z5-CNV-01 | la charge | plus la machine est chargée, plus elle doit chauffer | 43.6 °C → 44.5 °C (+0.9) | conforme |
| Z5-CNV-01 | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | 43.2 °C → 44.4 °C (+1.2) | conforme |
| Z5-CNV-01 | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 43.1 °C → 44.1 °C (+1.0) | conforme |
| Z5-CNV-01 | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 43.0 °C → 42.8 °C (-0.3) | insensible |
| Z6-CUV-01 | la charge | plus la machine est chargée, plus elle doit chauffer | 91.0 °C → 89.3 °C (-1.6) | À L'ENVERS |
| Z6-CUV-01 | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | situation absente des données | jamais observé |
| Z6-CUV-01 | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 78.9 °C → 89.8 °C (+10.9) | conforme |
| Z6-CUV-01 | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 80.9 °C → 58.8 °C (-22.1) | conforme |
| Z6-RES-01 | la charge | plus la machine est chargée, plus elle doit chauffer | situation absente des données | jamais observé |
| Z6-RES-01 | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | situation absente des données | jamais observé |
| Z6-RES-01 | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 32.2 °C → 70.7 °C (+38.5) | conforme |
| Z6-RES-01 | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 32.0 °C → 29.5 °C (-2.6) | conforme |
| Z6-PCI-01 | la charge | plus la machine est chargée, plus elle doit chauffer | 46.1 °C → 51.1 °C (+5.0) | conforme |
| Z6-PCI-01 | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | situation absente des données | jamais observé |
| Z6-PCI-01 | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 41.6 °C → 46.3 °C (+4.7) | conforme |
| Z6-PCI-01 | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 40.8 °C → 34.7 °C (-6.1) | conforme |
| Z7-CMP-01 | la charge | plus la machine est chargée, plus elle doit chauffer | 35.9 °C → 40.4 °C (+4.5) | conforme |
| Z7-CMP-01 | la chaleur ambiante | plus l'air est chaud, plus l'équipement doit être chaud | 38.5 °C → 38.0 °C (-0.5) | À L'ENVERS |
| Z7-CMP-01 | le temps écoulé depuis le démarrage | une machine qui vient de démarrer est plus froide qu'après une heure | 35.7 °C → 37.8 °C (+2.1) | conforme |
| Z7-CMP-01 | le temps écoulé depuis l'arrêt | une machine arrêtée depuis longtemps doit être plus froide | 35.7 °C → 32.2 °C (-3.6) | conforme |

**50 contrôles conformes, 6 sans effet, 6 jamais observés, 6 à l'envers.**

Un « jamais observé » n'est pas un défaut du modèle mais un trou dans les données : la situation ne s'est pas présentée pendant la période d'apprentissage. Si elle peut survenir sur le site, il faut allonger cette période ou la provoquer pendant un essai.

Raisonnements à corriger :

- **Z1-ELV-01** — plus l'air est chaud, plus l'équipement doit être chaud : le modèle fait l'inverse (-2.2 °C).
- **Z1-VIS-01** — plus l'air est chaud, plus l'équipement doit être chaud : le modèle fait l'inverse (-2.2 °C).
- **Z4-CHV-01** — plus l'air est chaud, plus l'équipement doit être chaud : le modèle fait l'inverse (-2.8 °C).
- **Z5-PAS-01** — une machine qui vient de démarrer est plus froide qu'après une heure : le modèle fait l'inverse (-3.6 °C).
- **Z6-CUV-01** — plus la machine est chargée, plus elle doit chauffer : le modèle fait l'inverse (-1.6 °C).
- **Z7-CMP-01** — plus l'air est chaud, plus l'équipement doit être chaud : le modèle fait l'inverse (-0.5 °C).

## 4. Ses pires moments

Les mesures que le modèle explique le plus mal, en fonctionnement normal. Si elles se concentrent sur un équipement ou sur un régime, la cause est là.

| Horodatage | Équipement | Régime | Mesurée | Attendue | Écart | Charge |
|---|---|---|---|---|---|---|
| 17/01 06:17 | Z4-CHV-01 | etabli | 199.3 °C | 130.0 °C | +69.3 °C | 63 % |
| 17/01 06:17 | Z4-CHV-01 | etabli | 199.3 °C | 130.0 °C | +69.3 °C | 63 % |
| 17/01 06:17 | Z4-CHV-01 | etabli | 199.2 °C | 130.0 °C | +69.2 °C | 63 % |
| 17/01 06:17 | Z4-CHV-01 | etabli | 199.2 °C | 130.0 °C | +69.2 °C | 63 % |
| 17/01 06:17 | Z4-CHV-01 | etabli | 198.9 °C | 130.0 °C | +68.9 °C | 63 % |
| 17/01 06:17 | Z4-CHV-01 | etabli | 198.8 °C | 130.0 °C | +68.8 °C | 63 % |
| 08/01 06:00 | Z4-CHV-01 | etabli | 193.1 °C | 127.8 °C | +65.3 °C | 57 % |
| 08/01 06:00 | Z4-CHV-01 | etabli | 192.8 °C | 127.8 °C | +65.0 °C | 57 % |

## Comment corriger

| Symptôme | Où agir |
|---|---|
| Un équipement mal prédit, biais marqué | sa plage dans `sites/sim01.json` : une plage fausse trompe le modèle |
| Un contrôle « à l'envers » | les données d'entraînement ne couvrent pas assez de situations : allonger la période d'apprentissage |
| Une entrée à 0 % | la retirer de `ENTREES` (ia/chaine.py) : elle encombre le modèle |
| Erreur forte en transitoire seulement | augmenter `MINUTES_TRANSITOIRE` (ia/chaine.py) |
| Trop de fausses alertes | relever les seuils d'entrée ou allonger les confirmations (`SEUILS_ENTREE`, `CONFIRMATION_S` dans ia/detection.py) |
| Détection trop tardive | abaisser les mêmes seuils, ou la criticité de l'équipement |
