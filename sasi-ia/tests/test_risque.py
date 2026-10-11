"""Tests du calcul de risque : la probabilité d'atteindre un seuil dangereux.

N'utilise que Python : ces tests tournent partout, y compris sur le boîtier.
"""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ia import risque

ALEA = random.Random(2026)


def serie(depart, pente, minutes=5, pas_s=10, bruit=0.25):
    """Suite de mesures montant à la vitesse voulue, avec un peu de bruit."""
    nombre = int(minutes * 60 / pas_s)
    return [(i * pas_s, depart + pente * (i * pas_s) / 60.0 + ALEA.gauss(0, bruit))
            for i in range(nombre)]


# ---------------------------------------------------------------- la pente
def test_pente_mesuree_correctement():
    pente, incertitude = risque.pente_et_incertitude(serie(50, 1.0, bruit=0.0))
    assert abs(pente - 1.0) < 0.01, pente
    assert incertitude is not None and incertitude < 0.01


def test_pente_incertaine_quand_les_mesures_sont_dispersees():
    _, nette = risque.pente_et_incertitude(serie(50, 1.0, bruit=0.1))
    _, brouillonne = risque.pente_et_incertitude(serie(50, 1.0, bruit=2.0))
    assert brouillonne > nette * 3, (nette, brouillonne)


def test_pas_assez_de_mesures():
    assert risque.pente_et_incertitude([(0, 50.0), (10, 51.0)]) == (None, None)


def test_pente_negative_reconnue():
    pente, _ = risque.pente_et_incertitude(serie(80, -0.5, bruit=0.0))
    assert pente < -0.4, pente


# ---------------------------------------------------------------- l'horizon
def test_horizon_suit_linertie():
    chaudiere = risque.horizon_minutes(temps_montee_min=50, criticite=2)
    armoire = risque.horizon_minutes(temps_montee_min=20, criticite=2)
    assert chaudiere > armoire, (chaudiere, armoire)


def test_horizon_plus_long_pour_un_equipement_critique():
    assert (risque.horizon_minutes(40, criticite=3)
            > risque.horizon_minutes(40, criticite=1))


def test_horizon_toujours_borne():
    assert risque.horizon_minutes(1, criticite=1) >= risque.HORIZON_MINIMAL_MIN
    assert risque.horizon_minutes(10000, criticite=3) <= risque.HORIZON_MAXIMAL_MIN


# ---------------------------------------------------------------- la probabilité
def evaluer(depart, pente, seuil=300, inertie=50, criticite=2):
    mesures = serie(depart, pente)
    return risque.evaluer(mesures[-1][1], seuil, mesures,
                          temps_montee_min=inertie, criticite=criticite)


def test_temperature_stable_sans_risque():
    assert evaluer(248, 0.0)["pourcentage"] == 0


def test_temperature_qui_redescend_sans_risque():
    """Le cœur de la demande : si ça revient à la normale, plus de risque."""
    assert evaluer(264, -0.3)["pourcentage"] == 0


def test_le_risque_croit_avec_la_vitesse():
    lente = evaluer(262, 0.2)["pourcentage"]
    moderee = evaluer(262, 0.6)["pourcentage"]
    rapide = evaluer(262, 1.2)["pourcentage"]
    assert lente < moderee < rapide, (lente, moderee, rapide)


def test_le_risque_croit_en_approchant_du_seuil():
    loin = evaluer(240, 0.6)["pourcentage"]
    proche = evaluer(285, 0.6)["pourcentage"]
    assert proche > loin, (loin, proche)


def test_progression_sans_marche_descalier():
    """Entre 0 % et 100 %, il doit exister des valeurs intermédiaires."""
    valeurs = [evaluer(262, p / 10.0)["pourcentage"] for p in range(0, 15)]
    intermediaires = [v for v in valeurs if 5 < v < 95]
    assert len(intermediaires) >= 3, valeurs


def test_seuil_deja_depasse():
    mesures = serie(310, 0.1)
    evaluation = risque.evaluer(mesures[-1][1], 300, mesures, temps_montee_min=50)
    assert evaluation["pourcentage"] == 100


def test_sans_seuil_pas_de_risque():
    mesures = serie(100, 2.0)
    assert risque.evaluer(mesures[-1][1], None, mesures)["pourcentage"] == 0


def test_temps_restant_estime():
    evaluation = evaluer(290, 1.0)
    assert evaluation["minutes_avant_seuil"] is not None
    assert 5 < evaluation["minutes_avant_seuil"] < 15, evaluation["minutes_avant_seuil"]


def test_pas_de_temps_restant_si_pas_de_montee():
    assert evaluer(260, -0.5)["minutes_avant_seuil"] is None


# ---------------------------------------------------------------- l'explication
def test_explication_dune_montee():
    phrase = risque.expliquer(evaluer(268, 0.9), "La chaudière")
    for morceau in ("°C par minute", "avant 300 °C", "probabilité"):
        assert morceau in phrase, phrase


def test_explication_dun_retour_a_la_normale():
    phrase = risque.expliquer(evaluer(264, -0.3), "La chaudière")
    assert "ne monte pas plus vite que prévu" in phrase, phrase
    assert "aucun risque" in phrase, phrase


def test_explication_dun_seuil_depasse():
    mesures = serie(310, 0.1)
    evaluation = risque.evaluer(mesures[-1][1], 300, mesures)
    assert "déjà dépassé" in risque.expliquer(evaluation, "La chaudière")


def test_explication_sans_mesures():
    evaluation = risque.evaluer(250, 300, [(0, 250.0)])
    assert "assez de mesures" in risque.expliquer(evaluation, "La chaudière")


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
