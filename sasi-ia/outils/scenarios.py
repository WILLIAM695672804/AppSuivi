"""Catalogue de pannes d'un site : combien, lesquelles, quand.

    ./venv/bin/python outils/scenarios.py                    brasserie, 60 pannes sur 30 jours
    ./venv/bin/python outils/scenarios.py minoterie --jours 14 --pannes 20
    ./venv/bin/python outils/scenarios.py --montrer          sans rien écrire

Le catalogue est écrit dans `sites/<site>.json`, champ `pannes_exemple`, que le
simulateur reprend pour fabriquer les lots d'essai. On peut le modifier à la
main : ce programme ne sert qu'à en produire un varié et complet.

Trois garanties :
  - chaque équipement est touché plusieurs fois, jamais deux fois le même jour ;
  - chaque signature de panne apparaît plusieurs fois ;
  - l'intensité reste physiquement plausible.

Ce dernier point demande une précaution. Une intensité calculée en proportion de
la plage normale donne des pannes dérisoires sur les équipements à plage étroite :
un pasteurisateur qui travaille entre 60 et 67 °C recevrait une « surchauffe » de
trois degrés, que personne ne remarquerait — et surtout pas l'IA, dont l'écart
habituel sur cet équipement est du même ordre. Chaque type de panne porte donc
aussi un plancher, tiré de ce qu'on observe sur le terrain.
"""

import argparse
import collections
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RACINE = Path(__file__).resolve().parents[1]

# (type, part de la plage, plancher en °C, durée minimale, durée maximale en heures)
REPERTOIRE = {
    "MOT": [("derive_lente", 0.20, 6.0, 4.0, 6.0),
            ("friction_roulement", 0.08, 2.5, 3.0, 4.5),
            ("montee_brutale", 0.06, 1.5, 0.3, 0.5)],
    "CHD": [("colmatage_filtre", 0.02, 1.5, 5.0, 7.0),
            ("surchauffe_bruleur", 0.45, 25.0, 1.0, 2.0),
            ("rupture_calorifuge", 0.25, 15.0, 2.0, 9.0),
            ("defaut_refroidissement", 0.15, 10.0, 6.0, 8.0)],
    "ARM": [("point_chaud_phase", 0.70, 12.0, 10.0, 14.0)],
    "POM": [("defaut_refroidissement", 0.40, 10.0, 6.0, 8.0),
            ("friction_roulement", 0.10, 2.5, 3.0, 4.5),
            ("derive_lente", 0.25, 6.0, 4.0, 6.0)],
    "RES": [("chauffe_a_vide", 0.40, 20.0, 0.3, 0.6)],
}

# Un équipement qui travaille sous zéro ne surchauffe pas : il perd son froid.
FROID = [("derive_froid", 0.02, 1.5, 8.0, 10.0)]
TEMPERATURE_FROID = 10.0


def repertoire_de(fiche):
    return FROID if fiche["plage_haute"] < TEMPERATURE_FROID else REPERTOIRE[fiche["famille"]]


def fabriquer(fiche, jour, alea, type_impose=None):
    """Une panne plausible pour cet équipement, ce jour-là."""
    amplitude = max(fiche["plage_haute"] - fiche["plage_basse"], 5)
    choix = [t for t in repertoire_de(fiche) if type_impose in (None, t[0])]
    type_panne, part, plancher, duree_min, duree_max = alea.choice(
        choix or repertoire_de(fiche))
    # Le plancher l'emporte sur la proportion : une surchauffe de brûleur fait
    # au moins vingt-cinq degrés, que la plage normale soit large ou étroite.
    intensite = max(amplitude * part, plancher) * alea.uniform(0.85, 1.15)
    return {
        "equipement": fiche["id"], "type": type_panne, "jour": jour,
        "heure": round(alea.uniform(2.0, 22.0), 1),
        "duree_h": round(alea.uniform(duree_min, duree_max), 1),
        "intensite": round(intensite, 1),
    }


def composer(equipements, jours=30, nombre=60, par_equipement=3, graine=20260923):
    """Construit un catalogue varié et complet."""
    alea = random.Random(graine)
    fiches = {e["id"]: e for e in equipements}
    liste = sorted(fiches)
    pannes, occupes = [], collections.defaultdict(set)

    # 1. chaque équipement est touché plusieurs fois, à des jours différents
    for _ in range(par_equipement):
        for identifiant in liste:
            libres = [j for j in range(jours) if j not in occupes[identifiant]]
            if not libres:
                continue
            jour = alea.choice(libres)
            occupes[identifiant].add(jour)
            pannes.append(fabriquer(fiches[identifiant], jour, alea))

    # 2. on complète en privilégiant les signatures les moins représentées
    tous_types = {t[0] for f in fiches.values() for t in repertoire_de(f)}
    while len(pannes) < nombre:
        compte = collections.Counter(p["type"] for p in pannes)
        rare = min(tous_types, key=lambda t: compte.get(t, 0))
        candidats = [e for e in liste
                     if any(t[0] == rare for t in repertoire_de(fiches[e]))
                     and len(occupes[e]) < jours]
        if not candidats:
            break
        identifiant = alea.choice(candidats)
        jour = alea.choice([j for j in range(jours) if j not in occupes[identifiant]])
        occupes[identifiant].add(jour)
        pannes.append(fabriquer(fiches[identifiant], jour, alea, type_impose=rare))

    pannes.sort(key=lambda p: (p["jour"], p["heure"]))
    for rang, panne in enumerate(pannes, 1):
        panne["id"] = f"P-{rang:02d}"
    return [{"id": p["id"], "equipement": p["equipement"], "type": p["type"],
             "jour": p["jour"], "heure": p["heure"], "duree_h": p["duree_h"],
             "intensite": p["intensite"]} for p in pannes]


def resumer(pannes, equipements):
    par_type = collections.Counter(p["type"] for p in pannes)
    par_equipement = collections.Counter(p["equipement"] for p in pannes)
    print(f"\n  {len(pannes)} pannes")
    print("  par signature :")
    for type_panne, nombre in sorted(par_type.items()):
        print(f"    {type_panne:24s} {nombre}")
    print(f"  équipements touchés : {len(par_equipement)}/{len(equipements)}, "
          f"de {min(par_equipement.values())} à {max(par_equipement.values())} fois")
    print("  intensités extrêmes : "
          f"{min(p['intensite'] for p in pannes):.1f} à "
          f"{max(p['intensite'] for p in pannes):.1f} °C")


def principal(nom_site="brasserie", jours=30, nombre=60, montrer=False, graine=20260923):
    chemin = RACINE / "sites" / f"{nom_site}.json"
    site = json.loads(chemin.read_text(encoding="utf-8"))
    pannes = composer(site["equipements"], jours, nombre, graine=graine)
    resumer(pannes, site["equipements"])

    if montrer:
        print("\n  (rien n'a été écrit : option --montrer)")
        return 0
    site["pannes_exemple"] = pannes
    chemin.write_text(json.dumps(site, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Catalogue écrit dans {chemin.relative_to(RACINE)}")
    print("  Régénérez les lots : ./venv/bin/python outils/simulateur.py " + nom_site)
    return 0


if __name__ == "__main__":
    analyseur = argparse.ArgumentParser(description="Compose le catalogue de pannes d'un site")
    analyseur.add_argument("site", nargs="?", default="brasserie")
    analyseur.add_argument("--jours", type=int, default=30)
    analyseur.add_argument("--pannes", type=int, default=60)
    analyseur.add_argument("--graine", type=int, default=20260923)
    analyseur.add_argument("--montrer", action="store_true",
                           help="afficher le catalogue sans l'enregistrer")
    arguments = analyseur.parse_args()
    sys.exit(principal(arguments.site, arguments.jours, arguments.pannes,
                       arguments.montrer, arguments.graine))
