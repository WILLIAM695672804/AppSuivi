"""Tests de l'entraînement et du calibrage.

Ces tests ont besoin de numpy et pandas. Ils s'annoncent « ignorés » si ces
bibliothèques ne sont pas installées.

Lancer :  ./venv/bin/python tests/test_entrainement.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import numpy as np
    import pandas as pd
    from ia import entrainement
    PRET = True
except ImportError as erreur:
    PRET = False
    MOTIF = str(erreur)


def tableau_exemple(n=600):
    """Température = 20 + 0,4 x charge, plus un peu de bruit."""
    alea = np.random.default_rng(12345)
    charge = alea.uniform(0, 100, n)
    ambiante = alea.uniform(24, 32, n)
    bruit = alea.normal(0, 0.3, n)
    return pd.DataFrame({
        "horodatage": pd.date_range("2026-01-05", periods=n, freq="1min"),
        "charge_pct": charge,
        "t_ambiante": ambiante,
        "Temperature": 20 + 0.4 * charge + 0.5 * (ambiante - 28) + bruit,
    })


ENTREES = ["charge_pct", "t_ambiante"]


def test_decoupage_chronologique():
    t = tableau_exemple(100)
    a, r, essai = entrainement.decouper_par_date(t)
    assert len(a) == 70 and len(r) == 15 and len(essai) == 15
    assert a["horodatage"].max() < r["horodatage"].min(), "les périodes se chevauchent"
    assert r["horodatage"].max() < essai["horodatage"].min(), "les périodes se chevauchent"


def test_modele_apprend_la_relation():
    t = tableau_exemple()
    a, r, essai = entrainement.decouper_par_date(t)
    modele = entrainement.entrainer(a, r, ENTREES)
    erreur = entrainement.erreur_moyenne(modele, essai, ENTREES)
    assert erreur < 1.5, f"erreur trop grande : {erreur:.2f} °C"


def test_calibrage_centre_sur_zero():
    t = tableau_exemple()
    a, r, _ = entrainement.decouper_par_date(t)
    modele = entrainement.entrainer(a, r, ENTREES)
    calibrage = entrainement.calibrer(modele, r, ENTREES)
    assert abs(calibrage["biais"]) < 0.5, calibrage
    assert 0.2 <= calibrage["dispersion"] < 3.0, calibrage


def test_modele_de_repli_fonctionne():
    t = tableau_exemple()
    a, r, essai = entrainement.decouper_par_date(t)
    modele = entrainement.ModeleTranches(ENTREES).fit(a[ENTREES], a["Temperature"])
    erreur = float(np.mean(np.abs(essai["Temperature"].to_numpy() - modele.predict(essai[ENTREES]))))
    assert erreur < 5.0, f"erreur trop grande : {erreur:.2f} °C"
    assert modele.contributions(essai[ENTREES]) is None


def test_contributions_expliquent_la_prediction():
    t = tableau_exemple()
    a, r, essai = entrainement.decouper_par_date(t)
    modele = entrainement.entrainer(a, r, ENTREES)
    if not hasattr(modele, "contributions"):
        return
    valeurs = modele.contributions(essai[ENTREES].head(5))
    if valeurs is None:
        return
    # dernière colonne = valeur de départ ; la somme doit redonner la prédiction
    somme = valeurs[0].sum()
    prediction = modele.predict(essai[ENTREES].head(5))[0]
    assert abs(somme - prediction) < 0.01, (somme, prediction)


def test_prediction_suit_la_charge():
    t = tableau_exemple()
    a, r, _ = entrainement.decouper_par_date(t)
    modele = entrainement.entrainer(a, r, ENTREES)
    essai = pd.DataFrame({"charge_pct": [10.0, 90.0], "t_ambiante": [28.0, 28.0]})
    basse, haute = modele.predict(essai)
    assert haute > basse + 20, (basse, haute)


if __name__ == "__main__":
    if not PRET:
        print(f"  IGNORÉ : bibliothèque manquante ({MOTIF})")
        sys.exit(0)
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
