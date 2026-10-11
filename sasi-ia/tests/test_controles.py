"""Tests des contrôles à l'entrée. N'utilise que Python."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ia.controles import SurveillanceCameras, trous_de_mesure, verifier_mesure

CONNUS = {"Z1-ELV-01", "Z4-ARM-01-A"}


def test_mesure_correcte():
    ok, motif = verifier_mesure({"equipement": "Z1-ELV-01", "t_max": 52.4, "secondes": 100},
                                CONNUS, horodatage_courant=100)
    assert ok and motif is None, motif


def test_equipement_inconnu():
    ok, motif = verifier_mesure({"equipement": "INCONNU-01", "t_max": 50.0}, CONNUS)
    assert not ok and motif == "equipement_inconnu", motif


def test_valeur_absente():
    ok, motif = verifier_mesure({"equipement": "Z1-ELV-01", "t_max": None}, CONNUS)
    assert not ok and motif == "valeur_absente", motif


def test_valeur_non_numerique():
    ok, motif = verifier_mesure({"equipement": "Z1-ELV-01", "t_max": float("nan")}, CONNUS)
    assert not ok and motif == "valeur_absente", motif


def test_valeur_hors_plage():
    ok, motif = verifier_mesure({"equipement": "Z1-ELV-01", "t_max": 1200.0}, CONNUS)
    assert not ok and motif == "valeur_hors_plage", motif


def test_zero_accepte():
    # 0 °C est une vraie température : elle ne doit pas être confondue avec une absence
    ok, _ = verifier_mesure({"equipement": "Z1-ELV-01", "t_max": 0.0}, CONNUS)
    assert ok


def test_horodatage_futur_rejete():
    ok, motif = verifier_mesure({"equipement": "Z1-ELV-01", "t_max": 50.0, "secondes": 500},
                                CONNUS, horodatage_courant=100)
    assert not ok and motif == "horodatage_dans_le_futur", motif


def test_mesure_en_retard_acceptee_mais_signalee():
    ok, motif = verifier_mesure({"equipement": "Z1-ELV-01", "t_max": 50.0, "secondes": 100},
                                CONNUS, horodatage_courant=1000)
    assert ok and motif == "mesure_en_retard", motif


def test_camera_muette():
    surveillance = SurveillanceCameras()
    surveillance.enregistrer("CAM-Z1", 0, 50.0)
    assert surveillance.controler(300) == []
    alertes = surveillance.controler(700)
    assert len(alertes) == 1 and alertes[0]["type"] == "camera_muette", alertes


def test_camera_muette_signalee_une_seule_fois():
    surveillance = SurveillanceCameras()
    surveillance.enregistrer("CAM-Z1", 0, 50.0)
    surveillance.controler(700)
    assert surveillance.controler(1300) == []


def test_retour_a_la_normale():
    surveillance = SurveillanceCameras()
    surveillance.enregistrer("CAM-Z1", 0, 50.0)
    surveillance.controler(700)
    retour = surveillance.enregistrer("CAM-Z1", 800, 50.5)
    assert retour and retour["type"] == "retour_a_la_normale", retour


def test_camera_figee():
    surveillance = SurveillanceCameras()
    for seconde in range(0, 2000, 10):
        surveillance.enregistrer("CAM-Z2", seconde, 47.0)      # valeur strictement identique
    alertes = surveillance.controler(2000)
    assert len(alertes) == 1 and alertes[0]["type"] == "camera_figee", alertes


def test_camera_vivante_non_signalee():
    surveillance = SurveillanceCameras()
    for i, seconde in enumerate(range(0, 2000, 10)):
        surveillance.enregistrer("CAM-Z3", seconde, 47.0 + (i % 5) * 0.3)
    assert surveillance.controler(2000) == []


def test_trous_de_mesure():
    secondes = [0, 10, 20, 400, 410]
    assert trous_de_mesure(secondes) == [(20, 400)]


def test_aucun_trou():
    assert trous_de_mesure([0, 10, 20, 30]) == []


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
