"""Tests du générateur « chaudière » (nécessite numpy et pandas)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    from outils import scenario_chaudiere as scenario
    PRET = True
except ImportError as erreur:
    PRET, MOTIF = False, str(erreur)


def test_marche_saine_sans_panne():
    t = scenario.generer(1, sain=True)
    assert (t["etiquette"] == 0).all()
    assert 70 < t["t_corps_c"].mean() < 74, t["t_corps_c"].mean()


def test_phases_etiquetees():
    t = scenario.generer(2, debut_derive=20, debut_feu=45)
    minutes = t["secondes"] / 60
    assert (t.loc[minutes < 45, "etiquette"] == 0).all()
    assert (t.loc[(minutes >= 45) & (minutes < 60), "etiquette"] == 1).all()
    assert (t.loc[minutes >= 60, "etiquette"] == 2).all()


def test_signatures_physiques():
    t = scenario.generer(3, debut_derive=20, debut_feu=45)
    avant = t[t["secondes"] < 20 * 60]
    feu = t[t["secondes"] >= 60 * 60]
    assert feu["t_corps_c"].mean() > avant["t_corps_c"].mean() + 100
    assert feu["co_ppm"].mean() > 1000
    assert feu["taux_o2_pct"].mean() < 1.5


def test_reproductible():
    assert scenario.generer(7).equals(scenario.generer(7))


def test_pas_de_cinq_secondes():
    t = scenario.generer(4)
    assert t["secondes"].diff().dropna().eq(5).all()
    assert len(t) == 90 * 60 // 5


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
