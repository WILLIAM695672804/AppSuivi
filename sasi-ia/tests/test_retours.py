"""Tests du retour terrain : ce que les équipes corrigent doit atteindre l'IA.

Les tests qui filtrent des mesures ont besoin de pandas ; ils sont ignorés s'il
n'est pas installé. Les autres tournent avec Python seul.
"""

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alertes.service import ServiceAlertes
from ia import retours
from ia.site import Site

try:
    import pandas as pd
    AVEC_PANDAS = True
except ImportError:
    AVEC_PANDAS = False

SITE = Site.charger("brasserie")
DEBUT = 1767600000.0            # 5 janvier 2026


def registre():
    return retours.Registre(SITE, dossier=tempfile.mkdtemp(prefix="sasi-retours-"))


# ---------------------------------------------------------------- registre
def test_fausse_alerte_couvre_aussi_ce_qui_precede():
    """La dérive commence avant le franchissement du seuil."""
    r = registre()
    fiche = r.ajouter_fausse_alerte("Z1-MOU-01", DEBUT, DEBUT + 600,
                                    "Nettoyage à la vapeur", "Awa N.")
    assert fiche["debut"] == DEBUT - retours.MARGE_AVANT_S
    assert fiche["fin"] == DEBUT + 600 + retours.MARGE_APRES_S
    assert fiche["genre"] == retours.FAUSSE_ALERTE


def test_periode_a_lenvers_refusee():
    r = registre()
    try:
        r.ajouter_manque("Z1-MOU-01", DEBUT + 600, DEBUT, "…", "Awa N.")
        raise AssertionError("une période à l'envers doit être refusée")
    except ValueError as souci:
        assert "période" in str(souci).lower()


def test_genre_inconnu_refuse():
    r = registre()
    try:
        r.ajouter("bavardage", "Z1-MOU-01", DEBUT, DEBUT + 60, "…", "Awa N.")
        raise AssertionError("un genre inconnu doit être refusé")
    except ValueError as souci:
        assert "inconnu" in str(souci)


def test_resume_compte_chaque_genre():
    r = registre()
    r.ajouter_fausse_alerte("Z1-MOU-01", DEBUT, DEBUT + 60, "Vapeur", "Awa N.")
    r.ajouter_manque("Z2-CHE-01", DEBUT, DEBUT + 60, "Roulement", "Serge M.")
    r.ajouter_confirme("Z5-PAS-01", DEBUT, DEBUT + 60, "Défaut réel", "Serge M.")
    bilan = r.resume()
    assert (bilan["fausses_alertes"], bilan["manques"], bilan["confirmes"]) == (1, 1, 1)
    assert bilan["en_attente"] == 3


def test_retours_conserves_sur_le_disque():
    r = registre()
    r.ajouter_manque("Z1-MOU-01", DEBUT, DEBUT + 60, "Roulement grippé", "Serge M.")
    relu = retours.Registre(SITE, dossier=r.dossier)
    assert len(relu.retours) == 1
    assert relu.retours[0]["motif"] == "Roulement grippé"


def test_prise_en_compte_vide_la_file():
    r = registre()
    r.ajouter_manque("Z1-MOU-01", DEBUT, DEBUT + 60, "Roulement", "Serge M.")
    r.marquer_pris_en_compte()
    assert r.en_attente() == []


# ---------------------------------------------------------------- effet sur les mesures
def tableau_d_essai():
    instants = [datetime.fromtimestamp(DEBUT + 60 * i, tz=timezone.utc) for i in range(40)]
    return pd.DataFrame({
        "horodatage": instants,
        "equipement": ["Z1-MOU-01"] * 20 + ["Z2-CHE-01"] * 20,
        "t_max": [30.0] * 40,
    })


def test_une_anomalie_reelle_sort_de_lapprentissage():
    """Apprendre une vraie panne comme normale rendrait l'IA aveugle."""
    r = registre()
    r.ajouter_manque("Z1-MOU-01", DEBUT, DEBUT + 600, "Roulement grippé", "Serge M.")
    retenues, retirees = retours.mesures_apprenables(tableau_d_essai(), r)
    assert retirees == 11, retirees
    assert len(retenues) == 29
    assert (retenues["equipement"] == "Z2-CHE-01").sum() == 20, "l'autre équipement est intact"


def test_une_fausse_alerte_reste_apprenable():
    """C'est même le but : le modèle doit apprendre que c'était normal."""
    r = registre()
    r.ajouter_fausse_alerte("Z1-MOU-01", DEBUT, DEBUT + 600, "Vapeur", "Awa N.")
    retenues, retirees = retours.mesures_apprenables(tableau_d_essai(), r)
    assert retirees == 0
    assert len(retenues) == 40


def test_marquage_des_mesures():
    r = registre()
    r.ajouter_manque("Z1-MOU-01", DEBUT, DEBUT + 300, "Roulement", "Serge M.")
    marque = retours.appliquer_aux_mesures(tableau_d_essai(), r)
    assert (marque["retour"] == retours.MANQUE).sum() == 6
    assert (marque["retour"] == "").sum() == 34


# ---------------------------------------------------------------- clôture d'alerte
def service():
    r = registre()
    return ServiceAlertes(SITE, registre_retours=r), r


def ouvrir_alerte(service_alertes, equipement="Z1-MOU-01"):
    service_alertes.traiter_niveau({"equipement": equipement, "niveau": "inspection",
                                    "secondes": DEBUT, "raison": "Chauffe",
                                    "action": "Vérifier"})
    service_alertes.traiter_commande({"action": "acquitter", "equipement": equipement,
                                      "secondes": DEBUT + 60, "par": "Awa N."})


def test_cloture_non_justifiee_devient_une_lecon():
    service_alertes, r = service()
    ouvrir_alerte(service_alertes)
    service_alertes.traiter_commande({
        "action": "cloturer", "equipement": "Z1-MOU-01", "secondes": DEBUT + 600,
        "par": "Awa N.", "constat": "Nettoyage à la vapeur, rien d'anormal.",
        "justifiee": False})
    fausses = r.par_genre(retours.FAUSSE_ALERTE)
    assert len(fausses) == 1, r.retours
    assert fausses[0]["equipement"] == "Z1-MOU-01"
    assert fausses[0]["alerte"].startswith("A-")
    assert "vapeur" in fausses[0]["motif"].lower()


def test_cloture_justifiee_enregistre_une_confirmation():
    service_alertes, r = service()
    ouvrir_alerte(service_alertes, "Z2-CHE-01")
    service_alertes.traiter_commande({
        "action": "cloturer", "equipement": "Z2-CHE-01", "secondes": DEBUT + 600,
        "par": "Serge M.", "constat": "Brûleur déréglé.", "justifiee": True})
    assert len(r.par_genre(retours.CONFIRME)) == 1
    assert r.par_genre(retours.FAUSSE_ALERTE) == []


def test_acquittement_seul_ne_cree_aucun_retour():
    service_alertes, r = service()
    ouvrir_alerte(service_alertes)
    assert r.retours == [], "seule une clôture porte un jugement"


SUR_MESURES = ("test_une_anomalie_reelle_sort_de_lapprentissage",
               "test_une_fausse_alerte_reste_apprenable",
               "test_marquage_des_mesures")

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    if not AVEC_PANDAS:
        tests = [t for t in tests if t.__name__ not in SUR_MESURES]
        print("  (pandas absent : les tests sur les mesures sont ignorés)")
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
