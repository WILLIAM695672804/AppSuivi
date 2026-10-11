# Projet SASI — Résultats de l'IA version 0

Date : 20/09/2026 18:19

Méthode : le modèle apprend la température normale d'un équipement à partir de son contexte de fonctionnement, puis signale les écarts persistants (voir le cahier des charges technique, chapitre 6).

## Résultats

### SKAB — banc de pompe

- Erreur moyenne de prédiction : **0.89 °C**
- Pannes connues : 34
- Pannes détectées : 1 (**3 %**, objectif ≥ 80 %)
- Alertes émises : 1
- Fausses alertes : 0 (**0 %**, objectif < 10 %)
- Délai médian de détection : 0 s

### NAB — machine industrielle

- Pannes connues : 4
- Pannes détectées : 0 (**0 %**, objectif ≥ 80 %)
- Alertes émises : 2
- Fausses alertes : 2 (**100 %**, objectif < 10 %)
- Délai médian de détection : —

## Limites

- Ces jeux de données ne sont pas des équipements de brasserie.
- Ils servent à valider la méthode, pas à mesurer les performances futures sur site.
- L'étape suivante est le lot A du jumeau numérique, puis les lots B et C.
