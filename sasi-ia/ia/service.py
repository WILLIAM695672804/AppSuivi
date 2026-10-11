"""Service de l'intelligence artificielle, en continu.

Il reçoit les mesures validées par le connecteur, calcule la température
attendue, applique les trois signaux et publie les changements de niveau.

    python -m ia.service

C'est la version « en service » de ce que fait lancer_site.py sur des fichiers.
"""

import json
import os
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from ia import explication
from ia import risque as module_risque
from ia.detection import DetecteurEquipement
from ia.site import Site

RACINE = Path(__file__).resolve().parents[1]
MODELES = RACINE / "modeles"

SUJET_VALIDEES = "sasi/{site}/interne/mesures_validees"
SUJET_CONTEXTE = "sasi/{site}/contexte"
# L'application demande le rechargement après une mise en service : le jugement
# reprend avec le nouveau modèle sans interrompre la surveillance.
SUJET_MODELE = "sasi/{site}/modele"
SUJET_NIVEAUX = "sasi/{site}/interne/niveaux"
# Chaque mesure jugée, pour les courbes de l'interface quand la base est absente.
SUJET_JUGEMENTS = "sasi/{site}/interne/jugements"

MINUTES_PLAFOND = 180
MINUTES_TRANSITOIRE = 45


class ServiceIA:
    """Tient l'état de chaque équipement et juge chaque mesure à son arrivée."""

    def __init__(self, site, modeles=None, calibrages=None, publier=None, depot=None):
        self.site = site
        self.modeles = modeles or {}
        self.calibrages = calibrages or {}
        self.publier = publier or (lambda sujet, message: None)
        self.depot = depot

        self.detecteurs = {}
        self.contexte = defaultdict(dict)      # equipement -> {etat, charge_pct, depuis}
        self.ambiance = {}                     # zone -> température
        self.dernieres_mesures = {}            # equipement -> (secondes, t_max)

    def recharger_modeles(self):
        """Reprend les modèles sur le disque, sans perdre l'état des détecteurs.

        Les détecteurs gardent leur historique : une alerte en cours le reste,
        et seul le jugement des mesures suivantes change.
        """
        from ia.modeles_en_service import charger
        self.modeles, self.calibrages = charger(self.site)
        return len(self.modeles)

    # ---------- contexte ----------
    def majorer_contexte(self, fiche):
        horodatage = fiche.get("horodatage")
        secondes = _en_secondes(horodatage)
        for ligne in fiche.get("equipements", []):
            equipement = ligne["equipement"]
            ancien = self.contexte[equipement]
            if ancien.get("etat") != ligne.get("etat"):
                ancien["depuis"] = secondes
            ancien["etat"] = ligne.get("etat", "marche")
            ancien["charge_pct"] = ligne.get("charge_pct", 0.0)
        for ligne in fiche.get("ambiance", []):
            self.ambiance[int(ligne["zone"])] = ligne.get("t_ambiante")

    def _entrees(self, equipement, secondes):
        """Reconstitue les entrées du modèle pour cet équipement, à cet instant."""
        contexte = self.contexte.get(equipement, {})
        etat_marche = 1 if contexte.get("etat", "marche") == "marche" else 0
        depuis = contexte.get("depuis", secondes)
        minutes = min((secondes - depuis) / 60.0, MINUTES_PLAFOND)
        charge = contexte.get("charge_pct", 0.0)
        zone = self.site.zone(equipement)
        t_ambiante = self.ambiance.get(zone, 28.0)
        temps_montee = self.site.temps_montee_min(equipement)
        instant = datetime.fromtimestamp(secondes, tz=timezone.utc)
        basse, haute = self.site.plage(equipement)

        import math
        constante = max(temps_montee / 3.0, 1.0)
        fraction = 1 - math.exp(-minutes / constante)
        return {
            "charge_pct": charge,
            "etat_marche": etat_marche,
            "t_ambiante": t_ambiante,
            "minutes_depuis_demarrage": minutes if etat_marche else 0.0,
            "minutes_depuis_arret": 0.0 if etat_marche else minutes,
            "charge_moy_30min": charge,          # affiné dès que l'historique est disponible
            "heure": instant.hour,
            "jour_semaine": instant.weekday(),
            "plage_basse": basse,
            "plage_haute": haute,
            "fraction_chauffe": fraction if etat_marche else 1.0,
            "fraction_refroidissement": 1.0 if etat_marche else fraction,
        }

    def _regime(self, entrees):
        minutes = (entrees["minutes_depuis_demarrage"] if entrees["etat_marche"]
                   else entrees["minutes_depuis_arret"])
        return "transitoire" if minutes < MINUTES_TRANSITOIRE else "etabli"

    def _detecteur(self, equipement):
        if equipement not in self.detecteurs:
            inspection, urgence = self.site.seuils_fixes(equipement)
            self.detecteurs[equipement] = DetecteurEquipement(
                equipement, criticite=self.site.criticite(equipement),
                seuil_fixe_inspection=inspection, seuil_fixe_urgence=urgence,
                temps_montee_min=self.site.temps_montee_min(equipement))
        return self.detecteurs[equipement]

    # ---------- traitement d'une mesure ----------
    def traiter(self, mesure):
        """Juge une mesure. Renvoie l'état, et publie tout changement de niveau."""
        equipement = mesure["equipement"]
        if equipement not in self.site.equipements:
            return None
        secondes = mesure.get("secondes") or _en_secondes(mesure.get("horodatage"))
        entrees = self._entrees(equipement, secondes)

        famille = self.site.famille(equipement)
        modele = self.modeles.get(famille)
        if modele is None:
            return None            # pas encore de modèle pour cette famille
        t_attendue = float(modele.predire(entrees))

        detecteur = self._detecteur(equipement)
        reglage = self.calibrages.get(equipement, {}).get(self._regime(entrees))
        if reglage:
            detecteur.biais = reglage["biais"]
            detecteur.dispersion = max(reglage["dispersion"], 0.2)

        mediane = self._mediane_jumeaux(equipement, secondes)
        etat = detecteur.traiter(secondes, mesure["t_max"], t_attendue, mediane)
        self.dernieres_mesures[equipement] = (secondes, mesure["t_max"])

        if self.depot:
            self.depot.enregistrer_prediction(mesure.get("horodatage"), equipement, etat)

        self.publier(SUJET_JUGEMENTS.format(site=self.site.identifiant), json.dumps({
            "equipement": equipement, "horodatage": mesure.get("horodatage"),
            "secondes": secondes, "t_max": etat["t_mesuree"], "t_attendue": etat["t_attendue"],
            "score": etat["score"], "niveau": etat["niveau"],
            "risque": etat["risque_pourcentage"]}))

        if etat["changement"]:
            message = {"equipement": equipement, "niveau": etat["niveau"],
                       "horodatage": mesure.get("horodatage"), "secondes": secondes,
                       "t_mesuree": etat["t_mesuree"], "t_attendue": etat["t_attendue"],
                       "score": etat["score"],
                       # la prévision : où cela va, et pourquoi on le pense
                       "risque": etat["risque_pourcentage"],
                       "risque_horizon_min": etat["risque_horizon_min"],
                       "risque_minutes_avant_seuil": etat["risque_minutes_avant_seuil"],
                       "risque_seuil": etat["risque_seuil"],
                       "risque_raison": module_risque.expliquer(
                           etat["risque_detail"], self.site.nom_equipement(equipement))}
            # Les facteurs ne sont calculés qu'ici : une fois par changement de
            # niveau, et non à chaque mesure — le coût resterait sinon inutile.
            contributions = None
            if hasattr(modele, "contributions"):
                try:
                    contributions = modele.contributions(entrees)
                except Exception:          # un modèle de repli n'explique pas
                    contributions = None
            message.update(explication.expliquer(
                etat, self.site.nom_equipement(equipement), famille,
                contexte=entrees, duree_s=secondes - (etat["debut_alerte"] or secondes),
                # l'ordre doit être celui du modèle, pas celui du dictionnaire
                contributions=contributions, entrees=getattr(modele, "entrees", None),
                action_specifique=self.site.action_specifique(equipement)))
            self.publier(SUJET_NIVEAUX.format(site=self.site.identifiant),
                         json.dumps(message))
        return etat

    def _mediane_jumeaux(self, equipement, secondes):
        """Température médiane des équipements identiques, si elle est récente."""
        jumeaux = self.site.jumeaux(equipement)
        valeurs = [self.dernieres_mesures[j][1] for j in jumeaux
                   if j in self.dernieres_mesures
                   and secondes - self.dernieres_mesures[j][0] <= 60]
        if len(valeurs) < 2:
            return None
        valeurs.sort()
        milieu = len(valeurs) // 2
        return (valeurs[milieu] if len(valeurs) % 2
                else (valeurs[milieu - 1] + valeurs[milieu]) / 2.0)


def _en_secondes(horodatage):
    if horodatage is None:
        return time.time()
    if isinstance(horodatage, (int, float)):
        return float(horodatage)
    return datetime.fromisoformat(str(horodatage).replace("Z", "+00:00")).timestamp()


# ---------------------------------------------------------------- exécution
def principal():
    import paho.mqtt.client as mqtt
    from ia.modeles_en_service import charger

    site = Site.charger(os.environ.get("SASI_SITE", "brasserie"))
    adresse = os.environ.get("SASI_MQTT", "localhost")
    modeles, calibrages = charger(site)

    depot = None
    if os.environ.get("SASI_BASE"):
        from connecteur.depot import Depot
        depot = Depot(os.environ["SASI_BASE"])

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    service = ServiceIA(site, modeles, calibrages, depot=depot,
                        publier=lambda sujet, message: client.publish(sujet, message, qos=1))

    def a_la_connexion(client, donnees, drapeaux, code, proprietes=None):
        client.subscribe(SUJET_VALIDEES.format(site=site.identifiant), qos=1)
        client.subscribe(SUJET_CONTEXTE.format(site=site.identifiant), qos=1)
        client.subscribe(SUJET_MODELE.format(site=site.identifiant), qos=1)
        print(f"Service IA prêt — site {site.identifiant}, "
              f"{len(service.modeles)} modèle(s) chargé(s)")

    def a_la_reception(client, donnees, message):
        fiche = json.loads(message.payload)
        if message.topic.endswith("/contexte"):
            service.majorer_contexte(fiche)
        elif message.topic.endswith("/modele"):
            if fiche.get("action") == "recharger":
                nombre = service.recharger_modeles()
                print(f"Modèle rechargé : version {fiche.get('version')}, "
                      f"{nombre} famille(s)")
        else:
            for mesure in fiche.get("mesures", []):
                service.traiter(mesure)

    client.on_connect = a_la_connexion
    client.on_message = a_la_reception
    client.connect(adresse, 1883, keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    principal()
