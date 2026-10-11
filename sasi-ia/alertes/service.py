"""Service des alertes : reçoit les changements de niveau, prévient les équipes.

    python -m alertes.service

Il écoute l'IA, tient la vie de chaque alerte (chapitre 7 du cahier technique) et
envoie les notifications et les SMS.
"""

import json
import os
import time

from alertes.moteur import MoteurAlertes
from ia import retours
from ia.site import Site

SUJET_NIVEAUX = "sasi/{site}/interne/niveaux"
SUJET_COMMANDES = "sasi/{site}/commandes"
SUJET_ALERTES = "sasi/{site}/alertes"
SUJET_ETATS = "sasi/{site}/niveaux"
PERIODE_CONTROLE_S = 30


class ServiceAlertes:
    def __init__(self, site, moteur=None, publier=None, depot=None, envoyer_sms=None,
                 registre_retours=None):
        self.site = site
        self.moteur = moteur or MoteurAlertes()
        self.publier = publier or (lambda sujet, message: None)
        self.depot = depot
        self.envoyer_sms = envoyer_sms or (lambda destinataire, texte: True)
        self.niveaux = {equipement: "normal" for equipement in site.liste()}
        # Ce que les équipes constatent redescend vers l'IA : une alerte clôturée
        # « non justifiée » devient une période de fonctionnement normal à apprendre.
        self.retours = registre_retours if registre_retours is not None else retours.Registre(site)

    def traiter_niveau(self, fiche):
        """Reçoit un changement de niveau venant de l'IA."""
        equipement = fiche["equipement"]
        niveau = fiche["niveau"]
        self.niveaux[equipement] = niveau
        explication = {"raison": fiche.get("raison"), "action": fiche.get("action"),
                       "facteurs": fiche.get("facteurs", []),
                       "t_mesuree": fiche.get("t_mesuree"),
                       "t_attendue": fiche.get("t_attendue"),
                       "score": fiche.get("score"),
                       "risque": fiche.get("risque"),
                       "risque_horizon_min": fiche.get("risque_horizon_min"),
                       "risque_minutes_avant_seuil": fiche.get("risque_minutes_avant_seuil"),
                       "risque_seuil": fiche.get("risque_seuil"),
                       "risque_raison": fiche.get("risque_raison")}

        envois = self.moteur.signaler(equipement, niveau, fiche.get("secondes", time.time()),
                                      explication)
        self._diffuser(equipement, envois, explication)
        return envois

    def _diffuser(self, equipement, envois, explication):
        alerte = self.moteur.ouvertes.get(equipement)
        if alerte is not None:
            resume = alerte.resume()
            self.publier(SUJET_ALERTES.format(site=self.site.identifiant),
                         json.dumps(resume))
            if self.depot:
                self.depot.enregistrer_alerte(
                    {**resume, "debut": resume["debut"]}, explication)
        self.publier(SUJET_ETATS.format(site=self.site.identifiant),
                     json.dumps({"niveaux": self.niveaux}))
        for envoi in envois:
            if envoi["canal"] == "sms":
                texte = self._texte_sms(equipement, explication)
                envoi["reussie"] = bool(self.envoyer_sms(envoi["destinataire"], texte))
            if self.depot:
                self.depot.enregistrer_alerte_technique(
                    {"type": "notification", "message": json.dumps(envoi),
                     "horodatage": None, "camera": None})

    def _texte_sms(self, equipement, explication):
        alerte = self.moteur.ouvertes.get(equipement)
        niveau = alerte.niveau.upper() if alerte else "ALERTE"
        nom = self.site.nom_equipement(equipement)
        return f"SASI {niveau} — {nom} ({equipement}). {explication.get('raison', '')}"[:300]

    # ---------- commandes venues de l'application ----------
    def traiter_commande(self, fiche):
        """Applique une action demandée par l'application (chapitre 7 du cahier technique).

        fiche : {action, equipement, par, a_qui, constat, justifiee}
        Renvoie l'alerte modifiée, ou None si la commande ne s'applique pas.
        """
        action = fiche.get("action")
        equipement = fiche.get("equipement")
        maintenant = fiche.get("secondes", time.time())
        par = fiche.get("par", "inconnu")

        if action == "acquitter":
            alerte = self.moteur.acquitter(equipement, maintenant, par)
        elif action == "assigner":
            alerte = self.moteur.assigner(equipement, maintenant, par, fiche.get("a_qui"))
        elif action == "cloturer":
            try:
                alerte = self.moteur.cloturer(equipement, maintenant, par,
                                              fiche.get("constat"), fiche.get("justifiee"))
            except ValueError as erreur:
                self.publier(SUJET_ALERTES.format(site=self.site.identifiant),
                             json.dumps({"erreur": str(erreur), "equipement": equipement}))
                return None
        elif action == "maintenance":
            self.moteur.mettre_en_maintenance(equipement, bool(fiche.get("en_maintenance", True)))
            return None
        else:
            return None

        if alerte is None:
            return None

        if action == "cloturer":
            self._enregistrer_retour(alerte, fiche)

        resume = alerte.resume()
        self.publier(SUJET_ALERTES.format(site=self.site.identifiant), json.dumps(resume))
        if self.depot:
            self.depot.enregistrer_alerte(resume, alerte.explication)
            self.depot.enregistrer_evenement(alerte.identifiant, alerte.evenements[-1])
            if action == "cloturer":
                self.depot.enregistrer_intervention(alerte)
        return alerte

    def _enregistrer_retour(self, alerte, fiche):
        """Transforme la réponse « alerte justifiée ? » en leçon pour l'IA."""
        if self.retours is None:
            return None
        motif = fiche.get("constat") or "Sans compte rendu"
        par = fiche.get("par", "inconnu")
        debut, fin = alerte.debut, alerte.fin or fiche.get("secondes", time.time())
        try:
            if fiche.get("justifiee"):
                return self.retours.ajouter_confirme(alerte.equipement, debut, fin,
                                                     motif, par, alerte.identifiant)
            return self.retours.ajouter_fausse_alerte(alerte.equipement, debut, fin,
                                                      motif, par, alerte.identifiant)
        except (ValueError, OSError) as souci:      # un retour raté ne bloque pas la clôture
            print(f"Retour non enregistré : {souci}")
            return None

    def controler(self, maintenant=None):
        envois = self.moteur.controler(maintenant if maintenant is not None else time.time())
        for envoi in envois:
            if envoi["canal"] == "sms":
                envoi["reussie"] = bool(self.envoyer_sms(envoi["destinataire"],
                                                         f"SASI — relance {envoi['alerte']}"))
        return envois


def principal():
    import paho.mqtt.client as mqtt

    site = Site.charger(os.environ.get("SASI_SITE", "brasserie"))
    adresse = os.environ.get("SASI_MQTT", "localhost")

    depot = None
    if os.environ.get("SASI_BASE"):
        from connecteur.depot import Depot
        depot = Depot(os.environ["SASI_BASE"])

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    service = ServiceAlertes(site, depot=depot,
                             publier=lambda sujet, msg: client.publish(sujet, msg, qos=1),
                             envoyer_sms=envoyer_sms_gammu)
    print(f"Retours du terrain : {service.retours.resume()['total']} déjà enregistrés")

    def a_la_connexion(client, donnees, drapeaux, code, proprietes=None):
        client.subscribe(SUJET_NIVEAUX.format(site=site.identifiant), qos=1)
        client.subscribe(SUJET_COMMANDES.format(site=site.identifiant), qos=1)
        print(f"Service des alertes prêt — site {site.identifiant}")

    def a_la_reception(client, donnees, message):
        fiche = json.loads(message.payload)
        if message.topic.endswith("/commandes"):
            service.traiter_commande(fiche)
        else:
            service.traiter_niveau(fiche)

    client.on_connect = a_la_connexion
    client.on_message = a_la_reception
    client.connect(adresse, 1883, keepalive=60)

    client.loop_start()
    try:
        while True:
            service.controler()
            time.sleep(PERIODE_CONTROLE_S)
    finally:
        client.loop_stop()


def envoyer_sms_gammu(destinataire, texte):
    """Envoi d'un SMS par le modem 4G (Gammu), sans passer par Internet.

    Le numéro exact de chaque destinataire viendra de la table « abonnement ».
    Tant qu'aucun modem n'est branché, l'envoi est seulement affiché.
    """
    numero = os.environ.get("SASI_SMS_" + destinataire.upper())
    if not numero:
        print(f"[SMS simulé → {destinataire}] {texte}")
        return True
    import subprocess
    resultat = subprocess.run(["gammu", "sendsms", "TEXT", numero, "-text", texte],
                              capture_output=True, text=True)
    return resultat.returncode == 0


if __name__ == "__main__":
    principal()
