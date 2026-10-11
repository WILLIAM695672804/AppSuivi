"""Évaluation : comparer les alertes de l'IA aux pannes réellement connues.

Indicateurs (chapitre 6.10 du cahier des charges technique) :
  - taux de détection : part des pannes signalées au moins en « surveillance »
  - fausses alertes   : part des alertes qui ne correspondent à aucune panne
  - délai de détection : temps entre le début de la panne et la première alerte
"""

NIVEAU_RETENU = ("surveillance", "inspection", "urgence")


def evaluer(alertes, fenetres_pannes, tolerance_s=600):
    """alertes : liste de dictionnaires {secondes, niveau}
    fenetres_pannes : liste de couples (début, fin) en secondes
    tolerance_s : une alerte qui précède de peu une panne compte comme détection
    """
    retenues = [a for a in alertes if a["niveau"] in NIVEAU_RETENU]

    detectees, delais = 0, []
    for debut, fin in fenetres_pannes:
        candidates = [a["secondes"] for a in retenues
                      if debut - tolerance_s <= a["secondes"] <= fin]
        if candidates:
            detectees += 1
            delais.append(max(min(candidates) - debut, 0))

    fausses = 0
    for alerte in retenues:
        dans_une_panne = any(debut - tolerance_s <= alerte["secondes"] <= fin
                             for debut, fin in fenetres_pannes)
        if not dans_une_panne:
            fausses += 1

    nb_pannes = len(fenetres_pannes)
    nb_alertes = len(retenues)
    delais_tries = sorted(delais)
    delai_median = delais_tries[len(delais_tries) // 2] if delais_tries else None

    return {
        "pannes": nb_pannes,
        "pannes_detectees": detectees,
        "taux_detection": (detectees / nb_pannes) if nb_pannes else None,
        "alertes": nb_alertes,
        "fausses_alertes": fausses,
        "part_fausses_alertes": (fausses / nb_alertes) if nb_alertes else None,
        "delai_median_s": delai_median,
    }


def pourcentage(valeur):
    return "—" if valeur is None else f"{valeur * 100:.0f} %"


def duree(secondes):
    if secondes is None:
        return "—"
    minutes = secondes / 60.0
    return f"{minutes:.0f} min" if minutes >= 1 else f"{secondes:.0f} s"


def ligne_rapport(nom, resultat, erreur_moyenne=None):
    lignes = [f"### {nom}", ""]
    if erreur_moyenne is not None:
        lignes.append(f"- Erreur moyenne de prédiction : **{erreur_moyenne:.2f} °C**")
    lignes += [
        f"- Pannes connues : {resultat['pannes']}",
        f"- Pannes détectées : {resultat['pannes_detectees']} "
        f"(**{pourcentage(resultat['taux_detection'])}**, objectif ≥ 80 %)",
        f"- Alertes émises : {resultat['alertes']}",
        f"- Fausses alertes : {resultat['fausses_alertes']} "
        f"(**{pourcentage(resultat['part_fausses_alertes'])}**, objectif < 10 %)",
        f"- Délai médian de détection : {duree(resultat['delai_median_s'])}",
        "",
    ]
    return "\n".join(lignes)


def evaluer_par_equipement(alertes, fenetres, tolerance_s=600):
    """Comme evaluer(), mais une alerte ne compte que sur le bon équipement.

    fenetres : liste de dictionnaires {id, equipement, type, debut, fin}
    """
    retenues = [a for a in alertes if a["niveau"] in NIVEAU_RETENU]

    detail, detectees, delais = [], 0, []
    for fenetre in fenetres:
        candidates = [a["secondes"] for a in retenues
                      if a["equipement"] == fenetre["equipement"]
                      and fenetre["debut"] - tolerance_s <= a["secondes"] <= fenetre["fin"]]
        trouvee = bool(candidates)
        delai = (min(candidates) - fenetre["debut"]) if trouvee else None
        if trouvee:
            detectees += 1
            delais.append(max(delai, 0))
        detail.append({**fenetre, "detectee": trouvee, "delai_s": delai})

    fausses = 0
    for alerte in retenues:
        dans_une_panne = any(
            alerte["equipement"] == f["equipement"]
            and f["debut"] - tolerance_s <= alerte["secondes"] <= f["fin"]
            for f in fenetres)
        if not dans_une_panne:
            fausses += 1

    delais_tries = sorted(delais)
    return {
        "pannes": len(fenetres),
        "pannes_detectees": detectees,
        "taux_detection": detectees / len(fenetres) if fenetres else None,
        "alertes": len(retenues),
        "fausses_alertes": fausses,
        "part_fausses_alertes": fausses / len(retenues) if retenues else None,
        "delai_median_s": delais_tries[len(delais_tries) // 2] if delais_tries else None,
        "detail": detail,
    }


def evaluer_episodes(episodes, fenetres, tolerance_s=600, retour_normale_s=7200):
    """Compare les épisodes d'alerte aux pannes connues.

    Un épisode compte comme détection s'il touche la période de la panne, sur le
    bon équipement. Les autres épisodes sont des fausses alertes.

    retour_normale_s : après la fin d'une panne, l'équipement reste chaud un
    moment. Les alertes de cette période ne sont ni une détection ni une fausse
    alerte : elles suivent une anomalie réelle.
    """
    detail, detectes, delais = [], 0, []
    for fenetre in fenetres:
        candidats = [e for e in episodes
                     if e["equipement"] == fenetre["equipement"]
                     and e["fin"] >= fenetre["debut"] - tolerance_s
                     and e["debut"] <= fenetre["fin"]]
        trouve = bool(candidats)
        delai = min(e["debut"] for e in candidats) - fenetre["debut"] if trouve else None
        if trouve:
            detectes += 1
            delais.append(max(delai, 0))
        detail.append({**fenetre, "detectee": trouve, "delai_s": delai,
                       "niveau": max((e["niveau_max"] for e in candidats), default=None)})

    def liee_a_une_panne(episode, marge_fin):
        return any(episode["equipement"] == f["equipement"]
                   and episode["fin"] >= f["debut"] - tolerance_s
                   and episode["debut"] <= f["fin"] + marge_fin
                   for f in fenetres)

    fausses = [e for e in episodes if not liee_a_une_panne(e, retour_normale_s)]
    suites = [e for e in episodes
              if not liee_a_une_panne(e, 0) and liee_a_une_panne(e, retour_normale_s)]
    delais_tries = sorted(delais)
    return {
        "pannes": len(fenetres),
        "pannes_detectees": detectes,
        "taux_detection": detectes / len(fenetres) if fenetres else None,
        "alertes": len(episodes),
        "suites_de_panne": len(suites),
        "fausses_alertes": len(fausses),
        "part_fausses_alertes": (len(fausses) / (len(episodes) - len(suites))
                                 if len(episodes) - len(suites) > 0 else None),
        "delai_median_s": delais_tries[len(delais_tries) // 2] if delais_tries else None,
        "detail": detail,
        "detail_fausses": fausses,
    }
