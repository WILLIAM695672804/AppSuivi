"""Banc d'essai : soumettre une situation à l'IA et regarder comment elle réagit.

    ./venv/bin/python outils/essayer.py Z2-CHE-01
    ./venv/bin/python outils/essayer.py Z2-CHE-01 --situation montee --vitesse 2
    ./venv/bin/python outils/essayer.py Z1-ELV-01 --situation retour
    ./venv/bin/python outils/essayer.py --toutes

On fabrique une situation de toutes pièces — une montée régulière, un palier, un
démarrage, une chauffe qui rentre dans l'ordre — et on la donne à l'IA minute par
minute, avec le modèle réellement en service. Elle répond ce qu'elle répondrait
sur le site : température attendue, écart, probabilité, niveau d'alerte, et la
phrase qu'elle afficherait.

C'est le moyen le plus court de répondre à trois questions :
  - que prévoit-elle, et à partir de quand ?
  - réagit-elle comme le bon sens l'exige ?
  - sa prévision retombe-t-elle quand la température revient à la normale ?

Rien n'est publié, rien n'est enregistré : c'est un essai, pas une mesure.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json

from ia import risque as module_risque
from ia.detection import DetecteurEquipement
from ia.site import Site

RACINE = Path(__file__).resolve().parents[1]
PAS_S = 30                 # une mesure toutes les trente secondes


def calibrage_reel(site, identifiant, regime="etabli"):
    """Décalage et dispersion appris pour cet équipement, s'ils existent.

    Sans eux, l'essai réagirait bien plus vite qu'en service : la dispersion vaut
    1 °C par défaut, alors qu'une chaudière tolère plusieurs degrés d'écart.
    """
    fiche = RACINE / "modeles" / site.identifiant.lower() / "modeles.json"
    if not fiche.exists():
        return None
    calibrages = json.loads(fiche.read_text(encoding="utf-8")).get("calibrages", {})
    return (calibrages.get(identifiant) or {}).get(regime)


SITUATIONS = {
    "montee": "chauffe régulière, à la vitesse demandée",
    "retour": "chauffe, puis retour à la normale à mi-parcours",
    "palier": "montée franche qui se stabilise et n'évolue plus",
    "demarrage": "mise en route normale, prévue par le modèle",
    "brutale": "bond soudain de température, puis maintien",
}


def fabriquer(situation, depart, vitesse, minutes, plage_haute):
    """Renvoie la suite (minute, température mesurée, température attendue).

    La température attendue est celle que le modèle prévoirait : pour une mise en
    route, elle monte aussi — c'est ce qui distingue un démarrage d'un défaut.
    """
    points = []
    pas_par_minute = 60 / PAS_S
    total = int(minutes * pas_par_minute)

    for i in range(total):
        minute = i / pas_par_minute
        attendue = depart

        if situation == "montee":
            mesuree = depart + vitesse * minute
        elif situation == "retour":
            moitie = minutes / 2
            if minute <= moitie:
                mesuree = depart + vitesse * minute
            else:
                sommet = depart + vitesse * moitie
                mesuree = max(sommet - vitesse * (minute - moitie), depart)
        elif situation == "palier":
            mesuree = depart + min(vitesse * minute, vitesse * minutes / 3)
        elif situation == "demarrage":
            # la machine monte vers son régime, et le modèle l'avait prévu
            fraction = min(minute / max(minutes / 2, 1), 1.0)
            mesuree = depart + (plage_haute - depart) * fraction
            attendue = depart + (plage_haute - depart) * fraction
        elif situation == "brutale":
            mesuree = depart + (0 if minute < minutes / 4 else vitesse * minutes / 2)
        else:
            mesuree = depart
        points.append((minute, mesuree, attendue))
    return points


def essayer(site, identifiant, situation="montee", vitesse=1.0, minutes=40, bavard=True):
    """Fait passer la situation dans le détecteur et raconte ce qui se passe."""
    if identifiant not in site.equipements:
        raise SystemExit(f"Équipement inconnu : {identifiant}")

    basse, haute = site.plage(identifiant)
    inspection, urgence = site.seuils_fixes(identifiant)
    reglage = calibrage_reel(site, identifiant) or {}
    detecteur = DetecteurEquipement(
        identifiant, criticite=site.criticite(identifiant),
        biais=reglage.get("biais", 0.0),
        dispersion=reglage.get("dispersion", 1.0),
        seuil_fixe_inspection=inspection, seuil_fixe_urgence=urgence,
        temps_montee_min=site.temps_montee_min(identifiant))

    depart = (basse + haute) / 2.0
    points = fabriquer(situation, depart, vitesse, minutes, haute)

    if bavard:
        print(f"\n=== {site.nom_equipement(identifiant)} ({identifiant}) ===")
        print(f"  plage normale {basse}–{haute} °C · inspection {inspection} °C · "
              f"urgence {urgence} °C · criticité {site.criticite(identifiant)}")
        if reglage:
            print(f"  calibrage appris : écart habituel {reglage['dispersion']:.1f} °C, "
                  f"décalage {reglage['biais']:+.1f} °C")
        else:
            print("  aucun calibrage appris : l'essai sera plus sensible qu'en service")
        print(f"  situation : {SITUATIONS.get(situation, situation)}"
              + (f", {vitesse:g} °C/min" if situation != "demarrage" else ""))
        print()
        print("   min   mesurée  attendue    écart   risque   niveau")

    changements = []
    for minute, mesuree, attendue in points:
        etat = detecteur.traiter(minute * 60, mesuree, attendue)
        if bavard and (int(minute * 2) % 4 == 0 or etat["changement"]):
            marque = " ←" if etat["changement"] else ""
            print(f"  {minute:5.1f} {mesuree:8.1f} {attendue:9.1f} "
                  f"{etat['ecart']:+8.1f} {etat['risque_pourcentage']:6d} %   "
                  f"{etat['niveau']:12s}{marque}")
        if etat["changement"]:
            changements.append((minute, etat))

    if bavard:
        print()
        if not changements:
            print("  Aucune alerte : l'IA n'a rien trouvé d'anormal.")
        for minute, etat in changements:
            print(f"  à {minute:.0f} min → {etat['niveau'].upper()}")
            print("     " + module_risque.expliquer(etat["risque_detail"],
                                                    site.nom_equipement(identifiant)))
    return changements


def toutes_les_situations(site, identifiant, vitesse, minutes):
    """Passe l'équipement par toutes les situations et résume en un tableau."""
    print(f"\n=== {site.nom_equipement(identifiant)} ({identifiant}) : "
          "réaction à chaque situation ===\n")
    print(f"  {'situation':12s} {'ce qui se passe':52s} {'alerte':10s} {'à'}")
    for situation, description in SITUATIONS.items():
        changements = essayer(site, identifiant, situation, vitesse, minutes, bavard=False)
        montees = [c for c in changements if c[1]["niveau"] != "normal"]
        if montees:
            minute, etat = montees[0]
            verdict, quand = etat["niveau"], f"{minute:.0f} min"
        else:
            verdict, quand = "aucune", "—"
        print(f"  {situation:12s} {description:52s} {verdict:10s} {quand}")
    print("\n  Ce qu'il faut y voir : « demarrage » ne doit jamais alerter — une mise")
    print("  en route prévue n'est pas un défaut. « retour » doit voir son risque")
    print("  retomber dès que la température redescend.")


if __name__ == "__main__":
    analyseur = argparse.ArgumentParser(
        description="Soumet une situation à l'IA et montre sa réaction")
    analyseur.add_argument("equipement", nargs="?", default="Z2-CHE-01")
    analyseur.add_argument("--site", default="brasserie")
    analyseur.add_argument("--situation", default="montee", choices=sorted(SITUATIONS))
    analyseur.add_argument("--vitesse", type=float, default=1.0,
                           help="vitesse de chauffe en °C par minute")
    analyseur.add_argument("--duree", type=float, default=40.0,
                           help="durée de la situation, en minutes")
    analyseur.add_argument("--toutes", action="store_true",
                           help="passer l'équipement par toutes les situations")
    arguments = analyseur.parse_args()

    site_essai = Site.charger(arguments.site)
    if arguments.toutes:
        toutes_les_situations(site_essai, arguments.equipement,
                              arguments.vitesse, arguments.duree)
    else:
        essayer(site_essai, arguments.equipement, arguments.situation,
                arguments.vitesse, arguments.duree)
