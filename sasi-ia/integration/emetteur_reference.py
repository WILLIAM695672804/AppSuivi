"""Émetteur de référence : ce que le jumeau numérique doit publier, en 200 lignes.

Il ne remplace pas le jumeau — son comportement thermique est volontairement
rudimentaire. Il sert de point de comparaison : si le vérificateur accepte cet
émetteur et refuse le vôtre, la différence est dans la forme des messages, et
non dans le serveur de messages ni dans l'IA.

    ./venv/bin/python integration/emetteur_reference.py --duree-min 30
    ./venv/bin/python integration/emetteur_reference.py --facteur 60 --duree-min 1440
    ./venv/bin/python integration/emetteur_reference.py --panne Z1-ELV-01:derive_lente:8

Sans serveur de messages, « --sortie fichier.jsonl » écrit les messages ligne à
ligne : le vérificateur les relit ensuite avec --fichier.
"""

import argparse
import json
import math
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from integration import contrat, referentiel as module_referentiel   # noqa: E402

DEBUT_PAR_DEFAUT = datetime(2026, 9, 19, 6, 0, 0, tzinfo=timezone.utc)
AMBIANCE_BASE = 28.0            # Douala
AMBIANCE_AMPLITUDE = 4.0
HEURE_LA_PLUS_CHAUDE = 15


def iso(instant):
    """Horodatage du contrat : heure universelle, à la seconde."""
    return instant.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ambiance(instant, zone):
    """Température ambiante d'une zone : cycle journalier, plus un décalage."""
    heure = instant.hour + instant.minute / 60
    base = AMBIANCE_BASE + AMBIANCE_AMPLITUDE * math.cos(
        (heure - HEURE_LA_PLUS_CHAUDE) * math.pi / 12)
    if zone == 3:                     # cave de fermentation : maintenue au froid
        return round(14.0 + 1.5 * math.cos((heure - 15) * math.pi / 12), 1)
    if zone == 4:                     # chaufferie : plus chaude que le reste
        return round(base + 7.0, 1)
    return round(base, 1)


class Equipement:
    """Comportement thermique minimal : chauffe en marche, refroidit à l'arrêt."""

    def __init__(self, fiche, alea):
        self.id = fiche["id"]
        self.zone = fiche["zone"]
        self.camera = fiche["camera"]
        basse, haute = fiche["t_normale_indicative"]
        self.repos, self.plateau = float(basse), float(haute)
        # Constante de temps : un équipement lourd met plus longtemps à monter.
        self.inertie_s = max(float(fiche.get("temps_montee_min") or 20), 5) * 60
        self.alea = alea
        self.temperature = self.repos
        self.supplement = 0.0          # surchauffe due à une panne en cours

    def avancer(self, instant, pas_s, en_marche, charge_pct):
        cible = ambiance(instant, self.zone)
        if en_marche:
            cible = self.repos + (self.plateau - self.repos) * (charge_pct / 100)
        cible += self.supplement
        # Approche exponentielle de la cible : T += (cible - T) * pas / inertie
        self.temperature += (cible - self.temperature) * min(pas_s / self.inertie_s, 1)
        self.temperature += self.alea.gauss(0, 0.15)
        return round(self.temperature, 1)

    def mesure(self, t_max):
        """Les trois températures d'une zone d'image, du plus froid au plus chaud."""
        etendue = max(2.0, (t_max - ambiance(DEBUT_PAR_DEFAUT, self.zone)) * 0.25)
        return {"equipement": self.id, "t_max": t_max,
                "t_moy": round(t_max - etendue * 0.4, 1),
                "t_min": round(t_max - etendue, 1)}


class Panne:
    """Surchauffe ajoutée à un équipement, avec son journal."""

    def __init__(self, identifiant, equipement, type_panne, intensite, debut_s, duree_s):
        self.id = identifiant
        self.equipement = equipement
        self.type = type_panne
        self.intensite = float(intensite)
        self.debut_s = debut_s
        self.fin_s = debut_s + duree_s
        self.ouverte = False

    def supplement(self, ecoule_s):
        """Part de l'intensité atteinte à cet instant."""
        if not self.debut_s <= ecoule_s <= self.fin_s:
            return 0.0
        if self.type in ("montee_brutale", "chauffe_a_vide"):
            return self.intensite
        avance = (ecoule_s - self.debut_s) / max(self.fin_s - self.debut_s, 1)
        return self.intensite * avance          # dérive : montée progressive


class Emetteur:
    def __init__(self, fiche_referentiel, publier, graine=20260919):
        self.site = fiche_referentiel["site"]
        self.alea = random.Random(graine)
        self.publier = publier
        self.equipements = {e["id"]: Equipement(e, self.alea)
                            for e in fiche_referentiel["equipements"]}
        self.par_camera = {}
        for equipement in self.equipements.values():
            self.par_camera.setdefault(equipement.camera, []).append(equipement)
        self.zones = sorted({e.zone for e in self.equipements.values()})
        self.pannes = []
        self.sujets = contrat.sujets(self.site)

    def ajouter_panne(self, specification, debut_s, duree_s):
        """« Z1-ELV-01:derive_lente:8 » — équipement, signature, intensité en °C."""
        morceaux = specification.split(":")
        identifiant = morceaux[0]
        if identifiant not in self.equipements:
            raise SystemExit(f"Équipement inconnu : {identifiant}")
        type_panne = morceaux[1] if len(morceaux) > 1 else "derive_lente"
        intensite = float(morceaux[2]) if len(morceaux) > 2 else 8.0
        self.pannes.append(Panne(f"P-{len(self.pannes) + 1:04d}", identifiant,
                                 type_panne, intensite, debut_s, duree_s))
        return self.pannes[-1]

    def en_marche(self, instant):
        """Planning sommaire : production de 6 h à 22 h, sauf le dimanche."""
        if instant.weekday() == 6:
            return False, 0
        if 6 <= instant.hour < 22:
            return True, 80
        return False, 0

    # ---------- les quatre messages du contrat ----------
    def annoncer_horloge(self, mode, facteur, debut):
        self.publier(self.sujets["entrants"]["horloge"], {
            "site": self.site, "mode": mode, "facteur": facteur,
            "scenario": "emetteur-de-reference", "debut_scenario": iso(debut)})

    def emettre_mesures(self, instant, ecoule_s):
        en_marche, charge = self.en_marche(instant)
        for equipement in self.equipements.values():
            equipement.supplement = sum(
                panne.supplement(ecoule_s) for panne in self.pannes
                if panne.equipement == equipement.id)
        for camera, liste in sorted(self.par_camera.items()):
            zones = [e.mesure(e.avancer(instant, contrat.PAS_MESURES_S, en_marche, charge))
                     for e in liste]
            self.publier(f"sasi/{self.site}/{camera}/mesures", {
                "site": self.site, "camera": camera, "horodatage": iso(instant),
                "source": "jumeau", "zones": zones})

    def emettre_contexte(self, instant):
        en_marche, charge = self.en_marche(instant)
        self.publier(self.sujets["entrants"]["contexte"], {
            "site": self.site, "horodatage": iso(instant),
            "equipements": [{"equipement": identifiant,
                             "etat": "marche" if en_marche else "arret",
                             "charge_pct": charge if en_marche else 0}
                            for identifiant in sorted(self.equipements)],
            "ambiance": [{"zone": zone, "t_ambiante": ambiance(instant, zone),
                          "humidite_pct": round(self.alea.uniform(70, 90))}
                         for zone in self.zones]})

    def emettre_pannes(self, instant, ecoule_s):
        """Un message au début, un à la fin : le contrôle automatique s'en sert."""
        for panne in self.pannes:
            if not panne.ouverte and ecoule_s >= panne.debut_s:
                panne.ouverte = True
                self._journal(panne, "debut", instant)
            elif panne.ouverte and ecoule_s >= panne.fin_s:
                panne.ouverte = False
                panne.fin_s = float("inf")          # un seul message de fin
                self._journal(panne, "fin", instant)

    def _journal(self, panne, evenement, instant):
        self.publier(self.sujets["entrants"]["pannes"], {
            "site": self.site, "id_panne": panne.id, "equipement": panne.equipement,
            "type": panne.type, "evenement": evenement, "horodatage": iso(instant),
            "intensite": panne.intensite,
            "description": f"{panne.type} de {panne.intensite:.1f} °C "
                           f"sur {panne.equipement}"})

    # ---------- boucle ----------
    def tourner(self, debut, duree_min, facteur=1.0, pas_s=None):
        pas_s = pas_s or contrat.PAS_MESURES_S
        mode = "reel" if facteur == 1 else "accelere"
        self.annoncer_horloge(mode, facteur, debut)

        instant, ecoule_s, dernier_contexte = debut, 0.0, -contrat.PAS_CONTEXTE_S
        fin_s = duree_min * 60
        while ecoule_s <= fin_s:
            if ecoule_s - dernier_contexte >= contrat.PAS_CONTEXTE_S:
                self.emettre_contexte(instant)
                dernier_contexte = ecoule_s
            self.emettre_pannes(instant, ecoule_s)
            self.emettre_mesures(instant, ecoule_s)
            ecoule_s += pas_s
            instant = debut + timedelta(seconds=ecoule_s)
            attente = pas_s / facteur
            if attente > 0.001:
                time.sleep(attente)
        return ecoule_s


def principal():
    analyseur = argparse.ArgumentParser(
        description="Émetteur de référence : publie un flux conforme au contrat SASI")
    analyseur.add_argument("--mqtt", default="localhost")
    analyseur.add_argument("--port", type=int, default=1883)
    analyseur.add_argument("--referentiel", default=None)
    analyseur.add_argument("--duree-min", type=float, default=10.0,
                           dest="duree_min", help="durée simulée, en minutes")
    analyseur.add_argument("--facteur", type=float, default=1.0,
                           help="accélération : 60 = une heure en une minute")
    analyseur.add_argument("--panne", action="append", default=[],
                           metavar="EQUIP:type:intensite")
    analyseur.add_argument("--panne-dans", type=float, default=2.0, dest="panne_dans",
                           help="minutes avant le début de la panne (défaut : 2)")
    analyseur.add_argument("--panne-duree", type=float, default=30.0,
                           dest="panne_duree", help="durée de la panne, en minutes")
    analyseur.add_argument("--sortie", default=None,
                           help="écrire dans un fichier .jsonl au lieu de publier")
    arguments = analyseur.parse_args()

    fiche = module_referentiel.charger(arguments.referentiel)
    compteur = {"messages": 0}

    if arguments.sortie:
        fichier = open(arguments.sortie, "w", encoding="utf-8")

        def publier(sujet, charge):
            fichier.write(json.dumps({"sujet": sujet, "charge": charge},
                                     ensure_ascii=False) + "\n")
            compteur["messages"] += 1
        client = None
    else:
        import messagerie
        client = messagerie.client("sasi-emetteur")
        messagerie.connecter(client, arguments.mqtt, arguments.port)
        client.loop_start()

        def publier(sujet, charge):
            client.publish(sujet, json.dumps(charge, ensure_ascii=False), qos=1)
            compteur["messages"] += 1
        fichier = None

    emetteur = Emetteur(fiche, publier)
    for specification in arguments.panne:
        panne = emetteur.ajouter_panne(specification, arguments.panne_dans * 60,
                                       arguments.panne_duree * 60)
        print(f"  panne {panne.id} : {panne.type} de {panne.intensite:.1f} °C "
              f"sur {panne.equipement}, à {arguments.panne_dans:.0f} min")

    print(f"  site {fiche['site']} — {len(emetteur.equipements)} équipements, "
          f"{len(emetteur.par_camera)} caméras")
    print(f"  {arguments.duree_min:.0f} min simulées, facteur {arguments.facteur:g}, "
          f"un message par caméra toutes les {contrat.PAS_MESURES_S} s")
    try:
        emetteur.tourner(DEBUT_PAR_DEFAUT, arguments.duree_min, arguments.facteur)
    except KeyboardInterrupt:
        print("\n  interrompu")
    finally:
        if client is not None:
            client.loop_stop()
            client.disconnect()
        if fichier is not None:
            fichier.close()
            print(f"  → {arguments.sortie}")
    print(f"  {compteur['messages']} messages publiés")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
