"""Jumeau numérique en direct : des mesures en temps réel, sans fichier.

    ./venv/bin/python outils/direct.py                       brasserie, un point toutes les 10 s
    ./venv/bin/python outils/direct.py minoterie --pas 5     un autre site, plus rapide
    ./venv/bin/python outils/direct.py --panne 180           une panne toutes les 3 minutes

Pour un scénario précis, choisi plutôt que tiré au sort :

    ./venv/bin/python outils/direct.py --equipement Z2-CHE-01 \
        --type surchauffe_bruleur --intensite 45 --dans 30 --une-seule --forcer-marche

« --forcer-marche » maintient l'équipement en service le temps de la panne : sans
cela, une machine arrêtée par le planning ne chauffe qu'à partir de l'ambiante, et
l'écart reste trop faible pour être parlant.

À la différence du rejeu, qui rediffuse un lot enregistré, ce programme produit
les mesures au fur et à mesure, horodatées à l'heure courante : les courbes de
l'interface avancent réellement sous les yeux.

Le temps du site est accéléré (« --heures-par-minute ») pour que la journée
défile : marche, arrêt, remise en route. Les températures, elles, suivent
l'horloge réelle, faute de quoi le connecteur écarterait des mesures datées du
futur.

Une panne est déclenchée à intervalle régulier sur un équipement tiré au sort :
la température monte, l'IA la signale, puis tout rentre dans l'ordre. C'est le
scénario le plus court pour montrer la chaîne complète.
"""

import argparse
import json
import math
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ia.site import Site
from outils import simulateur

# Signatures reconnues, celles du catalogue de pannes (outils/scenarios.py).
SIGNATURES = ("derive_lente", "montee_brutale", "point_chaud_phase", "chauffe_a_vide",
              "defaut_refroidissement", "derive_froid", "colmatage_filtre",
              "surchauffe_bruleur", "rupture_calorifuge", "friction_roulement")

MONTEE_C_PAR_MINUTE = 3.0          # vitesse d'échauffement d'une panne
DUREE_PANNE_S = 900                # au-delà, la panne se résorbe d'elle-même
TAU_PANNE_S = 90                   # un équipement en défaut ne se refroidit plus :
                                   # il suit sa cible bien plus vite qu'en marche normale


def horodater(instant):
    return instant.isoformat().replace("+00:00", "Z")


class Panne:
    """Échauffement d'un équipement, puis retour à la normale.

    Sans signature précisée, la montée est régulière puis s'efface. Avec une
    signature (`--type`), c'est celle du simulateur qui s'applique : colmatage
    de filtre, surchauffe de brûleur, rupture de calorifuge… Les deux décrivent
    la même physique, mais la seconde reproduit un scénario du catalogue.
    """

    def __init__(self, equipement, debut, duree_s=DUREE_PANNE_S,
                 type_panne=None, intensite=None):
        self.equipement = equipement
        self.debut = debut
        self.duree_s = duree_s
        self.type_panne = type_panne
        self.intensite = intensite

    def supplement(self, maintenant):
        ecoule = maintenant - self.debut
        if ecoule < 0:
            return 0.0
        if ecoule > self.duree_s:
            return None                     # terminée

        if self.type_panne:
            debut = datetime.fromtimestamp(self.debut, tz=timezone.utc)
            fiche = ("P-DIRECT", self.equipement, self.type_panne, debut,
                     debut + timedelta(seconds=self.duree_s), self.intensite or 10.0)
            valeur, _ = simulateur.supplement_panne(
                fiche, debut + timedelta(seconds=ecoule))
            return valeur

        montee = min(ecoule / 60.0 * MONTEE_C_PAR_MINUTE, 40.0)
        reste = self.duree_s - ecoule
        return montee * min(reste / 120.0, 1.0)     # s'efface sur les deux dernières minutes


def publier(site, adresse, pas_s, heures_par_minute, periode_panne_s, graine,
            equipement_vise=None, type_panne=None, intensite=None,
            duree_panne_s=DUREE_PANNE_S, dans_s=60.0, une_seule=False,
            forcer_marche=False):
    import paho.mqtt.client as mqtt

    simulateur.SITE = site          # le jumeau travaille sur le site déjà chargé
    alea = random.Random(graine)
    liste = simulateur.equipements()

    # Départ : les équipements en service permanent sont déjà chauds.
    temperature = {e["id"]: ((e["plage_basse"] + e["plage_haute"]) / 2.0
                             if e.get("activite") == "continu" else 27.0)
                   for e in liste}
    charges = {e["id"]: alea.uniform(60, 95) for e in liste}

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(adresse, 1883, keepalive=60)
    client.loop_start()

    depart_reel = time.time()
    instant_site = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    pannes = []
    prochaine_panne = depart_reel + (dans_s if equipement_vise else periode_panne_s)

    print(f"Jumeau en direct — site {site.identifiant}, un point toutes les {pas_s:g} s, "
          f"{heures_par_minute:g} h de site par minute réelle.", flush=True)
    if equipement_vise:
        print(f"Scénario : {type_panne or 'échauffement'} sur "
              f"{site.nom_equipement(equipement_vise)} ({equipement_vise}), "
              f"dans {dans_s:g} s, pendant {duree_panne_s / 60:g} min"
              + (f", intensité {intensite:g}" if intensite else "")
              + ("." if une_seule else ", puis en boucle."), flush=True)
    else:
        print(f"Première panne dans {periode_panne_s:g} s.", flush=True)
    print("Ctrl+C pour arrêter.", flush=True)

    try:
        while True:
            maintenant = time.time()
            reel = datetime.now(timezone.utc)
            # le planning du site défile plus vite que l'horloge : on voit les
            # arrêts et les remises en route sans attendre la nuit.
            instant_site += timedelta(seconds=pas_s * heures_par_minute * 60)

            if maintenant >= prochaine_panne:
                victime = equipement_vise or alea.choice([e["id"] for e in liste])
                pannes.append(Panne(victime, maintenant, duree_panne_s,
                                    type_panne, intensite))
                prochaine_panne = (float("inf") if une_seule
                                   else maintenant + periode_panne_s)
                print(f"  [{reel.strftime('%H:%M:%S')}] panne déclenchée sur {victime}"
                      + (f" — {type_panne}" if type_panne else ""), flush=True)

            ambiances = {zone: simulateur.ambiance(zone, instant_site, alea)
                         for zone in sorted(site.zones)}
            contexte, mesures_par_camera = [], {}

            for equipement in liste:
                marche, charge_nominale = simulateur.en_marche(
                    equipement.get("activite", "continu"), instant_site)
                # Une panne sur une machine à l'arrêt ne chauffe presque rien :
                # elle part de la température ambiante. Pour un scénario voulu,
                # on peut la maintenir en service le temps de la démonstration.
                if (forcer_marche and equipement["id"] == equipement_vise
                        and any(p.equipement == equipement["id"] for p in pannes)):
                    marche, charge_nominale = True, max(charge_nominale, 80)
                if marche:
                    charges[equipement["id"]] += alea.gauss(0, 0.4)
                    charges[equipement["id"]] = min(
                        max(charges[equipement["id"]], charge_nominale - 25), 100.0)
                    charge = charges[equipement["id"]]
                else:
                    charge = 0.0

                t_ambiante = ambiances[equipement["zone"]]
                if marche:
                    bande = equipement["plage_haute"] - equipement["plage_basse"]
                    cible = equipement["plage_basse"] + bande * (0.1 + 0.8 * charge / 100.0)
                    particulieres = site.climat.get("zones_particulieres", {})
                    if not particulieres.get(str(equipement["zone"]), {}).get("base"):
                        cible += (t_ambiante - 28.0) * 0.5
                    if equipement["plage_haute"] > t_ambiante:
                        cible = max(cible, t_ambiante + 1.0)
                else:
                    cible = t_ambiante

                en_defaut = False
                for panne in list(pannes):
                    if panne.equipement != equipement["id"]:
                        continue
                    supplement = panne.supplement(maintenant)
                    if supplement is None:
                        pannes.remove(panne)
                        print(f"  [{reel.strftime('%H:%M:%S')}] panne terminée "
                              f"sur {panne.equipement}", flush=True)
                        continue
                    cible += supplement
                    en_defaut = True

                tau = (TAU_PANNE_S if en_defaut
                       else max(equipement["temps_montee_min"] * 60 / 3.0, 1.0))
                courant = temperature[equipement["id"]]
                courant += (cible - courant) * (1 - math.exp(-pas_s / tau))
                temperature[equipement["id"]] = courant

                t_max = courant + alea.gauss(0, 0.3)
                mesures_par_camera.setdefault(equipement["camera"], []).append({
                    "equipement": equipement["id"], "t_max": round(t_max, 1),
                    "t_moy": round(t_max - 6 - alea.uniform(0, 2), 1),
                    "t_min": round(t_max - 14 - alea.uniform(0, 3), 1)})
                contexte.append({"equipement": equipement["id"],
                                 "etat": "marche" if marche else "arret",
                                 "charge_pct": round(charge)})

            horodatage = horodater(reel)
            client.publish(f"sasi/{site.identifiant}/contexte", json.dumps({
                "site": site.identifiant, "horodatage": horodatage,
                "equipements": contexte,
                "ambiance": [{"zone": zone, "t_ambiante": round(valeur, 1),
                              "humidite_pct": round(alea.uniform(70, 90))}
                             for zone, valeur in ambiances.items()],
            }), qos=1)

            for camera, zones in mesures_par_camera.items():
                client.publish(f"sasi/{site.identifiant}/{camera}/mesures", json.dumps({
                    "site": site.identifiant, "camera": camera, "horodatage": horodatage,
                    "source": "jumeau", "zones": zones}), qos=1)

            time.sleep(pas_s)
    except KeyboardInterrupt:
        print("\nJumeau arrêté.")
    finally:
        client.loop_stop()
        client.disconnect()


def principal():
    analyseur = argparse.ArgumentParser(
        description="Produit des mesures en temps réel, comme le ferait le jumeau numérique")
    analyseur.add_argument("site", nargs="?", default="brasserie")
    analyseur.add_argument("--pas", type=float, default=10.0,
                           help="secondes entre deux mesures (défaut : 10)")
    analyseur.add_argument("--heures-par-minute", type=float, default=2.0,
                           help="vitesse du planning du site (défaut : 2 h par minute)")
    analyseur.add_argument("--panne", type=float, default=300.0,
                           help="secondes entre deux pannes (défaut : 300)")
    analyseur.add_argument("--serveur", default="localhost")
    analyseur.add_argument("--graine", type=int, default=2026)

    precis = analyseur.add_argument_group("scénario précis")
    precis.add_argument("--equipement", default=None,
                        help="identifiant de l'équipement à mettre en défaut")
    precis.add_argument("--type", dest="type_panne", default=None,
                        choices=sorted(SIGNATURES),
                        help="signature de la panne (voir sites/<site>.json)")
    precis.add_argument("--intensite", type=float, default=None,
                        help="intensité de la panne, en °C (selon la signature)")
    precis.add_argument("--duree-panne", type=float, default=DUREE_PANNE_S / 60,
                        help="durée de la panne, en minutes (défaut : 15)")
    precis.add_argument("--dans", type=float, default=60.0,
                        help="délai avant le déclenchement, en secondes")
    precis.add_argument("--une-seule", action="store_true",
                        help="une seule panne, puis plus rien")
    precis.add_argument("--forcer-marche", action="store_true",
                        help="maintenir l'équipement en service pendant la panne")
    arguments = analyseur.parse_args()

    if arguments.type_panne and not arguments.equipement:
        analyseur.error("--type demande --equipement")

    site = Site.charger(arguments.site)
    if arguments.equipement and arguments.equipement not in site.equipements:
        analyseur.error(f"équipement inconnu : {arguments.equipement}. "
                        f"Choix : {', '.join(site.liste())}")

    publier(site, arguments.serveur, arguments.pas, arguments.heures_par_minute,
            arguments.panne, arguments.graine,
            equipement_vise=arguments.equipement, type_panne=arguments.type_panne,
            intensite=arguments.intensite, duree_panne_s=arguments.duree_panne * 60,
            dans_s=arguments.dans, une_seule=arguments.une_seule,
            forcer_marche=arguments.forcer_marche)


if __name__ == "__main__":
    principal()
