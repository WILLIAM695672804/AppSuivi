"""Tests de la liaison au serveur de messages. N'utilise que Python.

L'enjeu : un oubli de réglage ne doit pas ouvrir silencieusement le serveur de
messages sur Internet, et un mot de passe ne doit jamais apparaître dans un
journal.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import messagerie

VARIABLES = ("SASI_MQTT", "SASI_MQTT_PORT", "SASI_MQTT_UTILISATEUR",
             "SASI_MQTT_MOT_DE_PASSE", "SASI_MQTT_TLS")


class Environnement:
    """Remplace les variables d'environnement le temps d'un test."""

    def __init__(self, **valeurs):
        self.valeurs = valeurs
        self.anciennes = {}

    def __enter__(self):
        for nom in VARIABLES:
            self.anciennes[nom] = os.environ.pop(nom, None)
        os.environ.update({k: str(v) for k, v in self.valeurs.items()})
        return self

    def __exit__(self, *_):
        for nom in VARIABLES:
            os.environ.pop(nom, None)
            if self.anciennes[nom] is not None:
                os.environ[nom] = self.anciennes[nom]


def test_par_defaut_le_local_en_clair():
    """Rien ne change pour qui développe sur sa machine."""
    with Environnement():
        assert messagerie.adresse() == "localhost"
        assert messagerie.port() == messagerie.PORT_CLAIR
        assert messagerie.identite() == (None, None)
        assert not messagerie.tls_demande()


def test_le_port_suit_le_chiffrement():
    """Demander le chiffrement sans préciser le port ne doit pas rester en clair."""
    with Environnement(SASI_MQTT_TLS="1"):
        assert messagerie.port() == messagerie.PORT_CHIFFRE


def test_le_port_explicite_est_respecte():
    with Environnement(SASI_MQTT_TLS="1", SASI_MQTT_PORT="1884"):
        assert messagerie.port() == 1884


def test_un_port_illisible_ne_fait_pas_tomber_le_service():
    with Environnement(SASI_MQTT_PORT="huit-mille"):
        assert messagerie.port() == messagerie.PORT_CLAIR


def test_identite_lue_dans_l_environnement():
    with Environnement(SASI_MQTT_UTILISATEUR="sasi", SASI_MQTT_MOT_DE_PASSE="secret"):
        assert messagerie.identite() == ("sasi", "secret")


def test_compte_vide_vaut_acces_anonyme():
    """Une variable définie mais vide ne doit pas créer un compte « »."""
    with Environnement(SASI_MQTT_UTILISATEUR=""):
        assert messagerie.identite() == (None, None)


def test_le_resume_ne_laisse_pas_fuir_le_mot_de_passe():
    with Environnement(SASI_MQTT="boitier", SASI_MQTT_UTILISATEUR="sasi",
                       SASI_MQTT_MOT_DE_PASSE="secret", SASI_MQTT_TLS="1"):
        resume = messagerie.resume()
    assert "secret" not in resume
    assert "sasi" in resume and "boitier:8883" in resume and "chiffrée" in resume


def test_le_resume_dit_quand_l_acces_est_anonyme():
    """Lisible au démarrage : un serveur ouvert doit se voir dans le journal."""
    with Environnement():
        assert "anonyme" in messagerie.resume()


def test_le_resume_accepte_une_adresse_donnee():
    with Environnement():
        assert "192.168.1.20:1883" in messagerie.resume("192.168.1.20")


def test_les_formes_du_oui_sont_acceptees():
    for valeur in ("1", "oui", "true"):
        with Environnement(SASI_MQTT_TLS=valeur):
            assert messagerie.tls_demande(), valeur
    for valeur in ("0", "non", ""):
        with Environnement(SASI_MQTT_TLS=valeur):
            assert not messagerie.tls_demande(), valeur


def test_les_quatre_services_passent_par_le_module():
    """Un service qui appelle paho directement échapperait à l'authentification."""
    racine = Path(__file__).resolve().parents[1]
    for nom in ("connecteur/main.py", "ia/service.py", "alertes/service.py",
                "api/serveur.py"):
        texte = (racine / nom).read_text(encoding="utf-8")
        assert "import messagerie" in texte, nom
        assert "mqtt.Client(" not in texte, f"{nom} crée encore son client lui-même"


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
