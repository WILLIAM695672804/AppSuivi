"""Travaux longs lancés depuis l'application : entraînement, évaluation.

Un entraînement dure plusieurs minutes. Le service de l'application ne peut pas
attendre : il lance donc un **travail** dans un fil d'exécution séparé, rend
aussitôt la main, et l'interface interroge son avancement.

    travail = lancer_entrainement("brasserie", par="Awa N.")
    etat = lire(travail.identifiant)     # {etape, progression, journal, resultat}

Un seul entraînement à la fois : deux modèles écrits en même temps se
mélangeraient. Une demande concurrente est refusée, pas mise en attente — la
personne préfère savoir tout de suite.
"""

import threading
import traceback
from datetime import datetime
from itertools import count

VERROU = threading.Lock()
TRAVAUX = {}                    # identifiant -> Travail
NUMERO = count(1)

# Étapes de l'entraînement, avec la part de l'avancement que chacune représente.
ETAPES = [
    ("lecture", "Lecture des mesures de fonctionnement normal", 12),
    ("entrainement", "Entraînement d'un modèle par famille", 40),
    ("calibrage", "Calibrage de chaque équipement", 8),
    ("enregistrement", "Enregistrement de la nouvelle version", 5),
    ("inspection", "Inspection du raisonnement", 10),
    ("evaluation", "Évaluation sur des données jamais vues", 25),
]

# Étapes d'une inspection seule, sans réentraînement.
ETAPES_INSPECTION = [
    ("lecture", "Lecture des mesures de fonctionnement normal", 40),
    ("inspection", "Inspection du raisonnement", 60),
]


class Travail:
    """Un entraînement en cours, avec son avancement et son résultat."""

    def __init__(self, identifiant, site, par, etapes=None, genre="entrainement"):
        self.identifiant = identifiant
        self.site = site
        self.par = par
        self.etapes = etapes or ETAPES
        self.genre = genre
        self.debut = datetime.now()
        self.fin = None
        self.etat = "en cours"          # en cours / termine / echec
        self.etape = self.etapes[0][0]
        self.progression = 0
        self.journal = []
        self.resultat = None
        self.erreur = None

    def avancer(self, etape, detail=None):
        """Passe à l'étape suivante et note ce qui vient d'être fait."""
        acquis = 0
        for clef, _, poids in self.etapes:
            if clef == etape:
                break
            acquis += poids
        self.etape = etape
        self.progression = acquis
        if detail:
            self.noter(detail)

    def noter(self, detail):
        self.journal.append({"instant": datetime.now().isoformat(timespec="seconds"),
                             "detail": detail})

    def resume(self):
        libelle = next((texte for clef, texte, _ in self.etapes if clef == self.etape),
                       self.etape)
        return {
            "id": self.identifiant, "site": self.site, "par": self.par,
            "genre": self.genre,
            "etat": self.etat, "etape": self.etape, "etape_libelle": libelle,
            "progression": self.progression,
            "debut": self.debut.isoformat(timespec="seconds"),
            "fin": self.fin.isoformat(timespec="seconds") if self.fin else None,
            "duree_s": int(((self.fin or datetime.now()) - self.debut).total_seconds()),
            "journal": self.journal,
            "resultat": self.resultat,
            "erreur": self.erreur,
        }


def en_cours():
    """Le travail en cours, s'il y en a un."""
    return next((t for t in TRAVAUX.values() if t.etat == "en cours"), None)


def lire(identifiant):
    travail = TRAVAUX.get(identifiant)
    return travail.resume() if travail else None


def liste(nombre=10):
    travaux = sorted(TRAVAUX.values(), key=lambda t: t.debut, reverse=True)
    return [t.resume() for t in travaux[:nombre]]


def lancer_entrainement(nom_site="brasserie", par="inconnu", lot_normal="A", lot_essai="B"):
    """Démarre un entraînement en arrière-plan. Renvoie le travail créé."""
    with VERROU:
        if en_cours() is not None:
            raise RuntimeError("Un entraînement est déjà en cours.")
        travail = Travail(f"T-{next(NUMERO):04d}", nom_site, par)
        TRAVAUX[travail.identifiant] = travail

    fil = threading.Thread(target=_executer, name=f"entrainement-{travail.identifiant}",
                           args=(travail, nom_site, lot_normal, lot_essai), daemon=True)
    fil.start()
    return travail


def _executer(travail, nom_site, lot_normal, lot_essai):
    """Déroulé de l'entraînement. Tourne dans son propre fil d'exécution."""
    try:
        from ia import chaine, evaluation, modeles_en_service, retours

        site = chaine.definir_site(nom_site)
        travail.avancer("lecture", site.nom)

        lot_a, controle = chaine.controler_lot(chaine.charger_lot(lot_normal, pas_secondes=60))
        lot_a = chaine.ajouter_entrees(lot_a)
        ecartees = controle["recues"] - controle["conservees"]

        # Ce que les équipes ont corrigé : les périodes signalées comme de vraies
        # anomalies sortent de l'apprentissage, les fausses alertes y restent
        # justement pour que le modèle cesse de s'en étonner.
        registre = retours.Registre(site)
        bilan = registre.resume()
        lot_a, retirees = retours.mesures_apprenables(lot_a, registre)
        mesures = len(lot_a)
        travail.noter(f"{mesures} mesures retenues, {ecartees} écartée(s) par les contrôles")
        if bilan["total"]:
            travail.noter(
                f"Retours du terrain : {bilan['fausses_alertes']} fausse(s) alerte(s) "
                f"réapprise(s) comme normales, {bilan['manques'] + bilan['confirmes']} "
                f"période(s) d'anomalie écartée(s) ({retirees} mesures)")
        periode = (f"{lot_a['horodatage'].min():%d/%m/%Y} au "
                   f"{lot_a['horodatage'].max():%d/%m/%Y}")

        travail.avancer("entrainement")
        modeles, erreurs = {}, {}
        familles = sorted({chaine.famille(e) for e in lot_a["equipement"].unique()})
        part = 45 / max(len(familles), 1)
        for rang, nom_famille in enumerate(familles, 1):
            partie = lot_a[lot_a["equipement"].map(chaine.famille) == nom_famille]
            modele, erreur = _entrainer_une_famille(partie)
            modeles[nom_famille] = modele
            erreurs[nom_famille] = erreur
            travail.progression = 15 + int(part * rang)
            travail.noter(f"Famille {nom_famille} : erreur moyenne {erreur:.2f} °C")

        travail.avancer("calibrage")
        calibrages = chaine.calibrer_par_equipement(lot_a, modeles)
        travail.noter(f"{len(calibrages)} équipements calibrés")

        travail.avancer("enregistrement")
        cible = modeles_en_service.enregistrer(
            site, modeles, calibrages, chaine.ENTREES, erreurs,
            en_service=False, periode=periode, mesures=mesures,
            retours=bilan["total"])
        version = cible.name
        travail.noter(f"Version {version} enregistrée (pas encore en service)")

        travail.avancer("evaluation")
        try:
            lot_b = chaine.ajouter_entrees(chaine.charger_lot(lot_essai, pas_secondes=10))
            episodes, depart, etats = chaine.detecter(lot_b, modeles, calibrages)
            resultat_evaluation = evaluation.evaluer_episodes(
                episodes, chaine.fenetres_journal(depart, lot_essai))
            travail.noter(
                f"{resultat_evaluation['pannes_detectees']}/{resultat_evaluation['pannes']} "
                f"pannes détectées, {resultat_evaluation['fausses_alertes']} fausses alertes")
            _completer_version(site, version, resultat_evaluation)
        except FileNotFoundError:
            travail.noter("Aucun lot d'essai : évaluation impossible, version conservée.")

        travail.progression = 100
        travail.etat = "termine"
        travail.fin = datetime.now()
        if bilan["en_attente"]:
            registre.marquer_pris_en_compte()
            travail.noter(f"{bilan['en_attente']} retour(s) désormais pris en compte")

        travail.resultat = {
            "version": version, "erreurs": erreurs, "periode": periode,
            "mesures": mesures, "evaluation": resultat_evaluation,
            "retours": bilan["total"], "en_service": False,
        }
        travail.noter("Terminé. La mise en service reste à votre main.")
    except Exception as souci:                    # un travail ne doit jamais tuer le serveur
        travail.etat = "echec"
        travail.fin = datetime.now()
        travail.erreur = f"{type(souci).__name__} : {souci}"
        travail.noter(travail.erreur)
        travail.noter(traceback.format_exc(limit=3))


def lancer_inspection(nom_site="brasserie", par="inconnu", lot_normal="A"):
    """Inspecte le modèle en service, sans le réentraîner."""
    with VERROU:
        if en_cours() is not None:
            raise RuntimeError("Un travail est déjà en cours.")
        travail = Travail(f"T-{next(NUMERO):04d}", nom_site, par,
                          etapes=ETAPES_INSPECTION, genre="inspection")
        TRAVAUX[travail.identifiant] = travail

    fil = threading.Thread(target=_inspecter, name=f"inspection-{travail.identifiant}",
                           args=(travail, nom_site, lot_normal), daemon=True)
    fil.start()
    return travail


def _inspecter(travail, nom_site, lot_normal):
    """Inspection du modèle déjà en service. Tourne dans son propre fil."""
    try:
        from ia import chaine, modeles_en_service
        from outils.inspecter import inspecter

        site = chaine.definir_site(nom_site)
        travail.avancer("lecture", site.nom)
        lot = chaine.ajouter_entrees(chaine.charger_lot(lot_normal, pas_secondes=60))
        travail.noter(f"{len(lot)} mesures relues")

        travail.avancer("inspection")
        modeles, _ = modeles_en_service.charger(site)
        examen = inspecter(site, modeles, lot)
        version = modeles_en_service.lire_versions(site)["en_service"]
        modeles_en_service.enregistrer_inspection(site, version, examen)

        bilan = examen["resume"]
        travail.noter(f"{bilan['conformes']} contrôles conformes, "
                      f"{bilan['a_lenvers']} à l'envers, "
                      f"{bilan['jamais_observes']} jamais observés")
        travail.progression = 100
        travail.etat = "termine"
        travail.fin = datetime.now()
        travail.resultat = {"version": version, "resume": bilan}
    except Exception as souci:
        travail.etat = "echec"
        travail.fin = datetime.now()
        travail.erreur = f"{type(souci).__name__} : {souci}"
        travail.noter(travail.erreur)
        travail.noter(traceback.format_exc(limit=3))


def _entrainer_une_famille(partie):
    """Entraîne une famille et mesure son erreur sur des dates jamais vues."""
    from ia import chaine, entrainement

    apprentissage, reglage, test = entrainement.decouper_par_date(
        partie.sort_values("horodatage"))
    modele = entrainement.entrainer(apprentissage, reglage, chaine.ENTREES, cible="t_max")
    erreur = entrainement.erreur_moyenne(modele, test, chaine.ENTREES, cible="t_max")
    return modele, float(erreur)


def _completer_version(site, version, resultat):
    """Ajoute le résultat de l'évaluation à la fiche de la version."""
    from ia import modeles_en_service

    registre = modeles_en_service.lire_versions(site)
    for fiche in registre["versions"]:
        if fiche["version"] == version:
            fiche["evaluation"] = {
                "pannes": resultat["pannes"],
                "pannes_detectees": resultat["pannes_detectees"],
                "taux_detection": resultat["taux_detection"],
                "fausses_alertes": resultat["fausses_alertes"],
                "part_fausses_alertes": resultat["part_fausses_alertes"],
                "delai_median_s": resultat["delai_median_s"],
            }
    modeles_en_service._ecrire_versions(site, registre)
