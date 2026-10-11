"""Journal des pannes annoncées par le jumeau numérique (conventions, 6.4).

Le jumeau publie deux messages par panne — un début, une fin. Ce module les
rapproche en une ligne par panne, au format que le contrôle automatique attend
déjà (`ia/chaine.fenetres_journal`) :

    id,equipement,type,debut,fin,intensite

Sans ce journal, rien ne permet de dire si l'IA a détecté une panne ou si elle a
crié dans le vide : c'est la vérité de référence du contrôle.

Une panne commencée mais non terminée n'est pas écrite — sa fenêtre n'existe pas
encore. Elle reste disponible par `ouvertes()`.
"""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

ENTETE = ["id", "equipement", "type", "debut", "fin", "intensite"]


def _iso(horodatage):
    """Horodatage du contrat, qu'il arrive en texte ISO ou en secondes."""
    if horodatage is None:
        return None
    if isinstance(horodatage, (int, float)) and not isinstance(horodatage, bool):
        instant = datetime.fromtimestamp(float(horodatage), tz=timezone.utc)
        return instant.strftime("%Y-%m-%dT%H:%M:%SZ")
    return str(horodatage).replace("+00:00", "Z")


class JournalPannes:
    """Rapproche les débuts et les fins, et tient le fichier à jour."""

    def __init__(self, chemin=None):
        self.chemin = Path(chemin) if chemin else None
        self.pannes = {}                 # id_panne -> ligne en construction
        self.ordre = []                  # pour conserver l'ordre d'arrivée
        self.ecartes = 0

    def appliquer(self, charge_utile):
        """Traite un message du jumeau. Renvoie la panne complétée, ou None."""
        try:
            fiche = json.loads(charge_utile) if isinstance(charge_utile, (str, bytes)) \
                else charge_utile
        except (ValueError, TypeError):
            self.ecartes += 1
            return None
        if not isinstance(fiche, dict):
            self.ecartes += 1
            return None

        identifiant = fiche.get("id_panne")
        evenement = fiche.get("evenement")
        if not identifiant or evenement not in ("debut", "fin"):
            self.ecartes += 1
            return None

        ligne = self.pannes.get(identifiant)
        if ligne is None:
            ligne = {"id": identifiant, "equipement": fiche.get("equipement"),
                     "type": fiche.get("type"), "debut": None, "fin": None,
                     "intensite": fiche.get("intensite")}
            self.pannes[identifiant] = ligne
            self.ordre.append(identifiant)

        # Une fin sans début connu reste une fin : l'équipement et la signature
        # du message le plus récent font foi, le jumeau les répète dans les deux.
        ligne["equipement"] = fiche.get("equipement") or ligne["equipement"]
        ligne["type"] = fiche.get("type") or ligne["type"]
        if fiche.get("intensite") is not None:
            ligne["intensite"] = fiche["intensite"]
        ligne[evenement] = _iso(fiche.get("horodatage"))

        if ligne["debut"] and ligne["fin"]:
            self.ecrire()
            return dict(ligne)
        return None

    def completes(self):
        """Pannes dont le début et la fin sont connus."""
        return [self.pannes[i] for i in self.ordre
                if self.pannes[i]["debut"] and self.pannes[i]["fin"]]

    def ouvertes(self):
        """Pannes commencées, pas encore terminées."""
        return [self.pannes[i] for i in self.ordre
                if self.pannes[i]["debut"] and not self.pannes[i]["fin"]]

    def ecrire(self):
        """Réécrit le fichier en entier : une panne, une ligne."""
        if not self.chemin:
            return None
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        with open(self.chemin, "w", newline="", encoding="utf-8") as fichier:
            graveur = csv.DictWriter(fichier, fieldnames=ENTETE)
            graveur.writeheader()
            for ligne in self.completes():
                graveur.writerow(ligne)
        return self.chemin

    def resume(self):
        return {"completes": len(self.completes()), "ouvertes": len(self.ouvertes()),
                "ecartes": self.ecartes}
