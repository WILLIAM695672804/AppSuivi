"""Contrôles des mesures à l'entrée du système (cahier des charges technique, 5.4).

Rien n'atteint l'IA sans passer par ces contrôles : une valeur aberrante ou une
caméra muette ne doit jamais produire une alerte incendie, mais une alerte
technique destinée à l'administrateur.

Ce fichier n'utilise que Python.
"""

# Plage de mesure des caméras thermiques de l'inventaire (FLIR A70 : -20 à 1000 °C).
TEMPERATURE_MINIMALE = -30.0
TEMPERATURE_MAXIMALE = 1000.0

RETARD_TOLERE_S = 300          # 5 minutes
AVANCE_TOLEREE_S = 60          # 1 minute : petite dérive d'horloge admise
SILENCE_CAMERA_S = 600         # 10 minutes sans mesure : caméra muette
VALEUR_FIGEE_S = 1800          # 30 minutes sans la moindre variation : caméra figée


def verifier_mesure(mesure, equipements_connus=None, horodatage_courant=None):
    """Renvoie (acceptee, motif).

    mesure : {equipement, t_max, secondes}
    motif  : None si tout va bien, sinon la raison du rejet.
    """
    equipement = mesure.get("equipement")
    if not equipement:
        return False, "equipement_absent"
    if equipements_connus is not None and equipement not in equipements_connus:
        return False, "equipement_inconnu"

    valeur = mesure.get("t_max")
    if valeur is None:
        return False, "valeur_absente"
    try:
        valeur = float(valeur)
    except (TypeError, ValueError):
        return False, "valeur_illisible"
    if valeur != valeur:                      # not a number
        return False, "valeur_absente"
    if not TEMPERATURE_MINIMALE <= valeur <= TEMPERATURE_MAXIMALE:
        return False, "valeur_hors_plage"

    secondes = mesure.get("secondes")
    if secondes is not None and horodatage_courant is not None:
        if secondes > horodatage_courant + AVANCE_TOLEREE_S:
            return False, "horodatage_dans_le_futur"
        if secondes < horodatage_courant - RETARD_TOLERE_S:
            return True, "mesure_en_retard"   # acceptée, mais signalée

    return True, None


class SurveillanceCameras:
    """Suit l'activité de chaque caméra et signale les silences et les blocages."""

    def __init__(self, silence_s=SILENCE_CAMERA_S, figee_s=VALEUR_FIGEE_S):
        self.silence_s = silence_s
        self.figee_s = figee_s
        self.derniere_mesure = {}      # caméra -> secondes
        self.derniere_valeur = {}      # caméra -> (valeur, secondes du dernier changement)
        self.en_defaut = {}            # caméra -> motif en cours

    def enregistrer(self, camera, secondes, valeur=None):
        """Enregistre une mesure reçue. Renvoie une alerte technique si un défaut se termine."""
        retour = None
        if self.en_defaut.get(camera):
            retour = {"camera": camera, "secondes": secondes,
                      "type": "retour_a_la_normale", "motif": self.en_defaut[camera]}
            self.en_defaut[camera] = None

        self.derniere_mesure[camera] = secondes
        if valeur is not None:
            ancienne = self.derniere_valeur.get(camera)
            if ancienne is None or abs(valeur - ancienne[0]) > 0.05:
                self.derniere_valeur[camera] = (valeur, secondes)
        return retour

    def controler(self, secondes):
        """Renvoie la liste des alertes techniques à l'instant donné."""
        alertes = []
        for camera, derniere in self.derniere_mesure.items():
            if self.en_defaut.get(camera):
                continue
            if secondes - derniere >= self.silence_s:
                self.en_defaut[camera] = "camera_muette"
                alertes.append({"camera": camera, "secondes": secondes,
                                "type": "camera_muette",
                                "message": f"Aucune mesure de {camera} depuis "
                                           f"{int((secondes - derniere) // 60)} min."})
                continue
            valeur = self.derniere_valeur.get(camera)
            if valeur and secondes - valeur[1] >= self.figee_s:
                self.en_defaut[camera] = "camera_figee"
                alertes.append({"camera": camera, "secondes": secondes,
                                "type": "camera_figee",
                                "message": f"{camera} renvoie la même valeur depuis "
                                           f"{int((secondes - valeur[1]) // 60)} min."})
        return alertes


def trous_de_mesure(secondes, pas_attendu_s=10, facteur=3):
    """Périodes sans mesure, à partir d'une suite d'horodatages.

    Renvoie une liste de couples (début, fin) des interruptions dépassant
    « facteur » fois le pas attendu.
    """
    trous = []
    for precedent, suivant in zip(secondes, secondes[1:]):
        if suivant - precedent > pas_attendu_s * facteur:
            trous.append((precedent, suivant))
    return trous
