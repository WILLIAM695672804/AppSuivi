"""Entraînement du modèle de température attendue.

Méthode (chapitre 6.9 du cahier des charges technique) :
  1. on n'apprend que sur du fonctionnement normal ;
  2. on découpe par date, jamais au hasard ;
  3. on mesure l'erreur de prédiction sur une partie jamais vue ;
  4. on calcule le décalage et la dispersion propres à l'équipement (calibrage).
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
    LIGHTGBM_DISPONIBLE = True
except ImportError:                       # connexion trop lente pour l'installer
    lgb = None
    LIGHTGBM_DISPONIBLE = False

RACINE = Path(__file__).resolve().parents[1]
MODELES = RACINE / "modeles"


def decouper_par_date(tableau, part_apprentissage=0.70, part_reglage=0.15):
    """Découpe chronologique : apprentissage | réglage | test."""
    n = len(tableau)
    fin_apprentissage = int(n * part_apprentissage)
    fin_reglage = int(n * (part_apprentissage + part_reglage))
    return (tableau.iloc[:fin_apprentissage],
            tableau.iloc[fin_apprentissage:fin_reglage],
            tableau.iloc[fin_reglage:])


class ModeleTranches:
    """Modèle de repli, sans aucune bibliothèque supplémentaire.

    Principe : on découpe chaque entrée en tranches (par exemple 10 niveaux de
    courant), et la température attendue est la moyenne observée dans la
    combinaison de tranches correspondante. C'est moins fin que LightGBM, mais
    cela suffit à valider la méthode.
    """

    def __init__(self, entrees, nb_tranches=8, entrees_utilisees=3):
        self.entrees = entrees[:entrees_utilisees]
        self.nb_tranches = nb_tranches
        self.bornes = {}
        self.moyennes = {}
        self.moyenne_generale = 0.0

    def _tranches(self, tableau):
        codes = []
        for colonne in self.entrees:
            bornes = self.bornes[colonne]
            codes.append(np.clip(np.searchsorted(bornes, tableau[colonne].to_numpy()),
                                 0, self.nb_tranches - 1))
        return list(zip(*codes))

    def fit(self, tableau, cible):
        for colonne in self.entrees:
            quantiles = np.linspace(0, 100, self.nb_tranches + 1)[1:-1]
            self.bornes[colonne] = np.percentile(tableau[colonne].to_numpy(), quantiles)
        valeurs = cible.to_numpy()
        self.moyenne_generale = float(np.mean(valeurs))
        sommes, effectifs = {}, {}
        for clef, valeur in zip(self._tranches(tableau), valeurs):
            sommes[clef] = sommes.get(clef, 0.0) + valeur
            effectifs[clef] = effectifs.get(clef, 0) + 1
        self.moyennes = {k: sommes[k] / effectifs[k] for k in sommes if effectifs[k] >= 5}
        return self

    def predict(self, tableau):
        return np.array([self.moyennes.get(clef, self.moyenne_generale)
                         for clef in self._tranches(tableau)])

    def contributions(self, tableau):
        return None          # le modèle de repli n'explique pas ses prédictions


def entrainer(apprentissage, reglage, entrees, cible="Temperature"):
    if not LIGHTGBM_DISPONIBLE:
        print("  LightGBM absent : utilisation du modèle de repli (moyennes par tranches).")
        return ModeleTranches(entrees).fit(apprentissage[entrees], apprentissage[cible])

    # API native de LightGBM : elle ne demande pas scikit-learn.
    parametres = {
        "objective": "l1",              # erreur absolue : robuste aux valeurs extrêmes
        "learning_rate": 0.05,
        "num_leaves": 31,
        "min_data_in_leaf": 40,
        "verbose": -1,
    }
    jeu_apprentissage = lgb.Dataset(apprentissage[entrees].to_numpy(),
                                    label=apprentissage[cible].to_numpy(),
                                    feature_name=list(entrees))
    jeu_reglage = lgb.Dataset(reglage[entrees].to_numpy(), label=reglage[cible].to_numpy(),
                              reference=jeu_apprentissage)
    booster = lgb.train(parametres, jeu_apprentissage, num_boost_round=500,
                        valid_sets=[jeu_reglage],
                        callbacks=[lgb.early_stopping(50, verbose=False)])
    return ModeleLightGBM(booster, entrees)


class ModeleLightGBM:
    """Enveloppe pour que LightGBM et le modèle de repli s'utilisent pareil."""

    def __init__(self, booster, entrees):
        self.booster = booster
        self.entrees = list(entrees)

    def predict(self, tableau):
        valeurs = tableau[self.entrees].to_numpy() if hasattr(tableau, "columns") else tableau
        return self.booster.predict(valeurs)

    def contributions(self, tableau):
        """Part de chaque entrée dans la température attendue, en °C.

        LightGBM sait le calculer lui-même : aucune bibliothèque supplémentaire
        n'est nécessaire. La dernière colonne est la valeur de départ du modèle.
        """
        valeurs = tableau[self.entrees].to_numpy() if hasattr(tableau, "columns") else tableau
        return self.booster.predict(valeurs, pred_contrib=True)


def erreur_moyenne(modele, tableau, entrees, cible="Temperature"):
    prediction = modele.predict(tableau[entrees])
    return float(np.mean(np.abs(tableau[cible].to_numpy() - prediction)))


def calibrer(modele, reglage, entrees, cible="Temperature"):
    """Décalage et dispersion habituels des écarts, sur du fonctionnement normal.

    On utilise des mesures robustes (médiane et écart absolu médian) pour qu'un
    point aberrant ne fausse pas le calibrage.
    """
    residus = reglage[cible].to_numpy() - modele.predict(reglage[entrees])
    biais = float(np.median(residus))
    ecart_absolu_median = float(np.median(np.abs(residus - biais)))
    dispersion = max(1.4826 * ecart_absolu_median, 0.2)
    return {"biais": biais, "dispersion": dispersion}


def enregistrer(modele, calibrage, entrees, nom, resultats):
    MODELES.mkdir(parents=True, exist_ok=True)
    if hasattr(modele, "booster"):
        modele.booster.save_model(str(MODELES / f"{nom}.txt"))
    (MODELES / f"{nom}.json").write_text(json.dumps(
        {"entrees": entrees, "calibrage": calibrage, "resultats": resultats,
         "modele": "lightgbm" if hasattr(modele, "booster") else "tranches"},
        indent=2, ensure_ascii=False))
    print(f"  Modèle enregistré : modeles/{nom}.json")


def predire(modele, tableau, entrees):
    return pd.Series(modele.predict(tableau[entrees]), index=tableau.index)
