"""Contrat d'échange entre le jumeau numérique et SASI, sous forme exécutable.

Ce fichier est la référence : il décrit ce que le code accepte réellement, et non
ce qu'un document souhaiterait. Le vérificateur (`integration/verificateur.py`) et
les tests s'en servent tous les deux, de sorte qu'un écart entre le contrat et
l'implantation fasse échouer les tests.

Il n'utilise que la bibliothèque standard : l'équipe du jumeau peut le copier tel
quel, sans rien installer.

    from integration import contrat
    defauts = contrat.verifier("sasi/SIM01/CAM-Z1/mesures", charge_utile)
"""

import json
import math
import re

VERSION = "1.1"          # 1.0 = document « Conventions jumeau numérique », 19/09/2026

# --------------------------------------------------------------- vocabulaire
MOTIF_EQUIPEMENT = re.compile(r"^Z\d+-[A-Z]{3}-\d{2}(-[A-Z])?$")
MOTIF_CAMERA = re.compile(r"^CAM-Z\d+$")
MOTIF_HORODATAGE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")

ETATS_MARCHE = ("marche", "arret")
SOURCES = ("jumeau", "camera")
NIVEAUX = ("normal", "information", "surveillance", "inspection", "urgence")
ETATS_ALERTE = ("ouverte", "acquittee", "assignee", "cloturee")
EVENEMENTS_PANNE = ("debut", "fin")
MODES_HORLOGE = ("reel", "accelere")

# Signatures reconnues par le simulateur et par le contrôle automatique.
TYPES_PANNE = ("derive_lente", "montee_brutale", "point_chaud_phase",
               "chauffe_a_vide", "defaut_refroidissement", "friction_roulement",
               "colmatage_filtre", "surchauffe_bruleur", "rupture_calorifuge",
               "derive_froid")

# Bornes retenues par ia/controles.py : au-delà, la mesure est écartée.
TEMPERATURE_MINIMALE = -30.0
TEMPERATURE_MAXIMALE = 1000.0

PAS_MESURES_S = 10        # une mesure toutes les 10 s par caméra
PAS_CONTEXTE_S = 60       # contexte au moins toutes les 60 s


# ------------------------------------------------------------------- sujets
def sujets(site):
    """Sujets MQTT du site, dans les deux sens."""
    return {
        "entrants": {
            "mesures": f"sasi/{site}/+/mesures",
            "contexte": f"sasi/{site}/contexte",
            "pannes": f"sasi/{site}/jumeau/pannes",
            "horloge": f"sasi/{site}/jumeau/horloge",
        },
        "sortants": {
            "alertes": f"sasi/{site}/alertes",
            "niveaux": f"sasi/{site}/niveaux",
        },
    }


def genre(sujet):
    """Nature d'un message d'après son sujet, ou None si le sujet est inconnu."""
    morceaux = sujet.split("/")
    if len(morceaux) < 3 or morceaux[0] != "sasi":
        return None
    if morceaux[2:] == ["contexte"]:
        return "contexte"
    if morceaux[2:] == ["alertes"]:
        return "alertes"
    if morceaux[2:] == ["niveaux"]:
        return "niveaux"
    if morceaux[2:] == ["jumeau", "pannes"]:
        return "pannes"
    if morceaux[2:] == ["jumeau", "horloge"]:
        return "horloge"
    if len(morceaux) == 4 and morceaux[3] == "mesures":
        return "mesures"
    if morceaux[2] == "interne":
        return "interne"
    return None


# ------------------------------------------------------------- vérifications
class Rapport:
    """Défauts et avertissements relevés sur un message.

    Un défaut empêche la mesure d'être exploitée ; un avertissement signale un
    écart au contrat qui n'empêche rien, mais qu'il vaut mieux corriger.
    """

    def __init__(self):
        self.defauts = []
        self.avertissements = []

    def defaut(self, code, detail=""):
        self.defauts.append(f"{code}{' : ' + detail if detail else ''}")

    def avertir(self, code, detail=""):
        self.avertissements.append(f"{code}{' : ' + detail if detail else ''}")

    @property
    def conforme(self):
        return not self.defauts

    def __bool__(self):
        return bool(self.defauts or self.avertissements)


def _horodatage(valeur, rapport, champ="horodatage"):
    """Vérifie un horodatage. Renvoie les secondes depuis 1970, ou None."""
    if valeur is None:
        rapport.defaut("horodatage_absent", champ)
        return None
    if isinstance(valeur, bool):
        rapport.defaut("horodatage_illisible", f"{champ} = {valeur!r}")
        return None
    if isinstance(valeur, (int, float)):
        return float(valeur)             # secondes Unix : accepté par le connecteur
    if not MOTIF_HORODATAGE.match(str(valeur)):
        rapport.defaut("horodatage_mal_forme",
                       f"{champ} = {valeur!r}, attendu 2026-09-19T14:30:10Z")
        return None
    from datetime import datetime
    return datetime.fromisoformat(str(valeur).replace("Z", "+00:00")).timestamp()


def _temperature(valeur, rapport, champ, obligatoire=False):
    """Vérifie une température. « null » est permis, zéro par défaut ne l'est pas."""
    if valeur is None:
        if obligatoire:
            rapport.avertir("valeur_absente", f"{champ} : la mesure sera ignorée")
        return None
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        rapport.defaut("valeur_illisible", f"{champ} = {valeur!r}")
        return None
    if math.isnan(valeur) or math.isinf(valeur):
        rapport.defaut("valeur_illisible", f"{champ} = {valeur!r}")
        return None
    if not TEMPERATURE_MINIMALE <= valeur <= TEMPERATURE_MAXIMALE:
        rapport.defaut("valeur_hors_plage",
                       f"{champ} = {valeur} °C, attendu entre "
                       f"{TEMPERATURE_MINIMALE:.0f} et {TEMPERATURE_MAXIMALE:.0f}")
        return None
    if round(valeur, 1) != valeur:
        rapport.avertir("decimales_en_trop", f"{champ} = {valeur}, une décimale suffit")
    return float(valeur)


def _pourcentage(valeur, rapport, champ):
    if valeur is None:
        return None
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        rapport.defaut("valeur_illisible", f"{champ} = {valeur!r}")
        return None
    if not 0 <= valeur <= 100:
        rapport.defaut("pourcentage_hors_plage", f"{champ} = {valeur}")
    return float(valeur)


def verifier(sujet, charge_utile, referentiel=None):
    """Vérifie un message. Renvoie un Rapport.

    referentiel : dictionnaire renvoyé par `/api/referentiel`, ou None pour ne
    vérifier que la forme sans contrôler les identifiants.
    """
    rapport = Rapport()
    nature = genre(sujet)
    if nature is None:
        rapport.defaut("sujet_inconnu", sujet)
        return rapport
    if nature == "interne":
        return rapport                   # trafic interne : hors contrat

    try:
        fiche = json.loads(charge_utile) if isinstance(charge_utile, (str, bytes)) \
            else charge_utile
    except (ValueError, TypeError) as souci:
        rapport.defaut("json_illisible", str(souci))
        return rapport
    if not isinstance(fiche, dict):
        rapport.defaut("objet_attendu", f"reçu {type(fiche).__name__}")
        return rapport

    verificateurs = {"mesures": _mesures, "contexte": _contexte, "pannes": _pannes,
                     "horloge": _horloge, "alertes": _alertes, "niveaux": _niveaux}
    verificateurs[nature](sujet, fiche, rapport, referentiel or {})
    return rapport


def _connus(referentiel):
    """(équipements, caméras, zones) du référentiel."""
    liste = referentiel.get("equipements") or []
    equipements = {e.get("id") for e in liste}
    cameras = {e.get("camera") for e in liste if e.get("camera")}
    zones = {e.get("zone") for e in liste if e.get("zone") is not None}
    return equipements, cameras, zones


def _mesures(sujet, fiche, rapport, referentiel):
    equipements, cameras, _ = _connus(referentiel)
    camera_du_sujet = sujet.split("/")[2]

    if not fiche.get("site"):
        rapport.defaut("site_absent")
    camera = fiche.get("camera")
    if not camera:
        rapport.defaut("camera_absente")
    elif camera != camera_du_sujet:
        rapport.defaut("camera_incoherente",
                       f"sujet {camera_du_sujet}, message {camera}")
    elif not MOTIF_CAMERA.match(str(camera)):
        rapport.avertir("camera_hors_nomenclature", f"{camera}, attendu CAM-Z<n>")
    elif cameras and camera not in cameras:
        rapport.defaut("camera_inconnue", str(camera))

    _horodatage(fiche.get("horodatage"), rapport)

    source = fiche.get("source")
    if source is None:
        rapport.avertir("source_absente", "« camera » sera supposé")
    elif source not in SOURCES:
        rapport.defaut("source_inconnue", f"{source!r}, attendu {' ou '.join(SOURCES)}")

    zones = fiche.get("zones")
    if not isinstance(zones, list):
        rapport.defaut("zones_absentes", "la liste « zones » est obligatoire")
        return
    if not zones:
        rapport.avertir("zones_vides", "message sans aucune mesure")

    for rang, zone in enumerate(zones):
        if not isinstance(zone, dict):
            rapport.defaut("zone_mal_formee", f"zones[{rang}]")
            continue
        identifiant = zone.get("equipement")
        if not identifiant:
            rapport.defaut("equipement_absent", f"zones[{rang}]")
        elif not MOTIF_EQUIPEMENT.match(str(identifiant)):
            rapport.defaut("equipement_hors_nomenclature",
                           f"{identifiant}, attendu Z<zone>-<CODE>-<nn>")
        elif equipements and identifiant not in equipements:
            rapport.defaut("equipement_inconnu",
                           f"{identifiant} absent du référentiel")

        if "t_max" not in zone:
            rapport.defaut("t_max_absent", f"zones[{rang}] ({identifiant})")
        t_max = _temperature(zone.get("t_max"), rapport,
                             f"{identifiant}.t_max", obligatoire=True)
        t_moy = _temperature(zone.get("t_moy"), rapport, f"{identifiant}.t_moy")
        t_min = _temperature(zone.get("t_min"), rapport, f"{identifiant}.t_min")
        trois = [v for v in (t_min, t_moy, t_max) if v is not None]
        if len(trois) == 3 and not t_min <= t_moy <= t_max:
            rapport.defaut("temperatures_incoherentes",
                           f"{identifiant} : t_min {t_min}, t_moy {t_moy}, t_max {t_max}")


def _contexte(sujet, fiche, rapport, referentiel):
    equipements, _, zones_connues = _connus(referentiel)
    if not fiche.get("site"):
        rapport.defaut("site_absent")
    _horodatage(fiche.get("horodatage"), rapport)

    lignes = fiche.get("equipements")
    if lignes is None and fiche.get("ambiance") is None:
        rapport.defaut("contexte_vide", "ni « equipements » ni « ambiance »")
    for rang, ligne in enumerate(lignes or []):
        if not isinstance(ligne, dict):
            rapport.defaut("ligne_mal_formee", f"equipements[{rang}]")
            continue
        identifiant = ligne.get("equipement")
        if not identifiant:
            rapport.defaut("equipement_absent", f"equipements[{rang}]")
        elif equipements and identifiant not in equipements:
            rapport.defaut("equipement_inconnu", str(identifiant))
        etat = ligne.get("etat")
        if etat is None:
            rapport.avertir("etat_absent", f"{identifiant} : « marche » sera supposé")
        elif etat not in ETATS_MARCHE:
            rapport.defaut("etat_inconnu", f"{identifiant} = {etat!r}, "
                                           f"attendu {' ou '.join(ETATS_MARCHE)}")
        _pourcentage(ligne.get("charge_pct"), rapport, f"{identifiant}.charge_pct")

    for rang, ligne in enumerate(fiche.get("ambiance") or []):
        if not isinstance(ligne, dict):
            rapport.defaut("ligne_mal_formee", f"ambiance[{rang}]")
            continue
        zone = ligne.get("zone")
        if zone is None:
            rapport.defaut("zone_absente", f"ambiance[{rang}]")
        elif isinstance(zone, bool) or not isinstance(zone, int):
            rapport.defaut("zone_illisible", f"ambiance[{rang}] = {zone!r}, "
                                             "attendu un entier")
        elif zones_connues and zone not in zones_connues:
            rapport.defaut("zone_inconnue", str(zone))
        _temperature(ligne.get("t_ambiante"), rapport, f"zone {zone}.t_ambiante")
        _pourcentage(ligne.get("humidite_pct"), rapport, f"zone {zone}.humidite_pct")


def _pannes(sujet, fiche, rapport, referentiel):
    equipements, _, _ = _connus(referentiel)
    if not fiche.get("id_panne"):
        rapport.defaut("id_panne_absent")
    identifiant = fiche.get("equipement")
    if not identifiant:
        rapport.defaut("equipement_absent")
    elif equipements and identifiant not in equipements:
        rapport.defaut("equipement_inconnu", str(identifiant))
    type_panne = fiche.get("type")
    if not type_panne:
        rapport.defaut("type_absent")
    elif type_panne not in TYPES_PANNE:
        rapport.avertir("type_hors_repertoire",
                        f"{type_panne} : le contrôle automatique le comptera à part")
    evenement = fiche.get("evenement")
    if evenement not in EVENEMENTS_PANNE:
        rapport.defaut("evenement_inconnu",
                       f"{evenement!r}, attendu {' ou '.join(EVENEMENTS_PANNE)}")
    _horodatage(fiche.get("horodatage"), rapport)


def _horloge(sujet, fiche, rapport, referentiel):
    mode = fiche.get("mode")
    if mode not in MODES_HORLOGE:
        rapport.defaut("mode_inconnu", f"{mode!r}, attendu {' ou '.join(MODES_HORLOGE)}")
    facteur = fiche.get("facteur", 1)
    if isinstance(facteur, bool) or not isinstance(facteur, (int, float)):
        rapport.defaut("facteur_illisible", repr(facteur))
    elif facteur < 1:
        rapport.defaut("facteur_hors_plage", f"{facteur}, attendu au moins 1")
    elif mode == "reel" and facteur != 1:
        rapport.avertir("facteur_incoherent", "mode réel avec un facteur différent de 1")
    if fiche.get("debut_scenario") is not None:
        _horodatage(fiche.get("debut_scenario"), rapport, "debut_scenario")


def _alertes(sujet, fiche, rapport, referentiel):
    """Alerte publiée par l'application, relue par le jumeau pour colorer la maquette."""
    if not (fiche.get("id") or fiche.get("id_alerte")):
        rapport.defaut("id_absent")
    if not fiche.get("equipement"):
        rapport.defaut("equipement_absent")
    if fiche.get("niveau") not in NIVEAUX:
        rapport.defaut("niveau_inconnu", repr(fiche.get("niveau")))
    if fiche.get("etat") not in ETATS_ALERTE:
        rapport.defaut("etat_inconnu", repr(fiche.get("etat")))
    _horodatage(fiche.get("debut"), rapport, "debut")


def _niveaux(sujet, fiche, rapport, referentiel):
    equipements, _, _ = _connus(referentiel)
    niveaux = fiche.get("niveaux")
    if not isinstance(niveaux, dict):
        rapport.defaut("niveaux_absents")
        return
    for identifiant, niveau in niveaux.items():
        if equipements and identifiant not in equipements:
            rapport.defaut("equipement_inconnu", str(identifiant))
        if niveau not in NIVEAUX:
            rapport.defaut("niveau_inconnu", f"{identifiant} = {niveau!r}")
