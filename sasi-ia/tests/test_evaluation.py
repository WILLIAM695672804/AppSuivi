"""Tests de l'évaluation. N'utilise que Python."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ia.evaluation import duree, evaluer_episodes, pourcentage

PANNE = [{"id": "P-01", "equipement": "Z1-ELV-01", "type": "derive_lente",
          "debut": 1000.0, "fin": 5000.0}]


def episode(equipement="Z1-ELV-01", debut=1200.0, fin=3000.0, niveau="inspection"):
    return {"equipement": equipement, "debut": debut, "fin": fin,
            "niveau_max": niveau, "score_max": 5.0}


def test_detection_simple():
    r = evaluer_episodes([episode()], PANNE)
    assert r["pannes_detectees"] == 1 and r["fausses_alertes"] == 0, r


def test_delai_calcule():
    r = evaluer_episodes([episode(debut=1600.0)], PANNE)
    assert r["detail"][0]["delai_s"] == 600.0, r["detail"][0]


def test_mauvais_equipement_est_une_fausse_alerte():
    r = evaluer_episodes([episode(equipement="Z2-CHE-01")], PANNE)
    assert r["pannes_detectees"] == 0 and r["fausses_alertes"] == 1, r


def test_episode_hors_periode_est_une_fausse_alerte():
    r = evaluer_episodes([episode(debut=50000.0, fin=51000.0)], PANNE)
    assert r["fausses_alertes"] == 1, r


def test_alerte_juste_avant_la_panne_compte_comme_detection():
    r = evaluer_episodes([episode(debut=600.0, fin=1500.0)], PANNE)   # 400 s avant
    assert r["pannes_detectees"] == 1 and r["fausses_alertes"] == 0, r


def test_refroidissement_apres_panne_nest_pas_une_fausse_alerte():
    suite = episode(debut=6000.0, fin=7000.0)          # après la fin, dans le délai de retour
    r = evaluer_episodes([suite], PANNE)
    assert r["fausses_alertes"] == 0 and r["suites_de_panne"] == 1, r


def test_aucune_alerte():
    r = evaluer_episodes([], PANNE)
    assert r["taux_detection"] == 0.0 and r["part_fausses_alertes"] is None, r


def test_taux_sur_plusieurs_pannes():
    pannes = PANNE + [{"id": "P-02", "equipement": "Z2-CHE-01", "type": "montee_brutale",
                       "debut": 20000.0, "fin": 21000.0}]
    r = evaluer_episodes([episode()], pannes)
    assert r["taux_detection"] == 0.5, r


def test_affichages():
    assert pourcentage(0.8) == "80 %" and pourcentage(None) == "—"
    assert duree(120) == "2 min" and duree(30) == "30 s" and duree(None) == "—"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    echecs = 0
    for t in tests:
        try:
            t()
            print(f"  OK   {t.__name__}")
        except AssertionError as e:
            echecs += 1
            print(f"  ECHEC {t.__name__} : {e}")
    print(f"\n{len(tests) - echecs}/{len(tests)} tests réussis")
    sys.exit(1 if echecs else 0)
