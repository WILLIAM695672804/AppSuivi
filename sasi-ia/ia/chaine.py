"""Chaîne complète de traitement, pour n'importe quel site (lots A et B).

Lot A : fonctionnement normal  -> entraînement d'un modèle par famille
Lot B : avec pannes            -> détection, puis comparaison au journal des pannes
"""

from pathlib import Path

import numpy as np
import pandas as pd

from ia import controles, entrainement, explication
from ia.site import Site
from ia.detection import episodes, parcourir

RACINE = Path(__file__).resolve().parents[1]
def dossier_donnees():
    """Dossier des mesures du site courant : donnees/<identifiant>/."""
    return RACINE / "donnees" / SITE.identifiant.lower()

ENTREES = ["charge_pct", "etat_marche", "t_ambiante", "minutes_depuis_demarrage",
           "minutes_depuis_arret", "charge_moy_30min", "heure", "jour_semaine",
           "plage_basse", "plage_haute", "fraction_chauffe", "fraction_refroidissement"]

MINUTES_PLAFOND = 180     # au-delà, la température est stabilisée

# Site décrit dans sites/<nom>.json. On peut en changer à tout moment :
#     from ia import chaine ; chaine.definir_site("minoterie")
SITE = Site.charger("brasserie")


def definir_site(nom_ou_chemin):
    """Change le site étudié (liste des équipements, familles, seuils)."""
    global SITE
    SITE = Site.charger(nom_ou_chemin)
    return SITE


def famille(equipement):
    return SITE.famille(equipement)


def nom(equipement):
    return SITE.nom_equipement(equipement)


def plage(equipement):
    """Plage normale en marche : (basse, haute)."""
    return SITE.plage(equipement)


def seuils_fixes(equipement):
    """Filet de sécurité : plage normale + 15 °C (inspection) et + 30 °C (urgence)."""
    return SITE.seuils_fixes(equipement)


def criticite(equipement):
    return SITE.criticite(equipement)


def temps_montee_min(equipement):
    """Temps de mise en température, en minutes (fiche de l'équipement)."""
    return SITE.temps_montee_min(equipement)


# ------------------------------------------------------------------ chargement
def charger_lot(nom, pas_secondes=10):
    """Assemble mesures, contexte et ambiance en un seul tableau."""
    mesures = pd.read_csv(dossier_donnees() / f"mesures_{nom}.csv", parse_dates=["horodatage"])
    contexte = pd.read_csv(dossier_donnees() / f"contexte_{nom}.csv", parse_dates=["horodatage"])
    ambiance = pd.read_csv(dossier_donnees() / f"ambiance_{nom}.csv", parse_dates=["horodatage"])

    if pas_secondes > 10:
        garde = mesures["horodatage"].dt.second % pas_secondes == 0
        mesures = mesures[garde]

    mesures = mesures.sort_values("horodatage")
    contexte = contexte.sort_values("horodatage")
    ambiance = ambiance.sort_values("horodatage")

    mesures["zone"] = mesures["equipement"].str.slice(1, 2).astype(int)

    fusion = pd.merge_asof(mesures, contexte, on="horodatage", by="equipement",
                           direction="backward")
    fusion = pd.merge_asof(fusion, ambiance[["horodatage", "zone", "t_ambiante"]],
                           on="horodatage", by="zone", direction="backward")
    fusion = fusion.dropna(subset=["etat", "charge_pct", "t_ambiante"])
    return fusion


def controler_lot(tableau):
    """Écarte les mesures impossibles et signale ce qui a été retiré.

    Renvoie (tableau nettoyé, rapport). Les mêmes contrôles seront appliqués en
    continu par le connecteur, à l'entrée du système.
    """
    depart = len(tableau)
    connus = set(SITE.liste())

    inconnus = ~tableau["equipement"].isin(connus)
    hors_plage = ~tableau["t_max"].between(controles.TEMPERATURE_MINIMALE,
                                           controles.TEMPERATURE_MAXIMALE)
    absentes = tableau["t_max"].isna()
    a_retirer = inconnus | hors_plage | absentes

    rapport = {
        "recues": depart,
        "equipement_inconnu": int(inconnus.sum()),
        "valeur_hors_plage": int(hors_plage.sum()),
        "valeur_absente": int(absentes.sum()),
        "conservees": int((~a_retirer).sum()),
    }
    return tableau[~a_retirer].copy(), rapport


def ajouter_entrees(tableau):
    """Ajoute les informations calculées dont le modèle a besoin."""
    t = tableau.sort_values(["equipement", "horodatage"]).copy()
    t["etat_marche"] = (t["etat"] == "marche").astype(int)
    # La fiche de l'équipement : sans elle, le modèle confondrait un moulin
    # (50 à 75 °C) et une étiqueteuse (35 à 50 °C), qui sont de la même famille.
    t["plage_basse"] = t["equipement"].map(lambda e: plage(e)[0])
    t["plage_haute"] = t["equipement"].map(lambda e: plage(e)[1])
    t["temps_montee"] = t["equipement"].map(temps_montee_min)
    t["heure"] = t["horodatage"].dt.hour
    t["jour_semaine"] = t["horodatage"].dt.weekday

    groupes = t.groupby("equipement", sort=False)
    # numéro de la période de marche (change à chaque démarrage ou arrêt)
    t["periode"] = groupes["etat_marche"].transform(lambda s: (s != s.shift()).cumsum())
    debut_periode = t.groupby(["equipement", "periode"])["horodatage"].transform("min")
    ecoule = (t["horodatage"] - debut_periode).dt.total_seconds() / 60.0
    # Plafonné à 3 heures : au-delà, la température est stabilisée. Sans ce
    # plafond, la valeur grandirait indéfiniment pour une machine qui tourne en
    # continu, et le modèle s'en servirait comme d'un calendrier.
    ecoule = np.minimum(ecoule, MINUTES_PLAFOND)
    t["minutes_depuis_demarrage"] = np.where(t["etat_marche"] == 1, ecoule, 0.0)
    t["minutes_depuis_arret"] = np.where(t["etat_marche"] == 0, ecoule, 0.0)
    # Part de la montée (ou de la descente) déjà accomplie : une machine met un
    # certain temps à atteindre sa température de régime. Sans cette information,
    # le modèle se trompe à chaque démarrage et chaque arrêt.
    constante = t["temps_montee"] / 3.0
    t["fraction_chauffe"] = np.where(
        t["etat_marche"] == 1, 1 - np.exp(-t["minutes_depuis_demarrage"] / constante), 1.0)
    t["fraction_refroidissement"] = np.where(
        t["etat_marche"] == 0, 1 - np.exp(-t["minutes_depuis_arret"] / constante), 1.0)

    # Moyenne sur une vraie durée (30 minutes), et non sur un nombre de lignes :
    # sinon la valeur changerait de sens selon la fréquence des mesures.
    t["charge_moy_30min"] = (
        t.set_index("horodatage")
         .groupby("equipement", sort=False)["charge_pct"]
         .rolling("30min").mean()
         .reset_index(level=0, drop=True)
         .to_numpy())
    return t


# ------------------------------------------------------------------ modèles
def entrainer_par_famille(lot_a):
    """Un modèle par famille, entraîné uniquement sur du fonctionnement normal."""
    modeles, erreurs = {}, {}
    for nom_famille in sorted({famille(e) for e in lot_a["equipement"].unique()}):
        sous_ensemble = lot_a[lot_a["equipement"].map(famille) == nom_famille]
        apprentissage, reglage, test = entrainement.decouper_par_date(
            sous_ensemble.sort_values("horodatage"))
        modele = entrainement.entrainer(apprentissage, reglage, ENTREES, cible="t_max")
        erreur = entrainement.erreur_moyenne(modele, test, ENTREES, cible="t_max")
        modeles[nom_famille] = modele
        erreurs[nom_famille] = erreur
        print(f"    {nom_famille} : erreur moyenne {erreur:.2f} °C "
              f"({len(sous_ensemble):,} mesures)".replace(",", " "))
    return modeles, erreurs


MINUTES_TRANSITOIRE = 45      # une machine qui vient de démarrer ou de s'arrêter


def regime(tableau):
    """« transitoire » juste après un démarrage ou un arrêt, « etabli » ensuite.

    La prédiction est moins sûre pendant les transitions : on y tolère donc un
    écart plus grand, au lieu de déclencher une alerte à chaque démarrage.
    """
    recent = ((tableau["minutes_depuis_demarrage"] < MINUTES_TRANSITOIRE)
              & (tableau["etat_marche"] == 1)) | (
              (tableau["minutes_depuis_arret"] < MINUTES_TRANSITOIRE)
              & (tableau["etat_marche"] == 0))
    return np.where(recent, "transitoire", "etabli")


def calibrer_par_equipement(lot_a, modeles, part_reservee=0.30):
    """Décalage et dispersion propres à chaque équipement et à chaque régime.

    Le calibrage n'utilise que la fin du lot A, jamais vue à l'entraînement.
    Sur des mesures déjà apprises, les écarts seraient artificiellement petits,
    et le système alerterait ensuite à tort.
    """
    calibrages = {}
    lot_a = lot_a.copy()
    lot_a["regime"] = regime(lot_a)
    for equipement, tableau in lot_a.groupby("equipement"):
        tableau = tableau.sort_values("horodatage")
        tableau = tableau.iloc[int(len(tableau) * (1 - part_reservee)):]
        modele = modeles[famille(equipement)]
        residus = tableau["t_max"].to_numpy() - modele.predict(tableau[ENTREES])
        par_regime = {}
        for nom_regime in ("etabli", "transitoire"):
            masque = (tableau["regime"] == nom_regime).to_numpy()
            valeurs = residus[masque] if masque.sum() >= 50 else residus
            biais = float(np.median(valeurs))
            # Référence : l'écart le plus fort observé en fonctionnement normal
            # (millième le plus extrême). Un score de 1 correspond donc à cet
            # écart, et un score de 3 à trois fois celui-ci. Ce choix évite de
            # supposer que les écarts suivent une courbe en cloche, ce qui est
            # faux pendant les démarrages et les arrêts.
            extreme = float(np.quantile(np.abs(valeurs - biais), 0.999))
            dispersion = max(extreme, 0.3)
            par_regime[nom_regime] = {"biais": biais, "dispersion": dispersion}
        calibrages[equipement] = par_regime
    return calibrages


# ------------------------------------------------------------------ détection
def detecter(lot_b, modeles, calibrages, cloture_auto_s=1800):
    """Passe le lot B dans le détecteur et renvoie les alertes."""
    lot_b = lot_b.copy()
    lot_b["regime"] = regime(lot_b)
    lot_b["t_attendue"] = np.nan
    for nom_famille, modele in modeles.items():
        masque = lot_b["equipement"].map(famille) == nom_famille
        lot_b.loc[masque, "t_attendue"] = modele.predict(lot_b.loc[masque, ENTREES])
    # Une prédiction impossible ne doit jamais produire d'alerte : la mesure est écartée.
    lot_b = lot_b[lot_b["t_attendue"].notna() & lot_b["t_max"].notna()]

    # médiane des phases de l'armoire, pour la comparaison entre équipements jumeaux
    phases = lot_b[lot_b["equipement"].isin(SITE.tous_les_jumeaux())]
    medianes = phases.groupby("horodatage")["t_max"].median() if not phases.empty else None

    depart = lot_b["horodatage"].min()
    toutes_alertes, tous_episodes, tous_etats = [], [], []
    for equipement, tableau in lot_b.groupby("equipement"):
        tableau = tableau.sort_values("horodatage")
        secondes = (tableau["horodatage"] - depart).dt.total_seconds().to_numpy()
        mediane_jumeaux = None
        if SITE.jumeaux(equipement) and medianes is not None:
            mediane_jumeaux = medianes.reindex(tableau["horodatage"]).to_numpy()

        calibrage = calibrages[equipement]
        t_max = tableau["t_max"].to_numpy()
        t_attendue = tableau["t_attendue"].to_numpy()
        regimes = tableau["regime"].to_numpy()

        mesures = []
        for i in range(len(tableau)):
            reglage = calibrage[regimes[i]]
            mesures.append({
                "equipement": equipement,
                "secondes": float(secondes[i]),
                "t_mesuree": float(t_max[i]),
                "t_attendue": float(t_attendue[i]),
                "biais": reglage["biais"],
                "dispersion": reglage["dispersion"],
                "mediane_jumeaux": (float(mediane_jumeaux[i])
                                    if mediane_jumeaux is not None else None),
            })
        inspection, urgence = seuils_fixes(equipement)
        etats, alertes = parcourir(mesures,
                               biais=calibrage["etabli"]["biais"],
                               dispersion=calibrage["etabli"]["dispersion"],
                               criticite=criticite(equipement),
                               seuil_fixe_inspection=inspection,
                               seuil_fixe_urgence=urgence,
                               cloture_auto_s=cloture_auto_s,
                               temps_montee_min=temps_montee_min(equipement))
        toutes_alertes += alertes
        tous_episodes += episodes(etats)
        tous_etats += etats
    return (sorted(tous_episodes, key=lambda e: e["debut"]), depart,
            pd.DataFrame(tous_etats))


def fenetres_journal(depart, lot="B"):
    """Périodes de panne du lot, en secondes depuis son début."""
    journal = pd.read_csv(dossier_donnees() / f"journal_{lot}.csv",
                          parse_dates=["debut", "fin"])
    fenetres = []
    for _, ligne in journal.iterrows():
        fenetres.append({
            "id": ligne["id"],
            "equipement": ligne["equipement"],
            "type": ligne["type"],
            "debut": (ligne["debut"] - depart).total_seconds(),
            "fin": (ligne["fin"] - depart).total_seconds(),
        })
    return fenetres


# ------------------------------------------------------------------ explications
def expliquer_episodes(episodes_alerte, etats, lot_b, modeles):
    """Ajoute à chaque épisode sa raison, ses facteurs et l'action conseillée.

    L'explication est calculée au moment le plus fort de l'épisode.
    """
    lot_b = lot_b.sort_values(["equipement", "horodatage"]).copy()
    depart = lot_b["horodatage"].min()
    lot_b["secondes"] = (lot_b["horodatage"] - depart).dt.total_seconds()

    resultat = []
    for episode in episodes_alerte:
        equipement = episode["equipement"]
        fenetre = etats[(etats["equipement"] == equipement)
                        & (etats["secondes"] >= episode["debut"])
                        & (etats["secondes"] <= episode["fin"])]
        if fenetre.empty:
            resultat.append({**episode, "raison": "", "action": "", "facteurs": []})
            continue
        fort = fenetre.loc[fenetre["score"].idxmax()]

        ligne = lot_b[(lot_b["equipement"] == equipement)
                      & (lot_b["secondes"] == fort["secondes"])]
        contexte, contributions = {}, None
        if not ligne.empty:
            contexte = {"charge_pct": ligne["charge_pct"].iloc[0],
                        "t_ambiante": ligne["t_ambiante"].iloc[0],
                        "etat_marche": ligne["etat_marche"].iloc[0]}
            modele = modeles[famille(equipement)]
            valeurs = modele.contributions(ligne)
            if valeurs is not None:
                contributions = valeurs[0]

        texte = explication.expliquer(
            fort.to_dict(), nom(equipement), famille(equipement),
            contexte=contexte, duree_s=fort["secondes"] - episode["debut"],
            contributions=contributions, entrees=ENTREES,
            action_specifique=SITE.action_specifique(equipement))
        resultat.append({**episode, **texte})
    return resultat
