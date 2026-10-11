# Projet SASI — IA version 0 : résultats sur Site d'exemple — minoterie

Date : 23/09/2026 22:20

## Méthode

Un modèle par famille apprend la température normale de chaque équipement à partir de son contexte (charge, marche/arrêt, ambiance, temps depuis le démarrage, heure). Chaque équipement est ensuite calibré sur ses propres mesures. Les écarts persistants déclenchent une alerte (cahier des charges technique, chapitre 6).

- Entraînement : lot A, 14 jours de fonctionnement normal, aucune panne.
- Test : lot B, jamais vu, contenant 36 pannes.

## Erreur de prédiction par famille

| Famille | Erreur moyenne |
|---|---|
| ARM | 0.27 °C |
| CHD | 0.42 °C |
| MOT | 0.29 °C |
| POM | 0.29 °C |

## Résultats de détection

### Lot B — 36 pannes simulées

- Pannes connues : 36
- Pannes détectées : 36 (**100 %**, objectif ≥ 80 %)
- Alertes émises : 39
- Fausses alertes : 0 (**0 %**, objectif < 10 %)
- Délai médian de détection : 56 min

## Détail par panne

| Panne | Équipement | Type | Détectée | Délai |
|---|---|---|---|---|
| P-01 | Z4-ARM-01-B | point_chaud_phase | oui | 68 min |
| P-02 | Z3-ENS-01 | derive_lente | oui | 47 min |
| P-03 | Z4-SEC-01 | surchauffe_bruleur | oui | 10 min |
| P-04 | Z4-ARM-01-B | point_chaud_phase | oui | 106 min |
| P-05 | Z2-ASP-01 | derive_lente | oui | 36 min |
| P-06 | Z3-CNV-01 | montee_brutale | oui | 8 min |
| P-07 | Z4-ARM-01-B | point_chaud_phase | oui | 68 min |
| P-08 | Z4-CMP-01 | friction_roulement | oui | 67 min |
| P-09 | Z3-ENS-01 | derive_lente | oui | 42 min |
| P-10 | Z1-NET-01 | montee_brutale | oui | 9 min |
| P-11 | Z4-ARM-01-A | point_chaud_phase | oui | 62 min |
| P-12 | Z3-CNV-01 | friction_roulement | oui | 80 min |
| P-13 | Z1-ELV-01 | derive_lente | oui | 40 min |
| P-14 | Z2-MOU-01 | montee_brutale | oui | 7 min |
| P-15 | Z1-NET-01 | derive_lente | oui | 56 min |
| P-16 | Z4-ARM-01-C | point_chaud_phase | oui | 58 min |
| P-17 | Z2-MOU-01 | derive_lente | oui | 32 min |
| P-18 | Z4-ARM-01-A | point_chaud_phase | oui | 66 min |
| P-19 | Z1-NET-01 | derive_lente | oui | 54 min |
| P-20 | Z1-ELV-01 | friction_roulement | oui | 76 min |
| P-21 | Z3-CNV-01 | friction_roulement | oui | 76 min |
| P-22 | Z2-PLA-01 | montee_brutale | oui | 8 min |
| P-23 | Z4-ARM-01-A | point_chaud_phase | oui | 68 min |
| P-24 | Z4-SEC-01 | colmatage_filtre | oui | 123 min |
| P-25 | Z4-CMP-01 | friction_roulement | oui | 65 min |
| P-26 | Z2-ASP-01 | friction_roulement | oui | 70 min |
| P-27 | Z3-ENS-01 | friction_roulement | oui | 74 min |
| P-28 | Z2-MOU-01 | derive_lente | oui | 37 min |
| P-29 | Z4-ARM-01-C | point_chaud_phase | oui | 59 min |
| P-30 | Z4-CMP-01 | derive_lente | oui | 39 min |
| P-31 | Z1-ELV-01 | friction_roulement | oui | 75 min |
| P-32 | Z2-ASP-01 | derive_lente | oui | 34 min |
| P-33 | Z2-PLA-01 | montee_brutale | oui | 8 min |
| P-34 | Z4-ARM-01-C | point_chaud_phase | oui | 55 min |
| P-35 | Z4-SEC-01 | rupture_calorifuge | oui | 5 min |
| P-36 | Z2-PLA-01 | derive_lente | oui | 38 min |

## Exemples d'alertes expliquées

**URGENCE — Z4-ARM-01-B**

- Raison : La phase B de l'armoire est 13.4 °C plus chaud que d'habitude (43.5 °C mesurés pour 30.1 °C attendus) pour une ambiance de 30.3 °C depuis 9 h 41.
- Facteur : la charge des 30 dernières minutes diminue la température attendue de 4.1 °C
- Facteur : la charge diminue la température attendue de 3.4 °C
- Facteur : la chaleur ambiante diminue la température attendue de 1.3 °C
- Action conseillée : Vérifier la ventilation de l'armoire et la charge des départs.

**URGENCE — Z3-ENS-01**

- Raison : L'ensacheuse est 28.3 °C plus chaud que d'habitude (55.2 °C mesurés pour 26.9 °C attendus) pour une ambiance de 27.2 °C et la température monte encore de 0.13 °C par minute depuis 4 h 37.
- Facteur : la charge des 30 dernières minutes diminue la température attendue de 7.1 °C
- Facteur : le temps écoulé depuis l'arrêt diminue la température attendue de 2.9 °C
- Facteur : le bas de la plage normale de l'équipement diminue la température attendue de 1.7 °C
- Action conseillée : Contrôler les roulements et la lubrification ; vérifier l'alignement et la tension des courroies.

**URGENCE — Z4-SEC-01**

- Raison : Le séchoir à grain est 27.5 °C plus chaud que d'habitude (155.7 °C mesurés pour 128.2 °C attendus) pour une charge de 76 % et une ambiance de 35.3 °C et la température monte encore de 0.07 °C par minute depuis 1 h 27.
- Facteur : le temps écoulé depuis le démarrage augmente la température attendue de 22.4 °C
- Facteur : la charge des 30 dernières minutes augmente la température attendue de 11.5 °C
- Facteur : le temps écoulé depuis l'arrêt augmente la température attendue de 2.7 °C
- Action conseillée : Contrôler le brûleur, la régulation et l'évacuation des poussières.


## Limites

- Les données sont simulées par nos soins : elles suivent nos propres hypothèses.
- Un bon résultat prouve que la chaîne fonctionne, pas que l'IA réussira sur site.
- Étape suivante : rejouer cette évaluation sur les lots livrés par le jumeau numérique, puis sur les mesures d'un site réel.
