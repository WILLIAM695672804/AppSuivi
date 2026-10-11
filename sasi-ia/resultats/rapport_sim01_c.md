# Projet SASI — IA version 0 : résultats sur Site pilote — brasserie

Date : 23/09/2026 22:13

## Méthode

Un modèle par famille apprend la température normale de chaque équipement à partir de son contexte (charge, marche/arrêt, ambiance, temps depuis le démarrage, heure). Chaque équipement est ensuite calibré sur ses propres mesures. Les écarts persistants déclenchent une alerte (cahier des charges technique, chapitre 6).

- Entraînement : lot A, 14 jours de fonctionnement normal, aucune panne.
- Test : lot C, jamais vu, contenant 60 pannes.

## Erreur de prédiction par famille

| Famille | Erreur moyenne |
|---|---|
| ARM | 0.28 °C |
| CHD | 0.42 °C |
| MOT | 0.28 °C |
| POM | 0.29 °C |
| RES | 0.49 °C |

## Résultats de détection

### Lot C — 60 pannes simulées

- Pannes connues : 60
- Pannes détectées : 60 (**100 %**, objectif ≥ 80 %)
- Alertes émises : 104
- Fausses alertes : 28 (**27 %**, objectif < 10 %)
- Délai médian de détection : 38 min

## Détail par panne

| Panne | Équipement | Type | Détectée | Délai |
|---|---|---|---|---|
| P-01 | Z6-CUV-01 | colmatage_filtre | oui | 126 min |
| P-02 | Z4-ARM-01-C | point_chaud_phase | oui | 142 min |
| P-03 | Z3-PTR-01 | friction_roulement | oui | 77 min |
| P-04 | Z5-ETQ-01 | derive_lente | oui | 38 min |
| P-05 | Z6-RES-01 | chauffe_a_vide | oui | 2 min |
| P-06 | Z5-ETQ-01 | derive_lente | oui | 38 min |
| P-07 | Z5-CNV-01 | montee_brutale | oui | 9 min |
| P-08 | Z2-CHE-01 | colmatage_filtre | oui | 182 min |
| P-09 | Z3-GFG-01 | derive_froid | oui | 92 min |
| P-10 | Z4-CHV-01 | defaut_refroidissement | oui | 14 min |
| P-11 | Z1-ELV-01 | montee_brutale | oui | 6 min |
| P-12 | Z4-CHV-01 | surchauffe_bruleur | oui | 15 min |
| P-13 | Z5-CNV-01 | montee_brutale | oui | 8 min |
| P-14 | Z5-PAS-01 | surchauffe_bruleur | oui | 8 min |
| P-15 | Z3-GFG-01 | derive_froid | oui | 95 min |
| P-16 | Z4-ARM-01-C | point_chaud_phase | oui | 97 min |
| P-17 | Z6-CUV-01 | colmatage_filtre | oui | 142 min |
| P-18 | Z1-ELV-01 | friction_roulement | oui | 80 min |
| P-19 | Z1-MOU-01 | derive_lente | oui | 19 min |
| P-20 | Z5-ETQ-01 | montee_brutale | oui | 9 min |
| P-21 | Z5-PAS-01 | surchauffe_bruleur | oui | 13 min |
| P-22 | Z6-CUV-01 | surchauffe_bruleur | oui | 10 min |
| P-23 | Z6-CUV-01 | rupture_calorifuge | oui | 6 min |
| P-24 | Z4-CHV-01 | rupture_calorifuge | oui | 8 min |
| P-25 | Z6-CUV-01 | colmatage_filtre | oui | 144 min |
| P-26 | Z1-ELV-01 | derive_lente | oui | 44 min |
| P-27 | Z4-ARM-01-C | point_chaud_phase | oui | 144 min |
| P-28 | Z4-ARM-01-B | point_chaud_phase | oui | 65 min |
| P-29 | Z3-GFG-01 | derive_froid | oui | 112 min |
| P-30 | Z4-ARM-01-A | point_chaud_phase | oui | 93 min |
| P-31 | Z6-CUV-01 | defaut_refroidissement | oui | 20 min |
| P-32 | Z5-PAS-01 | rupture_calorifuge | oui | 8 min |
| P-33 | Z7-CMP-01 | derive_lente | oui | 36 min |
| P-34 | Z1-VIS-01 | montee_brutale | oui | 9 min |
| P-35 | Z6-PCI-01 | defaut_refroidissement | oui | 2 min |
| P-36 | Z1-MOU-01 | derive_lente | oui | 24 min |
| P-37 | Z1-VIS-01 | friction_roulement | oui | 75 min |
| P-38 | Z4-ARM-01-B | point_chaud_phase | oui | 70 min |
| P-39 | Z6-PCI-01 | derive_lente | oui | 44 min |
| P-40 | Z7-CMP-01 | defaut_refroidissement | oui | 4 min |
| P-41 | Z6-RES-01 | chauffe_a_vide | oui | 2 min |
| P-42 | Z4-CHV-01 | surchauffe_bruleur | oui | 14 min |
| P-43 | Z2-CHE-01 | rupture_calorifuge | oui | 6 min |
| P-44 | Z5-CNV-01 | friction_roulement | oui | 74 min |
| P-45 | Z6-PCI-01 | friction_roulement | oui | 80 min |
| P-46 | Z4-CHV-01 | defaut_refroidissement | oui | 15 min |
| P-47 | Z3-PTR-01 | derive_lente | oui | 38 min |
| P-48 | Z1-MOU-01 | montee_brutale | oui | 5 min |
| P-49 | Z2-CHE-01 | colmatage_filtre | oui | 199 min |
| P-50 | Z6-RES-01 | chauffe_a_vide | oui | 2 min |
| P-51 | Z3-PTR-01 | derive_lente | oui | 51 min |
| P-52 | Z6-RES-01 | chauffe_a_vide | oui | 2 min |
| P-53 | Z1-VIS-01 | derive_lente | oui | 42 min |
| P-54 | Z4-ARM-01-B | point_chaud_phase | oui | 74 min |
| P-55 | Z3-GFG-01 | derive_froid | oui | 112 min |
| P-56 | Z4-ARM-01-A | point_chaud_phase | oui | 105 min |
| P-57 | Z4-ARM-01-A | point_chaud_phase | oui | 104 min |
| P-58 | Z7-CMP-01 | derive_lente | oui | 35 min |
| P-59 | Z3-GFG-01 | derive_froid | oui | 90 min |
| P-60 | Z6-RES-01 | chauffe_a_vide | oui | 2 min |

## Exemples d'alertes expliquées

**INSPECTION — Z1-MOU-01**

- Raison : Le moulin est 0.8 °C plus chaud que d'habitude (35.0 °C mesurés pour 34.2 °C attendus) pour une charge de 98 % et une ambiance de 29.8 °C et la température monte encore de 0.12 °C par minute depuis 0 min.
- Facteur : le bas de la plage normale de l'équipement diminue la température attendue de 7.4 °C
- Facteur : la charge des 30 dernières minutes augmente la température attendue de 7.0 °C
- Facteur : le haut de la plage normale de l'équipement diminue la température attendue de 4.4 °C
- Action conseillée : Contrôler les roulements et la lubrification ; vérifier l'alignement et la tension des courroies.

**INSPECTION — Z1-MOU-01**

- Raison : Le moulin monte de 0.13 °C par minute, plus vite que prévu (34.6 °C atteints) pour une charge de 93 % et une ambiance de 30.9 °C depuis 0 min.
- Facteur : le bas de la plage normale de l'équipement diminue la température attendue de 7.4 °C
- Facteur : la charge des 30 dernières minutes augmente la température attendue de 6.9 °C
- Facteur : le haut de la plage normale de l'équipement diminue la température attendue de 4.5 °C
- Action conseillée : Vérifier l'absence de blocage ou de corps étranger ; arrêter la machine si la montée continue.

**INSPECTION — Z1-MOU-01**

- Raison : Le moulin est 0.5 °C plus chaud que d'habitude (34.4 °C mesurés pour 33.9 °C attendus) pour une charge de 93 % et une ambiance de 30.4 °C depuis 4 min.
- Facteur : le bas de la plage normale de l'équipement diminue la température attendue de 7.4 °C
- Facteur : la charge des 30 dernières minutes augmente la température attendue de 6.6 °C
- Facteur : le haut de la plage normale de l'équipement diminue la température attendue de 4.4 °C
- Action conseillée : Contrôler les roulements et la lubrification ; vérifier l'alignement et la tension des courroies.


## Limites

- Les données sont simulées par nos soins : elles suivent nos propres hypothèses.
- Un bon résultat prouve que la chaîne fonctionne, pas que l'IA réussira sur site.
- Étape suivante : rejouer cette évaluation sur les lots livrés par le jumeau numérique, puis sur les mesures d'un site réel.
