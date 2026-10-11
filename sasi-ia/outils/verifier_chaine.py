"""Contrôle de la chaîne complète, dans un seul programme.

    python3 outils/verifier_chaine.py

Il fait circuler des mesures depuis l'entrée jusqu'aux écrans, sans rien
installer : ni serveur de messages, ni base de données, ni bibliothèque.
Le serveur de messages est remplacé par un aiguilleur en mémoire (« Courtier »)
qui distribue les messages exactement comme Mosquitto le ferait.

Trajet vérifié :

    jumeau numérique  →  connecteur  →  service IA  →  service des alertes
                                                    →  registre du serveur
                                                    →  écrans (temps réel)
    écrans  →  commande (acquitter / assigner / clôturer)  →  service des alertes

Ce n'est pas un essai de performance : c'est la preuve que les six éléments se
parlent et que l'état revient bien jusqu'à l'écran.
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alertes.service import ServiceAlertes
from api.registre import Registre
from connecteur.main import Connecteur
from ia.service import ServiceIA
from ia.site import Site

EQUIPEMENT = "Z1-ELV-01"
CHARGE = 60.0
PAS_S = 30
PAS_NORMAUX = 80            # 40 min de marche normale
PAS_DERIVE = 80             # puis échauffement progressif
DERIVE_PAR_PAS = 0.10       # °C


# ---------------------------------------------------------------- aiguilleur
class Courtier:
    """Serveur de messages en mémoire : publier ici, c'est appeler là."""

    def __init__(self):
        self.abonnements = []      # (sujet, fonction)
        self.journal = []          # (sujet, fiche) — pour les vérifications

    def abonner(self, sujet, fonction):
        self.abonnements.append((sujet, fonction))

    def publier(self, sujet, message):
        fiche = json.loads(message) if isinstance(message, (str, bytes)) else message
        self.journal.append((sujet, fiche))
        for motif, fonction in self.abonnements:
            if sujet == motif:
                fonction(sujet, fiche)

    def messages(self, sujet):
        return [fiche for s, fiche in self.journal if s == sujet]


# ---------------------------------------------------------------- modèle d'essai
class ModeleDePlage:
    """Modèle minimal : la température attendue se déduit de la fiche équipement.

    Il remplace LightGBM le temps de cette vérification : ce que l'on contrôle
    ici, c'est la circulation des messages, pas la qualité de la prédiction.
    """

    def predire(self, entrees):
        basse, haute = entrees["plage_basse"], entrees["plage_haute"]
        if not entrees["etat_marche"]:
            return basse
        part = 0.1 + 0.8 * entrees["charge_pct"] / 100.0
        return basse + (haute - basse) * part * entrees["fraction_chauffe"]


def _iso(secondes):
    """Horodatage au format du jumeau numérique : 2026-09-19T14:30:10Z."""
    return datetime.fromtimestamp(secondes, tz=timezone.utc).isoformat().replace("+00:00", "Z")


# ---------------------------------------------------------------- montage
def monter(site):
    """Relie les six éléments par l'aiguilleur, comme le ferait Mosquitto."""
    courtier = Courtier()
    identifiant = site.identifiant

    connecteur = Connecteur(site, publier=courtier.publier)
    ia = ServiceIA(site, modeles={f: ModeleDePlage() for f in site.familles},
                   publier=courtier.publier)
    alertes = ServiceAlertes(site, publier=courtier.publier)
    registre = Registre(site)

    ecrans = []                 # ce que les navigateurs auraient reçu

    def vers_ia(sujet, fiche):
        for mesure in fiche.get("mesures", []):
            ia.traiter(mesure)

    courtier.abonner(f"sasi/{identifiant}/interne/mesures_validees", vers_ia)
    courtier.abonner(f"sasi/{identifiant}/interne/niveaux",
                     lambda sujet, fiche: alertes.traiter_niveau(fiche))
    courtier.abonner(f"sasi/{identifiant}/commandes",
                     lambda sujet, fiche: alertes.traiter_commande(fiche))
    for sujet in (f"sasi/{identifiant}/alertes", f"sasi/{identifiant}/niveaux",
                  f"sasi/{identifiant}/interne/alertes_techniques",
                  f"sasi/{identifiant}/interne/jugements"):
        courtier.abonner(sujet, lambda s, f: ecrans.append(registre.appliquer(s, f)))

    return courtier, connecteur, ia, alertes, registre, ecrans


def jouer(courtier, connecteur, ia, site, debut):
    """Envoie une marche normale puis un échauffement, mesure par mesure."""
    camera = site.camera(EQUIPEMENT)
    zone = site.zone(EQUIPEMENT)

    fiche_contexte = {
        "horodatage": _iso(debut),
        "equipements": [{"equipement": EQUIPEMENT, "etat": "marche", "charge_pct": CHARGE}],
        "ambiance": [{"zone": zone, "t_ambiante": 30.0}],
    }
    connecteur.traiter_contexte(json.dumps(fiche_contexte))
    ia.majorer_contexte(fiche_contexte)

    basse, haute = site.plage(EQUIPEMENT)
    attendue = basse + (haute - basse) * (0.1 + 0.8 * CHARGE / 100.0)
    supplement = 0.0

    for pas in range(PAS_NORMAUX + PAS_DERIVE):
        secondes = debut + pas * PAS_S
        if pas >= PAS_NORMAUX:
            supplement += DERIVE_PAR_PAS
        oscillation = 0.15 * ((pas % 4) - 1.5)          # bruit reproductible
        mesure = {"camera": camera, "horodatage": _iso(secondes),
                  "zones": [{"equipement": EQUIPEMENT,
                             "t_max": round(attendue + oscillation + supplement, 2)}]}
        connecteur.traiter_message(f"sasi/{site.identifiant}/{camera}/mesures",
                                   json.dumps(mesure), maintenant=secondes)
    return debut + (PAS_NORMAUX + PAS_DERIVE) * PAS_S


# ---------------------------------------------------------------- vérifications
def principal():
    site = Site.charger("brasserie")
    debut = time.time() - 3600
    courtier, connecteur, ia, alertes, registre, ecrans = monter(site)
    fin = jouer(courtier, connecteur, ia, site, debut)

    controles = []

    def verifier(intitule, condition, detail=""):
        controles.append((intitule, bool(condition), detail))

    identifiant = site.identifiant
    validees = courtier.messages(f"sasi/{identifiant}/interne/mesures_validees")
    niveaux_ia = courtier.messages(f"sasi/{identifiant}/interne/niveaux")
    publiees = courtier.messages(f"sasi/{identifiant}/alertes")

    verifier("le connecteur valide et republie les mesures",
             len(validees) == PAS_NORMAUX + PAS_DERIVE,
             f"{len(validees)} lot(s) de mesures")
    verifier("aucune mesure écartée à tort", connecteur.compteurs["ecartees"] == 0,
             f"{connecteur.compteurs['ecartees']} écartée(s)")
    verifier("l'IA signale au moins un changement de niveau", niveaux_ia,
             " → ".join(m["niveau"] for m in niveaux_ia))
    verifier("l'IA atteint au moins le niveau inspection",
             any(m["niveau"] in ("inspection", "urgence") for m in niveaux_ia))
    verifier("l'IA joint une explication en clair",
             all(m.get("raison") and m.get("action") for m in niveaux_ia))
    verifier("le service des alertes ouvre une alerte",
             EQUIPEMENT in alertes.moteur.ouvertes or publiees,
             f"{len(publiees)} publication(s)")

    alerte = alertes.moteur.ouvertes.get(EQUIPEMENT)
    verifier("l'alerte porte sur le bon équipement",
             alerte is not None and alerte.equipement == EQUIPEMENT)
    verifier("le registre du serveur connaît l'alerte", registre.liste_alertes(),
             f"{len(registre.alertes)} alerte(s)")
    verifier("le niveau remonte jusqu'aux écrans",
             registre.niveaux.get(EQUIPEMENT) not in (None, "normal"),
             f"niveau affiché : {registre.niveaux.get(EQUIPEMENT)}")
    serie = registre.serie(EQUIPEMENT, heures=24)
    verifier("le serveur garde les mesures pour les courbes",
             len(serie) == PAS_NORMAUX + PAS_DERIVE, f"{len(serie)} point(s)")
    verifier("chaque point porte la mesure et la température attendue",
             all(p.get("t_max") is not None and p.get("t_attendue") is not None
                 for p in serie))
    verifier("les jugements n'encombrent pas les écrans",
             all(m is None or m["type"] != "jugement" for m in ecrans))

    verifier("les écrans reçoivent des messages en direct",
             any(m and m["type"] == "alerte" for m in ecrans),
             f"{len([m for m in ecrans if m])} message(s)")

    # ----- actions venues de l'application
    sujet_commandes = f"sasi/{identifiant}/commandes"
    courtier.publier(sujet_commandes,
                     registre.commande("acquitter", EQUIPEMENT, par="agent.essai",
                                       secondes=fin))
    verifier("l'acquittement remonte jusqu'au registre",
             any(a.get("etat") == "acquittee" for a in registre.liste_alertes()),
             f"état : {registre.liste_alertes()[0].get('etat')}")

    courtier.publier(sujet_commandes,
                     registre.commande("assigner", EQUIPEMENT, par="agent.essai",
                                       a_qui="technicien.essai", secondes=fin + 60))
    verifier("l'assignation remonte jusqu'au registre",
             any(a.get("assignee_a") == "technicien.essai" for a in registre.liste_alertes()))

    avant = len(courtier.messages(f"sasi/{identifiant}/alertes"))
    courtier.publier(sujet_commandes,
                     registre.commande("cloturer", EQUIPEMENT, par="agent.essai",
                                       constat="", justifiee=True, secondes=fin + 120))
    refus = [m for m in courtier.messages(f"sasi/{identifiant}/alertes")[avant:]
             if m.get("erreur")]
    verifier("une clôture sans compte rendu est refusée", refus,
             refus[0]["erreur"] if refus else "acceptée à tort")

    courtier.publier(sujet_commandes,
                     registre.commande("cloturer", EQUIPEMENT, par="agent.essai",
                                       constat="Essai de chaîne : roulement vérifié.",
                                       justifiee=True, secondes=fin + 180))
    verifier("la clôture ferme l'alerte partout",
             EQUIPEMENT not in alertes.moteur.ouvertes
             and any(a.get("etat") == "cloturee" for a in registre.liste_alertes()))
    verifier("la clôture est visible à l'écran",
             any(m and m["type"] == "alerte" and m["alerte"].get("etat") == "cloturee"
                 for m in ecrans))

    # ----- mise en maintenance
    courtier.publier(sujet_commandes,
                     registre.commande("maintenance", EQUIPEMENT, en_maintenance=True,
                                       secondes=fin + 240))
    verifier("la mise en maintenance est prise en compte",
             EQUIPEMENT in alertes.moteur.en_maintenance)

    # ----- mesure aberrante
    aberrante = {"camera": site.camera(EQUIPEMENT), "horodatage": _iso(fin + 300),
                 "zones": [{"equipement": EQUIPEMENT, "t_max": 5000}]}
    ecartees_avant = connecteur.compteurs["ecartees"]
    connecteur.traiter_message(f"sasi/{identifiant}/mesures", json.dumps(aberrante),
                               maintenant=fin + 300)
    verifier("une température impossible est écartée",
             connecteur.compteurs["ecartees"] == ecartees_avant + 1)
    verifier("l'écart est signalé aux écrans comme alerte technique",
             registre.techniques, f"{len(registre.techniques)} alerte(s) technique(s)")

    # ----- bilan
    print("=== Contrôle de la chaîne complète ===\n")
    for intitule, reussi, detail in controles:
        marque = "OK   " if reussi else "ECHEC"
        print(f"  {marque} {intitule}" + (f"  ({detail})" if detail else ""))
    echecs = sum(1 for _, reussi, _ in controles if not reussi)
    print(f"\n{len(controles)} contrôle(s), {echecs} échec(s)")
    if not echecs:
        print("\nLes six éléments se parlent : connecteur, IA, alertes, registre, "
              "écrans, commandes.")
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(principal())
