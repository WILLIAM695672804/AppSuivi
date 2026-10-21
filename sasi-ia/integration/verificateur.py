"""Vérifie qu'un émetteur respecte le contrat, et dit précisément ce qui cloche.

C'est l'outil que l'équipe du jumeau exécute contre son propre jumeau, sans avoir
besoin de l'IA, de la base ni de l'application : seuls le serveur de messages et
le jumeau tournent.

    ./venv/bin/python integration/verificateur.py --duree 120
    ./venv/bin/python integration/verificateur.py --mqtt 192.168.1.20 --site SIM01
    ./venv/bin/python integration/verificateur.py --referentiel integration/referentiel_SIM01.json

Hors ligne, sur un message enregistré dans un fichier :

    ./venv/bin/python integration/verificateur.py --fichier message.json \
        --sujet sasi/SIM01/CAM-Z1/mesures

Code de sortie : 0 si aucun défaut, 1 s'il en reste un seul. Utilisable tel quel
dans une chaîne d'intégration continue.
"""

import argparse
import collections
import json
import statistics
import sys
import time
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))

from integration import contrat, referentiel as module_referentiel   # noqa: E402

LARGEUR = 74


class Verificateur:
    """Accumule les messages reçus et en tire un rapport."""

    def __init__(self, site, referentiel=None):
        self.site = site
        self.referentiel = referentiel or {}
        self.messages = collections.Counter()          # nature -> nombre
        self.defauts = collections.Counter()           # code -> nombre
        self.avertissements = collections.Counter()
        self.exemples = {}                             # code -> (sujet, détail)
        self.arrivees = collections.defaultdict(list)  # caméra -> horodatages reçus
        self.equipements_vus = set()
        self.cameras_vues = set()
        self.types_de_panne = collections.Counter()
        self.horloge = None
        self.illisibles = 0

    def examiner(self, sujet, charge_utile):
        """Examine un message. Renvoie le rapport du contrat."""
        nature = contrat.genre(sujet)
        rapport = contrat.verifier(sujet, charge_utile, self.referentiel)
        self.messages[nature or "sujet_inconnu"] += 1

        for ligne in rapport.defauts:
            code = ligne.split(" : ")[0]
            self.defauts[code] += 1
            self.exemples.setdefault(code, (sujet, ligne))
        for ligne in rapport.avertissements:
            code = ligne.split(" : ")[0]
            self.avertissements[code] += 1
            self.exemples.setdefault(code, (sujet, ligne))

        try:
            fiche = json.loads(charge_utile) if isinstance(charge_utile, (str, bytes)) \
                else charge_utile
        except (ValueError, TypeError):
            self.illisibles += 1
            return rapport
        if not isinstance(fiche, dict):
            return rapport

        if nature == "mesures":
            camera = fiche.get("camera") or sujet.split("/")[2]
            self.cameras_vues.add(camera)
            horodatage = fiche.get("horodatage")
            if horodatage is not None:
                secondes = _en_secondes(horodatage)
                if secondes is not None:
                    self.arrivees[camera].append(secondes)
            for zone in fiche.get("zones") or []:
                if isinstance(zone, dict) and zone.get("equipement"):
                    self.equipements_vus.add(zone["equipement"])
        elif nature == "contexte":
            horodatage = fiche.get("horodatage")
            if horodatage is not None:
                secondes = _en_secondes(horodatage)
                if secondes is not None:
                    self.arrivees["(contexte)"].append(secondes)
        elif nature == "pannes":
            self.types_de_panne[fiche.get("type")] += 1
        elif nature == "horloge":
            self.horloge = fiche
        return rapport

    # ---------- cadence ----------
    def cadences(self):
        """Pour chaque émetteur : nombre, pas médian, plus grand trou."""
        resultat = {}
        for nom, instants in sorted(self.arrivees.items()):
            instants = sorted(instants)
            if len(instants) < 2:
                resultat[nom] = {"nombre": len(instants), "pas": None, "trou": None}
                continue
            ecarts = [b - a for a, b in zip(instants, instants[1:])]
            resultat[nom] = {"nombre": len(instants),
                             "pas": statistics.median(ecarts),
                             "trou": max(ecarts)}
        return resultat

    def manquants(self):
        """Équipements et caméras du référentiel dont rien n'est arrivé."""
        attendus, cameras, _ = contrat._connus(self.referentiel)
        return (sorted(attendus - self.equipements_vus) if attendus else [],
                sorted(cameras - self.cameras_vues) if cameras else [])

    # ---------- rapport ----------
    def rapport(self):
        lignes = ["", "─" * LARGEUR,
                  f" Vérification du contrat SASI {contrat.VERSION} — site {self.site}",
                  "─" * LARGEUR]
        total = sum(self.messages.values())
        if not total:
            lignes += ["", "  Aucun message reçu.", "",
                       "  À vérifier : le serveur de messages est-il joignable, "
                       "l'émetteur",
                       "  publie-t-il bien sous « sasi/%s/… » ?" % self.site, ""]
            return "\n".join(lignes)

        lignes.append("")
        lignes.append(f"  {total} message{_s(total)} reçu{_s(total)}")
        for nature, nombre in sorted(self.messages.items()):
            lignes.append(f"    {nature:16s} {nombre:6d}")

        cadences = self.cadences()
        if cadences:
            lignes += ["", "  Cadence (en temps des messages)",
                       f"    {'émetteur':14s} {'messages':>9s} {'pas médian':>12s}"
                       f" {'plus grand trou':>17s}"]
            for nom, chiffres in cadences.items():
                pas = "—" if chiffres["pas"] is None else f"{chiffres['pas']:.1f} s"
                trou = "—" if chiffres["trou"] is None else f"{chiffres['trou']:.1f} s"
                attendu = contrat.PAS_CONTEXTE_S if nom == "(contexte)" \
                    else contrat.PAS_MESURES_S
                marque = " "
                if chiffres["trou"] is not None and chiffres["trou"] > attendu * 3:
                    marque = "!"
                lignes.append(f"  {marque} {nom:14s} {chiffres['nombre']:9d} "
                              f"{pas:>12s} {trou:>17s}")
            lignes.append(f"    attendu : {contrat.PAS_MESURES_S} s par caméra, "
                          f"{contrat.PAS_CONTEXTE_S} s pour le contexte")

        equipements, cameras = self.manquants()
        if equipements or cameras:
            lignes += ["", "  Rien reçu de :"]
            if cameras:
                lignes.append(f"    caméras     {', '.join(cameras)}")
            if equipements:
                lignes.append(f"    équipements {', '.join(equipements)}")

        if self.types_de_panne:
            lignes += ["", "  Journal des pannes"]
            for type_panne, nombre in sorted(self.types_de_panne.items(),
                                             key=lambda t: -t[1]):
                lignes.append(f"    {str(type_panne):24s} {nombre:4d} message(s)")
        if self.horloge:
            lignes += ["", f"  Horloge : mode {self.horloge.get('mode')}, "
                           f"facteur {self.horloge.get('facteur')}"]

        if self.defauts:
            nombre_defauts = sum(self.defauts.values())
            lignes += ["", f"  {nombre_defauts} défaut{_s(nombre_defauts)}, "
                           f"{len(self.defauts)} sorte{_s(len(self.defauts))}"]
            for code, nombre in self.defauts.most_common():
                sujet, detail = self.exemples[code]
                lignes.append(f"    ✗ {code} — {nombre} fois")
                lignes.append(f"        {detail}")
                lignes.append(f"        sur {sujet}")
        if self.avertissements:
            nombre_avertissements = sum(self.avertissements.values())
            lignes += ["", f"  {nombre_avertissements} "
                           f"avertissement{_s(nombre_avertissements)}"]
            for code, nombre in self.avertissements.most_common():
                sujet, detail = self.exemples[code]
                lignes.append(f"    · {code} — {nombre} fois : {detail}")

        lignes += ["", "─" * LARGEUR]
        if self.defauts:
            lignes.append("  CONTRAT NON RESPECTÉ — voir les défauts ci-dessus.")
        elif self.avertissements:
            lignes.append("  Contrat respecté, avec des réserves sans gravité.")
        else:
            lignes.append("  Contrat respecté.")
        lignes += ["─" * LARGEUR, ""]
        return "\n".join(lignes)


def _s(nombre):
    """Marque du pluriel, pour que le rapport se lise correctement."""
    return "s" if nombre > 1 else ""


def _en_secondes(horodatage):
    try:
        if isinstance(horodatage, (int, float)) and not isinstance(horodatage, bool):
            return float(horodatage)
        from datetime import datetime
        return datetime.fromisoformat(str(horodatage).replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError):
        return None


def ecouter(verificateur, adresse, duree, port=1883):
    """Écoute le serveur de messages pendant « duree » secondes."""
    import messagerie

    client = messagerie.client("sasi-verificateur")
    sujet = f"sasi/{verificateur.site}/#"

    def a_la_connexion(client, donnees, drapeaux, code, proprietes=None):
        client.subscribe(sujet, qos=1)
        print(f"  abonné à « {sujet} » sur {adresse}:{port}")

    def a_la_reception(client, donnees, message):
        verificateur.examiner(message.topic, message.payload)

    client.on_connect = a_la_connexion
    client.on_message = a_la_reception
    messagerie.connecter(client, adresse, port)
    client.loop_start()
    fin = time.time() + duree
    try:
        while time.time() < fin:
            time.sleep(0.5)
            reste = int(fin - time.time())
            print(f"\r  écoute… {reste:4d} s restantes, "
                  f"{sum(verificateur.messages.values())} messages", end="", flush=True)
    except KeyboardInterrupt:
        print("\n  interrompu")
    finally:
        client.loop_stop()
        client.disconnect()
    print()


def depuis_fichier(verificateur, chemin, sujet=None):
    """Vérifie un message enregistré, ou un fichier de lignes {sujet, charge}."""
    texte = Path(chemin).read_text(encoding="utf-8")
    if sujet:
        verificateur.examiner(sujet, texte)
        return
    for ligne in texte.splitlines():
        if not ligne.strip():
            continue
        fiche = json.loads(ligne)
        verificateur.examiner(fiche["sujet"], json.dumps(fiche["charge"]))


def principal():
    analyseur = argparse.ArgumentParser(
        description="Vérifie la conformité d'un émetteur au contrat SASI")
    analyseur.add_argument("--site", default="SIM01", help="identifiant du site (SIM01…)")
    analyseur.add_argument("--mqtt", default="localhost")
    analyseur.add_argument("--port", type=int, default=1883)
    analyseur.add_argument("--duree", type=float, default=60.0,
                           help="durée d'écoute en secondes (défaut : 60)")
    analyseur.add_argument("--referentiel", default=None,
                           help="adresse HTTP ou fichier ; par défaut l'application")
    analyseur.add_argument("--fichier", default=None,
                           help="vérifier un fichier au lieu d'écouter le réseau")
    analyseur.add_argument("--sujet", default=None,
                           help="sujet du message, avec --fichier")
    arguments = analyseur.parse_args()

    try:
        fiche = module_referentiel.charger(arguments.referentiel)
        print(f"  référentiel : {len(fiche['equipements'])} équipements "
              f"(version {fiche.get('version')})")
    except Exception as souci:
        fiche = {}
        print(f"  référentiel indisponible ({souci}) : seule la forme sera vérifiée")

    site = fiche.get("site") or arguments.site
    verificateur = Verificateur(site, fiche)

    if arguments.fichier:
        depuis_fichier(verificateur, arguments.fichier, arguments.sujet)
    else:
        ecouter(verificateur, arguments.mqtt, arguments.duree, arguments.port)

    print(verificateur.rapport())
    return 1 if verificateur.defauts else 0


if __name__ == "__main__":
    sys.exit(principal())
