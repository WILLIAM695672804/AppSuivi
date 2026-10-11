"""Adaptateur Modbus : lit les mesures d'une vraie caméra thermique.

Une caméra range ses valeurs dans des cases numérotées (registres). Le fichier de
réglage de la caméra indique quelle case correspond à quel équipement :

    camera: CAM-Z1
    adresse: 192.168.1.21
    adaptateur: modbus
    periode_s: 10
    zones:
      Z1-ELV-01: { t_max: 4012, t_moy: 4013, t_min: 4014, echelle: 0.1 }

Les numéros de cases figurent dans la notice de la caméra : ils restent à
confirmer lors de la première installation.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
DOSSIER_REGLAGES = RACINE / "config" / "cameras"


def charger_reglage(camera):
    """Lit le fichier de réglage d'une caméra (format JSON)."""
    chemin = DOSSIER_REGLAGES / f"{camera}.json"
    if not chemin.exists():
        raise FileNotFoundError(f"Réglage introuvable pour {camera} : {chemin}")
    return json.loads(chemin.read_text(encoding="utf-8"))


def construire_fiche(site, camera, valeurs, horodatage=None):
    """Assemble une fiche au format commun à partir des valeurs lues.

    valeurs : {equipement: {"t_max": …, "t_moy": …, "t_min": …}}
    """
    horodatage = horodatage or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {"site": site, "camera": camera, "horodatage": horodatage,
            "source": "camera",
            "zones": [{"equipement": equipement, **mesures}
                      for equipement, mesures in valeurs.items()]}


def lire(client_modbus, reglage):
    """Lit toutes les zones réglées dans la caméra.

    client_modbus : objet fourni par la bibliothèque Modbus retenue, muni d'une
    méthode read_holding_registers(adresse, nombre). Cette partie sera terminée
    lors de la première installation, avec la notice de la caméra sous les yeux.
    """
    valeurs = {}
    for equipement, cases in reglage["zones"].items():
        echelle = cases.get("echelle", 0.1)
        mesures = {}
        for champ in ("t_max", "t_moy", "t_min"):
            if champ in cases:
                brut = client_modbus.read_holding_registers(cases[champ], 1)
                mesures[champ] = round(brut[0] * echelle, 1)
        valeurs[equipement] = mesures
    return valeurs
