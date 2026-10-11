"""Tests des explications d'alerte. N'utilise que Python.

Lancer :  python3 tests/test_explication.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ia.explication import (action_conseillee, expliquer, facteurs_influents,
                            phrase_raison, signal_dominant)


def etat(s1=0.0, s2=0.0, s3=0.0, mesuree=68.0, attendue=50.0):
    return {"s1_ecart_normalise": s1, "s2_pente": s2, "s3_ecart_jumeau": s3,
            "t_mesuree": mesuree, "t_attendue": attendue, "score": max(s1, s2, s3)}


def test_signal_ecart():
    assert signal_dominant(etat(s1=6.0, s2=0.1, s3=0.0)) == "ecart"


def test_signal_pente():
    assert signal_dominant(etat(s1=1.5, s2=2.0)) == "pente"


def test_signal_jumeau():
    assert signal_dominant(etat(s1=1.0, s2=0.1, s3=14.0)) == "jumeau"


def test_phrase_ecart_lisible():
    texte = phrase_raison(etat(s1=6.0), "Le moteur de l'élévateur",
                          {"charge_pct": 75, "t_ambiante": 31.2, "etat_marche": 1})
    assert "18.0 °C plus chaud que d'habitude" in texte, texte
    assert "charge de 75 %" in texte and "ambiance de 31.2 °C" in texte, texte
    assert texte.endswith("."), texte


def test_phrase_pente():
    texte = phrase_raison(etat(s1=1.2, s2=0.8), "La résistance")
    assert "monte de 0.8 °C par minute" in texte, texte


def test_phrase_jumeau():
    texte = phrase_raison(etat(s1=1.0, s3=14.0), "La phase B")
    assert "14.0 °C plus chaud que les équipements identiques" in texte, texte


def test_duree_mentionnee():
    texte = phrase_raison(etat(s1=6.0), "Le moteur", duree_s=2700)
    assert "depuis 45 min" in texte, texte


def test_action_par_famille():
    assert "roulements" in action_conseillee("MOT", "ecart")
    assert "connexions" in action_conseillee("ARM", "jumeau")
    assert action_conseillee("MOT", "jumeau") == "Faire contrôler l'équipement par un technicien."


def test_action_urgence_resistance():
    assert action_conseillee("RES", "pente").startswith("URGENCE")


def test_facteurs_classes_par_importance():
    entrees = ["charge_pct", "t_ambiante", "heure"]
    textes = facteurs_influents([5.2, -1.1, 0.05], entrees)
    assert len(textes) == 2, textes            # 0,05 °C est négligeable
    assert textes[0].startswith("la charge augmente"), textes
    assert "diminue" in textes[1], textes


def test_explication_complete():
    resultat = expliquer(etat(s1=6.0), "Le moulin", "MOT",
                         contexte={"charge_pct": 90, "etat_marche": 1},
                         duree_s=600, contributions=[4.0], entrees=["charge_pct"])
    assert set(resultat) == {"signal", "raison", "action", "facteurs"}
    assert resultat["signal"] == "ecart"
    assert resultat["facteurs"], resultat


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
