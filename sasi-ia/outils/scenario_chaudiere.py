"""Scénario « départ de feu d'une chaudière » — générateur de données étiquetées.

Reprise fidèle du générateur de la spécification SPE-AI-ENG-042, version 2.1
(« Spécification technique & données synthétiques — Prédiction incendie
chaudière »), avec deux ajouts nécessaires à l'évaluation :
  - des marches saines (aucune panne injectée) pour mesurer les fausses alertes ;
  - des débuts de dérive et de feu tirés au hasard, pour ne pas tester l'IA
    toujours sur le même minutage.

Phases (étiquette entre crochets) :
  0  régime nominal                                     [0]
  1  étranglement d'air, accumulation d'imbrûlés        [0]  à partir de debut_derive
  2  défaillance du calorifuge, préchauffe critique     [1]  à partir de debut_feu
  3  inflammation externe                               [2]  à partir de debut_feu + 15 min

    ./venv/bin/python outils/scenario_chaudiere.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]
SORTIE = RACINE / "donnees" / "chaudiere"

PAS_S = 5                      # pas d'échantillonnage de la spécification
DUREE_MIN = 90

VARIABLES = ["t_corps_c", "t_fumees_c", "p_foyer_mbar", "taux_o2_pct",
             "co_ppm", "vibr_vent_mms", "flamme_ir_pct"]


def generer(graine, sain=False, debut_derive=20.0, debut_feu=45.0, duree_min=DUREE_MIN):
    """Une marche de chaudière. Renvoie un tableau d'une ligne par pas de 5 s."""
    alea = np.random.default_rng(graine)
    secondes = np.arange(0, duree_min * 60, PAS_S)
    t_min = secondes / 60.0
    n = len(secondes)

    # Phase 0 : bruit de fond nominal (valeurs de la spécification)
    t_corps = 72.0 + alea.normal(0, 0.5, n)
    t_fumees = 185.0 + alea.normal(0, 1.2, n)
    taux_o2 = 3.8 + alea.normal(0, 0.08, n)
    co_ppm = 25.0 + alea.normal(0, 3.0, n)
    p_foyer = -0.30 + alea.normal(0, 0.02, n)
    vibr_vent = 1.10 + alea.normal(0, 0.05, n)
    flamme_ir = 96.0 + alea.normal(0, 0.8, n)
    etiquette = np.zeros(n, dtype=int)

    if not sain:
        # Phase 1 : défaut de comburant
        p1 = t_min >= debut_derive
        dt1 = t_min[p1] - debut_derive
        taux_o2[p1] -= 0.08 * dt1
        co_ppm[p1] += 1.5 * np.exp(0.18 * dt1)
        t_fumees[p1] += 1.2 * dt1
        vibr_vent[p1] += 0.035 * dt1

        # Phase 2 : préchauffe critique et surpression
        p2 = t_min >= debut_feu
        dt2 = t_min[p2] - debut_feu
        t_corps[p2] += 4.5 * dt2 + 0.3 * dt2 ** 2
        p_foyer[p2] += 0.04 * dt2
        flamme_ir[p2] -= 1.8 * dt2 + alea.normal(0, 2.5, p2.sum())
        etiquette[p2] = 1

        # Phase 3 : inflammation externe
        p3 = t_min >= debut_feu + 15.0
        t_corps[p3] += 60.0
        etiquette[p3] = 2

    taux_o2 = np.clip(taux_o2, 0.1, 10.0)
    return pd.DataFrame({
        "secondes": secondes,
        "t_corps_c": np.round(t_corps, 2),
        "t_fumees_c": np.round(t_fumees, 2),
        "p_foyer_mbar": np.round(p_foyer, 3),
        "taux_o2_pct": np.round(taux_o2, 2),
        "co_ppm": np.round(co_ppm, 1),
        "vibr_vent_mms": np.round(vibr_vent, 3),
        "flamme_ir_pct": np.round(flamme_ir, 1),
        "etiquette": etiquette,
    })


def lot(nombre_feux=50, nombre_sains=50, graine=2026):
    """Un lot de marches : des départs de feu à des moments variés, et des marches saines."""
    alea = np.random.default_rng(graine)
    marches = []
    for i in range(nombre_feux):
        debut_derive = float(alea.uniform(15, 25))
        debut_feu = float(debut_derive + alea.uniform(20, 30))
        tableau = generer(graine * 1000 + i, debut_derive=debut_derive, debut_feu=debut_feu)
        marches.append({"id": f"FEU-{i + 1:03d}", "sain": False, "debut_derive": debut_derive,
                        "debut_feu": debut_feu, "inflammation": debut_feu + 15.0,
                        "donnees": tableau})
    for i in range(nombre_sains):
        tableau = generer(graine * 1000 + 500 + i, sain=True)
        marches.append({"id": f"SAIN-{i + 1:03d}", "sain": True, "debut_derive": None,
                        "debut_feu": None, "inflammation": None, "donnees": tableau})
    return marches


def enregistrer(marches, nom):
    SORTIE.mkdir(parents=True, exist_ok=True)
    lignes = []
    for marche in marches:
        tableau = marche["donnees"].copy()
        tableau.insert(0, "marche", marche["id"])
        lignes.append(tableau)
    pd.concat(lignes).to_csv(SORTIE / f"chaudiere_{nom}.csv", index=False)
    pd.DataFrame([{k: v for k, v in m.items() if k != "donnees"} for m in marches]) \
        .to_csv(SORTIE / f"journal_{nom}.csv", index=False)
    return SORTIE / f"chaudiere_{nom}.csv"


if __name__ == "__main__":
    apprentissage = lot(nombre_feux=0, nombre_sains=40, graine=11)     # marches saines seulement
    essai = lot(nombre_feux=50, nombre_sains=50, graine=2026)          # jamais vues
    print("Scénario chaudière (spécification SPE-AI-ENG-042)")
    print(f"  apprentissage : {enregistrer(apprentissage, 'apprentissage')}")
    print(f"  essai         : {enregistrer(essai, 'essai')}")
    sys.exit(0)
