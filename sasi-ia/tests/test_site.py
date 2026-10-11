"""Tests du chargement d'un site. N'utilise que Python."""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ia.site import Site, sites_disponibles

MINIMAL = {
    "site": {"id": "TST01", "nom": "Site de test", "secteur": "Essai"},
    "zones": {"1": "Atelier"},
    "familles": {"MOT": "Moteurs et convoyeurs"},
    "planning": {"continu": {"jours": "tous", "debut": 0, "fin": 24, "charge": 70}},
    "climat": {"base": 28.0, "amplitude": 4.0},
    "groupes_jumeaux": [],
    "equipements": [
        {"id": "Z1-MOT-01", "nom": "Le moteur", "camera": "CAM-Z1", "zone": 1,
         "famille": "MOT", "activite": "continu", "plage_basse": 40, "plage_haute": 60,
         "temps_montee_min": 30, "criticite": 2},
    ],
}


def site_depuis(modifications=None):
    donnees = json.loads(json.dumps(MINIMAL))
    if modifications:
        modifications(donnees)
    return Site(donnees)


def test_chargement_minimal():
    site = site_depuis()
    assert site.identifiant == "TST01" and site.liste() == ["Z1-MOT-01"]


def test_acces_aux_informations():
    site = site_depuis()
    assert site.famille("Z1-MOT-01") == "MOT"
    assert site.plage("Z1-MOT-01") == (40, 60)
    assert site.criticite("Z1-MOT-01") == 2
    assert site.nom_equipement("Z1-MOT-01") == "Le moteur"


def test_seuils_fixes():
    assert site_depuis().seuils_fixes("Z1-MOT-01") == (75, 90)


def test_champ_manquant_refuse():
    def retirer(donnees):
        del donnees["equipements"][0]["criticite"]
    try:
        site_depuis(retirer)
    except ValueError as erreur:
        assert "criticite" in str(erreur), erreur
    else:
        raise AssertionError("un champ manquant doit être refusé")


def test_plage_incoherente_refusee():
    def inverser(donnees):
        donnees["equipements"][0]["plage_basse"] = 90
    try:
        site_depuis(inverser)
    except ValueError as erreur:
        assert "plage_basse" in str(erreur), erreur
    else:
        raise AssertionError("une plage incohérente doit être refusée")


def test_famille_inconnue_refusee():
    def changer(donnees):
        donnees["equipements"][0]["famille"] = "XXX"
    try:
        site_depuis(changer)
    except ValueError as erreur:
        assert "famille" in str(erreur), erreur
    else:
        raise AssertionError("une famille inconnue doit être refusée")


def test_criticite_hors_bornes_refusee():
    def changer(donnees):
        donnees["equipements"][0]["criticite"] = 7
    try:
        site_depuis(changer)
    except ValueError:
        pass
    else:
        raise AssertionError("une criticité hors de 1-3 doit être refusée")


def test_jumeaux():
    def ajouter(donnees):
        for lettre in "BC":
            equipement = dict(donnees["equipements"][0])
            equipement["id"] = f"Z1-ARM-01-{lettre}"
            donnees["equipements"].append(equipement)
        donnees["groupes_jumeaux"] = [["Z1-MOT-01", "Z1-ARM-01-B", "Z1-ARM-01-C"]]
    site = site_depuis(ajouter)
    assert site.jumeaux("Z1-ARM-01-B") == ["Z1-MOT-01", "Z1-ARM-01-C"]
    assert len(site.tous_les_jumeaux()) == 3


def test_groupe_avec_equipement_inconnu_refuse():
    def casser(donnees):
        donnees["groupes_jumeaux"] = [["Z1-MOT-01", "INCONNU"]]
    try:
        site_depuis(casser)
    except ValueError as erreur:
        assert "INCONNU" in str(erreur), erreur
    else:
        raise AssertionError("un groupe mal formé doit être refusé")


def test_fichier_introuvable():
    try:
        Site.charger("site_qui_nexiste_pas")
    except FileNotFoundError as erreur:
        assert "disponibles" in str(erreur), erreur
    else:
        raise AssertionError("un site inexistant doit lever une erreur claire")


def test_sites_livres_valides():
    noms = sites_disponibles()
    assert "brasserie" in noms and "minoterie" in noms, noms
    for nom in noms:
        site = Site.charger(nom)       # doit se charger sans erreur
        assert site.liste(), nom


def test_chargement_depuis_un_chemin():
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(MINIMAL, f)
        chemin = f.name
    try:
        assert Site.charger(chemin).identifiant == "TST01"
    finally:
        Path(chemin).unlink()


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
