"""Évaluation de l'IA sur le scénario « départ de feu d'une chaudière ».

    ./venv/bin/python lancer_chaudiere.py

Deux configurations sont comparées :
  1. version 1 du produit : température seule (corps et fumées de la chaudière) ;
  2. avec les capteurs de la version 2 : oxygène, monoxyde de carbone, pression
     du foyer et stabilité de la flamme en plus.

Mesures retenues (spécification SPE-AI-ENG-042, chapitre 6) :
  - délai d'anticipation : temps entre la première alerte et l'inflammation ;
  - détection : part des départs de feu signalés avant l'inflammation ;
  - fausses alertes : marches saines ayant déclenché une alerte.
"""

from datetime import datetime
from pathlib import Path

import numpy as np

from ia.detection import DetecteurEquipement
from outils import scenario_chaudiere as scenario

RACINE = Path(__file__).resolve().parent
RESULTATS = RACINE / "resultats"

# variable -> sens de l'anomalie (+1 : une hausse est dangereuse, -1 : une baisse)
TEMPERATURE_SEULE = {"t_corps_c": +1, "t_fumees_c": +1}
AVEC_GAZ = {**TEMPERATURE_SEULE, "co_ppm": +1, "taux_o2_pct": -1,
            "p_foyer_mbar": +1, "flamme_ir_pct": -1}

NIVEAUX_ALERTE = ("surveillance", "inspection", "urgence")
CRITICITE_CHAUDIERE = 3


def calibrer(marches_saines, variables):
    """Valeur habituelle et écart extrême de chaque variable, sur des marches saines."""
    reglages = {}
    for variable, sens in variables.items():
        valeurs = np.concatenate([sens * m["donnees"][variable].to_numpy() for m in marches_saines])
        centre = float(np.median(valeurs))
        extreme = float(np.quantile(np.abs(valeurs - centre), 0.999))
        reglages[variable] = {"centre": centre, "dispersion": max(extreme, 1e-3), "sens": sens}
    return reglages


def premiere_alerte(marche, reglages):
    """Heure (en minutes) de la première alerte, toutes variables confondues."""
    premier, variable_declenchante = None, None
    for variable, reglage in reglages.items():
        detecteur = DetecteurEquipement(variable, dispersion=reglage["dispersion"],
                                        criticite=CRITICITE_CHAUDIERE)
        valeurs = reglage["sens"] * marche["donnees"][variable].to_numpy()
        secondes = marche["donnees"]["secondes"].to_numpy()
        for s, v in zip(secondes, valeurs):
            etat = detecteur.traiter(float(s), float(v), reglage["centre"])
            if etat["niveau"] in NIVEAUX_ALERTE:
                minute = s / 60.0
                if premier is None or minute < premier:
                    premier, variable_declenchante = minute, variable
                break
    return premier, variable_declenchante


def evaluer(essai, reglages):
    delais, manques, fausses, declencheurs = [], 0, 0, {}
    for marche in essai:
        minute, variable = premiere_alerte(marche, reglages)
        if marche["sain"]:
            fausses += minute is not None
            continue
        if minute is None or minute >= marche["inflammation"]:
            manques += 1
            continue
        delais.append(marche["inflammation"] - minute)
        declencheurs[variable] = declencheurs.get(variable, 0) + 1
    nb_feux = sum(not m["sain"] for m in essai)
    nb_sains = sum(m["sain"] for m in essai)
    return {
        "feux": nb_feux, "detectes": nb_feux - manques, "sains": nb_sains,
        "fausses": fausses,
        "delai_median": float(np.median(delais)) if delais else None,
        "delai_min": float(np.min(delais)) if delais else None,
        "declencheurs": declencheurs,
    }


def afficher(nom, r):
    print(f"\n  {nom}")
    print(f"    départs de feu signalés avant l'inflammation : {r['detectes']}/{r['feux']}")
    if r["delai_median"] is not None:
        print(f"    délai d'anticipation : médian {r['delai_median']:.1f} min, "
              f"minimum {r['delai_min']:.1f} min (objectif ≥ 12 min)")
    print(f"    marches saines en fausse alerte : {r['fausses']}/{r['sains']}")
    print(f"    variable qui alerte la première : {r['declencheurs']}")


def rapport(temperature, gaz):
    RESULTATS.mkdir(parents=True, exist_ok=True)
    def lignes(nom, r):
        return [f"### {nom}", "",
                f"- Départs de feu signalés avant l'inflammation : **{r['detectes']} sur {r['feux']}**",
                f"- Délai d'anticipation médian : **{r['delai_median']:.1f} min** "
                f"(minimum {r['delai_min']:.1f} min ; objectif de la spécification ≥ 12 min)"
                if r["delai_median"] is not None else "- Aucun départ de feu signalé à temps",
                f"- Marches saines en fausse alerte : **{r['fausses']} sur {r['sains']}**",
                f"- Variable qui alerte la première : {r['declencheurs']}", ""]
    texte = [
        "# Projet SASI — Scénario chaudière", "",
        f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}", "",
        f"Données produites par le générateur de la spécification SPE-AI-ENG-042 : "
        f"{temperature['feux']} départs de feu à des moments variés et {temperature['sains']} "
        "marches saines, jamais vus pendant le réglage, lui-même mené sur 120 autres "
        "marches saines.", "",
        "## Résultats", "",
        *lignes("Version 1 — température seule", temperature),
        *lignes("Avec les capteurs de la version 2 (O₂, CO, pression, flamme)", gaz),
        "## Lecture", "",
        "- La température seule voit le feu arriver quand la paroi commence à chauffer (phase 2).",
        "- Les gaz le voient pendant l'étranglement d'air (phase 1), bien plus tôt.",
        "- Données simulées : ces chiffres valident la méthode, pas la performance sur une vraie chaudière.",
        "",
    ]
    chemin = RESULTATS / "rapport_chaudiere.md"
    chemin.write_text("\n".join(texte), encoding="utf-8")
    print(f"\nRapport écrit : {chemin}")


if __name__ == "__main__":
    print("=== Scénario chaudière ===")
    # Échantillon élargi : plus une conclusion porte sur de nombreuses marches,
    # moins elle tient au hasard d'un tirage.
    reglage = scenario.lot(nombre_feux=0, nombre_sains=120, graine=11)
    essai = scenario.lot(nombre_feux=150, nombre_sains=150, graine=2026)
    resultat_temperature = evaluer(essai, calibrer(reglage, TEMPERATURE_SEULE))
    resultat_gaz = evaluer(essai, calibrer(reglage, AVEC_GAZ))
    afficher("Version 1 — température seule", resultat_temperature)
    afficher("Avec les capteurs de la version 2", resultat_gaz)
    rapport(resultat_temperature, resultat_gaz)
