"""Copie locale de l'état, tenue par le serveur de l'application.

Le service des alertes est le seul à décider : il ouvre, escalade et clôture les
alertes. Le serveur de l'application en garde une copie pour répondre vite aux
écrans, et lui transmet les actions des équipes par le serveur de messages.

Ce fichier ne dépend ni de FastAPI, ni de paho, ni de la base : il peut donc
être vérifié seul (outils/verifier_chaine.py).
"""

import json
import time
from collections import defaultdict, deque

from alertes.moteur import MoteurAlertes

# Sans base de données, le serveur garde en mémoire les dernières heures de
# mesures : assez pour les courbes de l'interface, rien de durable.
POINTS_PAR_EQUIPEMENT = 4000

# Au-delà, une courbe ne gagne plus en lisibilité mais fige le navigateur :
# on n'en sert qu'un point sur n.
POINTS_SERVIS = 400


def reduire(points, maximum):
    """Garde au plus « maximum » points, régulièrement espacés, dernier compris."""
    if maximum and len(points) > maximum:
        pas = len(points) / maximum
        reduits = [points[int(rang * pas)] for rang in range(maximum)]
        if reduits[-1] is not points[-1]:
            reduits[-1] = points[-1]
        return reduits
    return list(points)


class Registre:
    """État courant du site, alimenté par les messages reçus."""

    def __init__(self, site):
        self.site = site
        self.niveaux = {equipement: "normal" for equipement in site.liste()}
        self.alertes = {}                    # identifiant -> fiche
        self.techniques = []
        self.moteur_local = MoteurAlertes()  # secours quand le serveur de messages est absent
        self.connecte = False
        self.series = defaultdict(lambda: deque(maxlen=POINTS_PAR_EQUIPEMENT))

    # ---------- réception ----------
    def appliquer(self, sujet, charge_utile):
        """Range un message reçu. Renvoie ce qu'il faut envoyer aux écrans, ou None."""
        try:
            fiche = charge_utile if isinstance(charge_utile, dict) else json.loads(charge_utile)
        except (ValueError, TypeError):
            return None

        if sujet.endswith("/jugements"):
            equipement = fiche.get("equipement")
            if equipement:
                self.series[equipement].append(fiche)
            return None                  # trop fréquent pour être envoyé aux écrans

        if sujet.endswith("/niveaux"):
            self.niveaux.update(fiche.get("niveaux") or {})
            return {"type": "niveaux", "niveaux": dict(self.niveaux)}

        if sujet.endswith("/alertes_techniques"):
            self.techniques.insert(0, fiche)
            del self.techniques[20:]
            return {"type": "technique", "alerte": fiche}

        if sujet.endswith("/alertes"):
            if fiche.get("erreur"):
                return {"type": "erreur", "message": fiche["erreur"],
                        "equipement": fiche.get("equipement")}
            if fiche.get("id"):
                self.alertes[fiche["id"]] = fiche
                return {"type": "alerte", "alerte": fiche}
        return None

    # ---------- lecture ----------
    def serie(self, equipement, heures=24, maximum=POINTS_SERVIS):
        """Mesures et températures attendues gardées en mémoire, les plus anciennes d'abord.

        La fenêtre part du dernier point reçu, et non de l'horloge de la machine :
        un lot rejoué garde ainsi ses courbes. Le nombre de points est plafonné,
        sans quoi le tracé de dix-sept courbes fige le navigateur.
        """
        points = self.series.get(equipement)
        if not points:
            return []
        fin = points[-1].get("secondes") or time.time()
        limite = fin - heures * 3600
        retenus = [point for point in points if (point.get("secondes") or 0) >= limite]
        return reduire(retenus, maximum)

    def liste_alertes(self):
        """Alertes connues, la plus récente d'abord."""
        connues = sorted(self.alertes.values(),
                         key=lambda a: a.get("debut") or 0, reverse=True)
        return connues or self.moteur_local.toutes()

    def alerte(self, identifiant):
        fiche = self.alertes.get(identifiant)
        if fiche:
            return fiche
        for alerte in self.moteur_local.historique:
            if alerte.identifiant == identifiant:
                return {**alerte.resume(), "evenements": alerte.evenements,
                        "explication": alerte.explication}
        return None

    # ---------- actions des équipes ----------
    def commande(self, action, equipement, **details):
        """Construit la fiche de commande envoyée au service des alertes."""
        return {"action": action, "equipement": equipement,
                "secondes": details.pop("secondes", time.time()), **details}

    def appliquer_localement(self, fiche):
        """Applique une commande sans serveur de messages (démonstration).

        Lève ValueError si la clôture est refusée, comme le moteur lui-même.
        """
        action = fiche.get("action")
        equipement = fiche.get("equipement")
        maintenant = fiche.get("secondes", time.time())
        par = fiche.get("par", "inconnu")
        moteur = self.moteur_local

        if action == "acquitter":
            alerte = moteur.acquitter(equipement, maintenant, par)
        elif action == "assigner":
            alerte = moteur.assigner(equipement, maintenant, par, fiche.get("a_qui"))
        elif action == "cloturer":
            alerte = moteur.cloturer(equipement, maintenant, par,
                                     fiche.get("constat"), fiche.get("justifiee"))
        elif action == "maintenance":
            moteur.mettre_en_maintenance(equipement, bool(fiche.get("en_maintenance", True)))
            return None
        else:
            return None

        if alerte is not None:
            self.alertes[alerte.identifiant] = alerte.resume()
        return alerte
