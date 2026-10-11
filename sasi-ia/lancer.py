"""Chaîne complète de l'IA version 0.

    python3 lancer.py

Étapes :
  1. chargement des jeux publics (SKAB, NAB)
  2. entraînement du modèle de température attendue, sur du normal uniquement
  3. détection des anomalies sur des données jamais vues
  4. comparaison aux pannes connues et rédaction du rapport
"""

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ia import donnees, entrainement, evaluation
from ia.detection import parcourir

RACINE = Path(__file__).resolve().parent
RESULTATS = RACINE / "resultats"


def _secondes(index):
    """Convertit une suite d'horodatages en secondes depuis le premier."""
    depart = index[0]
    return [(h - depart).total_seconds() for h in index]


def _fenetres_en_secondes(fenetres, depart):
    return [((debut - depart).total_seconds(), (fin - depart).total_seconds())
            for debut, fin in fenetres]


# ---------------------------------------------------------------- SKAB
def etape_skab():
    print("\n=== SKAB : banc de pompe (température, courant, tension, pression) ===")
    normal, fichiers_pannes = donnees.charger_skab()
    contexte = donnees.colonnes_contexte(normal)
    print(f"  Contexte utilisé : {', '.join(contexte)}")
    print(f"  Mesures normales : {len(normal):,}".replace(",", " "))

    normal = donnees.preparer(normal, contexte)
    entrees = donnees.entrees(contexte)
    apprentissage, reglage, test_normal = entrainement.decouper_par_date(normal)

    modele = entrainement.entrainer(apprentissage, reglage, entrees)
    erreur = entrainement.erreur_moyenne(modele, test_normal, entrees)
    calibrage = entrainement.calibrer(modele, reglage, entrees)
    print(f"  Erreur moyenne de prédiction : {erreur:.2f} °C")
    print(f"  Calibrage : décalage {calibrage['biais']:.2f} °C, "
          f"dispersion {calibrage['dispersion']:.2f} °C")

    toutes_alertes, toutes_fenetres = [], []
    decalage = 0.0
    for tableau in fichiers_pannes:
        tableau = donnees.preparer(tableau, contexte)
        if tableau.empty:
            continue
        prediction = entrainement.predire(modele, tableau, entrees)
        secondes = _secondes(tableau.index)

        mesures = [{"equipement": "SKAB", "secondes": decalage + s,
                    "t_mesuree": float(t), "t_attendue": float(p)}
                   for s, t, p in zip(secondes, tableau["Temperature"], prediction)]
        _, alertes = parcourir(mesures, biais=calibrage["biais"],
                               dispersion=calibrage["dispersion"], criticite=1)
        toutes_alertes += alertes

        fenetres = donnees.fenetres_depuis_etiquettes(tableau)
        depart = tableau.index[0]
        toutes_fenetres += [(decalage + d, decalage + f)
                            for d, f in _fenetres_en_secondes(fenetres, depart)]
        decalage += (secondes[-1] if secondes else 0) + 3600   # fichiers séparés d'une heure

    resultat = evaluation.evaluer(toutes_alertes, toutes_fenetres)
    print(f"  Pannes connues : {resultat['pannes']} — détectées : "
          f"{resultat['pannes_detectees']} ({evaluation.pourcentage(resultat['taux_detection'])})")
    print(f"  Fausses alertes : {evaluation.pourcentage(resultat['part_fausses_alertes'])}")
    entrainement.enregistrer(modele, calibrage, entrees, "skab",
                             {"erreur_moyenne": erreur, **resultat})
    return resultat, erreur


# ---------------------------------------------------------------- NAB
def etape_nab():
    print("\n=== NAB : température d'une machine industrielle réelle ===")
    mesures, fenetres = donnees.charger_nab()
    print(f"  Mesures : {len(mesures):,}".replace(",", " "))
    print(f"  Pannes connues : {len(fenetres)}")

    # Aucun contexte disponible : la température attendue est la moyenne
    # glissante des 3 heures précédentes (le pas de mesure est de 5 minutes).
    attendue = mesures["t_max"].shift(1).rolling(window=36, min_periods=12).mean()
    tableau = mesures.assign(t_attendue=attendue).dropna(subset=["t_attendue"])

    residus = tableau["t_max"] - tableau["t_attendue"]
    biais = float(np.median(residus))
    dispersion = max(1.4826 * float(np.median(np.abs(residus - biais))), 0.2)
    print(f"  Dispersion habituelle : {dispersion:.2f} °C")

    secondes = _secondes(tableau.index)
    entrees_detection = [{"equipement": "NAB", "secondes": s,
                          "t_mesuree": float(t), "t_attendue": float(a)}
                         for s, t, a in zip(secondes, tableau["t_max"], tableau["t_attendue"])]
    _, alertes = parcourir(entrees_detection, biais=biais, dispersion=dispersion)

    depart = tableau.index[0]
    fenetres_s = _fenetres_en_secondes(fenetres, depart)
    resultat = evaluation.evaluer(alertes, fenetres_s, tolerance_s=3600)
    print(f"  Pannes détectées : {resultat['pannes_detectees']}/{resultat['pannes']} "
          f"({evaluation.pourcentage(resultat['taux_detection'])})")
    print(f"  Fausses alertes : {evaluation.pourcentage(resultat['part_fausses_alertes'])}")
    return resultat


# ---------------------------------------------------------------- rapport
def rapport(resultat_skab, erreur_skab, resultat_nab):
    RESULTATS.mkdir(parents=True, exist_ok=True)
    texte = [
        "# Projet SASI — Résultats de l'IA version 0",
        "",
        f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        "Méthode : le modèle apprend la température normale d'un équipement à partir de son "
        "contexte de fonctionnement, puis signale les écarts persistants "
        "(voir le cahier des charges technique, chapitre 6).",
        "",
        "## Résultats",
        "",
        evaluation.ligne_rapport("SKAB — banc de pompe", resultat_skab, erreur_skab),
        evaluation.ligne_rapport("NAB — machine industrielle", resultat_nab),
        "## Limites",
        "",
        "- Ces jeux de données ne sont pas des équipements de brasserie.",
        "- Ils servent à valider la méthode, pas à mesurer les performances futures sur site.",
        "- L'étape suivante est le lot A du jumeau numérique, puis les lots B et C.",
        "",
    ]
    chemin = RESULTATS / "rapport_ia_v0.md"
    chemin.write_text("\n".join(texte), encoding="utf-8")
    print(f"\nRapport écrit : {chemin}")


if __name__ == "__main__":
    pd.options.mode.chained_assignment = None
    resultat_skab, erreur_skab = etape_skab()
    resultat_nab = etape_nab()
    rapport(resultat_skab, erreur_skab, resultat_nab)
