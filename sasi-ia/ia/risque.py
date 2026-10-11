"""Probabilité d'atteindre un seuil dangereux, et explication de ce calcul.

Le détecteur dit ce qui se passe maintenant ; ce fichier dit où cela va.

    « À +0,9 °C par minute, il reste 32 °C avant les 300 °C de la chaudière,
      soit environ 35 minutes. Sur les 50 prochaines minutes, la probabilité
      d'atteindre ce seuil est de 78 %. »

Méthode. La température des prochaines minutes est extrapolée à partir de sa
vitesse actuelle, mesurée par une droite ajustée sur les dernières minutes.
Cette vitesse n'est pas connue exactement : l'ajustement fournit aussi son
incertitude. La probabilité est alors la part des évolutions plausibles qui
franchissent le seuil dans l'horizon retenu.

Une précaution décisive : c'est la vitesse **excédentaire** qui est extrapolée,
c'est-à-dire ce que la machine fait de plus que ce que le modèle prévoyait. Une
machine qui démarre monte de plusieurs degrés par minute : extrapoler cette
montée donnerait une alerte à chaque mise en route, alors qu'elle va se
stabiliser d'elle-même. Seul l'excédent annonce un emballement.

Deux conséquences voulues :
  - une chauffe rapide donne une probabilité élevée bien avant d'être dangereuse ;
  - une température haute mais stable voit sa probabilité retomber, puisque plus
    rien n'indique qu'elle continuera de monter.

L'horizon n'est pas le même pour tous : une chaudière s'emballe en minutes, une
armoire dérive en heures. Il se déduit de l'inertie de l'équipement, de sa
criticité, du niveau d'alerte déjà atteint et de la distance au seuil.

Ce fichier n'utilise que la bibliothèque standard : il tourne tel quel sur le
boîtier du site.
"""

import math

# Bornes de l'horizon de prévision, en minutes. En deçà de dix minutes, personne
# n'a le temps d'agir ; au-delà de deux heures, l'extrapolation ne veut plus rien
# dire.
HORIZON_MINIMAL_MIN = 10
HORIZON_MAXIMAL_MIN = 120

# Plus un équipement est critique, plus on regarde loin devant : on veut voir
# venir le danger assez tôt pour agir.
FACTEUR_CRITICITE = {1: 0.8, 2: 1.0, 3: 1.3}

# Incertitude minimale sur la température, en °C : le bruit d'une caméra
# thermique et les à-coups de la prédiction.
INCERTITUDE_MINIMALE_C = 0.5

# Incertitude minimale sur la vitesse, en °C/min. Une montée parfaitement
# régulière sur cinq minutes ne garantit pas la suivante : sans ce plancher, le
# calcul afficherait 0 % puis 100 % d'un coup, ce qu'aucun physicien ne signerait.
INCERTITUDE_MINIMALE_PENTE = 0.05

# Part de la montée prévue que l'on tient pour incertaine. Une machine ne monte
# pas en ligne droite pendant une heure : la régulation reprend la main, la
# charge varie, le procédé s'arrête. Extrapoler une tendance revient donc à
# parier, et ce coefficient dit à quel point. Sans lui, le calcul passerait de
# 0 % à 100 % pour une différence de vitesse minime.
INCERTITUDE_RELATIVE_TENDANCE = 0.35

# En deçà de cette vitesse, on considère que la température ne monte pas.
PENTE_NEGLIGEABLE = 0.01        # °C par minute


def loi_normale(x):
    """Part des valeurs d'une loi normale centrée réduite inférieures à x."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def pente_et_incertitude(historique):
    """Vitesse de montée et son incertitude, par une droite ajustée aux mesures.

    historique : suite de couples (secondes, température), du plus ancien au plus
    récent. Renvoie (pente en °C/min, incertitude de la pente en °C/min), ou
    (None, None) si les points sont trop peu nombreux.

    L'incertitude est l'erreur-type de la pente : elle grandit quand les points
    s'écartent de la droite, c'est-à-dire quand la tendance est douteuse.
    """
    points = list(historique)
    if len(points) < 4:
        return None, None

    t0 = points[0][0]
    xs = [(s - t0) / 60.0 for s, _ in points]      # en minutes
    ys = [v for _, v in points]
    n = len(points)
    moyenne_x = sum(xs) / n
    moyenne_y = sum(ys) / n

    variation_x = sum((x - moyenne_x) ** 2 for x in xs)
    if variation_x <= 0:
        return None, None
    covariation = sum((x - moyenne_x) * (y - moyenne_y) for x, y in zip(xs, ys))
    pente = covariation / variation_x

    if n <= 2:
        return pente, None
    ordonnee = moyenne_y - pente * moyenne_x
    residus = sum((y - (ordonnee + pente * x)) ** 2 for x, y in zip(xs, ys))
    variance_residuelle = residus / (n - 2)
    incertitude = math.sqrt(max(variance_residuelle, 0.0) / variation_x)
    return pente, incertitude


def horizon_minutes(temps_montee_min, criticite=1):
    """Sur combien de temps regarder devant soi, pour cet équipement.

    Deux facteurs, et deux seulement : l'inertie thermique, qui donne l'échelle
    de temps du procédé (une chaudière s'emballe en minutes, une armoire dérive
    en heures), et la criticité, qui dit combien on veut anticiper.

    L'horizon ne dépend volontairement ni du niveau d'alerte en cours, ni de la
    distance au seuil. Les faire entrer ici créerait une boucle : le niveau
    dépend de la probabilité, qui dépendrait de l'horizon, qui dépendrait du
    niveau — le chiffre se mettrait à osciller sans qu'aucune température ne
    bouge. Ces deux facteurs agissent déjà, et mieux, à l'intérieur du calcul :
    la distance au seuil est ce qu'il reste à parcourir, et la température
    actuelle en fait partie.
    """
    base = max(float(temps_montee_min or 30.0), 5.0) * FACTEUR_CRITICITE.get(criticite, 1.0)
    return max(min(base, HORIZON_MAXIMAL_MIN), HORIZON_MINIMAL_MIN)


def probabilite(temperature, seuil, pente, incertitude_pente, horizon_min,
                incertitude_mesure=INCERTITUDE_MINIMALE_C):
    """Probabilité d'atteindre le seuil dans l'horizon, entre 0 et 1.

    pente et incertitude_pente sont en °C par minute, horizon_min en minutes.
    """
    if seuil is None or horizon_min <= 0:
        return 0.0
    reste = seuil - temperature
    if reste <= 0:
        return 1.0
    if pente is None:
        return 0.0

    montee_prevue = pente * horizon_min
    incertitude_pente = max(incertitude_pente or 0.0, INCERTITUDE_MINIMALE_PENTE)
    ecart_type = math.sqrt(
        (incertitude_pente * horizon_min) ** 2                      # tendance mal connue
        + (INCERTITUDE_RELATIVE_TENDANCE * montee_prevue) ** 2      # tendance non garantie
        + max(incertitude_mesure, INCERTITUDE_MINIMALE_C) ** 2)     # bruit de mesure
    if ecart_type <= 0:
        return 1.0 if montee_prevue >= reste else 0.0
    return loi_normale((montee_prevue - reste) / ecart_type)


def minutes_avant_seuil(temperature, seuil, pente):
    """Temps qu'il reste avant le seuil, au rythme actuel. None si la température ne monte pas."""
    if seuil is None or pente is None or pente <= PENTE_NEGLIGEABLE:
        return None
    reste = seuil - temperature
    if reste <= 0:
        return 0.0
    return reste / pente


def evaluer(temperature, seuil, historique, temps_montee_min=30, criticite=1,
            incertitude_mesure=INCERTITUDE_MINIMALE_C, historique_attendu=None):
    """Calcule le risque à partir des mesures récentes. Renvoie tout ce qui a servi.

    historique_attendu : les températures que le modèle prévoyait aux mêmes
    instants. Quand elles sont fournies, seule la vitesse excédentaire est
    extrapolée — une montée prévue n'annonce aucun danger.

    Le détail est conservé : c'est lui qui permet d'expliquer le chiffre aux
    équipes, et de vérifier plus tard que le raisonnement était juste.
    """
    pente_mesuree, incertitude = pente_et_incertitude(historique)
    pente_attendue = None
    if historique_attendu is not None:
        pente_attendue, incertitude_attendue = pente_et_incertitude(historique_attendu)
        if pente_mesuree is not None and pente_attendue is not None:
            incertitude = math.sqrt((incertitude or 0.0) ** 2
                                    + (incertitude_attendue or 0.0) ** 2)
    pente = pente_mesuree
    if pente_mesuree is not None and pente_attendue is not None:
        pente = pente_mesuree - pente_attendue
    reste = None if seuil is None else seuil - temperature
    horizon = horizon_minutes(temps_montee_min, criticite)
    valeur = probabilite(temperature, seuil, pente, incertitude, horizon, incertitude_mesure)
    return {
        "probabilite": valeur,
        "pourcentage": int(round(valeur * 100)),
        "horizon_min": round(horizon, 1),
        "pente": pente,
        "pente_mesuree": pente_mesuree,
        "pente_attendue": pente_attendue,
        "incertitude_pente": incertitude,
        "seuil": seuil,
        "temperature": temperature,
        "reste_avant_seuil": reste,
        "minutes_avant_seuil": minutes_avant_seuil(temperature, seuil, pente),
    }


def expliquer(evaluation, nom_equipement="l'équipement"):
    """Met le calcul en phrases, pour l'écran et pour le rapport."""
    if evaluation.get("seuil") is None:
        return "Aucun seuil critique n'est défini pour cet équipement."
    if evaluation.get("anomalie_constatee") is False:
        return (f"{nom_equipement} se comporte comme prévu : aucune anomalie constatée, "
                "donc aucun risque annoncé.")

    pourcentage = evaluation["pourcentage"]
    pente = evaluation.get("pente")
    reste = evaluation.get("reste_avant_seuil")
    horizon = evaluation.get("horizon_min")
    minutes = evaluation.get("minutes_avant_seuil")

    if reste is not None and reste <= 0:
        return (f"{nom_equipement} a déjà dépassé {evaluation['seuil']:.0f} °C : "
                "le risque est avéré.")

    if pente is None:
        return (f"Pas encore assez de mesures pour prévoir l'évolution de "
                f"{nom_equipement}.")

    if pente <= PENTE_NEGLIGEABLE:
        return (f"{nom_equipement} ne monte pas plus vite que prévu "
                f"({pente:+.2f} °C/min d'écart). "
                f"Il reste {reste:.0f} °C avant {evaluation['seuil']:.0f} °C : "
                f"aucun risque d'atteindre ce seuil dans les {horizon:.0f} prochaines "
                "minutes.")

    mesuree = evaluation.get("pente_mesuree")
    attendue = evaluation.get("pente_attendue")
    if attendue is not None and mesuree is not None:
        if attendue < -PENTE_NEGLIGEABLE:
            comparaison = (f", alors que le modèle prévoyait une baisse de "
                           f"{abs(attendue):.2f} °C par minute")
        elif attendue > PENTE_NEGLIGEABLE:
            comparaison = f", soit {pente:.2f} °C de plus que prévu"
        else:
            comparaison = ", alors qu'elle devrait être stable"
        phrase = (f"{nom_equipement} monte de {mesuree:.2f} °C par minute{comparaison} ; "
                  f"il reste {reste:.0f} °C avant {evaluation['seuil']:.0f} °C")
    else:
        phrase = (f"{nom_equipement} monte de {pente:.2f} °C par minute ; il reste "
                  f"{reste:.0f} °C avant {evaluation['seuil']:.0f} °C")
    if minutes is not None:
        phrase += f", soit environ {_duree(minutes)} à ce rythme"
    phrase += (f". Sur les {horizon:.0f} prochaines minutes, la probabilité "
               f"d'atteindre ce seuil est de {pourcentage} %")
    incertitude = evaluation.get("incertitude_pente")
    if incertitude:
        phrase += f" (vitesse connue à ± {incertitude:.2f} °C/min près)"
    return phrase + "."


def _duree(minutes):
    if minutes < 1:
        return "moins d'une minute"
    if minutes < 90:
        return f"{int(round(minutes))} min"
    heures = minutes / 60.0
    return f"{heures:.1f} h".replace(".", ",")
