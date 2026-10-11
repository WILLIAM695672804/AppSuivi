"""Mini jumeau numérique : produit des mesures de brasserie.

Ce programme n'est PAS le jumeau numérique du projet (celui-ci est confié à une
autre personne). C'est une version réduite, écrite pour ne pas rester bloqué en
attendant sa livraison, et pour disposer tout de suite de données au bon format.

Il suit le « Cahier des scénarios » : mêmes identifiants, mêmes familles, mêmes
plages de température, même planning, mêmes types de pannes.

    python3 outils/simulateur.py

Produit dans donnees/simule/ :
    mesures_A.csv, contexte_A.csv, ambiance_A.csv        (fonctionnement normal)
    mesures_B.csv, contexte_B.csv, ambiance_B.csv, journal_B.csv   (avec pannes)
"""

import csv
import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ia.site import Site

RACINE = Path(__file__).resolve().parents[1]
SORTIE = RACINE / "donnees" / "simule"      # remplacé par le dossier du site au chargement

PAS_S = 10

SITE = None          # chargé par charger_site()


def charger_site(nom_ou_chemin="brasserie"):
    """Choisit le site à simuler (fichier sites/<nom>.json)."""
    global SITE, SORTIE
    SITE = Site.charger(nom_ou_chemin)
    SORTIE = RACINE / "donnees" / SITE.identifiant.lower()
    return SITE


def equipements():
    if SITE is None:
        charger_site()
    return [dict(e) for e in SITE.donnees["equipements"]]


# ----------------------------------------------------------------- planning
def en_marche(activite, instant):
    """Renvoie (en marche, charge en %) d'après le planning décrit dans le fichier de site."""
    if SITE is None:
        charger_site()
    regle = SITE.planning.get(activite)
    if regle is None:
        return False, 0

    heure = instant.hour + instant.minute / 60.0
    jours = regle.get("jours", "lundi-samedi")
    if jours == "lundi-samedi" and instant.weekday() == 6:
        return False, 0
    if jours == "lundi-vendredi" and instant.weekday() >= 5:
        return False, 0

    marche = regle["debut"] <= heure < regle["fin"]
    return marche, regle.get("charge", 80)


def ambiance(zone, instant, alea):
    """Température ambiante d'une zone, d'après le climat décrit dans le fichier de site."""
    if SITE is None:
        charger_site()
    climat = SITE.climat
    heure = instant.hour + instant.minute / 60.0
    decalage_heure = climat.get("heure_maximum", 15) - 6.0
    forme = math.sin((heure - decalage_heure) / 24.0 * 2 * math.pi)

    particulier = climat.get("zones_particulieres", {}).get(str(zone), {})
    base = particulier.get("base", climat.get("base", 28.0))
    amplitude = particulier.get("amplitude", climat.get("amplitude", 4.0))
    valeur = base + amplitude * forme + particulier.get("decalage", 0.0)
    return valeur + alea.gauss(0, 0.3)


# ----------------------------------------------------------------- pannes
def pannes_lot_b(debut):
    """Pannes du lot B, décrites dans le fichier de site (« pannes_exemple »)."""
    if SITE is None:
        charger_site()
    pannes = []
    for panne in SITE.donnees.get("pannes_exemple", []):
        depart = debut + timedelta(days=panne["jour"], hours=panne["heure"])
        pannes.append((panne["id"], panne["equipement"], panne["type"],
                       depart, depart + timedelta(hours=panne["duree_h"]),
                       panne["intensite"]))
    return pannes


def supplement_panne(panne, instant):
    """Chaleur ajoutée par une panne, en °C.

    Les types suivent le journal des incidents du guide d'audit terrain
    (AUD-IA-BRASS-01, fiche REL-DATA-04) : chaque étiquette du document a sa
    signature thermique.
    """
    _, _, type_panne, debut, fin, intensite = panne
    if not (debut <= instant <= fin):
        return 0.0, False
    heures = (instant - debut).total_seconds() / 3600.0
    minutes = heures * 60.0
    if type_panne == "derive_lente":
        return intensite * heures, False
    if type_panne == "montee_brutale":
        return intensite * minutes, False
    if type_panne == "point_chaud_phase":
        montee = min(heures / 6.0, 1.0)          # s'installe en 6 heures
        return intensite * montee, False
    if type_panne == "chauffe_a_vide":
        return intensite * minutes, True         # la cuve est vide : plus de refroidissement
    if type_panne == "defaut_refroidissement":
        return intensite, False
    if type_panne == "derive_froid":
        return intensite * heures, False

    # --- types repris du journal des incidents du guide d'audit ---
    if type_panne == "colmatage_filtre":
        # « Colmatage filtre d'air comburant » — dérive lente qui s'aggrave :
        # moins d'air, moins de refroidissement, donc accélération progressive.
        return intensite * heures ** 1.6, False
    if type_panne == "surchauffe_bruleur":
        # « Arrêt d'urgence brûleur (surchauffe) » — montée sévère puis palier
        # haut, le brûleur restant bloqué en position haute avant déclenchement.
        montee = min(minutes / 20.0, 1.0)
        return intensite * montee, False
    if type_panne == "rupture_calorifuge":
        # « Rupture joint / début de fumée externe » — la paroi perd son
        # isolation d'un coup, la température de surface bondit puis se stabilise.
        return intensite * (1.0 if minutes > 2 else minutes / 2.0), False
    if type_panne == "friction_roulement":
        # Usure mécanique : la friction augmente avec la chaleur qu'elle produit.
        return intensite * heures ** 2.2, False
    return 0.0, False


# ----------------------------------------------------------------- simulation
def simuler(nom, debut, jours, pannes=(), graine=20260120):
    alea = random.Random(graine)
    SORTIE.mkdir(parents=True, exist_ok=True)
    liste = equipements()
    # État de départ : un équipement qui tourne en permanence est déjà à sa
    # température de régime ; les autres sont à la température de la pièce.
    temperature = {e["id"]: ((e["plage_basse"] + e["plage_haute"]) / 2.0
                             if e.get("activite") == "continu" else 27.0)
                   for e in liste}
    charges = {e["id"]: alea.uniform(60, 95) for e in liste}

    fin = debut + timedelta(days=jours)
    f_mes = open(SORTIE / f"mesures_{nom}.csv", "w", newline="", encoding="utf-8")
    f_ctx = open(SORTIE / f"contexte_{nom}.csv", "w", newline="", encoding="utf-8")
    f_amb = open(SORTIE / f"ambiance_{nom}.csv", "w", newline="", encoding="utf-8")
    m, c, a = csv.writer(f_mes), csv.writer(f_ctx), csv.writer(f_amb)
    m.writerow(["horodatage", "camera", "equipement", "t_max", "t_moy", "t_min"])
    c.writerow(["horodatage", "equipement", "etat", "charge_pct"])
    a.writerow(["horodatage", "zone", "t_ambiante", "humidite_pct"])

    instant = debut
    lignes = 0
    while instant < fin:
        horodatage = instant.strftime("%Y-%m-%dT%H:%M:%SZ")
        minute_pleine = instant.second == 0 and instant.minute % 1 == 0

        ambiances = {z: ambiance(z, instant, alea) for z in sorted(SITE.zones)}
        if minute_pleine:
            for zone, valeur in ambiances.items():
                humidite = SITE.climat.get("humidite", [70, 90])
                a.writerow([horodatage, zone, round(valeur, 1),
                            round(alea.uniform(humidite[0], humidite[1]))])

        for e in liste:
            marche, charge_nominale = en_marche(e.get("activite", "continu"), instant)
            if marche:
                # la charge dérive lentement autour de sa valeur nominale
                charges[e["id"]] += alea.gauss(0, 0.4)
                charges[e["id"]] = min(max(charges[e["id"]], charge_nominale - 25), 100.0)
                charge = charges[e["id"]]
            else:
                charge = 0.0

            t_ambiante = ambiances[e["zone"]]
            if marche:
                # La charge place l'équipement entre 10 % et 90 % de sa plage normale :
                # en fonctionnement normal, il reste dans la plage relevée sur le terrain.
                bande = e["plage_haute"] - e["plage_basse"]
                cible = e["plage_basse"] + bande * (0.1 + 0.8 * charge / 100.0)
                if not SITE.climat.get("zones_particulieres", {}).get(str(e["zone"]), {}).get("base"):
                    cible += (t_ambiante - 28.0) * 0.5
                # Un équipement qui chauffe ne peut pas être plus froid que l'air qui l'entoure.
                if e["plage_haute"] > t_ambiante:
                    cible = max(cible, t_ambiante + 1.0)
            else:
                cible = t_ambiante

            sans_refroidissement = False
            for panne in pannes:
                if panne[1] == e["id"]:
                    supplement, emballement = supplement_panne(panne, instant)
                    cible += supplement
                    sans_refroidissement = sans_refroidissement or emballement

            tau = e["temps_montee_min"] * 60 / 3.0 if not sans_refroidissement else 60.0
            courant = temperature[e["id"]]
            courant += (cible - courant) * (1 - math.exp(-PAS_S / tau))
            temperature[e["id"]] = courant

            t_max = courant + alea.gauss(0, 0.3)
            m.writerow([horodatage, e["camera"], e["id"],
                        round(t_max, 1), round(t_max - 6 - alea.uniform(0, 2), 1),
                        round(t_max - 14 - alea.uniform(0, 3), 1)])
            lignes += 1

            if minute_pleine:
                c.writerow([horodatage, e["id"], "marche" if marche else "arret", round(charge)])

        instant += timedelta(seconds=PAS_S)

    for fichier in (f_mes, f_ctx, f_amb):
        fichier.close()

    if pannes:
        with open(SORTIE / f"journal_{nom}.csv", "w", newline="", encoding="utf-8") as f:
            j = csv.writer(f)
            j.writerow(["id", "equipement", "type", "debut", "fin", "intensite"])
            for identifiant, equipement, type_panne, debut_p, fin_p, intensite in pannes:
                j.writerow([identifiant, equipement, type_panne,
                            debut_p.strftime("%Y-%m-%dT%H:%M:%SZ"),
                            fin_p.strftime("%Y-%m-%dT%H:%M:%SZ"), intensite])
    print(f"  Lot {nom} : {jours} jours, {lignes:,} mesures".replace(",", " ")
          + (f", {len(pannes)} pannes" if pannes else ", aucune panne"))


if __name__ == "__main__":
    nom_site = sys.argv[1] if len(sys.argv) > 1 else "brasserie"
    charger_site(nom_site)
    debut_a = datetime(2026, 1, 5, 0, 0, 0)          # un lundi
    print(f"Simulation — {SITE.resume()}")
    # Trente jours d'apprentissage : un mois complet, avec ses week-ends, ses
    # arrêts de nettoyage et toute la variété du climat de Douala.
    jours_a = 30 if nom_site == "brasserie" else 20
    simuler("A", debut_a, jours=jours_a, graine=20260120)
    jours_b = 30 if nom_site == "brasserie" else 14
    debut_b = debut_a + timedelta(days=jours_a + 7)  # un autre lundi, tirage différent
    simuler("B", debut_b, jours=jours_b, pannes=pannes_lot_b(debut_b), graine=77777)

    # Lot C : mêmes pannes, autre tirage et autre période. Il sert à vérifier
    # qu'un bon résultat ne tient pas au hasard d'un seul jeu de données.
    debut_c = debut_b + timedelta(days=jours_b + 7)
    simuler("C", debut_c, jours=jours_b, pannes=pannes_lot_b(debut_c), graine=31415)
    print(f"\nFichiers écrits dans {SORTIE}")
