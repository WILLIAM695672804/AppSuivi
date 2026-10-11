"""Inspection du raisonnement de l'IA : est-il juste, et où se trompe-t-il ?

    ./venv/bin/python outils/inspecter.py                   site par défaut
    ./venv/bin/python outils/inspecter.py minoterie
    ./venv/bin/python outils/inspecter.py brasserie --equipement Z1-MOU-01
    ./venv/bin/python outils/inspecter.py brasserie --sans heure,jour_semaine

Quatre questions, quatre réponses :

  1. Où le modèle se trompe-t-il ?     erreur par famille, par équipement, par régime
  2. Sur quoi s'appuie-t-il ?          poids de chaque entrée dans ses décisions
  3. Raisonne-t-il dans le bon sens ?  contrôles de bon sens (plus de charge = plus chaud…)
  4. Quels sont ses pires moments ?    les mesures qu'il explique le plus mal

Le troisième point est le plus important : un modèle peut être précis en moyenne
et raisonner à l'envers sur un cas particulier. Ces contrôles le disent.

Le rapport est écrit dans resultats/inspection_<site>.md.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ia import chaine
from ia.explication import NOMS_ENTREES
from ia.site import Site

RACINE = Path(__file__).resolve().parents[1]
RESULTATS = RACINE / "resultats"

# Contrôles de bon sens : (entrée testée, valeurs essayées, sens attendu, intitulé)
# « + » : la température attendue doit monter quand l'entrée monte.
CONTROLES = [
    ("charge_pct", [0, 25, 50, 75, 100], "+",
     "plus la machine est chargée, plus elle doit chauffer"),
    ("t_ambiante", [22, 26, 30, 34, 38], "+",
     "plus l'air est chaud, plus l'équipement doit être chaud"),
    ("minutes_depuis_demarrage", [0, 15, 30, 60, 120], "+",
     "une machine qui vient de démarrer est plus froide qu'après une heure"),
    ("minutes_depuis_arret", [0, 15, 30, 60, 120], "-",
     "une machine arrêtée depuis longtemps doit être plus froide"),
]

TOLERANCE_C = 0.3          # en deçà, on considère que le modèle n'a pas bougé
COUVERTURE_MINIMALE = 0.25  # part de l'intervalle testé qu'il faut avoir observée


def entrees_type(site, equipement, etat_marche=1):
    """Un jeu d'entrées plausible, servant de point de départ aux contrôles."""
    basse, haute = site.plage(equipement)
    return {
        "charge_pct": 70.0, "etat_marche": etat_marche, "t_ambiante": 29.0,
        "minutes_depuis_demarrage": 90.0 if etat_marche else 0.0,
        "minutes_depuis_arret": 0.0 if etat_marche else 90.0,
        "charge_moy_30min": 70.0, "heure": 14, "jour_semaine": 2,
        "plage_basse": basse, "plage_haute": haute,
        "fraction_chauffe": 0.95 if etat_marche else 1.0,
        "fraction_refroidissement": 1.0 if etat_marche else 0.95,
    }


def predire(modele, entrees):
    tableau = pd.DataFrame([[entrees[nom] for nom in chaine.ENTREES]], columns=chaine.ENTREES)
    return float(modele.predict(tableau)[0])


# ---------------------------------------------------------------- 1. erreurs
def erreurs_par_equipement(lot, modeles):
    """Écart moyen entre la température prédite et la température observée."""
    lignes = []
    for equipement, mesures in lot.groupby("equipement"):
        modele = modeles.get(chaine.famille(equipement))
        if modele is None:
            continue
        attendue = modele.predict(mesures[chaine.ENTREES])
        ecart = mesures["t_max"].to_numpy() - attendue
        etabli = chaine.regime(mesures) == "etabli"
        lignes.append({
            "equipement": equipement,
            "famille": chaine.famille(equipement),
            "mesures": len(mesures),
            "erreur_moyenne": float(np.mean(np.abs(ecart))),
            "erreur_etabli": float(np.mean(np.abs(ecart[etabli]))) if etabli.any() else None,
            "erreur_transitoire": (float(np.mean(np.abs(ecart[~etabli])))
                                   if (~etabli).any() else None),
            "biais": float(np.mean(ecart)),
            "pire": float(np.max(np.abs(ecart))),
        })
    return sorted(lignes, key=lambda l: -l["erreur_moyenne"])


# ---------------------------------------------------------------- 2. appuis
def poids_des_entrees(modeles):
    """Part de chaque entrée dans les décisions du modèle, en pourcentage."""
    resultat = {}
    for nom_famille, modele in modeles.items():
        booster = getattr(modele, "booster", None)
        if booster is None:
            resultat[nom_famille] = None          # modèle de repli : pas de poids
            continue
        poids = booster.feature_importance(importance_type="gain")
        total = float(np.sum(poids)) or 1.0
        couples = sorted(zip(chaine.ENTREES, poids), key=lambda c: -c[1])
        resultat[nom_famille] = [(nom, 100.0 * valeur / total) for nom, valeur in couples]
    return resultat


# ---------------------------------------------------------------- 3. bon sens
def intervalles_observes(lot):
    """Pour chaque équipement et chaque entrée, ce que les données ont montré.

    Interroger le modèle en dehors de cet intervalle ne prouve rien : il
    extrapole. La résistance de nettoyage, par exemple, ne tourne qu'à 22 h,
    par 25 °C d'ambiance : lui demander son comportement à 38 °C est une
    question à laquelle rien ne l'a préparé.
    """
    observes = {}
    for equipement, mesures in lot.groupby("equipement"):
        par_etat = {}
        for marche in (0, 1):
            partie = mesures[mesures["etat_marche"] == marche]
            if partie.empty:
                continue
            par_etat[marche] = {entree: (float(partie[entree].min()),
                                         float(partie[entree].max()))
                                for entree, *_ in CONTROLES if entree in partie}
        observes[equipement] = par_etat
    return observes


def controler_bon_sens(site, modeles, equipements, observes=None):
    """Fait varier une entrée à la fois et vérifie le sens de la réponse.

    Les valeurs essayées sont limitées à ce que les données ont montré : un
    modèle n'a pas à répondre juste sur des situations qu'il n'a jamais vues.
    """
    constats = []
    for equipement in equipements:
        modele = modeles.get(chaine.famille(equipement))
        if modele is None:
            continue
        for entree, valeurs, sens, intitule in CONTROLES:
            marche = 0 if entree == "minutes_depuis_arret" else 1
            base = entrees_type(site, equipement, etat_marche=marche)

            borne = (observes or {}).get(equipement, {}).get(marche, {}).get(entree)
            essayees = list(valeurs)
            couverture = 1.0
            if borne:
                bas, haut = borne
                essayees = [v for v in valeurs if bas <= v <= haut]
                etendue = max(valeurs) - min(valeurs)
                couverture = (haut - bas) / etendue if etendue else 1.0
            if len(essayees) < 2 or couverture < COUVERTURE_MINIMALE:
                constats.append({"equipement": equipement, "entree": entree,
                                 "intitule": intitule, "variation": 0.0,
                                 "reponses": [], "valeurs": essayees,
                                 "verdict": "jamais observé"})
                continue

            reponses = []
            for valeur in essayees:
                essai = dict(base)
                essai[entree] = valeur
                if entree == "charge_pct":
                    essai["charge_moy_30min"] = valeur     # les deux vont de pair
                reponses.append(predire(modele, essai))

            variation = reponses[-1] - reponses[0]
            if abs(variation) < TOLERANCE_C:
                verdict = "insensible"
            elif (variation > 0) == (sens == "+"):
                verdict = "conforme"
            else:
                verdict = "À L'ENVERS"
            constats.append({"equipement": equipement, "entree": entree,
                             "intitule": intitule, "variation": variation,
                             "reponses": reponses, "valeurs": essayees,
                             "verdict": verdict})
    return constats


# ---------------------------------------------------------------- 4. pires cas
def pires_moments(lot, modeles, nombre=8):
    """Les mesures que le modèle explique le plus mal, avec leur contexte."""
    morceaux = []
    for equipement, mesures in lot.groupby("equipement"):
        modele = modeles.get(chaine.famille(equipement))
        if modele is None:
            continue
        copie = mesures.copy()
        copie["t_attendue"] = modele.predict(mesures[chaine.ENTREES])
        copie["ecart"] = copie["t_max"] - copie["t_attendue"]
        copie["regime"] = chaine.regime(copie)
        morceaux.append(copie)
    tout = pd.concat(morceaux)
    tout["abs_ecart"] = tout["ecart"].abs()
    return tout.nlargest(nombre, "abs_ecart")


# ---------------------------------------------------------------- en un appel
def inspecter(site, modeles, lot, equipements=None, erreurs_familles=None):
    """Inspection complète, renvoyée telle quelle : aucun fichier écrit.

    C'est la forme qu'utilise l'application ; le programme en ligne de commande
    s'en sert aussi, puis en fait un rapport.
    """
    observes = intervalles_observes(lot)
    par_equipement = erreurs_par_equipement(lot, modeles)
    poids = poids_des_entrees(modeles)
    constats = controler_bon_sens(site, modeles, equipements or site.liste(), observes)
    pires = pires_moments(lot, modeles)

    if erreurs_familles is None:
        erreurs_familles = {}
        for ligne in par_equipement:
            erreurs_familles.setdefault(ligne["famille"], []).append(ligne["erreur_moyenne"])
        erreurs_familles = {f: sum(v) / len(v) for f, v in erreurs_familles.items()}

    return {
        "site": site.identifiant,
        "erreurs_familles": erreurs_familles,
        "par_equipement": par_equipement,
        "poids": {famille: [{"entree": nom, "libelle": NOMS_ENTREES.get(nom, nom),
                             "part": part} for nom, part in (couples or [])]
                  for famille, couples in poids.items()},
        "bon_sens": [{"equipement": c["equipement"], "entree": c["entree"],
                      "libelle": NOMS_ENTREES.get(c["entree"], c["entree"]),
                      "intitule": c["intitule"], "variation": c["variation"],
                      "verdict": c["verdict"]} for c in constats],
        "pires": [{"horodatage": ligne["horodatage"].isoformat(),
                   "equipement": ligne["equipement"], "regime": ligne["regime"],
                   "t_max": float(ligne["t_max"]), "t_attendue": float(ligne["t_attendue"]),
                   "ecart": float(ligne["ecart"]), "charge_pct": float(ligne["charge_pct"])}
                  for _, ligne in pires.iterrows()],
        "resume": {
            "conformes": sum(1 for c in constats if c["verdict"] == "conforme"),
            "insensibles": sum(1 for c in constats if c["verdict"] == "insensible"),
            "jamais_observes": sum(1 for c in constats if c["verdict"] == "jamais observé"),
            "a_lenvers": sum(1 for c in constats if c["verdict"] == "À L'ENVERS"),
        },
    }


# ---------------------------------------------------------------- rapport
def ecrire(site, erreurs_familles, par_equipement, poids, constats, pires, chemin):
    lignes = [
        f"# Projet SASI — Inspection du raisonnement : {site.nom}", "",
        f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}", "",
        "Ce rapport ne mesure pas la détection des pannes (voir `rapport_"
        f"{site.identifiant.lower()}.md`) mais la justesse du raisonnement : "
        "sur quoi le modèle s'appuie, où il se trompe, et s'il raisonne dans le bon sens.",
        "",
        "## 1. Où le modèle se trompe-t-il ?", "",
        "L'erreur est l'écart entre la température prédite et la température réellement "
        "mesurée, en fonctionnement normal. Plus elle est faible, plus l'écart anormal "
        "ressort nettement le jour d'une panne.", "",
        "| Famille | Erreur moyenne |", "|---|---|",
    ]
    for nom_famille, erreur in sorted(erreurs_familles.items()):
        lignes.append(f"| {nom_famille} | {erreur:.2f} °C |")

    lignes += ["", "### Par équipement, du plus mal prédit au mieux prédit", "",
               "| Équipement | Erreur | En régime établi | En transitoire | Biais | Pire écart |",
               "|---|---|---|---|---|---|"]
    for ligne in par_equipement:
        etabli = f"{ligne['erreur_etabli']:.2f} °C" if ligne["erreur_etabli"] else "—"
        transitoire = (f"{ligne['erreur_transitoire']:.2f} °C"
                       if ligne["erreur_transitoire"] else "—")
        lignes.append(
            f"| {ligne['equipement']} | {ligne['erreur_moyenne']:.2f} °C | {etabli} | "
            f"{transitoire} | {ligne['biais']:+.2f} °C | {ligne['pire']:.1f} °C |")
    lignes += ["",
               "Un **biais** franchement positif signifie que le modèle sous-estime "
               "cet équipement : il le croit plus froid qu'il n'est, et risque donc "
               "d'alerter à tort. Un biais négatif est l'inverse, et retarde la détection.",
               "",
               "Une erreur bien plus forte **en transitoire** qu'en régime établi est "
               "normale : la montée en température est le moment le plus difficile à "
               "prédire. C'est pourquoi le calibrage distingue les deux régimes.", ""]

    lignes += ["## 2. Sur quoi s'appuie-t-il ?", "",
               "Part de chaque information dans les décisions du modèle. Une entrée à "
               "0 % ne sert à rien ; une entrée écrasante mérite qu'on vérifie qu'elle "
               "est bien mesurée sur le terrain.", ""]
    for nom_famille, couples in sorted(poids.items()):
        lignes.append(f"**{nom_famille}**", )
        lignes.append("")
        if couples is None:
            lignes += ["- modèle de repli : il n'expose pas ses poids.", ""]
            continue
        for nom_entree, part in couples:
            if part < 0.5:
                continue
            lignes.append(f"- {NOMS_ENTREES.get(nom_entree, nom_entree)} "
                          f": {part:.1f} %")
        lignes.append("")

    lignes += ["## 3. Raisonne-t-il dans le bon sens ?", "",
               "On fait varier une seule information à la fois, toutes choses égales "
               "par ailleurs, et on regarde si la température attendue évolue comme le "
               "bon sens l'exige. Un « À L'ENVERS » est une anomalie à corriger : le "
               "modèle a appris une relation fausse, souvent faute de données variées.",
               "",
               "| Équipement | Ce qui varie | Attendu | Réponse du modèle | Verdict |",
               "|---|---|---|---|---|"]
    for constat in constats:
        if not constat["reponses"]:
            lignes.append(
                f"| {constat['equipement']} | "
                f"{NOMS_ENTREES.get(constat['entree'], constat['entree'])} "
                f"| {constat['intitule']} | situation absente des données | jamais observé |")
            continue
        depart, arrivee = constat["reponses"][0], constat["reponses"][-1]
        lignes.append(
            f"| {constat['equipement']} | {NOMS_ENTREES.get(constat['entree'], constat['entree'])} "
            f"| {constat['intitule']} | {depart:.1f} °C → {arrivee:.1f} °C "
            f"({constat['variation']:+.1f}) | {constat['verdict']} |")

    anomalies = [c for c in constats if c["verdict"] == "À L'ENVERS"]
    insensibles = [c for c in constats if c["verdict"] == "insensible"]
    jamais = [c for c in constats if c["verdict"] == "jamais observé"]
    conformes = len(constats) - len(anomalies) - len(insensibles) - len(jamais)
    lignes += ["",
               f"**{conformes} contrôles conformes, {len(insensibles)} sans effet, "
               f"{len(jamais)} jamais observés, {len(anomalies)} à l'envers.**", "",
               "Un « jamais observé » n'est pas un défaut du modèle mais un trou dans "
               "les données : la situation ne s'est pas présentée pendant la période "
               "d'apprentissage. Si elle peut survenir sur le site, il faut allonger "
               "cette période ou la provoquer pendant un essai.", ""]
    if anomalies:
        lignes += ["Raisonnements à corriger :", ""]
        for constat in anomalies:
            lignes.append(f"- **{constat['equipement']}** — {constat['intitule']} : "
                          f"le modèle fait l'inverse ({constat['variation']:+.1f} °C).")
        lignes.append("")

    lignes += ["## 4. Ses pires moments", "",
               "Les mesures que le modèle explique le plus mal, en fonctionnement normal. "
               "Si elles se concentrent sur un équipement ou sur un régime, la cause est "
               "là.", "",
               "| Horodatage | Équipement | Régime | Mesurée | Attendue | Écart | Charge |",
               "|---|---|---|---|---|---|---|"]
    for _, ligne in pires.iterrows():
        lignes.append(
            f"| {ligne['horodatage']:%d/%m %H:%M} | {ligne['equipement']} | {ligne['regime']} "
            f"| {ligne['t_max']:.1f} °C | {ligne['t_attendue']:.1f} °C "
            f"| {ligne['ecart']:+.1f} °C | {ligne['charge_pct']:.0f} % |")

    lignes += ["", "## Comment corriger", "",
               "| Symptôme | Où agir |", "|---|---|",
               "| Un équipement mal prédit, biais marqué | sa plage dans `sites/"
               f"{site.identifiant.lower()}.json` : une plage fausse trompe le modèle |",
               "| Un contrôle « à l'envers » | les données d'entraînement ne couvrent pas "
               "assez de situations : allonger la période d'apprentissage |",
               "| Une entrée à 0 % | la retirer de `ENTREES` (ia/chaine.py) : elle "
               "encombre le modèle |",
               "| Erreur forte en transitoire seulement | augmenter `MINUTES_TRANSITOIRE` "
               "(ia/chaine.py) |",
               "| Trop de fausses alertes | relever les seuils d'entrée ou allonger les "
               "confirmations (`SEUILS_ENTREE`, `CONFIRMATION_S` dans ia/detection.py) |",
               "| Détection trop tardive | abaisser les mêmes seuils, ou la criticité de "
               "l'équipement |", ""]

    chemin.write_text("\n".join(lignes), encoding="utf-8")


def principal(nom_site="brasserie", equipement=None, lot="A", sans=()):
    site = Site.charger(nom_site)
    chaine.definir_site(nom_site)
    print(f"=== Inspection du raisonnement — {site.nom} ===\n")

    # Essai d'une correction : on retire une ou plusieurs entrées et on regarde
    # si le raisonnement s'améliore. Rien n'est modifié durablement.
    if sans:
        chaine.ENTREES = [e for e in chaine.ENTREES if e not in sans]
        print(f"  Entrées retirées pour cet essai : {', '.join(sans)}")
        print(f"  Il en reste {len(chaine.ENTREES)}.\n")

    print("  Lecture des mesures de fonctionnement normal…")
    lot_a = chaine.charger_lot(lot)
    lot_a = chaine.ajouter_entrees(lot_a)

    print("  Entraînement des modèles…")
    modeles, erreurs_familles = chaine.entrainer_par_famille(lot_a)

    print("\n  1. Erreur par équipement")
    par_equipement = erreurs_par_equipement(lot_a, modeles)
    for ligne in par_equipement[:5]:
        print(f"     {ligne['equipement']:14s} {ligne['erreur_moyenne']:.2f} °C "
              f"(biais {ligne['biais']:+.2f})")

    print("\n  2. Ce sur quoi le modèle s'appuie")
    poids = poids_des_entrees(modeles)
    for nom_famille, couples in sorted(poids.items()):
        if not couples:
            print(f"     {nom_famille} : modèle de repli, poids indisponibles")
            continue
        tete = ", ".join(f"{nom} {part:.0f} %" for nom, part in couples[:3])
        print(f"     {nom_famille} : {tete}")

    print("\n  3. Contrôles de bon sens")
    cibles = [equipement] if equipement else site.liste()
    constats = controler_bon_sens(site, modeles, cibles, intervalles_observes(lot_a))
    conformes = sum(1 for c in constats if c["verdict"] == "conforme")
    envers = [c for c in constats if c["verdict"] == "À L'ENVERS"]
    insensibles = sum(1 for c in constats if c["verdict"] == "insensible")
    jamais = sum(1 for c in constats if c["verdict"] == "jamais observé")
    print(f"     {conformes} conformes, {insensibles} sans effet, "
          f"{jamais} jamais observés, {len(envers)} à l'envers")
    for constat in envers[:6]:
        print(f"       ! {constat['equipement']} — {constat['intitule']} "
              f"({constat['variation']:+.1f} °C)")

    print("\n  4. Pires écarts en fonctionnement normal")
    pires = pires_moments(lot_a, modeles)
    for _, ligne in pires.head(3).iterrows():
        print(f"     {ligne['equipement']:14s} {ligne['ecart']:+.1f} °C "
              f"({ligne['regime']}, charge {ligne['charge_pct']:.0f} %)")

    RESULTATS.mkdir(parents=True, exist_ok=True)
    chemin = RESULTATS / f"inspection_{site.identifiant.lower()}.md"
    ecrire(site, erreurs_familles, par_equipement, poids, constats, pires, chemin)
    print(f"\nRapport écrit : {chemin}")
    return 1 if envers else 0


if __name__ == "__main__":
    analyseur = argparse.ArgumentParser(description="Inspecte le raisonnement de l'IA")
    analyseur.add_argument("site", nargs="?", default="brasserie")
    analyseur.add_argument("--equipement", default=None,
                           help="n'inspecter qu'un équipement (contrôles de bon sens)")
    analyseur.add_argument("--lot", default="A", help="lot de fonctionnement normal")
    analyseur.add_argument("--sans", default="",
                           help="entrées à retirer pour l'essai, séparées par des virgules")
    arguments = analyseur.parse_args()
    retirees = [e.strip() for e in arguments.sans.split(",") if e.strip()]
    sys.exit(principal(arguments.site, arguments.equipement, arguments.lot, retirees))
