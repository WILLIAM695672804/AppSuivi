# Projet SASI — Scénario chaudière

Date : 23/09/2026 20:00

Données produites par le générateur de la spécification SPE-AI-ENG-042 : 150 départs de feu à des moments variés et 150 marches saines, jamais vus pendant le réglage, lui-même mené sur 120 autres marches saines.

## Résultats

### Version 1 — température seule

- Départs de feu signalés avant l'inflammation : **150 sur 150**
- Délai d'anticipation médian : **33.0 min** (minimum 26.8 min ; objectif de la spécification ≥ 12 min)
- Marches saines en fausse alerte : **0 sur 150**
- Variable qui alerte la première : {'t_fumees_c': 150}

### Avec les capteurs de la version 2 (O₂, CO, pression, flamme)

- Départs de feu signalés avant l'inflammation : **150 sur 150**
- Délai d'anticipation médian : **33.0 min** (minimum 27.2 min ; objectif de la spécification ≥ 12 min)
- Marches saines en fausse alerte : **0 sur 150**
- Variable qui alerte la première : {'t_fumees_c': 125, 'taux_o2_pct': 25}

## Lecture

- La température seule voit le feu arriver quand la paroi commence à chauffer (phase 2).
- Les gaz le voient pendant l'étranglement d'air (phase 1), bien plus tôt.
- Données simulées : ces chiffres valident la méthode, pas la performance sur une vraie chaudière.
