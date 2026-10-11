"""Serveur de l'application (cahier des charges technique, chapitre 8).

    uvicorn api.serveur:app --host 0.0.0.0 --port 8000

Rôle : fournir les données à l'interface, transmettre les actions des équipes au
service des alertes, et diffuser les changements en direct.

Qui décide de quoi :
  - le service des alertes tient l'état des alertes (création, escalade, clôture) ;
  - ce serveur en garde une copie pour répondre vite, et lui transmet les actions
    par le serveur de messages ;
  - la base de données conserve l'historique.

La documentation des services est produite automatiquement à l'adresse /docs.
"""

import asyncio
import json
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.registre import Registre, reduire
from ia.site import Site

RACINE = Path(__file__).resolve().parents[1]
WEB = RACINE / "frontend" / "dist"
WEB_SIMPLE = RACINE / "web"

# Le nom du fichier de site (« brasserie ») et son identifiant (« SIM01 ») sont
# deux choses différentes : on garde le premier pour tout rechargement.
NOM_SITE = os.environ.get("SASI_SITE", "brasserie")
SITE = Site.charger(NOM_SITE)
ADRESSE_BASE = os.environ.get("SASI_BASE")
ADRESSE_MQTT = os.environ.get("SASI_MQTT")

SUJET_ALERTES = f"sasi/{SITE.identifiant}/alertes"
SUJET_NIVEAUX = f"sasi/{SITE.identifiant}/niveaux"
SUJET_COMMANDES = f"sasi/{SITE.identifiant}/commandes"
SUJET_TECHNIQUE = f"sasi/{SITE.identifiant}/interne/alertes_techniques"
SUJET_JUGEMENTS = f"sasi/{SITE.identifiant}/interne/jugements"


REGISTRE = Registre(SITE)
ABONNES = set()
BOUCLE = None
CLIENT_MQTT = None


# ---------------------------------------------------------------- données reçues
class Acquittement(BaseModel):
    par: str


class Assignation(BaseModel):
    par: str
    a_qui: str


class Cloture(BaseModel):
    par: str
    constat: str
    travaux: str = ""
    justifiee: bool


class DemandeEntrainement(BaseModel):
    par: str
    lot_normal: str = "A"
    lot_essai: str = "B"


class MiseEnService(BaseModel):
    par: str


class DemandeEssai(BaseModel):
    """Une situation soumise à l'IA, pour voir comment elle réagit."""
    equipement: str
    situation: str = "montee"
    vitesse: float = 1.0
    duree: float = 40.0


class SignalementManque(BaseModel):
    """Un échauffement réel que l'IA n'a pas signalé, déclaré après coup."""
    par: str
    debut: float                 # secondes depuis 1970
    fin: float
    motif: str


# ---------------------------------------------------------------- temps réel
async def diffuser(message):
    """Envoie un message à toutes les interfaces ouvertes."""
    morts = []
    for connexion in ABONNES:
        try:
            await connexion.send_text(json.dumps(message))
        except Exception:
            morts.append(connexion)
    for connexion in morts:
        ABONNES.discard(connexion)


def _diffuser_depuis_mqtt(message):
    if BOUCLE is not None:
        asyncio.run_coroutine_threadsafe(diffuser(message), BOUCLE)


def sur_message_mqtt(client, donnees, message):
    """Reçoit les niveaux, les alertes et les alertes techniques."""
    sortie = REGISTRE.appliquer(message.topic, message.payload)
    if sortie:
        _diffuser_depuis_mqtt(sortie)


def publier_commande(action, equipement, **details):
    """Transmet une action au service des alertes.

    Sans serveur de messages, elle est appliquée localement pour que
    l'application reste utilisable en démonstration.
    """
    fiche = REGISTRE.commande(action, equipement, **details)
    if CLIENT_MQTT is not None and REGISTRE.connecte:
        CLIENT_MQTT.publish(SUJET_COMMANDES, json.dumps(fiche), qos=1)
        return None
    return REGISTRE.appliquer_localement(fiche)


@asynccontextmanager
async def cycle_de_vie(app):
    """Ouvre la liaison avec le serveur de messages et relit la base au démarrage."""
    global BOUCLE, CLIENT_MQTT
    BOUCLE = asyncio.get_running_loop()

    if ADRESSE_BASE:
        try:
            from connecteur.depot import Depot
            depot = Depot(ADRESSE_BASE)
            for fiche in depot.lire_alertes():
                fiche["debut"] = fiche["debut"].timestamp() if fiche.get("debut") else None
                fiche["fin"] = fiche["fin"].timestamp() if fiche.get("fin") else None
                REGISTRE.appliquer(SUJET_ALERTES, fiche)
            depot.fermer()
            print(f"Base relue : {len(REGISTRE.alertes)} alertes")
        except Exception as erreur:
            print(f"Base injoignable : {erreur}")

    if ADRESSE_MQTT:
        try:
            import paho.mqtt.client as mqtt
            CLIENT_MQTT = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            CLIENT_MQTT.on_message = sur_message_mqtt
            CLIENT_MQTT.connect(ADRESSE_MQTT, 1883, 60)
            for sujet in (SUJET_NIVEAUX, SUJET_ALERTES, SUJET_TECHNIQUE, SUJET_JUGEMENTS):
                CLIENT_MQTT.subscribe(sujet, qos=1)
            CLIENT_MQTT.loop_start()
            REGISTRE.connecte = True
            print(f"Serveur de messages : {ADRESSE_MQTT}")
        except Exception as erreur:              # l'application reste consultable
            print(f"Serveur de messages injoignable : {erreur}")

    yield

    if CLIENT_MQTT:
        CLIENT_MQTT.loop_stop()


app = FastAPI(title="SASI — application de surveillance", lifespan=cycle_de_vie)


# ---------------------------------------------------------------- services
@app.get("/api/etat")
def etat_du_systeme():
    """Ce à quoi le serveur est relié : utile au premier démarrage."""
    return {
        "site": SITE.identifiant,
        "serveur_de_messages": bool(REGISTRE.connecte),
        "base_de_donnees": bool(ADRESSE_BASE),
        "alertes_en_memoire": len(REGISTRE.alertes),
        "equipements_suivis": len(REGISTRE.series),
        "alertes_techniques": len(REGISTRE.techniques),
    }


@app.get("/api/site")
def lire_site():
    """Description du site : zones, familles, équipements."""
    return {"site": {"id": SITE.identifiant, "nom": SITE.nom, "secteur": SITE.secteur},
            "zones": SITE.zones, "familles": SITE.familles,
            "equipements": [dict(SITE.equipements[e]) for e in SITE.liste()]}


@app.get("/api/equipements")
def lire_equipements():
    """Liste des équipements avec leur niveau actuel."""
    return [{"id": identifiant,
             "nom": SITE.nom_equipement(identifiant),
             "zone": SITE.zone(identifiant),
             "famille": SITE.famille(identifiant),
             "criticite": SITE.criticite(identifiant),
             "niveau": REGISTRE.niveaux.get(identifiant, "normal")}
            for identifiant in SITE.liste()]


@app.get("/api/equipements/{identifiant}/mesures")
def lire_mesures(identifiant: str, heures: int = 24, points: int = 400):
    """Mesures et températures attendues d'un équipement, sur une période."""
    if identifiant not in SITE.equipements:
        raise HTTPException(404, "Équipement inconnu")
    if not ADRESSE_BASE:
        # Sans base, on sert ce que le serveur a gardé en mémoire depuis son démarrage.
        serie = REGISTRE.serie(identifiant, heures, points)
        return {"equipement": identifiant, "source": "memoire",
                "mesures": [{"horodatage": p.get("horodatage"), "t_max": p.get("t_max"),
                             "t_attendue": p.get("t_attendue"), "score": p.get("score"),
                             "niveau": p.get("niveau")} for p in serie]}
    depuis = datetime.now(timezone.utc) - timedelta(hours=heures)
    import psycopg
    with psycopg.connect(ADRESSE_BASE) as connexion, connexion.cursor() as curseur:
        curseur.execute(
            "SELECT m.horodatage, m.t_max, p.t_attendue, p.score, p.niveau"
            " FROM mesure m LEFT JOIN prediction p"
            "   ON p.equipement = m.equipement AND p.horodatage = m.horodatage"
            " WHERE m.equipement = %s AND m.horodatage >= %s"
            " ORDER BY m.horodatage", (identifiant, depuis))
        lignes = reduire(curseur.fetchall(), points)
    return {"equipement": identifiant,
            "mesures": [{"horodatage": l[0].isoformat(), "t_max": l[1],
                         "t_attendue": l[2], "score": l[3], "niveau": l[4]}
                        for l in lignes]}


@app.get("/api/alertes")
def lire_alertes(etat: str | None = None, niveau: str | None = None):
    """Alertes, filtrables par état et par niveau."""
    alertes = REGISTRE.liste_alertes()
    if etat:
        alertes = [a for a in alertes if a.get("etat") == etat]
    if niveau:
        alertes = [a for a in alertes if a.get("niveau") == niveau]
    return alertes


@app.get("/api/alertes/techniques")
def lire_alertes_techniques():
    """Caméras muettes ou figées : un circuit séparé des alertes incendie."""
    return REGISTRE.techniques


@app.get("/api/alertes/{identifiant}")
def lire_alerte(identifiant: str):
    fiche = REGISTRE.alerte(identifiant)
    if fiche is None:
        raise HTTPException(404, "Alerte inconnue")
    return fiche


@app.post("/api/alertes/{equipement}/acquitter")
async def acquitter(equipement: str, demande: Acquittement):
    publier_commande("acquitter", equipement, par=demande.par)
    return {"equipement": equipement, "action": "acquitter", "transmise": True}


@app.post("/api/alertes/{equipement}/assigner")
async def assigner(equipement: str, demande: Assignation):
    publier_commande("assigner", equipement, par=demande.par, a_qui=demande.a_qui)
    return {"equipement": equipement, "action": "assigner", "transmise": True}


@app.post("/api/alertes/{equipement}/cloturer")
async def cloturer(equipement: str, demande: Cloture):
    if not demande.constat:
        raise HTTPException(400, "Une clôture exige un compte rendu.")
    try:
        publier_commande("cloturer", equipement, par=demande.par, constat=demande.constat,
                         justifiee=demande.justifiee)
    except ValueError as erreur:
        raise HTTPException(400, str(erreur))
    return {"equipement": equipement, "action": "cloturer", "transmise": True}


@app.post("/api/equipements/{identifiant}/maintenance")
def maintenance(identifiant: str, en_maintenance: bool = True):
    publier_commande("maintenance", identifiant, en_maintenance=en_maintenance)
    REGISTRE.moteur_local.mettre_en_maintenance(identifiant, en_maintenance)
    return {"equipement": identifiant, "en_maintenance": en_maintenance}


@app.get("/api/cameras")
def lire_cameras():
    """Caméras du site, avec le nombre d'équipements et de contours."""
    cameras = {}
    for identifiant in SITE.liste():
        nom_camera = SITE.camera(identifiant)
        fiche = cameras.setdefault(nom_camera, {
            "id": nom_camera, "zone": SITE.zone(identifiant),
            "modele": None, "adresse": None, "distance": None, "emissivite": None,
            "etat": "en service", "equipements": 0, "contours": 0,
        })
        fiche["equipements"] += 1

    for technique in REGISTRE.techniques:
        if technique.get("camera") in cameras and technique.get("type") == "camera_muette":
            cameras[technique["camera"]]["etat"] = "muette"

    if ADRESSE_BASE:
        import psycopg
        with psycopg.connect(ADRESSE_BASE) as connexion, connexion.cursor() as curseur:
            curseur.execute("SELECT id, modele, adresse, distance_m, emissivite FROM camera")
            for identifiant, modele, reseau, distance, emissivite in curseur.fetchall():
                if identifiant in cameras:
                    cameras[identifiant].update({"modele": modele, "adresse": reseau,
                                                 "distance": distance, "emissivite": emissivite})
            curseur.execute("SELECT camera, count(*) FROM zone_image GROUP BY camera")
            for identifiant, nombre in curseur.fetchall():
                if identifiant in cameras:
                    cameras[identifiant]["contours"] = nombre
    return sorted(cameras.values(), key=lambda c: c["id"])


@app.get("/api/rapports/hebdomadaire")
def rapport_hebdomadaire(jours: int = 7):
    """Bilan de la période : alertes, délais, équipements exposés."""
    depuis = time.time() - jours * 86400
    alertes = [a for a in REGISTRE.liste_alertes() if (a.get("debut") or 0) >= depuis]
    if not alertes:
        return {"periode": f"{jours} derniers jours", "alertes": 0, "alertesPrecedentes": 0,
                "delaiMedian": None, "delaiMaximum": None, "justifiees": 0,
                "disponibilite": None, "parZone": [], "exposes": [], "cameras": []}

    par_zone, par_equipement = {}, {}
    for alerte in alertes:
        equipement = alerte.get("equipement")
        zone = SITE.zone(equipement) if equipement in SITE.equipements else 0
        ligne = par_zone.setdefault(zone, {"zone": zone})
        ligne[alerte["niveau"]] = ligne.get(alerte["niveau"], 0) + 1
        fiche = par_equipement.setdefault(equipement, {
            "equipement": equipement, "alertes": 0, "niveau": alerte["niveau"], "duree": "—"})
        fiche["alertes"] += 1

    return {
        "periode": f"{jours} derniers jours",
        "alertes": len(alertes),
        "alertesPrecedentes": 0,
        "delaiMedian": None,
        "delaiMaximum": None,
        "justifiees": sum(1 for a in alertes if a.get("justifiee")),
        "disponibilite": None,
        "parZone": sorted(par_zone.values(), key=lambda l: l["zone"]),
        "exposes": sorted(par_equipement.values(), key=lambda l: -l["alertes"])[:5],
        "cameras": [],
    }


# ---------------------------------------------------------------- modèle de l'IA
SUJET_MODELE = f"sasi/{SITE.identifiant}/modele"


@app.get("/api/modele")
def lire_modele():
    """État du modèle en service : d'où il vient, ce qu'il vaut, ce qu'il a appris."""
    from ia import modeles_en_service

    registre = modeles_en_service.adopter_existant(SITE)
    en_service = next((v for v in registre["versions"]
                       if v["version"] == registre["en_service"]), None)
    from ia import retours as module_retours
    return {"site": SITE.identifiant, "en_service": en_service,
            "versions": registre["versions"],
            "travail": (travail_en_cours() or {}),
            "entrees": _entrees_du_modele(),
            "retours": module_retours.Registre(SITE).resume()}


def _entrees_du_modele():
    """Les informations dont le modèle se sert, telles qu'enregistrées."""
    from ia import modeles_en_service
    fiche = modeles_en_service.dossier(SITE) / "modeles.json"
    if not fiche.exists():
        return []
    return json.loads(fiche.read_text(encoding="utf-8")).get("entrees", [])


def travail_en_cours():
    from ia import travaux
    travail = travaux.en_cours()
    return travail.resume() if travail else None


@app.get("/api/modele/travaux")
def lire_travaux(nombre: int = 10):
    """Les derniers entraînements lancés, le plus récent d'abord."""
    from ia import travaux
    return travaux.liste(nombre)


@app.get("/api/modele/travaux/{identifiant}")
def lire_travail(identifiant: str):
    """Avancement d'un entraînement : étape, progression, journal."""
    from ia import travaux
    fiche = travaux.lire(identifiant)
    if fiche is None:
        raise HTTPException(404, "Travail inconnu")
    return fiche


@app.post("/api/modele/entrainer")
def entrainer(demande: DemandeEntrainement):
    """Lance un entraînement en arrière-plan. La mise en service reste manuelle."""
    from ia import travaux
    try:
        travail = travaux.lancer_entrainement(
            NOM_SITE, demande.par, demande.lot_normal, demande.lot_essai)
    except RuntimeError as souci:
        raise HTTPException(409, str(souci))
    return travail.resume()


@app.get("/api/modele/inspection")
def lire_inspection(version: str | None = None):
    """Comment le modèle raisonne : erreurs, appuis, contrôles de bon sens."""
    from ia import modeles_en_service
    examen = modeles_en_service.lire_inspection(SITE, version)
    if examen is None:
        raise HTTPException(404, "Aucune inspection : lancez-la depuis l'écran du modèle.")
    return examen


@app.post("/api/modele/inspecter")
def inspecter_modele(demande: MiseEnService):
    """Inspecte le modèle en service, sans le réentraîner."""
    from ia import travaux
    try:
        travail = travaux.lancer_inspection(NOM_SITE, demande.par)
    except RuntimeError as souci:
        raise HTTPException(409, str(souci))
    return travail.resume()


@app.post("/api/modele/essai")
def essai(demande: DemandeEssai):
    """Soumet une situation à l'IA et renvoie sa réaction, pas à pas.

    L'essai est immédiat : quelques centaines de mesures dans le détecteur, sans
    toucher au modèle ni à la surveillance en cours.
    """
    from ia import risque as module_risque
    from outils import essayer as banc

    if demande.equipement not in SITE.equipements:
        raise HTTPException(404, "Équipement inconnu")
    if demande.situation not in banc.SITUATIONS:
        raise HTTPException(400, f"Situation inconnue : {demande.situation}")
    if not 1 <= demande.duree <= 240:
        raise HTTPException(400, "La durée doit tenir entre 1 et 240 minutes.")

    from ia.detection import DetecteurEquipement
    basse, haute = SITE.plage(demande.equipement)
    inspection, urgence = SITE.seuils_fixes(demande.equipement)
    reglage = banc.calibrage_reel(SITE, demande.equipement) or {}
    detecteur = DetecteurEquipement(
        demande.equipement, criticite=SITE.criticite(demande.equipement),
        biais=reglage.get("biais", 0.0), dispersion=reglage.get("dispersion", 1.0),
        seuil_fixe_inspection=inspection, seuil_fixe_urgence=urgence,
        temps_montee_min=SITE.temps_montee_min(demande.equipement))

    depart = (basse + haute) / 2.0
    points = banc.fabriquer(demande.situation, depart, demande.vitesse,
                            demande.duree, haute)
    nom = SITE.nom_equipement(demande.equipement)

    trace, changements = [], []
    for minute, mesuree, attendue in points:
        etat = detecteur.traiter(minute * 60, mesuree, attendue)
        trace.append({"minute": round(minute, 2), "mesuree": round(mesuree, 2),
                      "attendue": round(attendue, 2), "ecart": round(etat["ecart"], 2),
                      "risque": etat["risque_pourcentage"], "niveau": etat["niveau"]})
        if etat["changement"]:
            changements.append({
                "minute": round(minute, 1), "niveau": etat["niveau"],
                "raison": module_risque.expliquer(etat["risque_detail"], nom)})

    return {
        "equipement": demande.equipement, "nom": nom,
        "situation": demande.situation,
        "libelle": banc.SITUATIONS[demande.situation],
        "plage": [basse, haute], "seuil_inspection": inspection,
        "seuil_urgence": urgence, "criticite": SITE.criticite(demande.equipement),
        "calibrage": reglage or None,
        "trace": trace, "changements": changements,
    }


@app.get("/api/modele/situations")
def situations():
    """Les situations que l'on peut soumettre à l'IA."""
    from outils import essayer as banc
    return [{"clef": clef, "libelle": libelle} for clef, libelle in banc.SITUATIONS.items()]


@app.post("/api/modele/versions/{version}/en-service")
def mettre_version_en_service(version: str, demande: MiseEnService):
    """Met une version en service, et demande aux services de la recharger."""
    from ia import modeles_en_service
    try:
        modeles_en_service.mettre_en_service(SITE, version)
    except ValueError as souci:
        raise HTTPException(404, str(souci))

    if CLIENT_MQTT is not None and REGISTRE.connecte:
        CLIENT_MQTT.publish(SUJET_MODELE, json.dumps(
            {"action": "recharger", "version": version, "par": demande.par}), qos=1)
    return {"version": version, "en_service": True,
            "rechargement_demande": bool(REGISTRE.connecte)}


# ---------------------------------------------------------------- retours du terrain
@app.get("/api/retours")
def lire_retours():
    """Ce que les équipes ont corrigé : fausses alertes, manques, alertes confirmées."""
    from ia import retours
    return retours.Registre(SITE).resume()


@app.post("/api/equipements/{identifiant}/manque")
def signaler_manque(identifiant: str, demande: SignalementManque):
    """Déclare un échauffement que l'IA aurait dû signaler.

    C'est la seule erreur qu'aucune alerte ne révèle : sans ce service, le
    modèle ne pourrait jamais apprendre ce qu'il a laissé passer.
    """
    from ia import retours
    if identifiant not in SITE.equipements:
        raise HTTPException(404, "Équipement inconnu")
    if not demande.motif:
        raise HTTPException(400, "Indiquez ce qui a été constaté.")
    try:
        fiche = retours.Registre(SITE).ajouter_manque(
            identifiant, demande.debut, demande.fin, demande.motif, demande.par)
    except ValueError as souci:
        raise HTTPException(400, str(souci))
    return fiche


@app.get("/api/referentiel")
def referentiel():
    """Liste de référence, relue par le jumeau numérique (conventions, 6.6).

    Les noms des équipements n'ont qu'une source : ce service. Le jumeau la relit
    au démarrage plutôt que de recopier la liste, faute de quoi « Z4-ARM-1 » d'un
    côté et « Z4-ARM-01 » de l'autre finissent par se croiser sans se reconnaître.
    """
    from integration.referentiel import depuis_site
    return depuis_site(SITE)


@app.websocket("/ws/temps-reel")
async def temps_reel(connexion: WebSocket):
    """Met les écrans à jour sans recharger la page."""
    await connexion.accept()
    ABONNES.add(connexion)
    await connexion.send_text(json.dumps({"type": "niveaux", "niveaux": REGISTRE.niveaux}))
    for fiche in REGISTRE.liste_alertes()[:20]:
        await connexion.send_text(json.dumps({"type": "alerte", "alerte": fiche}))
    try:
        while True:
            await connexion.receive_text()
    except WebSocketDisconnect:
        ABONNES.discard(connexion)


# ---------------------------------------------------------------- interface
# Montée en dernier : les adresses /api et /ws restent prioritaires.
# On sert la version compilée (frontend/dist) si elle existe, sinon la
# démonstration sans compilation (web/).
DOSSIER_INTERFACE = WEB if WEB.exists() else WEB_SIMPLE
if DOSSIER_INTERFACE.exists():
    app.mount("/", StaticFiles(directory=DOSSIER_INTERFACE, html=True), name="interface")
