"""Tests de la détection. N'utilise que Python : exécutable sans rien installer.

Lancer :  python3 tests/test_detection.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ia.detection import DetecteurEquipement, parcourir


def serie(valeurs, attendue=50.0, pas=10):
    """Construit une série de mesures à partir d'une liste de températures."""
    return [{"equipement": "Z1-ELV-01", "secondes": i * pas,
             "t_mesuree": v, "t_attendue": attendue} for i, v in enumerate(valeurs)]


def test_normal_pas_alerte():
    mesures = serie([50.0, 50.2, 49.8, 50.1] * 20)
    _, alertes = parcourir(mesures, dispersion=1.0)
    assert alertes == [], f"aucune alerte attendue, obtenu : {alertes}"


def test_pic_isole_ignore():
    valeurs = [50.0] * 10 + [58.0] + [50.0] * 10      # un seul point très chaud
    _, alertes = parcourir(serie(valeurs), dispersion=1.0)
    assert alertes == [], f"un pic isolé ne doit pas alerter, obtenu : {alertes}"


def test_ecart_persistant_alerte():
    valeurs = [50.0] * 10 + [53.5] * 20               # +3,5 °C durable
    _, alertes = parcourir(serie(valeurs), dispersion=1.0)
    niveaux = [a["niveau"] for a in alertes]
    # +3,5 écarts habituels : le niveau surveillance est atteint directement
    assert "surveillance" in niveaux, niveaux
    assert "urgence" not in niveaux, "un écart modéré ne doit pas donner une urgence"


def test_urgence_ne_se_leve_pas_seule():
    valeurs = [50.0] * 5 + [58.0] * 25 + [50.0] * 90  # forte montée puis retour
    etats, _ = parcourir(serie(valeurs), dispersion=1.0)
    assert etats[-1]["niveau"] == "urgence", etats[-1]["niveau"]


def test_hysteresis_descente():
    valeurs = [50.0] * 5 + [53.5] * 20 + [50.0] * 90  # surveillance puis retour au normal
    etats, _ = parcourir(serie(valeurs), dispersion=1.0)
    assert etats[-1]["niveau"] == "normal", etats[-1]["niveau"]


def test_seuil_fixe():
    d = DetecteurEquipement("Z6-RES-01", dispersion=1.0,
                            seuil_fixe_inspection=110, seuil_fixe_urgence=150)
    etat = d.traiter(0, 155.0, 90.0)                  # dépassement immédiat
    assert etat["niveau"] == "urgence", etat["niveau"]


def test_pente():
    # +0,6 °C toutes les 10 s = 3,6 °C/min : bien au-dessus de la référence
    valeurs = [50.0 + 0.6 * i for i in range(20)]
    _, alertes = parcourir(serie(valeurs, attendue=50.0), dispersion=3.0)
    assert alertes, "une montée rapide doit alerter même si l'écart reste faible"


def test_criticite_augmente_le_score():
    mesures = serie([50.0] * 5 + [52.6] * 15)
    _, sans = parcourir(mesures, dispersion=1.0, criticite=1)
    _, avec = parcourir(mesures, dispersion=1.0, criticite=3)
    assert len(avec) >= len(sans), (len(sans), len(avec))


def test_jumeau():
    mesures = [{"equipement": "Z4-ARM-01-B", "secondes": i * 10, "t_mesuree": 45.0,
                "t_attendue": 45.0, "mediane_jumeaux": 32.0} for i in range(12)]
    _, alertes = parcourir(mesures, dispersion=10.0)
    assert alertes, "13 °C de plus que les phases voisines doit alerter"


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
