"""Explication des alertes : pourquoi le système alerte, et que faire.

Trois éléments accompagnent chaque alerte (cahier des charges technique, 6.8) :
  1. une phrase de raison, en français courant ;
  2. les facteurs qui expliquent la température attendue ;
  3. une action conseillée, selon la famille et le signal dominant.

Ce fichier n'utilise que Python : il peut tourner tel quel sur le boîtier.
"""

SIGNAUX = ("ecart", "pente", "jumeau")

# Action conseillée par famille et par signal dominant.
# Tableau de départ, à faire valider par un responsable sécurité.
ACTIONS = {
    ("MOT", "ecart"): "Contrôler les roulements et la lubrification ; vérifier l'alignement et la tension des courroies.",
    ("MOT", "pente"): "Vérifier l'absence de blocage ou de corps étranger ; arrêter la machine si la montée continue.",
    ("ARM", "ecart"): "Vérifier la ventilation de l'armoire et la charge des départs.",
    ("ARM", "pente"): "Contrôler les connexions et la charge ; surveiller de près jusqu'à l'intervention.",
    ("ARM", "jumeau"): "Contrôler le serrage des connexions de la phase concernée ; vérifier l'équilibre des charges.",
    ("CHD", "ecart"): "Contrôler le brûleur ou la régulation ; vérifier l'isolation et l'évacuation des fumées.",
    ("CHD", "pente"): "Vérifier la régulation de chauffe ; couper si la montée se poursuit.",
    ("POM", "ecart"): "Vérifier la ventilation, les filtres et les roulements ; contrôler le niveau d'huile.",
    ("POM", "pente"): "Vérifier l'absence de marche à sec et de blocage ; arrêter si la montée continue.",
    ("RES", "ecart"): "Vérifier le niveau de liquide dans la cuve et l'état de la résistance.",
    ("RES", "pente"): "URGENCE : couper la chauffe et vérifier le niveau de liquide dans la cuve.",
}
ACTION_PAR_DEFAUT = "Faire contrôler l'équipement par un technicien."

# Comment nommer les entrées du modèle dans une phrase.
NOMS_ENTREES = {
    "charge_pct": "la charge",
    "charge_moy_30min": "la charge des 30 dernières minutes",
    "etat_marche": "l'état de marche",
    "t_ambiante": "la chaleur ambiante",
    "minutes_depuis_demarrage": "le temps écoulé depuis le démarrage",
    "minutes_depuis_arret": "le temps écoulé depuis l'arrêt",
    "fraction_chauffe": "la montée en température en cours",
    "fraction_refroidissement": "le refroidissement en cours",
    "heure": "l'heure de la journée",
    "jour_semaine": "le jour de la semaine",
    "plage_basse": "le bas de la plage normale de l'équipement",
    "plage_haute": "le haut de la plage normale de l'équipement",
}

SEUIL_PENTE_MENTION = 0.05      # °C/min : en dessous, inutile de parler de montée


def signal_dominant(etat):
    """Quel signal a déclenché l'alerte : écart, vitesse de montée ou voisin identique."""
    classement = {
        "ecart": etat.get("s1_ecart_normalise", 0.0),
        "pente": etat.get("s2_pente", 0.0) / 0.5,
        "jumeau": etat.get("s3_ecart_jumeau", 0.0) / 4.0,
    }
    return max(classement, key=classement.get)


def _arrondi(valeur, decimales=1):
    return round(float(valeur), decimales)


def phrase_raison(etat, nom_equipement, contexte=None, duree_s=None):
    """Phrase en français courant, lisible par un technicien."""
    contexte = contexte or {}
    dominant = signal_dominant(etat)
    ecart = etat["t_mesuree"] - etat["t_attendue"]
    morceaux = []

    if dominant == "jumeau":
        morceaux.append(
            f"{nom_equipement} est {_arrondi(etat['s3_ecart_jumeau'])} °C plus chaud que les "
            f"équipements identiques ({_arrondi(etat['t_mesuree'])} °C mesurés)")
    elif dominant == "pente":
        morceaux.append(
            f"{nom_equipement} monte de {_arrondi(etat['s2_pente'], 2)} °C par minute, "
            f"plus vite que prévu ({_arrondi(etat['t_mesuree'])} °C atteints)")
    else:
        morceaux.append(
            f"{nom_equipement} est {_arrondi(ecart)} °C plus chaud que d'habitude "
            f"({_arrondi(etat['t_mesuree'])} °C mesurés pour {_arrondi(etat['t_attendue'])} °C attendus)")

    conditions = []
    if contexte.get("charge_pct") is not None and contexte.get("etat_marche", 1):
        conditions.append(f"une charge de {int(contexte['charge_pct'])} %")
    if contexte.get("t_ambiante") is not None:
        conditions.append(f"une ambiance de {_arrondi(contexte['t_ambiante'])} °C")
    if conditions:
        morceaux.append("pour " + " et ".join(conditions))

    if dominant != "pente" and etat.get("s2_pente", 0) > SEUIL_PENTE_MENTION:
        morceaux.append(f"et la température monte encore de {_arrondi(etat['s2_pente'], 2)} °C par minute")

    if duree_s:
        minutes = int(duree_s // 60)
        morceaux.append(f"depuis {minutes} min" if minutes < 60
                        else f"depuis {minutes // 60} h {minutes % 60:02d}")

    return " ".join(morceaux).strip() + "."


def facteurs_influents(contributions, entrees, nombre=3):
    """Ce qui explique le plus la température attendue.

    contributions : une valeur par entrée (fournie par LightGBM), en °C.
    """
    couples = [(entrees[i], float(contributions[i])) for i in range(len(entrees))]
    couples = [c for c in couples if abs(c[1]) >= 0.2]
    couples.sort(key=lambda c: abs(c[1]), reverse=True)
    resultat = []
    for nom, valeur in couples[:nombre]:
        libelle = NOMS_ENTREES.get(nom, nom)
        sens = "augmente" if valeur > 0 else "diminue"
        resultat.append(f"{libelle} {sens} la température attendue de {abs(round(valeur, 1))} °C")
    return resultat


def action_conseillee(famille, dominant, action_specifique=None):
    """Action à conseiller. Une action propre à l'équipement prime sur celle de sa famille."""
    if action_specifique:
        return action_specifique
    return ACTIONS.get((famille, dominant), ACTION_PAR_DEFAUT)


def expliquer(etat, nom_equipement, famille, contexte=None, duree_s=None,
              contributions=None, entrees=None, action_specifique=None):
    """Explication complète d'une alerte."""
    dominant = signal_dominant(etat)
    explication = {
        "signal": dominant,
        "raison": phrase_raison(etat, nom_equipement, contexte, duree_s),
        "action": action_conseillee(famille, dominant, action_specifique),
        "facteurs": [],
    }
    if contributions is not None and entrees:
        explication["facteurs"] = facteurs_influents(contributions, entrees)
    return explication
