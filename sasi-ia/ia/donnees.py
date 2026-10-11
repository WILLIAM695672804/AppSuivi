"""Chargement des jeux de données publics et mise au format commun.

Format commun (une ligne = une mesure) :
    horodatage | equipement | t_max | + colonnes de contexte

Nécessite pandas.
"""

import json
from pathlib import Path

import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
DOSSIER = RACINE / "donnees"

# Colonnes de SKAB utilisées comme contexte. La température (cible) et le
# thermocouple sont exclus : utiliser une température pour prédire une autre
# température reviendrait à tricher.
CONTEXTE_SKAB = ["Current", "Voltage", "Pressure", "Volume Flow RateRMS"]


def _lire_csv_skab(chemin):
    tableau = pd.read_csv(chemin, sep=";", index_col="datetime", parse_dates=True)
    tableau = tableau.sort_index()
    tableau.index.name = "horodatage"
    return tableau


def charger_skab():
    """Renvoie (normal, avec_pannes).

    normal       : fichier « anomaly-free », sans aucune anomalie (entraînement)
    avec_pannes  : fichiers contenant des anomalies étiquetées (test)
    """
    base = DOSSIER / "skab"
    if not base.exists():
        raise FileNotFoundError(
            "Données SKAB absentes. Lancez d'abord : python3 outils/telecharger_donnees.py")

    fichiers_normaux = sorted(base.glob("anomaly-free/*.csv"))
    if not fichiers_normaux:
        raise FileNotFoundError(f"Aucun fichier « anomaly-free » trouvé dans {base}")
    normal = pd.concat([_lire_csv_skab(f) for f in fichiers_normaux])

    morceaux = []
    for fichier in sorted(base.rglob("*.csv")):
        if "anomaly-free" in fichier.as_posix():
            continue
        tableau = _lire_csv_skab(fichier)
        if "anomaly" not in tableau.columns:
            continue
        tableau["fichier"] = fichier.stem
        tableau["equipement"] = f"SKAB-{fichier.parent.name}-{fichier.stem}"
        morceaux.append(tableau)
    if not morceaux:
        raise FileNotFoundError("Aucun fichier SKAB avec anomalies trouvé.")

    normal["equipement"] = "SKAB-normal"
    return normal, morceaux


def colonnes_contexte(tableau):
    """Colonnes de contexte réellement présentes dans le tableau."""
    return [c for c in CONTEXTE_SKAB if c in tableau.columns]


def preparer(tableau, contexte):
    """Ajoute les entrées calculées : heure, moyennes glissantes."""
    prepare = tableau.copy()
    prepare["heure"] = prepare.index.hour
    prepare["minute_du_jour"] = prepare.index.hour * 60 + prepare.index.minute
    for colonne in contexte:
        prepare[f"{colonne}_moy_5min"] = (
            prepare[colonne].rolling(window=300, min_periods=1).mean())
    return prepare.dropna(subset=contexte)


def entrees(contexte):
    """Liste des colonnes données au modèle."""
    return contexte + [f"{c}_moy_5min" for c in contexte] + ["heure", "minute_du_jour"]


def charger_nab():
    """Renvoie (mesures, fenetres_de_panne) pour le jeu NAB."""
    base = DOSSIER / "nab"
    fichier = base / "machine_temperature_system_failure.csv"
    if not fichier.exists():
        raise FileNotFoundError(
            "Données NAB absentes. Lancez d'abord : python3 outils/telecharger_donnees.py")
    mesures = pd.read_csv(fichier, parse_dates=["timestamp"])
    mesures = mesures.rename(columns={"timestamp": "horodatage", "value": "t_max"})
    mesures = mesures.set_index("horodatage").sort_index()
    mesures["equipement"] = "NAB-machine"

    chemin_fenetres = base / "fenetres_pannes.json"
    fenetres = []
    if chemin_fenetres.exists():
        for debut, fin in json.loads(chemin_fenetres.read_text()):
            fenetres.append((pd.Timestamp(debut), pd.Timestamp(fin)))
    return mesures, fenetres


def fenetres_depuis_etiquettes(tableau, colonne="anomaly"):
    """Transforme une colonne 0/1 en liste de périodes (début, fin)."""
    etiquettes = tableau[colonne].fillna(0).astype(int)
    fenetres = []
    debut = None
    for horodatage, valeur in etiquettes.items():
        if valeur == 1 and debut is None:
            debut = horodatage
        elif valeur == 0 and debut is not None:
            fenetres.append((debut, horodatage))
            debut = None
    if debut is not None:
        fenetres.append((debut, etiquettes.index[-1]))
    return fenetres
