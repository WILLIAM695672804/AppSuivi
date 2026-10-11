"""Moteur d'alertes : vie d'une alerte, escalade, notifications.

Règles du cahier des charges technique, chapitre 7 :
  - une seule alerte ouverte par équipement ; si le niveau monte, l'alerte monte ;
  - chaque changement est enregistré (qui, quoi, quand) ;
  - escalade si personne n'acquitte dans le délai ;
  - clôture impossible sans compte rendu ;
  - un équipement en maintenance n'alerte pas, sauf seuil fixe d'urgence.

Ce fichier n'utilise que Python.
"""

from itertools import count

ETATS = ("ouverte", "acquittee", "assignee", "cloturee")

NIVEAUX_NOTIFIES = ("surveillance", "inspection", "urgence")
NIVEAUX_SMS = ("inspection", "urgence")

DELAI_ESCALADE_S = 600          # 10 minutes sans acquittement
DELAI_ESCALADE_FINALE_S = 1200  # 20 minutes : responsable sécurité
DELAI_ANTI_RAFALE_S = 900       # au plus un SMS par équipement toutes les 15 minutes


class Alerte:
    def __init__(self, identifiant, equipement, niveau, secondes, explication=None):
        self.identifiant = identifiant
        self.equipement = equipement
        self.niveau = niveau
        self.etat = "ouverte"
        self.debut = secondes
        self.fin = None
        self.assignee_a = None
        self.compte_rendu = None
        self.justifiee = None
        self.explication = explication or {}
        self.escalades = 0
        self.evenements = [{"secondes": secondes, "type": "creation",
                            "niveau": niveau, "par": "systeme"}]

    def journaliser(self, secondes, type_evenement, par="systeme", **details):
        self.evenements.append({"secondes": secondes, "type": type_evenement,
                                "par": par, **details})

    def resume(self):
        return {"id": self.identifiant, "equipement": self.equipement,
                "niveau": self.niveau, "etat": self.etat, "debut": self.debut,
                "fin": self.fin, "assignee_a": self.assignee_a,
                "justifiee": self.justifiee,
                "raison": self.explication.get("raison"),
                "action": self.explication.get("action"),
                "facteurs": self.explication.get("facteurs", []),
                # chiffres du jugement, affichés sur la fiche d'alerte
                "t_mesuree": self.explication.get("t_mesuree"),
                "t_attendue": self.explication.get("t_attendue"),
                "score": self.explication.get("score"),
                # prévision : probabilité d'atteindre le seuil dangereux
                "risque": self.explication.get("risque"),
                "risque_horizon_min": self.explication.get("risque_horizon_min"),
                "risque_minutes_avant_seuil": self.explication.get("risque_minutes_avant_seuil"),
                "risque_seuil": self.explication.get("risque_seuil"),
                "risque_raison": self.explication.get("risque_raison"),
                # vie de l'alerte : ouverture, montées de niveau, prise en charge…
                "evenements": list(self.evenements)}


class MoteurAlertes:
    """Tient la liste des alertes en cours et décide des notifications."""

    def __init__(self, delai_escalade_s=DELAI_ESCALADE_S,
                 delai_escalade_finale_s=DELAI_ESCALADE_FINALE_S):
        self.delai_escalade_s = delai_escalade_s
        self.delai_escalade_finale_s = delai_escalade_finale_s
        self.numero = count(1)
        self.ouvertes = {}        # equipement -> Alerte
        self.historique = []
        self.en_maintenance = set()
        self.dernier_sms = {}     # equipement -> secondes

    # ---------- cycle de vie ----------
    def signaler(self, equipement, niveau, secondes, explication=None,
                 seuil_fixe_depasse=False):
        """Appelé par l'IA à chaque changement de niveau. Renvoie les notifications à envoyer."""
        if niveau == "normal":
            return []
        if equipement in self.en_maintenance and not (
                niveau == "urgence" and seuil_fixe_depasse):
            return []

        alerte = self.ouvertes.get(equipement)
        if alerte is None:
            alerte = Alerte(f"A-{next(self.numero):04d}", equipement, niveau,
                            secondes, explication)
            self.ouvertes[equipement] = alerte
            self.historique.append(alerte)
            return self._notifications(alerte, secondes, "creation")

        if _rang(niveau) > _rang(alerte.niveau):
            alerte.niveau = niveau
            if explication:
                alerte.explication = explication
            alerte.journaliser(secondes, "montee_de_niveau", niveau=niveau)
            return self._notifications(alerte, secondes, "montee_de_niveau")
        return []

    def acquitter(self, equipement, secondes, par):
        alerte = self.ouvertes.get(equipement)
        if alerte is None or alerte.etat != "ouverte":
            return None
        alerte.etat = "acquittee"
        alerte.journaliser(secondes, "acquittement", par=par)
        return alerte

    def assigner(self, equipement, secondes, par, a_qui):
        alerte = self.ouvertes.get(equipement)
        if alerte is None or alerte.etat == "cloturee":
            return None
        alerte.etat = "assignee"
        alerte.assignee_a = a_qui
        alerte.journaliser(secondes, "assignation", par=par, a_qui=a_qui)
        return alerte

    def cloturer(self, equipement, secondes, par, compte_rendu, justifiee):
        """Clôture impossible sans compte rendu ni réponse à « alerte justifiée »."""
        alerte = self.ouvertes.get(equipement)
        if alerte is None:
            return None
        if not compte_rendu or justifiee is None:
            raise ValueError("Une clôture exige un compte rendu et la réponse "
                             "« alerte justifiée : oui ou non ».")
        alerte.etat = "cloturee"
        alerte.fin = secondes
        alerte.compte_rendu = compte_rendu
        alerte.justifiee = bool(justifiee)
        alerte.journaliser(secondes, "cloture", par=par, justifiee=bool(justifiee))
        del self.ouvertes[equipement]
        return alerte

    # ---------- maintenance ----------
    def mettre_en_maintenance(self, equipement, en_maintenance=True):
        if en_maintenance:
            self.en_maintenance.add(equipement)
        else:
            self.en_maintenance.discard(equipement)

    # ---------- escalade ----------
    def controler(self, secondes):
        """À appeler régulièrement : renvoie les notifications d'escalade."""
        notifications = []
        for alerte in list(self.ouvertes.values()):
            if alerte.etat != "ouverte" or alerte.niveau not in NIVEAUX_SMS:
                continue
            attente = secondes - alerte.debut
            if alerte.escalades == 0 and attente >= self.delai_escalade_s:
                alerte.escalades = 1
                alerte.journaliser(secondes, "escalade", destinataire="personne_suivante")
                notifications.append({"alerte": alerte.identifiant, "canal": "sms",
                                      "destinataire": "personne_suivante",
                                      "secondes": secondes, "motif": "escalade"})
            elif alerte.escalades == 1 and attente >= self.delai_escalade_finale_s:
                alerte.escalades = 2
                alerte.journaliser(secondes, "escalade", destinataire="responsable_securite")
                notifications.append({"alerte": alerte.identifiant, "canal": "sms",
                                      "destinataire": "responsable_securite",
                                      "secondes": secondes, "motif": "escalade_finale"})
        return notifications

    # ---------- notifications ----------
    def _notifications(self, alerte, secondes, motif):
        envois = []
        if alerte.niveau in NIVEAUX_NOTIFIES:
            envois.append({"alerte": alerte.identifiant, "canal": "notification",
                           "destinataire": "abonnes_zone", "secondes": secondes,
                           "motif": motif})
        if alerte.niveau in NIVEAUX_SMS and self._sms_autorise(alerte, secondes, motif):
            self.dernier_sms[alerte.equipement] = secondes
            envois.append({"alerte": alerte.identifiant, "canal": "sms",
                           "destinataire": "abonnes_zone", "secondes": secondes,
                           "motif": motif})
        return envois

    def _sms_autorise(self, alerte, secondes, motif):
        """Anti-rafale : un SMS au plus toutes les 15 min, sauf changement de niveau."""
        if motif == "montee_de_niveau":
            return True
        dernier = self.dernier_sms.get(alerte.equipement)
        return dernier is None or secondes - dernier >= DELAI_ANTI_RAFALE_S

    # ---------- consultation ----------
    def alertes_ouvertes(self):
        return [a.resume() for a in self.ouvertes.values()]

    def toutes(self):
        return [a.resume() for a in self.historique]


def _rang(niveau):
    ordre = ("normal", "information", "surveillance", "inspection", "urgence")
    return ordre.index(niveau)
