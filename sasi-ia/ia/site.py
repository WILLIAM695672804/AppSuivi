"""Description d'un site industriel, lue dans un fichier de configuration.

Changer de site ou de secteur ne demande aucune modification du code : il suffit
d'écrire un fichier dans le dossier sites/ (voir sites/brasserie.json).

Ce fichier n'utilise que Python.
"""

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DOSSIER_SITES = RACINE / "sites"

CHAMPS_OBLIGATOIRES = ("id", "nom", "camera", "zone", "famille",
                       "plage_basse", "plage_haute", "temps_montee_min", "criticite")

MARGE_INSPECTION = 15      # °C au-dessus de la plage normale
MARGE_URGENCE = 30


class Site:
    """Tout ce que le système doit savoir d'un site : équipements, zones, planning."""

    def __init__(self, donnees):
        self.donnees = donnees
        self.identifiant = donnees["site"]["id"]
        self.nom = donnees["site"]["nom"]
        self.secteur = donnees["site"].get("secteur", "")
        self.zones = {int(k): v for k, v in donnees.get("zones", {}).items()}
        self.familles = donnees.get("familles", {})
        self.planning = donnees.get("planning", {})
        self.climat = donnees.get("climat", {})
        self.groupes_jumeaux = donnees.get("groupes_jumeaux", [])
        self.equipements = {e["id"]: e for e in donnees["equipements"]}
        self._verifier()

    # ---------- chargement ----------
    @classmethod
    def charger(cls, nom_ou_chemin="brasserie"):
        chemin = Path(nom_ou_chemin)
        if not chemin.exists():
            chemin = DOSSIER_SITES / f"{nom_ou_chemin}.json"
        if not chemin.exists():
            disponibles = ", ".join(sorted(f.stem for f in DOSSIER_SITES.glob("*.json")))
            raise FileNotFoundError(
                f"Site « {nom_ou_chemin} » introuvable. Sites disponibles : {disponibles}")
        return cls(json.loads(chemin.read_text(encoding="utf-8")))

    def _verifier(self):
        """Refuse un fichier incomplet plutôt que de produire des résultats faux."""
        if not self.equipements:
            raise ValueError("Le site ne contient aucun équipement.")
        for identifiant, equipement in self.equipements.items():
            manquants = [c for c in CHAMPS_OBLIGATOIRES if equipement.get(c) is None]
            if manquants:
                raise ValueError(f"{identifiant} : champ(s) manquant(s) : {', '.join(manquants)}")
            if equipement["plage_basse"] > equipement["plage_haute"]:
                raise ValueError(f"{identifiant} : plage_basse supérieure à plage_haute.")
            inspection = equipement.get("seuil_inspection")
            urgence = equipement.get("seuil_urgence")
            if inspection is not None and urgence is not None and inspection >= urgence:
                raise ValueError(f"{identifiant} : le seuil d'inspection doit être inférieur "
                                 "au seuil d'urgence.")
            if equipement["criticite"] not in (1, 2, 3):
                raise ValueError(f"{identifiant} : la criticité doit valoir 1, 2 ou 3.")
            if self.familles and equipement["famille"] not in self.familles:
                raise ValueError(f"{identifiant} : famille inconnue « {equipement['famille']} ».")
        for groupe in self.groupes_jumeaux:
            for identifiant in groupe:
                if identifiant not in self.equipements:
                    raise ValueError(f"Groupe d'équipements jumeaux : {identifiant} inconnu.")

    # ---------- accès ----------
    def liste(self):
        return list(self.equipements)

    def famille(self, identifiant):
        return self.equipements[identifiant]["famille"]

    def nom_equipement(self, identifiant):
        return self.equipements[identifiant].get("nom", identifiant)

    def plage(self, identifiant):
        equipement = self.equipements[identifiant]
        return equipement["plage_basse"], equipement["plage_haute"]

    def criticite(self, identifiant):
        return self.equipements[identifiant]["criticite"]

    def temps_montee_min(self, identifiant):
        return self.equipements[identifiant]["temps_montee_min"]

    def action_specifique(self, identifiant):
        return self.equipements[identifiant].get("action")

    def camera(self, identifiant):
        return self.equipements[identifiant]["camera"]

    def activite(self, identifiant):
        return self.equipements[identifiant].get("activite", "continu")

    def zone(self, identifiant):
        return self.equipements[identifiant]["zone"]

    def seuils_fixes(self, identifiant):
        """Filet de sécurité : seuils relevés sur le terrain s'ils existent, sinon
        plage normale + 15 °C (inspection) et + 30 °C (urgence)."""
        equipement = self.equipements[identifiant]
        haut = equipement["plage_haute"]
        inspection = equipement.get("seuil_inspection")
        urgence = equipement.get("seuil_urgence")
        if inspection is None:
            inspection = haut + MARGE_INSPECTION
        if urgence is None:
            urgence = inspection + MARGE_URGENCE - MARGE_INSPECTION
        return inspection, urgence

    def jumeaux(self, identifiant):
        """Équipements identiques auxquels comparer celui-ci."""
        for groupe in self.groupes_jumeaux:
            if identifiant in groupe:
                return [e for e in groupe if e != identifiant]
        return []

    def tous_les_jumeaux(self):
        return [e for groupe in self.groupes_jumeaux for e in groupe]

    def resume(self):
        return (f"{self.nom} ({self.secteur}) : {len(self.equipements)} équipements, "
                f"{len(self.zones)} zones, {len(self.familles)} familles")


def sites_disponibles():
    return sorted(f.stem for f in DOSSIER_SITES.glob("*.json"))
