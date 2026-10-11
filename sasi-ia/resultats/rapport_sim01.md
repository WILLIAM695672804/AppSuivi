# Projet SASI — IA version 0 : résultats sur Site pilote — brasserie

Date : 23/09/2026 22:01

## Méthode

Un modèle par famille apprend la température normale de chaque équipement à partir de son contexte (charge, marche/arrêt, ambiance, temps depuis le démarrage, heure). Chaque équipement est ensuite calibré sur ses propres mesures. Les écarts persistants déclenchent une alerte (cahier des charges technique, chapitre 6).

- Entraînement : lot A, 14 jours de fonctionnement normal, aucune panne.
- Test : lot B, jamais vu, contenant 60 pannes.

## Erreur de prédiction par famille

| Famille | Erreur moyenne |
|---|---|
| ARM | 0.28 °C |
| CHD | 0.42 °C |
| MOT | 0.28 °C |
| POM | 0.29 °C |
| RES | 0.49 °C |

## Résultats de détection

### Lot B — 60 pannes simulées

- Pannes connues : 60
- Pannes détectées : 60 (**100 %**, objectif ≥ 80 %)
- Alertes émises : 98
- Fausses alertes : 19 (**20 %**, objectif < 10 %)
- Délai médian de détection : 39 min

## Détail par panne

| Panne | Équipement | Type | Détectée | Délai |
|---|---|---|---|---|
| P-01 | Z6-CUV-01 | colmatage_filtre | oui | 121 min |
| P-02 | Z4-ARM-01-C | point_chaud_phase | oui | 144 min |
| P-03 | Z3-PTR-01 | friction_roulement | oui | 75 min |
| P-04 | Z5-ETQ-01 | derive_lente | oui | 38 min |
| P-05 | Z6-RES-01 | chauffe_a_vide | oui | 2 min |
| P-06 | Z5-ETQ-01 | derive_lente | oui | 36 min |
| P-07 | Z5-CNV-01 | montee_brutale | oui | 9 min |
| P-08 | Z2-CHE-01 | colmatage_filtre | oui | 181 min |
| P-09 | Z3-GFG-01 | derive_froid | oui | 95 min |
| P-10 | Z4-CHV-01 | defaut_refroidissement | oui | 14 min |
| P-11 | Z1-ELV-01 | montee_brutale | oui | 8 min |
| P-12 | Z4-CHV-01 | surchauffe_bruleur | oui | 17 min |
| P-13 | Z5-CNV-01 | montee_brutale | oui | 8 min |
| P-14 | Z5-PAS-01 | surchauffe_bruleur | oui | 9 min |
| P-15 | Z3-GFG-01 | derive_froid | oui | 91 min |
| P-16 | Z4-ARM-01-C | point_chaud_phase | oui | 97 min |
| P-17 | Z6-CUV-01 | colmatage_filtre | oui | 136 min |
| P-18 | Z1-ELV-01 | friction_roulement | oui | 65 min |
| P-19 | Z1-MOU-01 | derive_lente | oui | 24 min |
| P-20 | Z5-ETQ-01 | montee_brutale | oui | 9 min |
| P-21 | Z5-PAS-01 | surchauffe_bruleur | oui | 8 min |
| P-22 | Z6-CUV-01 | surchauffe_bruleur | oui | 10 min |
| P-23 | Z6-CUV-01 | rupture_calorifuge | oui | 6 min |
| P-24 | Z4-CHV-01 | rupture_calorifuge | oui | 19 min |
| P-25 | Z6-CUV-01 | colmatage_filtre | oui | 141 min |
| P-26 | Z1-ELV-01 | derive_lente | oui | 42 min |
| P-27 | Z4-ARM-01-C | point_chaud_phase | oui | 137 min |
| P-28 | Z4-ARM-01-B | point_chaud_phase | oui | 71 min |
| P-29 | Z3-GFG-01 | derive_froid | oui | 116 min |
| P-30 | Z4-ARM-01-A | point_chaud_phase | oui | 107 min |
| P-31 | Z6-CUV-01 | defaut_refroidissement | oui | 24 min |
| P-32 | Z5-PAS-01 | rupture_calorifuge | oui | 8 min |
| P-33 | Z7-CMP-01 | derive_lente | oui | 40 min |
| P-34 | Z1-VIS-01 | montee_brutale | oui | 9 min |
| P-35 | Z6-PCI-01 | defaut_refroidissement | oui | 3 min |
| P-36 | Z1-MOU-01 | derive_lente | oui | 21 min |
| P-37 | Z1-VIS-01 | friction_roulement | oui | 55 min |
| P-38 | Z4-ARM-01-B | point_chaud_phase | oui | 69 min |
| P-39 | Z6-PCI-01 | derive_lente | oui | 44 min |
| P-40 | Z7-CMP-01 | defaut_refroidissement | oui | 5 min |
| P-41 | Z6-RES-01 | chauffe_a_vide | oui | 2 min |
| P-42 | Z4-CHV-01 | surchauffe_bruleur | oui | 14 min |
| P-43 | Z2-CHE-01 | rupture_calorifuge | oui | 6 min |
| P-44 | Z5-CNV-01 | friction_roulement | oui | 75 min |
| P-45 | Z6-PCI-01 | friction_roulement | oui | 80 min |
| P-46 | Z4-CHV-01 | defaut_refroidissement | oui | 14 min |
| P-47 | Z3-PTR-01 | derive_lente | oui | 39 min |
| P-48 | Z1-MOU-01 | montee_brutale | oui | 6 min |
| P-49 | Z2-CHE-01 | colmatage_filtre | oui | 195 min |
| P-50 | Z6-RES-01 | chauffe_a_vide | oui | 2 min |
| P-51 | Z3-PTR-01 | derive_lente | oui | 47 min |
| P-52 | Z6-RES-01 | chauffe_a_vide | oui | 2 min |
| P-53 | Z1-VIS-01 | derive_lente | oui | 45 min |
| P-54 | Z4-ARM-01-B | point_chaud_phase | oui | 69 min |
| P-55 | Z3-GFG-01 | derive_froid | oui | 107 min |
| P-56 | Z4-ARM-01-A | point_chaud_phase | oui | 110 min |
| P-57 | Z4-ARM-01-A | point_chaud_phase | oui | 113 min |
| P-58 | Z7-CMP-01 | derive_lente | oui | 38 min |
| P-59 | Z3-GFG-01 | derive_froid | oui | 94 min |
| P-60 | Z6-RES-01 | chauffe_a_vide | oui | 2 min |

## Exemples d'alertes expliquées

**URGENCE — Z6-CUV-01**

- Raison : La cuve de nettoyage est 31.0 °C plus chaud que d'habitude (58.4 °C mesurés pour 27.4 °C attendus) pour une ambiance de 27.3 °C et la température monte encore de 0.06 °C par minute depuis 4 h 17.
- Facteur : la charge des 30 dernières minutes diminue la température attendue de 18.2 °C
- Facteur : le temps écoulé depuis l'arrêt diminue la température attendue de 10.3 °C
- Facteur : la chaleur ambiante diminue la température attendue de 10.2 °C
- Action conseillée : Contrôler le brûleur ou la régulation ; vérifier l'isolation et l'évacuation des fumées.

**URGENCE — Z4-ARM-01-C**

- Raison : La phase C de l'armoire est 13.2 °C plus chaud que d'habitude (47.8 °C mesurés pour 34.6 °C attendus) pour une ambiance de 33.5 °C depuis 4 h 00.
- Facteur : la chaleur ambiante augmente la température attendue de 0.6 °C
- Facteur : l'heure de la journée augmente la température attendue de 0.6 °C
- Facteur : le refroidissement en cours augmente la température attendue de 0.3 °C
- Action conseillée : Vérifier la ventilation de l'armoire et la charge des départs.

**URGENCE — Z3-PTR-01**

- Raison : La pompe de transfert est 54.3 °C plus chaud que d'habitude (109.9 °C mesurés pour 55.6 °C attendus) pour une charge de 84 % et une ambiance de 15.2 °C et la température monte encore de 0.44 °C par minute depuis 2 h 51.
- Facteur : le bas de la plage normale de l'équipement augmente la température attendue de 18.1 °C
- Facteur : le temps écoulé depuis l'arrêt augmente la température attendue de 10.4 °C
- Facteur : le temps écoulé depuis le démarrage augmente la température attendue de 2.8 °C
- Action conseillée : Vérifier la ventilation, les filtres et les roulements ; contrôler le niveau d'huile.


## Limites

- Les données sont simulées par nos soins : elles suivent nos propres hypothèses.
- Un bon résultat prouve que la chaîne fonctionne, pas que l'IA réussira sur site.
- Étape suivante : rejouer cette évaluation sur les lots livrés par le jumeau numérique, puis sur les mesures d'un site réel.
