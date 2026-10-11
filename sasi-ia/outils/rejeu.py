"""Rejeu d'un lot de mesures, comme s'il venait des caméras.

    ./venv/bin/python outils/rejeu.py brasserie B --vitesse 60
    ./venv/bin/python outils/rejeu.py brasserie B --vitesse 600 --maintenant
    ./venv/bin/python outils/rejeu.py brasserie B --vitesse 60 --maintenant --boucle

Le lecteur lit les fichiers du lot et publie les messages MQTT au format des
conventions d'échange. Il sert aux essais et aux démonstrations, sans matériel.

L'option --maintenant redate le lot pour qu'il se termine à l'instant présent :
les courbes de l'interface, qui n'affichent que les dernières heures, montrent
alors les mesures au lieu d'un graphique vide.

L'option --boucle reprend le lot au début dès qu'il est épuisé, en le redatant à
chaque tour : le flux ne s'arrête jamais, et les écrans continuent d'avancer.
"""

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ia.site import Site

RACINE = Path(__file__).resolve().parents[1]


def lire(chemin):
    with open(chemin, encoding="utf-8") as fichier:
        return list(csv.DictReader(fichier))


def grouper_par_horodatage(mesures):
    """Regroupe les mesures par instant et par caméra, comme le ferait une caméra."""
    groupes = defaultdict(lambda: defaultdict(list))
    for ligne in mesures:
        groupes[ligne["horodatage"]][ligne["camera"]].append(ligne)
    return groupes


def en_date(texte):
    return datetime.fromisoformat(str(texte).replace("Z", "+00:00"))


def calculer_decalage(instants, redater, origine="fin"):
    """Décalage à appliquer pour placer le lot par rapport à l'instant présent.

    origine="fin"   : le dernier instant du lot tombe maintenant (lot complet) ;
    origine="debut" : le premier instant tombe maintenant, et le rejeu avance
                      ensuite dans le temps (flux continu, option --boucle).
    """
    if not redater or not instants:
        return timedelta(0)
    repere = instants[-1] if origine == "fin" else instants[0]
    return datetime.now(timezone.utc) - en_date(repere)


def decaler(horodatage, decalage):
    if not decalage:
        return horodatage
    return (en_date(horodatage) + decalage).isoformat().replace("+00:00", "Z")


def fiche_mesures(site, camera, horodatage, lignes, source="jumeau"):
    return {"site": site, "camera": camera, "horodatage": horodatage, "source": source,
            "zones": [{"equipement": l["equipement"], "t_max": float(l["t_max"]),
                       "t_moy": float(l["t_moy"]), "t_min": float(l["t_min"])}
                      for l in lignes]}


def rejouer(nom_site, lot, vitesse=60.0, adresse="localhost", limite=None, redater=False,
            boucle=False):
    import paho.mqtt.client as mqtt

    site = Site.charger(nom_site)
    dossier = RACINE / "donnees" / site.identifiant.lower()
    mesures = lire(dossier / f"mesures_{lot}.csv")
    contexte = lire(dossier / f"contexte_{lot}.csv")
    ambiance = lire(dossier / f"ambiance_{lot}.csv")

    contexte_par_temps = defaultdict(list)
    for ligne in contexte:
        contexte_par_temps[ligne["horodatage"]].append(ligne)
    ambiance_par_temps = defaultdict(list)
    for ligne in ambiance:
        ambiance_par_temps[ligne["horodatage"]].append(ligne)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.connect(adresse, 1883, keepalive=60)
    client.loop_start()

    groupes = grouper_par_horodatage(mesures)
    instants = sorted(groupes)
    if limite:
        instants = instants[:limite]
    attente = 10.0 / max(vitesse, 0.001)          # le pas des mesures est de 10 s
    # En boucle, on part du début : les mesures suivent alors l'horloge réelle
    # et l'interface les voit arriver l'une après l'autre.
    decalage = calculer_decalage(instants, redater, "debut" if boucle else "fin")
    print(f"Rejeu de {len(instants)} instants ({site.identifiant}, lot {lot}) "
          f"à {vitesse:g} fois la vitesse réelle"
          + (f", redaté de {decalage.days} jours" if decalage else "")
          + (", en boucle (Ctrl+C pour arrêter)" if boucle else ""))

    def publier_instant(horodatage, decalage):
        """Publie le contexte et les mesures d'un instant, redatés si besoin."""
        publie = decaler(horodatage, decalage)
        if horodatage in contexte_par_temps or horodatage in ambiance_par_temps:
            client.publish(f"sasi/{site.identifiant}/contexte", json.dumps({
                "site": site.identifiant, "horodatage": publie,
                "equipements": [{"equipement": l["equipement"], "etat": l["etat"],
                                 "charge_pct": float(l["charge_pct"])}
                                for l in contexte_par_temps.get(horodatage, [])],
                "ambiance": [{"zone": int(l["zone"]),
                              "t_ambiante": float(l["t_ambiante"]),
                              "humidite_pct": float(l["humidite_pct"])}
                             for l in ambiance_par_temps.get(horodatage, [])],
            }), qos=1)
        for camera, lignes in groupes[horodatage].items():
            client.publish(f"sasi/{site.identifiant}/{camera}/mesures",
                           json.dumps(fiche_mesures(site.identifiant, camera,
                                                    publie, lignes)), qos=1)
        return publie

    try:
        tour = 1
        while True:
            for numero, horodatage in enumerate(instants, 1):
                publie = publier_instant(horodatage, decalage)
                if numero % 100 == 0:
                    print(f"  {numero}/{len(instants)} instants publiés ({publie})")
                time.sleep(attente)
            if not boucle:
                break
            tour += 1
            decalage = calculer_decalage(instants, True, "debut")
            print(f"Fin du lot : reprise au début (tour {tour}).")
    except KeyboardInterrupt:
        print("\nRejeu interrompu.")
    finally:
        client.loop_stop()
        client.disconnect()
    print("Rejeu terminé.")


if __name__ == "__main__":
    analyseur = argparse.ArgumentParser(description="Rejoue un lot de mesures en MQTT")
    analyseur.add_argument("site", nargs="?", default="brasserie")
    analyseur.add_argument("lot", nargs="?", default="B")
    analyseur.add_argument("--vitesse", type=float, default=60.0,
                           help="1 = temps réel, 60 = une minute par seconde")
    analyseur.add_argument("--serveur", default="localhost")
    analyseur.add_argument("--limite", type=int, default=None,
                           help="nombre d'instants à publier (essais)")
    analyseur.add_argument("--maintenant", action="store_true",
                           help="redate le lot pour qu'il se termine à l'instant présent")
    analyseur.add_argument("--boucle", action="store_true",
                           help="reprend le lot au début sans jamais s'arrêter")
    arguments = analyseur.parse_args()
    rejouer(arguments.site, arguments.lot, arguments.vitesse,
            arguments.serveur, arguments.limite, arguments.maintenant or arguments.boucle,
            arguments.boucle)
