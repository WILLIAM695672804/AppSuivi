"""Tests du versionnement des modèles et des travaux d'entraînement.

Aucun entraînement réel n'est lancé : on vérifie la mécanique, pas LightGBM.
"""

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ia import modeles_en_service as versions
from ia import travaux
from ia.site import Site

SITE = Site.charger("brasserie")


class BoosterFactice:
    """Se contente d'écrire un fichier, comme le ferait LightGBM."""

    def __init__(self, nom):
        self.nom = nom

    def save_model(self, chemin):
        Path(chemin).write_text(f"modele {self.nom}", encoding="utf-8")


class ModeleFactice:
    def __init__(self, nom):
        self.booster = BoosterFactice(nom)


def bac_a_sable():
    """Redirige les modèles vers un dossier temporaire, le temps d'un test."""
    dossier = Path(tempfile.mkdtemp(prefix="sasi-modeles-"))
    versions.MODELES = dossier
    return dossier


def enregistrer(erreurs=None, en_service=True, **details):
    modeles = {"MOT": ModeleFactice("MOT"), "ARM": ModeleFactice("ARM")}
    return versions.enregistrer(SITE, modeles, {"Z1-ELV-01": {}}, ["charge_pct"],
                                erreurs or {"MOT": 0.3, "ARM": 0.4},
                                en_service=en_service, **details)


# ---------------------------------------------------------------- versions
def test_premier_enregistrement_cree_la_version_1():
    bac_a_sable()
    cible = enregistrer()
    assert cible.name == "v1", cible
    registre = versions.lire_versions(SITE)
    assert registre["en_service"] == "v1"
    assert registre["versions"][0]["erreur_moyenne"] == 0.35


def test_les_versions_se_suivent():
    bac_a_sable()
    enregistrer()
    deuxieme = enregistrer(en_service=False)
    assert deuxieme.name == "v2"
    registre = versions.lire_versions(SITE)
    assert [v["version"] for v in registre["versions"]] == ["v2", "v1"]
    assert registre["en_service"] == "v1", "une nouvelle version n'entre pas en service seule"


def test_mise_en_service_copie_les_fichiers():
    bac_a_sable()
    enregistrer(erreurs={"MOT": 0.9})
    enregistrer(erreurs={"MOT": 0.1}, en_service=False)
    versions.mettre_en_service(SITE, "v2")

    registre = versions.lire_versions(SITE)
    assert registre["en_service"] == "v2"
    assert [v["en_service"] for v in registre["versions"]] == [True, False]
    fiche = json.loads((versions.dossier(SITE) / "modeles.json").read_text(encoding="utf-8"))
    assert fiche["version"] == "v2", "les fichiers servis doivent être ceux de la version"


def test_retour_a_la_version_precedente():
    bac_a_sable()
    enregistrer()
    enregistrer(en_service=True)
    versions.mettre_en_service(SITE, "v1")
    assert versions.lire_versions(SITE)["en_service"] == "v1"


def test_version_inconnue_refusee():
    bac_a_sable()
    enregistrer()
    try:
        versions.mettre_en_service(SITE, "v99")
        raise AssertionError("une version inconnue doit être refusée")
    except ValueError as souci:
        assert "v99" in str(souci)


def test_modele_anterieur_devient_la_version_1():
    """Un modèle entraîné avant le versionnement ne doit pas être perdu."""
    dossier = bac_a_sable()
    cible = dossier / SITE.identifiant.lower()
    cible.mkdir(parents=True)
    (cible / "MOT.txt").write_text("ancien modèle", encoding="utf-8")
    (cible / "modeles.json").write_text(json.dumps({
        "site": SITE.identifiant, "entraine_le": "2026-09-22T17:36:32",
        "entrees": ["charge_pct"], "familles": ["MOT"], "erreurs": {"MOT": 0.28},
    }), encoding="utf-8")

    registre = versions.adopter_existant(SITE)
    assert registre["en_service"] == "v1"
    assert (dossier / SITE.identifiant.lower() / "versions" / "v1" / "MOT.txt").exists()


def test_adoption_sans_effet_si_deja_versionne():
    bac_a_sable()
    enregistrer()
    avant = versions.lire_versions(SITE)
    assert versions.adopter_existant(SITE) == avant


# ---------------------------------------------------------------- travaux
def test_avancement_dun_travail():
    travail = travaux.Travail("T-9001", "brasserie", "Awa N.")
    assert travail.progression == 0
    travail.avancer("calibrage", "17 équipements")
    attendu = sum(poids for clef, _, poids in travaux.ETAPES
                  if clef in ("lecture", "entrainement"))
    assert travail.progression == attendu, travail.progression
    resume = travail.resume()
    assert resume["etape_libelle"] == "Calibrage de chaque équipement"
    assert resume["journal"][0]["detail"] == "17 équipements"


def test_un_seul_entrainement_a_la_fois():
    travaux.TRAVAUX.clear()
    occupe = travaux.Travail("T-9002", "brasserie", "Awa N.")
    travaux.TRAVAUX[occupe.identifiant] = occupe
    try:
        travaux.lancer_entrainement("brasserie", par="Serge M.")
        raise AssertionError("une demande concurrente doit être refusée")
    except RuntimeError as souci:
        assert "déjà en cours" in str(souci)
    finally:
        travaux.TRAVAUX.clear()


def test_inspection_a_ses_propres_etapes():
    travail = travaux.Travail("T-9004", "brasserie", "Awa N.",
                              etapes=travaux.ETAPES_INSPECTION, genre="inspection")
    travail.avancer("inspection")
    resume = travail.resume()
    assert resume["genre"] == "inspection"
    assert resume["etape_libelle"] == "Inspection du raisonnement"
    assert travail.progression == 40, travail.progression


def test_travail_termine_libere_la_place():
    travaux.TRAVAUX.clear()
    fini = travaux.Travail("T-9003", "brasserie", "Awa N.")
    fini.etat = "termine"
    fini.fin = datetime.now()
    travaux.TRAVAUX[fini.identifiant] = fini
    assert travaux.en_cours() is None
    assert travaux.lire("T-9003")["etat"] == "termine"
    assert travaux.lire("inconnu") is None
    travaux.TRAVAUX.clear()


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
