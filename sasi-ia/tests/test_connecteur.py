"""Tests du connecteur. N'utilise que Python (aucun serveur de messages nécessaire)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connecteur.main import Connecteur, horodatage_en_secondes
from ia.site import Site

SITE = Site.charger("brasserie")
HORODATAGE = "2026-01-05T07:00:00Z"
SECONDES = horodatage_en_secondes(HORODATAGE)


class DepotFactice:
    def __init__(self):
        self.mesures, self.contextes, self.techniques = [], [], []

    def enregistrer_mesures(self, mesures): self.mesures.extend(mesures)
    def enregistrer_contexte(self, horodatage, lignes): self.contextes.extend(lignes)
    def enregistrer_ambiance(self, horodatage, site, lignes): pass
    def enregistrer_alerte_technique(self, alerte): self.techniques.append(alerte)


def connecteur():
    publications = []
    depot = DepotFactice()
    c = Connecteur(SITE, depot, publier=lambda sujet, message: publications.append((sujet, json.loads(message))))
    return c, depot, publications


def fiche(equipement="Z1-ELV-01", t_max=52.4, camera="CAM-Z1"):
    return json.dumps({"site": "SIM01", "camera": camera, "horodatage": HORODATAGE,
                       "source": "jumeau",
                       "zones": [{"equipement": equipement, "t_max": t_max,
                                  "t_moy": 45.0, "t_min": 38.0}]})


def test_mesure_conservee():
    c, depot, publications = connecteur()
    conservees = c.traiter_message("sasi/SIM01/CAM-Z1/mesures", fiche(), maintenant=SECONDES)
    assert len(conservees) == 1 and depot.mesures, conservees
    assert any(sujet.endswith("mesures_validees") for sujet, _ in publications)


def test_equipement_inconnu_ecarte():
    c, depot, publications = connecteur()
    c.traiter_message("s", fiche(equipement="ZZ-XXX-99"), maintenant=SECONDES)
    assert depot.mesures == []
    assert any(message.get("motif") == "equipement_inconnu" for _, message in publications)


def test_valeur_aberrante_ecartee():
    c, depot, _ = connecteur()
    c.traiter_message("s", fiche(t_max=1500.0), maintenant=SECONDES)
    assert depot.mesures == [] and c.compteurs["ecartees"] == 1


def test_message_illisible_ignore():
    c, depot, _ = connecteur()
    assert c.traiter_message("s", "ceci n'est pas du JSON", maintenant=SECONDES) == []
    assert depot.mesures == []


def test_compteurs():
    c, _, _ = connecteur()
    c.traiter_message("s", fiche(), maintenant=SECONDES)
    c.traiter_message("s", fiche(t_max=2000.0), maintenant=SECONDES)
    assert c.compteurs == {"recues": 2, "conservees": 1, "ecartees": 1}, c.compteurs


def test_contexte_enregistre():
    c, depot, _ = connecteur()
    c.traiter_contexte(json.dumps({"horodatage": HORODATAGE, "equipements": [
        {"equipement": "Z1-ELV-01", "etat": "marche", "charge_pct": 75}]}))
    assert depot.contextes and depot.contextes[0]["charge_pct"] == 75


def test_camera_muette_signalee():
    c, depot, publications = connecteur()
    c.traiter_message("s", fiche(), maintenant=SECONDES)
    alertes = c.controler(SECONDES + 700)
    assert len(alertes) == 1 and alertes[0]["type"] == "camera_muette", alertes
    assert depot.techniques, "l'alerte technique doit être enregistrée"


def test_rejeu_ancien_ne_declenche_pas_de_camera_muette():
    """Un lot rejoué est daté du passé : les contrôles suivent l'horloge des données."""
    import time
    c, _, _ = connecteur()
    c.traiter_message("s", fiche(), maintenant=SECONDES)
    assert c.controler(time.time()) == [], "le rejeu ne doit pas rendre les caméras muettes"


def test_horodatage_accepte_un_nombre():
    assert horodatage_en_secondes(1767600000.0) == 1767600000.0


def test_horodatage_converti():
    assert horodatage_en_secondes("1970-01-01T00:00:10Z") == 10.0


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
