"""Schémas JSON des messages du contrat, pour les langages autres que Python.

Le jumeau numérique sera probablement écrit en C# ou en JavaScript ; `contrat.py`
ne lui sert alors que de documentation. Ces schémas, eux, s'emploient directement
avec n'importe quelle bibliothèque de validation JSON Schema (draft 2020-12).

    ./venv/bin/python integration/schemas.py          écrit integration/schemas/

Ils sont *engendrés* à partir des constantes de `contrat.py`, et non recopiés :
un test vérifie que les fichiers sur le disque correspondent à ce que ce module
produit. Ajouter une signature de panne au contrat met donc les schémas en
défaut jusqu'à ce qu'ils soient régénérés.

Ils contrôlent la forme, pas la cohérence : l'appartenance d'un équipement à la
liste de référence, l'ordre des trois températures et la cadence restent du
ressort du vérificateur.
"""

import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from integration import contrat                                     # noqa: E402

DOSSIER = Path(__file__).parent / "schemas"
BROUILLON = "https://json-schema.org/draft/2020-12/schema"
BASE = "https://sasi.local/schemas"

HORODATAGE = {
    "description": "Heure universelle 2026-09-19T14:30:10Z, ou secondes Unix",
    "oneOf": [{"type": "string", "pattern": contrat.MOTIF_HORODATAGE.pattern},
              {"type": "number"}],
}
TEMPERATURE = {
    "description": "Degrés Celsius, une décimale ; « null » si la valeur manque",
    "type": ["number", "null"],
    "minimum": contrat.TEMPERATURE_MINIMALE,
    "maximum": contrat.TEMPERATURE_MAXIMALE,
}
POURCENTAGE = {"type": ["number", "null"], "minimum": 0, "maximum": 100}
IDENTIFIANT = {"type": "string", "pattern": contrat.MOTIF_EQUIPEMENT.pattern}
CAMERA = {"type": "string", "pattern": contrat.MOTIF_CAMERA.pattern}


def _schema(nom, titre, description, proprietes, obligatoires):
    return {
        "$schema": BROUILLON,
        "$id": f"{BASE}/{nom}.json",
        "title": titre,
        "description": description,
        "x-contrat": contrat.VERSION,
        "type": "object",
        "properties": proprietes,
        "required": obligatoires,
    }


def mesures():
    return _schema(
        "mesures", "Mesures de température",
        "sasi/<site>/<camera>/mesures — une publication par caméra, "
        f"toutes les {contrat.PAS_MESURES_S} s",
        {
            "site": {"type": "string", "minLength": 1},
            "camera": CAMERA,
            "horodatage": HORODATAGE,
            "source": {"enum": list(contrat.SOURCES),
                       "description": "« jumeau » pour une mesure simulée, "
                                      "« camera » pour une mesure réelle"},
            "zones": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"equipement": IDENTIFIANT, "t_max": TEMPERATURE,
                                   "t_moy": TEMPERATURE, "t_min": TEMPERATURE},
                    "required": ["equipement", "t_max"],
                },
            },
        },
        ["site", "camera", "horodatage", "zones"])


def contexte():
    return _schema(
        "contexte", "Contexte de fonctionnement",
        f"sasi/<site>/contexte — à chaque changement, au moins toutes les "
        f"{contrat.PAS_CONTEXTE_S} s",
        {
            "site": {"type": "string", "minLength": 1},
            "horodatage": HORODATAGE,
            "equipements": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"equipement": IDENTIFIANT,
                                   "etat": {"enum": list(contrat.ETATS_MARCHE)},
                                   "charge_pct": POURCENTAGE},
                    "required": ["equipement"],
                },
            },
            "ambiance": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"zone": {"type": "integer", "minimum": 1},
                                   "t_ambiante": TEMPERATURE,
                                   "humidite_pct": POURCENTAGE},
                    "required": ["zone"],
                },
            },
        },
        ["site", "horodatage"])


def pannes():
    return _schema(
        "pannes", "Journal des pannes",
        "sasi/<site>/jumeau/pannes — un message au début, un à la fin, "
        "même id_panne pour les deux",
        {
            "site": {"type": "string"},
            "id_panne": {"type": "string", "minLength": 1},
            "equipement": IDENTIFIANT,
            "type": {"type": "string", "examples": list(contrat.TYPES_PANNE),
                     "description": "signature de la panne ; une valeur hors "
                                    "répertoire est acceptée mais comptée à part"},
            "evenement": {"enum": list(contrat.EVENEMENTS_PANNE)},
            "horodatage": HORODATAGE,
            "intensite": {"type": ["number", "string", "null"]},
            "description": {"type": "string"},
        },
        ["id_panne", "equipement", "type", "evenement", "horodatage"])


def horloge():
    return _schema(
        "horloge", "Mode d'horloge du jumeau",
        "sasi/<site>/jumeau/horloge — au lancement d'un scénario. Les "
        "horodatages portent toujours l'heure simulée.",
        {
            "site": {"type": "string"},
            "mode": {"enum": list(contrat.MODES_HORLOGE)},
            "facteur": {"type": "number", "minimum": 1,
                        "description": "168 = une semaine en une heure"},
            "scenario": {"type": "string"},
            "debut_scenario": HORODATAGE,
        },
        ["mode"])


def alertes():
    return _schema(
        "alertes", "Alerte publiée par l'application",
        "sasi/<site>/alertes — à chaque création ou changement d'état. "
        "Relue par le jumeau pour colorer la maquette.",
        {
            "id": {"type": "string"},
            "equipement": IDENTIFIANT,
            "niveau": {"enum": list(contrat.NIVEAUX)},
            "etat": {"enum": list(contrat.ETATS_ALERTE)},
            "debut": HORODATAGE,
            "fin": {"oneOf": [HORODATAGE, {"type": "null"}]},
            "t_mesuree": TEMPERATURE,
            "t_attendue": TEMPERATURE,
            "raison": {"type": ["string", "null"]},
        },
        ["id", "equipement", "niveau", "etat", "debut"])


def niveaux():
    return _schema(
        "niveaux", "Niveau de chaque équipement",
        "sasi/<site>/niveaux — à chaque changement, pour colorer la maquette",
        {
            "horodatage": HORODATAGE,
            "niveaux": {
                "type": "object",
                "description": "identifiant d'équipement → niveau",
                "additionalProperties": {"enum": list(contrat.NIVEAUX)},
            },
        },
        ["niveaux"])


def tous():
    """Les six schémas, par nature de message."""
    return {"mesures": mesures(), "contexte": contexte(), "pannes": pannes(),
            "horloge": horloge(), "alertes": alertes(), "niveaux": niveaux()}


def ecrire(dossier=DOSSIER):
    dossier = Path(dossier)
    dossier.mkdir(parents=True, exist_ok=True)
    chemins = []
    for nom, schema in tous().items():
        chemin = dossier / f"{nom}.json"
        chemin.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8")
        chemins.append(chemin)
    return chemins


if __name__ == "__main__":
    for chemin in ecrire():
        print(f"  {chemin.relative_to(RACINE)}")
