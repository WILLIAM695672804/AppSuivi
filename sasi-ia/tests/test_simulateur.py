"""Tests du mini jumeau numérique. N'utilise que Python."""

import csv
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import outils.simulateur as simulateur

DEBUT = datetime(2026, 1, 5, 0, 0, 0)          # un lundi


def simuler_dans(dossier, jours=1, pannes=(), graine=1234):
    simulateur.SORTIE = Path(dossier)
    simulateur.simuler("T", DEBUT, jours=jours, pannes=pannes, graine=graine)
    with open(Path(dossier) / "mesures_T.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_planning_dimanche_arret():
    dimanche = DEBUT + timedelta(days=6, hours=10)
    assert simulateur.en_marche("conditionnement", dimanche)[0] is False


def test_planning_en_continu():
    dimanche = DEBUT + timedelta(days=6, hours=3)
    assert simulateur.en_marche("continu", dimanche)[0] is True


def test_ambiance_plus_chaude_l_apres_midi():
    import random
    alea = random.Random(1)
    nuit = simulateur.ambiance(1, DEBUT + timedelta(hours=3), alea)
    apres_midi = simulateur.ambiance(1, DEBUT + timedelta(hours=15), alea)
    assert apres_midi > nuit + 3, (nuit, apres_midi)


def test_chaufferie_plus_chaude_que_les_autres_zones():
    import random
    alea = random.Random(1)
    instant = DEBUT + timedelta(hours=12)
    assert simulateur.ambiance(4, instant, alea) > simulateur.ambiance(1, instant, alea) + 4


def test_fichiers_produits():
    dossier = tempfile.mkdtemp()
    try:
        simuler_dans(dossier)
        for nom in ("mesures_T.csv", "contexte_T.csv", "ambiance_T.csv"):
            assert (Path(dossier) / nom).exists(), nom
    finally:
        shutil.rmtree(dossier)


def test_tous_les_equipements_presents():
    dossier = tempfile.mkdtemp()
    try:
        lignes = simuler_dans(dossier)
        vus = {l["equipement"] for l in lignes}
        attendus = {e["id"] for e in simulateur.equipements()}
        assert vus == attendus, attendus - vus
    finally:
        shutil.rmtree(dossier)


def test_temperatures_plausibles():
    dossier = tempfile.mkdtemp()
    try:
        lignes = simuler_dans(dossier)
        for l in lignes:
            t = float(l["t_max"])
            assert -10 < t < 300, (l["equipement"], t)
            assert float(l["t_moy"]) < t, l
    finally:
        shutil.rmtree(dossier)


def test_reproductible():
    a, b = tempfile.mkdtemp(), tempfile.mkdtemp()
    try:
        assert simuler_dans(a, graine=42) == simuler_dans(b, graine=42)
    finally:
        shutil.rmtree(a); shutil.rmtree(b)


def test_graine_differente_donne_des_donnees_differentes():
    a, b = tempfile.mkdtemp(), tempfile.mkdtemp()
    try:
        assert simuler_dans(a, graine=1) != simuler_dans(b, graine=2)
    finally:
        shutil.rmtree(a); shutil.rmtree(b)


def test_panne_rechauffe_l_equipement():
    sans, avec = tempfile.mkdtemp(), tempfile.mkdtemp()
    panne = [("P-T", "Z1-ELV-01", "derive_lente",
              DEBUT + timedelta(hours=8), DEBUT + timedelta(hours=12), 10.0)]
    try:
        froid = [float(l["t_max"]) for l in simuler_dans(sans, graine=7)
                 if l["equipement"] == "Z1-ELV-01"]
        chaud = [float(l["t_max"]) for l in simuler_dans(avec, pannes=panne, graine=7)
                 if l["equipement"] == "Z1-ELV-01"]
        assert max(chaud) > max(froid) + 15, (max(froid), max(chaud))
    finally:
        shutil.rmtree(sans); shutil.rmtree(avec)


def test_journal_ecrit_avec_les_pannes():
    dossier = tempfile.mkdtemp()
    panne = [("P-T", "Z6-RES-01", "chauffe_a_vide",
              DEBUT + timedelta(hours=22), DEBUT + timedelta(hours=23), 40.0)]
    try:
        simuler_dans(dossier, pannes=panne)
        with open(Path(dossier) / "journal_T.csv", encoding="utf-8") as f:
            lignes = list(csv.DictReader(f))
        assert len(lignes) == 1 and lignes[0]["equipement"] == "Z6-RES-01", lignes
    finally:
        shutil.rmtree(dossier)


# --------------------------------------------------- pannes du guide d'audit
def panne(type_panne, intensite=5.0, duree_h=4.0):
    from datetime import datetime, timedelta
    debut = datetime(2026, 1, 5, 8, 0, 0)
    return ("P-99", "EQ", type_panne, debut, debut + timedelta(hours=duree_h), intensite)


def chaleur(type_panne, minutes, intensite=5.0, duree_h=4.0):
    from datetime import timedelta
    fiche = panne(type_panne, intensite, duree_h)
    return simulateur.supplement_panne(fiche, fiche[3] + timedelta(minutes=minutes))[0]


def test_colmatage_filtre_saggrave():
    """« Colmatage filtre d'air comburant » : dérive lente qui s'accélère."""
    debut, milieu, fin = chaleur("colmatage_filtre", 30), chaleur("colmatage_filtre", 120), \
        chaleur("colmatage_filtre", 240)
    assert debut < milieu < fin, (debut, milieu, fin)
    assert fin > 4 * milieu / 3, "l'aggravation doit être plus que proportionnelle"


def test_surchauffe_bruleur_atteint_un_palier():
    """« Arrêt d'urgence brûleur » : montée sévère puis palier haut."""
    assert chaleur("surchauffe_bruleur", 5) < chaleur("surchauffe_bruleur", 20)
    assert chaleur("surchauffe_bruleur", 20) == chaleur("surchauffe_bruleur", 120)


def test_rupture_calorifuge_est_immediate():
    """« Rupture joint / début de fumée » : la paroi bondit en deux minutes."""
    assert chaleur("rupture_calorifuge", 3) == 5.0
    assert chaleur("rupture_calorifuge", 1) < 5.0


def test_friction_roulement_semballe():
    """La friction produit la chaleur qui aggrave la friction."""
    assert chaleur("friction_roulement", 240) > 10 * chaleur("friction_roulement", 60)


def test_panne_terminee_ne_chauffe_plus():
    assert chaleur("friction_roulement", 300, duree_h=4.0) == 0.0


def test_type_inconnu_sans_effet():
    assert chaleur("bavardage", 60) == 0.0


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
