"""Retours du terrain : ce que les équipes ont constaté, et que l'IA doit apprendre.

L'IA se trompe de deux façons, et les équipes sont seules à pouvoir le dire :

  - **fausse alerte** : elle a signalé une chauffe qui n'en était pas une.
    La personne clôture l'alerte en répondant « non » à « alerte justifiée ».
    Cette période devient une période de fonctionnement normal : au prochain
    entraînement, le modèle l'apprend comme telle et cesse d'y voir un défaut.

  - **manque** : un échauffement réel qu'elle n'a pas signalé. Personne ne le
    voit dans les alertes, par définition : il faut donc pouvoir le déclarer
    après coup, depuis la fiche de l'équipement.

Les retours sont conservés dans `retours/<site>.json`, à part des mesures : ce
sont des jugements humains, qui doivent survivre au réentraînement et rester
consultables. Chaque retour porte qui l'a donné et quand — une correction du
modèle n'est jamais anonyme.

    retours = Registre("SIM01")
    retours.ajouter_fausse_alerte("Z1-MOU-01", debut, fin, "Nettoyage à la vapeur", "Awa N.")
    retours.ajouter_manque("Z2-CHE-01", debut, fin, "Roulement grippé", "Serge M.")
"""

import json
from datetime import datetime, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
RETOURS = RACINE / "retours"

# Une alerte clôturée « non justifiée » couvre aussi les minutes qui précèdent :
# la dérive avait commencé avant que le seuil ne soit franchi.
MARGE_AVANT_S = 900
MARGE_APRES_S = 300

FAUSSE_ALERTE = "fausse_alerte"
MANQUE = "manque"
CONFIRME = "confirme"


def _en_secondes(valeur):
    if valeur is None:
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)
    return datetime.fromisoformat(str(valeur).replace("Z", "+00:00")).timestamp()


class Registre:
    """Les retours d'un site, lus et écrits sur le disque."""

    def __init__(self, site, dossier=None):
        self.site = site if isinstance(site, str) else site.identifiant
        self.dossier = Path(dossier) if dossier else RETOURS
        self.chemin = self.dossier / f"{self.site.lower()}.json"
        self.retours = self._lire()

    def _lire(self):
        if not self.chemin.exists():
            return []
        return json.loads(self.chemin.read_text(encoding="utf-8")).get("retours", [])

    def _ecrire(self):
        self.dossier.mkdir(parents=True, exist_ok=True)
        self.chemin.write_text(json.dumps(
            {"site": self.site, "retours": self.retours}, ensure_ascii=False, indent=2),
            encoding="utf-8")

    # ---------- écriture ----------
    def ajouter(self, genre, equipement, debut, fin, motif, par, alerte=None):
        """Enregistre un retour. Renvoie la fiche créée."""
        if genre not in (FAUSSE_ALERTE, MANQUE, CONFIRME):
            raise ValueError(f"Genre de retour inconnu : {genre}")
        if not equipement:
            raise ValueError("Un retour porte toujours sur un équipement.")
        debut, fin = _en_secondes(debut), _en_secondes(fin)
        if debut is None or fin is None or fin <= debut:
            raise ValueError("La période du retour est vide ou à l'envers.")

        fiche = {
            "id": f"R-{len(self.retours) + 1:04d}",
            "genre": genre, "equipement": equipement,
            "debut": debut, "fin": fin,
            "motif": motif, "par": par, "alerte": alerte,
            "enregistre_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "pris_en_compte_le": None,
        }
        self.retours.append(fiche)
        self._ecrire()
        return fiche

    def ajouter_fausse_alerte(self, equipement, debut, fin, motif, par, alerte=None):
        """La période signalée était normale : le modèle doit l'apprendre."""
        return self.ajouter(FAUSSE_ALERTE, equipement,
                            _en_secondes(debut) - MARGE_AVANT_S,
                            _en_secondes(fin) + MARGE_APRES_S, motif, par, alerte)

    def ajouter_manque(self, equipement, debut, fin, motif, par):
        """Un échauffement réel que l'IA n'a pas signalé."""
        return self.ajouter(MANQUE, equipement, debut, fin, motif, par)

    def ajouter_confirme(self, equipement, debut, fin, motif, par, alerte=None):
        """L'alerte était juste : la période sert à mesurer la détection."""
        return self.ajouter(CONFIRME, equipement, debut, fin, motif, par, alerte)

    def marquer_pris_en_compte(self, identifiants=None):
        """Note que ces retours ont servi à un entraînement."""
        instant = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for fiche in self.retours:
            if identifiants is None or fiche["id"] in identifiants:
                fiche["pris_en_compte_le"] = instant
        self._ecrire()

    # ---------- lecture ----------
    def par_genre(self, genre):
        return [f for f in self.retours if f["genre"] == genre]

    def en_attente(self):
        """Retours qui n'ont pas encore servi à un entraînement."""
        return [f for f in self.retours if not f["pris_en_compte_le"]]

    def resume(self):
        return {
            "site": self.site,
            "total": len(self.retours),
            "fausses_alertes": len(self.par_genre(FAUSSE_ALERTE)),
            "manques": len(self.par_genre(MANQUE)),
            "confirmes": len(self.par_genre(CONFIRME)),
            "en_attente": len(self.en_attente()),
            "derniers": sorted(self.retours, key=lambda f: f["enregistre_le"],
                               reverse=True)[:10],
        }

    def periodes(self, genre, equipement=None):
        """Périodes (début, fin) d'un genre donné, pour filtrer un tableau de mesures."""
        return [(f["debut"], f["fin"]) for f in self.par_genre(genre)
                if equipement is None or f["equipement"] == equipement]


def appliquer_aux_mesures(tableau, registre):
    """Marque chaque mesure selon les retours reçus.

    Ajoute deux colonnes :
      - `retour` : fausse_alerte, manque, confirme, ou vide ;
      - `apprenable` : faux pour les périodes d'anomalie réelle (manque, confirmé),
        qui ne doivent jamais servir à apprendre ce qu'est un fonctionnement normal.

    Une fausse alerte, elle, reste apprenable : c'est même tout l'intérêt.
    """
    import pandas as pd

    resultat = tableau.copy()
    resultat["retour"] = ""
    # Conversion indépendante de la résolution : selon les versions, pandas
    # compte en nanosecondes ou en microsecondes, et diviser à l'aveugle donne
    # des dates de 1970.
    horodatages = pd.to_datetime(resultat["horodatage"], utc=True)
    secondes = (horodatages - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()

    for fiche in registre.retours:
        dans_la_periode = ((resultat["equipement"] == fiche["equipement"])
                           & (secondes >= fiche["debut"]) & (secondes <= fiche["fin"]))
        resultat.loc[dans_la_periode, "retour"] = fiche["genre"]

    resultat["apprenable"] = ~resultat["retour"].isin([MANQUE, CONFIRME])
    return resultat


def mesures_apprenables(tableau, registre):
    """Écarte du lot d'apprentissage les périodes d'anomalie réelle."""
    marque = appliquer_aux_mesures(tableau, registre)
    retirees = int((~marque["apprenable"]).sum())
    return marque[marque["apprenable"]].drop(columns=["retour", "apprenable"]), retirees
