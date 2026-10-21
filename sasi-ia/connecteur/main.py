"""Connecteur : porte d'entrée des mesures (cahier des charges technique, chapitre 5).

Il reçoit les mesures (du jumeau numérique ou d'une vraie caméra), les contrôle,
les enregistre dans la base, puis prévient l'IA.

    python -m connecteur.main

Réglages par variables d'environnement :
    SASI_SITE   nom du site           (défaut : brasserie)
    SASI_MQTT   adresse du serveur    (défaut : localhost)
    SASI_BASE   adresse de la base    (défaut : aucune, les mesures ne sont pas enregistrées)
"""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from ia import controles
from ia.site import Site

RACINE = Path(__file__).resolve().parents[1]

SUJET_MESURES = "sasi/{site}/+/mesures"
SUJET_CONTEXTE = "sasi/{site}/contexte"
SUJET_PANNES = "sasi/{site}/jumeau/pannes"
SUJET_HORLOGE = "sasi/{site}/jumeau/horloge"
SUJET_VALIDEES = "sasi/{site}/interne/mesures_validees"
SUJET_TECHNIQUE = "sasi/{site}/interne/alertes_techniques"

PERIODE_CONTROLE_S = 60

# Au-delà de cet écart entre l'horloge de la machine et l'horodatage des mesures,
# on considère que le flux est rejoué (outils/rejeu.py, essais, démonstrations) :
# les contrôles de caméra se règlent alors sur l'horloge des données.
ECART_REJEU_S = 3600


def horodatage_en_secondes(horodatage):
    """Convertit « 2026-09-19T14:30:10Z » en secondes depuis 1970.

    Un nombre de secondes est accepté tel quel : certains émetteurs l'envoient
    déjà sous cette forme.
    """
    if isinstance(horodatage, (int, float)):
        return float(horodatage)
    return datetime.fromisoformat(str(horodatage).replace("Z", "+00:00")).timestamp()


class Connecteur:
    def __init__(self, site, depot=None, publier=None, journal=None):
        self.site = site
        self.depot = depot                 # écriture en base (facultative)
        self.publier = publier or (lambda sujet, message: None)
        # Journal des pannes annoncées par le jumeau : vérité de référence du
        # contrôle automatique (conventions, 6.4). Facultatif en service réel,
        # où personne n'annonce les pannes à l'avance.
        self.journal = journal
        self.horloge = None                # mode et facteur annoncés par le jumeau
        self.connus = set(site.liste())
        self.surveillance = controles.SurveillanceCameras()
        self.compteurs = {"recues": 0, "conservees": 0, "ecartees": 0}
        self.dernier_controle = 0.0
        self.dernier_reel = 0.0            # dernier contrôle, à l'horloge de la machine
        self.horloge_donnees = None        # horodatage le plus récent reçu

    def maintenant(self, horloge=None):
        """Instant de référence des contrôles.

        En service, c'est l'horloge de la machine. Quand un lot ancien est rejoué,
        elle s'écarte de l'horodatage des mesures : on suit alors les données,
        sinon toutes les caméras seraient déclarées muettes.
        """
        horloge = horloge if horloge is not None else time.time()
        if self.horloge_donnees is None:
            return horloge
        if abs(horloge - self.horloge_donnees) > ECART_REJEU_S:
            return self.horloge_donnees
        return horloge

    # ---------- réception ----------
    def traiter_message(self, sujet, charge_utile, maintenant=None):
        """Traite un message reçu. Renvoie la liste des mesures conservées."""
        maintenant = maintenant if maintenant is not None else time.time()
        try:
            fiche = json.loads(charge_utile)
        except (ValueError, TypeError):
            self.compteurs["ecartees"] += 1
            return []

        camera = fiche.get("camera", "inconnue")
        horodatage = fiche.get("horodatage")
        secondes = horodatage_en_secondes(horodatage) if horodatage else maintenant

        if self.horloge_donnees is None or secondes > self.horloge_donnees:
            self.horloge_donnees = secondes

        retour = self.surveillance.enregistrer(camera, secondes)
        if retour:
            self.publier(SUJET_TECHNIQUE.format(site=self.site.identifiant),
                         json.dumps(retour))

        conservees = []
        for zone in fiche.get("zones", []):
            self.compteurs["recues"] += 1
            mesure = {"equipement": zone.get("equipement"), "t_max": zone.get("t_max"),
                      "secondes": secondes}
            acceptee, motif = controles.verifier_mesure(mesure, self.connus, maintenant)
            if not acceptee:
                self.compteurs["ecartees"] += 1
                self.publier(SUJET_TECHNIQUE.format(site=self.site.identifiant),
                             json.dumps({"type": "mesure_ecartee", "motif": motif,
                                         "equipement": mesure["equipement"],
                                         "camera": camera, "secondes": secondes}))
                continue

            self.compteurs["conservees"] += 1
            complete = {"horodatage": horodatage, "secondes": secondes,
                        "camera": camera, "equipement": mesure["equipement"],
                        "t_max": float(zone["t_max"]),
                        "t_moy": zone.get("t_moy"), "t_min": zone.get("t_min"),
                        "source": fiche.get("source", "camera")}
            conservees.append(complete)
            self.surveillance.enregistrer(camera, secondes, complete["t_max"])

        if conservees:
            if self.depot:
                self.depot.enregistrer_mesures(conservees)
            self.publier(SUJET_VALIDEES.format(site=self.site.identifiant),
                         json.dumps({"mesures": conservees}))
        return conservees

    def traiter_contexte(self, charge_utile):
        """Enregistre l'état de marche et la charge des équipements."""
        try:
            fiche = json.loads(charge_utile)
        except (ValueError, TypeError):
            return []
        lignes = fiche.get("equipements", [])
        if self.depot and lignes:
            self.depot.enregistrer_contexte(fiche.get("horodatage"), lignes)
        if self.depot and fiche.get("ambiance"):
            self.depot.enregistrer_ambiance(fiche.get("horodatage"),
                                            self.site.identifiant, fiche["ambiance"])
        return lignes

    def traiter_panne(self, charge_utile):
        """Enregistre une panne annoncée par le jumeau (début ou fin)."""
        if self.journal is None:
            return None
        complete = self.journal.appliquer(charge_utile)
        if complete:
            print(f"Panne {complete['id']} close : {complete['equipement']}, "
                  f"{complete['type']}")
        return complete

    def traiter_horloge(self, charge_utile):
        """Retient le mode d'horloge du jumeau : temps réel ou accéléré."""
        try:
            fiche = json.loads(charge_utile)
        except (ValueError, TypeError):
            return None
        if not isinstance(fiche, dict) or fiche.get("mode") not in ("reel", "accelere"):
            return None
        self.horloge = fiche
        print(f"Horloge du jumeau : {fiche['mode']}, facteur {fiche.get('facteur', 1)}"
              + (f", scénario « {fiche['scenario']} »" if fiche.get("scenario") else ""))
        return fiche

    # ---------- surveillance des caméras ----------
    def controler(self, maintenant=None):
        maintenant = self.maintenant(maintenant)
        alertes = self.surveillance.controler(maintenant)
        for alerte in alertes:
            self.publier(SUJET_TECHNIQUE.format(site=self.site.identifiant),
                         json.dumps(alerte))
            if self.depot:
                self.depot.enregistrer_alerte_technique(alerte)
        self.dernier_controle = maintenant
        return alertes


# ---------------------------------------------------------------- exécution
def principal():
    import messagerie                        # importé ici : inutile pour les tests

    site = Site.charger(os.environ.get("SASI_SITE", "brasserie"))

    depot = None
    if os.environ.get("SASI_BASE"):
        from connecteur.depot import Depot
        depot = Depot(os.environ["SASI_BASE"])

    from connecteur.journal_pannes import JournalPannes
    journal = JournalPannes(
        RACINE / "donnees" / site.identifiant.lower() / "journal_jumeau.csv")

    client = messagerie.client("sasi-connecteur")
    connecteur = Connecteur(site, depot, journal=journal,
                            publier=lambda sujet, message: client.publish(sujet, message, qos=1))

    def a_la_connexion(client, donnees, drapeaux, code, proprietes=None):
        for sujet in (SUJET_MESURES, SUJET_CONTEXTE, SUJET_PANNES, SUJET_HORLOGE):
            client.subscribe(sujet.format(site=site.identifiant), qos=1)
        print(f"Connecteur prêt — site {site.identifiant}, "
              f"serveur {messagerie.resume()}")

    def a_la_reception(client, donnees, message):
        if message.topic.endswith("/contexte"):
            connecteur.traiter_contexte(message.payload)
        elif message.topic.endswith("/jumeau/pannes"):
            connecteur.traiter_panne(message.payload)
        elif message.topic.endswith("/jumeau/horloge"):
            connecteur.traiter_horloge(message.payload)
        else:
            connecteur.traiter_message(message.topic, message.payload)
        if time.time() - connecteur.dernier_reel >= PERIODE_CONTROLE_S:
            connecteur.dernier_reel = time.time()
            connecteur.controler()

    client.on_connect = a_la_connexion
    client.on_message = a_la_reception
    messagerie.connecter(client)
    client.loop_forever()


if __name__ == "__main__":
    principal()
