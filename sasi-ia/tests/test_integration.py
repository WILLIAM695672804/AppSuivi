"""Tests du kit d'intégration du jumeau numérique.

N'utilise que Python : aucun serveur de messages, aucune base, aucun réseau.

Ces tests ont une raison d'être particulière : ils vérifient que le contrat
remis à l'équipe du jumeau décrit bien ce que le code accepte. Un contrat qui
s'éloigne de l'implantation est pire qu'un contrat absent, car il fait chercher
la panne du mauvais côté.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from connecteur.journal_pannes import JournalPannes
from connecteur.main import Connecteur, SUJET_CONTEXTE, SUJET_HORLOGE, SUJET_PANNES
from ia.site import Site
from integration import contrat, referentiel, schemas
from integration.emetteur_reference import DEBUT_PAR_DEFAUT, Emetteur
from integration.verificateur import Verificateur

SITE = Site.charger("brasserie")
REFERENTIEL = referentiel.depuis_site(SITE)
HORODATAGE = "2026-09-19T14:30:10Z"


def mesures(**remplacements):
    fiche = {"site": "SIM01", "camera": "CAM-Z1", "horodatage": HORODATAGE,
             "source": "jumeau",
             "zones": [{"equipement": "Z1-ELV-01", "t_max": 52.4,
                        "t_moy": 45.0, "t_min": 38.1}]}
    fiche.update(remplacements)
    return json.dumps(fiche)


def verifier(charge, sujet="sasi/SIM01/CAM-Z1/mesures"):
    return contrat.verifier(sujet, charge, REFERENTIEL)


# ------------------------------------------------- le contrat dit la vérité
def test_les_sujets_du_contrat_sont_ceux_du_code():
    """Si le connecteur change de sujet, le contrat remis à l'équipe doit suivre."""
    attendus = contrat.sujets(SITE.identifiant)["entrants"]
    assert attendus["contexte"] == SUJET_CONTEXTE.format(site=SITE.identifiant)
    assert attendus["pannes"] == SUJET_PANNES.format(site=SITE.identifiant)
    assert attendus["horloge"] == SUJET_HORLOGE.format(site=SITE.identifiant)


def test_les_bornes_du_contrat_sont_celles_des_controles():
    from ia import controles
    assert contrat.TEMPERATURE_MINIMALE == controles.TEMPERATURE_MINIMALE
    assert contrat.TEMPERATURE_MAXIMALE == controles.TEMPERATURE_MAXIMALE


def test_les_niveaux_du_contrat_sont_ceux_de_la_detection():
    from ia import detection
    assert set(contrat.NIVEAUX) >= set(detection.PALIERS_RISQUE) | {"normal"}


def test_les_types_de_panne_du_contrat_couvrent_le_catalogue():
    """Toute signature produite par le générateur doit être reconnue au contrat."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "outils"))
    import scenarios
    produits = {t[0] for liste in scenarios.REPERTOIRE.values() for t in liste}
    produits |= {t[0] for t in scenarios.FROID}
    manquants = produits - set(contrat.TYPES_PANNE)
    assert not manquants, f"signatures absentes du contrat : {sorted(manquants)}"


def test_un_message_du_contrat_est_accepte_par_le_connecteur():
    """Ce que le contrat déclare conforme, le connecteur doit le conserver."""
    conservees = Connecteur(SITE).traiter_message("sasi/SIM01/CAM-Z1/mesures", mesures())
    assert verifier(mesures()).conforme
    assert len(conservees) == 1 and conservees[0]["equipement"] == "Z1-ELV-01"


# ------------------------------------------------------- forme des messages
def test_message_conforme():
    rapport = verifier(mesures())
    assert rapport.conforme and not rapport.avertissements, rapport.defauts


def test_sujet_inconnu_refuse():
    assert "sujet_inconnu" in verifier(mesures(), "autre/chose").defauts[0]


def test_json_illisible():
    assert "json_illisible" in verifier("{pas du json").defauts[0]


def test_equipement_hors_nomenclature():
    charge = mesures(zones=[{"equipement": "Z4-ARM-1", "t_max": 50.0}])
    assert any("hors_nomenclature" in d for d in verifier(charge).defauts)


def test_equipement_inconnu_du_referentiel():
    charge = mesures(zones=[{"equipement": "Z9-XXX-01", "t_max": 50.0}])
    assert any("equipement_inconnu" in d for d in verifier(charge).defauts)


def test_camera_incoherente_avec_le_sujet():
    assert any("camera_incoherente" in d for d in verifier(mesures(camera="CAM-Z2")).defauts)


def test_horodatage_mal_forme():
    assert any("horodatage_mal_forme" in d
               for d in verifier(mesures(horodatage="19/09/2026 14:30")).defauts)


def test_horodatage_en_secondes_accepte():
    """Le connecteur accepte les secondes Unix : le contrat doit l'accepter aussi."""
    assert verifier(mesures(horodatage=1789000000.0)).conforme


def test_valeur_hors_plage():
    charge = mesures(zones=[{"equipement": "Z1-ELV-01", "t_max": 5000.0}])
    assert any("valeur_hors_plage" in d for d in verifier(charge).defauts)


def test_temperatures_incoherentes():
    charge = mesures(zones=[{"equipement": "Z1-ELV-01", "t_max": 40.0,
                             "t_moy": 45.0, "t_min": 38.0}])
    assert any("temperatures_incoherentes" in d for d in verifier(charge).defauts)


def test_valeur_nulle_averti_sans_defaut():
    """V-06 : un champ à « null » ne provoque aucune erreur, la valeur est ignorée."""
    charge = mesures(zones=[{"equipement": "Z1-ELV-01", "t_max": None}])
    rapport = verifier(charge)
    assert rapport.conforme and any("valeur_absente" in a for a in rapport.avertissements)


def test_zones_absentes():
    charge = json.dumps({"site": "SIM01", "camera": "CAM-Z1", "horodatage": HORODATAGE})
    assert any("zones_absentes" in d for d in verifier(charge).defauts)


def test_contexte_conforme():
    charge = json.dumps({"site": "SIM01", "horodatage": HORODATAGE,
                         "equipements": [{"equipement": "Z1-ELV-01", "etat": "marche",
                                          "charge_pct": 75}],
                         "ambiance": [{"zone": 1, "t_ambiante": 31.5,
                                       "humidite_pct": 78}]})
    assert verifier(charge, "sasi/SIM01/contexte").conforme


def test_contexte_etat_inconnu():
    charge = json.dumps({"site": "SIM01", "horodatage": HORODATAGE,
                         "equipements": [{"equipement": "Z1-ELV-01", "etat": "ON"}]})
    assert any("etat_inconnu" in d
               for d in verifier(charge, "sasi/SIM01/contexte").defauts)


def test_contexte_zone_inconnue():
    charge = json.dumps({"site": "SIM01", "horodatage": HORODATAGE,
                         "ambiance": [{"zone": 42, "t_ambiante": 30.0}]})
    assert any("zone_inconnue" in d for d in verifier(charge, "sasi/SIM01/contexte").defauts)


def test_panne_conforme():
    charge = json.dumps({"id_panne": "P-0042", "equipement": "Z1-ELV-01",
                         "type": "derive_lente", "evenement": "debut",
                         "horodatage": HORODATAGE, "intensite": 8})
    assert verifier(charge, "sasi/SIM01/jumeau/pannes").conforme


def test_panne_evenement_inconnu():
    charge = json.dumps({"id_panne": "P-1", "equipement": "Z1-ELV-01",
                         "type": "derive_lente", "evenement": "milieu",
                         "horodatage": HORODATAGE})
    assert any("evenement_inconnu" in d
               for d in verifier(charge, "sasi/SIM01/jumeau/pannes").defauts)


def test_horloge_conforme():
    charge = json.dumps({"mode": "accelere", "facteur": 168,
                         "debut_scenario": HORODATAGE})
    assert verifier(charge, "sasi/SIM01/jumeau/horloge").conforme


def test_horloge_facteur_hors_plage():
    charge = json.dumps({"mode": "accelere", "facteur": 0})
    assert any("facteur_hors_plage" in d
               for d in verifier(charge, "sasi/SIM01/jumeau/horloge").defauts)


def test_niveaux_conformes():
    charge = json.dumps({"horodatage": HORODATAGE,
                         "niveaux": {"Z1-ELV-01": "inspection", "Z1-VIS-01": "normal"}})
    assert verifier(charge, "sasi/SIM01/niveaux").conforme


def test_niveau_inconnu():
    charge = json.dumps({"niveaux": {"Z1-ELV-01": "chaud"}})
    assert any("niveau_inconnu" in d for d in verifier(charge, "sasi/SIM01/niveaux").defauts)


def test_alerte_publiee_est_conforme():
    """Ce que le moteur d'alertes publie doit être relisible par le jumeau."""
    from alertes.moteur import MoteurAlertes
    moteur = MoteurAlertes()
    moteur.signaler("Z1-ELV-01", "inspection", 1789000000.0,
                    {"raison": "18 °C de plus que d'habitude", "t_mesuree": 68.0,
                     "t_attendue": 50.0})
    resume = moteur.ouvertes["Z1-ELV-01"].resume()
    rapport = verifier(json.dumps(resume), "sasi/SIM01/alertes")
    assert rapport.conforme, rapport.defauts


def test_trafic_interne_hors_contrat():
    """Les sujets « interne » ne concernent pas le jumeau : rien à vérifier."""
    assert verifier("n'importe quoi", "sasi/SIM01/interne/niveaux").conforme


# --------------------------------------------------------- liste de référence
def test_referentiel_conforme_aux_conventions():
    for champ in ("site", "version", "equipements", "zones", "familles"):
        assert champ in REFERENTIEL, champ
    fiche = REFERENTIEL["equipements"][0]
    for champ in ("id", "nom", "zone", "famille", "camera", "criticite",
                  "position_plan", "t_normale_indicative"):
        assert champ in fiche, champ
    assert len(fiche["t_normale_indicative"]) == 2


def test_referentiel_couvre_tous_les_equipements():
    assert {e["id"] for e in REFERENTIEL["equipements"]} == set(SITE.liste())


def test_referentiel_nomenclature_respectee():
    for fiche in REFERENTIEL["equipements"]:
        assert contrat.MOTIF_EQUIPEMENT.match(fiche["id"]), fiche["id"]
        assert contrat.MOTIF_CAMERA.match(fiche["camera"]), fiche["camera"]


def test_referentiel_depuis_un_fichier():
    with tempfile.TemporaryDirectory() as dossier:
        chemin = referentiel.ecrire(Path(dossier) / "r.json", REFERENTIEL)
        assert referentiel.charger(str(chemin))["site"] == "SIM01"


# ------------------------------------------------- émetteur de référence
def collecter(duree_min=2.0, pannes=()):
    """Fait tourner l'émetteur sans réseau et renvoie les messages publiés."""
    publies = []
    emetteur = Emetteur(REFERENTIEL, lambda sujet, charge: publies.append((sujet, charge)))
    for specification in pannes:
        emetteur.ajouter_panne(specification, 0.0, 60.0)
    emetteur.tourner(DEBUT_PAR_DEFAUT, duree_min, facteur=1e9)
    return publies


def test_emetteur_de_reference_est_conforme():
    """Référence utile seulement si elle est irréprochable."""
    verificateur = Verificateur("SIM01", REFERENTIEL)
    for sujet, charge in collecter(pannes=["Z1-ELV-01:derive_lente:8"]):
        verificateur.examiner(sujet, json.dumps(charge))
    assert not verificateur.defauts, dict(verificateur.defauts)
    assert not verificateur.avertissements, dict(verificateur.avertissements)


def test_emetteur_couvre_tout_le_site():
    """V-01 : les 17 équipements et les 7 caméras doivent apparaître."""
    verificateur = Verificateur("SIM01", REFERENTIEL)
    for sujet, charge in collecter():
        verificateur.examiner(sujet, json.dumps(charge))
    equipements, cameras = verificateur.manquants()
    assert not equipements and not cameras, (equipements, cameras)


def test_emetteur_respecte_la_cadence():
    verificateur = Verificateur("SIM01", REFERENTIEL)
    for sujet, charge in collecter(duree_min=5.0):
        verificateur.examiner(sujet, json.dumps(charge))
    cadences = verificateur.cadences()
    assert cadences["CAM-Z1"]["pas"] == contrat.PAS_MESURES_S
    assert cadences["(contexte)"]["pas"] == contrat.PAS_CONTEXTE_S


def test_emetteur_annonce_son_horloge():
    sujets = [s for s, _ in collecter()]
    assert sujets[0].endswith("/jumeau/horloge"), "l'horloge s'annonce en premier"


def test_emetteur_annonce_le_debut_de_la_panne():
    pannes = [c for s, c in collecter(pannes=["Z2-CHE-01:montee_brutale:30"])
              if s.endswith("/jumeau/pannes")]
    assert pannes and pannes[0]["evenement"] == "debut"
    assert pannes[0]["equipement"] == "Z2-CHE-01"


def test_emetteur_reproductible():
    """V-05 : un même scénario relancé produit exactement les mêmes données."""
    assert collecter() == collecter()


def test_panne_de_l_emetteur_fait_monter_la_temperature():
    sans = {s: c for s, c in collecter(duree_min=3.0)}
    avec = {s: c for s, c in collecter(duree_min=3.0,
                                       pannes=["Z1-ELV-01:montee_brutale:30"])}
    sujet = "sasi/SIM01/CAM-Z1/mesures"
    froid = [z["t_max"] for z in sans[sujet]["zones"] if z["equipement"] == "Z1-ELV-01"][0]
    chaud = [z["t_max"] for z in avec[sujet]["zones"] if z["equipement"] == "Z1-ELV-01"][0]
    assert chaud > froid, f"{chaud} °C devrait dépasser {froid} °C"


def test_emetteur_refuse_un_equipement_inconnu():
    emetteur = Emetteur(REFERENTIEL, lambda sujet, charge: None)
    try:
        emetteur.ajouter_panne("Z9-XXX-01:derive_lente:8", 0.0, 60.0)
    except SystemExit:
        return
    raise AssertionError("un équipement absent du référentiel doit être refusé")


# ------------------------------------------------------ journal des pannes
def message_panne(evenement, horodatage, identifiant="P-0001"):
    return json.dumps({"id_panne": identifiant, "equipement": "Z1-ELV-01",
                       "type": "derive_lente", "evenement": evenement,
                       "horodatage": horodatage, "intensite": 8.0})


def test_journal_rapproche_debut_et_fin():
    journal = JournalPannes()
    assert journal.appliquer(message_panne("debut", "2026-09-19T06:00:00Z")) is None
    complete = journal.appliquer(message_panne("fin", "2026-09-19T06:30:00Z"))
    assert complete["debut"] == "2026-09-19T06:00:00Z"
    assert complete["fin"] == "2026-09-19T06:30:00Z"


def test_journal_distingue_ouvertes_et_completes():
    journal = JournalPannes()
    journal.appliquer(message_panne("debut", "2026-09-19T06:00:00Z", "P-0001"))
    journal.appliquer(message_panne("debut", "2026-09-19T07:00:00Z", "P-0002"))
    journal.appliquer(message_panne("fin", "2026-09-19T07:30:00Z", "P-0002"))
    assert [p["id"] for p in journal.ouvertes()] == ["P-0001"]
    assert [p["id"] for p in journal.completes()] == ["P-0002"]


def test_journal_ecarte_un_message_incomplet():
    journal = JournalPannes()
    assert journal.appliquer('{"evenement": "debut"}') is None
    assert journal.appliquer("{pas du json") is None
    assert journal.resume()["ecartes"] == 2


def test_journal_accepte_les_secondes():
    journal = JournalPannes()
    journal.appliquer(message_panne("debut", 1789000000.0))
    complete = journal.appliquer(message_panne("fin", 1789003600.0))
    assert complete["debut"].endswith("Z") and "T" in complete["debut"]


def test_journal_ecrit_le_format_du_controle_automatique():
    """Le fichier doit être relisible tel quel par ia.chaine.fenetres_journal."""
    import csv
    with tempfile.TemporaryDirectory() as dossier:
        journal = JournalPannes(Path(dossier) / "journal_jumeau.csv")
        journal.appliquer(message_panne("debut", "2026-09-19T06:00:00Z"))
        journal.appliquer(message_panne("fin", "2026-09-19T06:30:00Z"))
        with open(journal.chemin, encoding="utf-8") as fichier:
            lignes = list(csv.DictReader(fichier))
    assert list(lignes[0]) == ["id", "equipement", "type", "debut", "fin", "intensite"]
    assert lignes[0]["equipement"] == "Z1-ELV-01"


def test_connecteur_tient_le_journal():
    connecteur = Connecteur(SITE, journal=JournalPannes())
    connecteur.traiter_panne(message_panne("debut", "2026-09-19T06:00:00Z"))
    assert connecteur.traiter_panne(message_panne("fin", "2026-09-19T06:30:00Z"))


def test_connecteur_sans_journal_ne_plante_pas():
    """En service réel, personne n'annonce les pannes : le message est ignoré."""
    assert Connecteur(SITE).traiter_panne(message_panne("debut", HORODATAGE)) is None


def test_connecteur_retient_l_horloge():
    connecteur = Connecteur(SITE)
    connecteur.traiter_horloge(json.dumps({"mode": "accelere", "facteur": 168}))
    assert connecteur.horloge["facteur"] == 168


def test_connecteur_ignore_une_horloge_mal_formee():
    connecteur = Connecteur(SITE)
    assert connecteur.traiter_horloge('{"mode": "turbo"}') is None
    assert connecteur.horloge is None


# ------------------------------------------------------------- vérificateur
def test_verificateur_signale_les_manquants():
    verificateur = Verificateur("SIM01", REFERENTIEL)
    verificateur.examiner("sasi/SIM01/CAM-Z1/mesures", mesures())
    equipements, cameras = verificateur.manquants()
    assert "CAM-Z7" in cameras and "Z7-CMP-01" in equipements


def test_verificateur_compte_les_defauts_par_code():
    verificateur = Verificateur("SIM01", REFERENTIEL)
    charge = mesures(zones=[{"equipement": "Z9-XXX-01", "t_max": 50.0}])
    verificateur.examiner("sasi/SIM01/CAM-Z1/mesures", charge)
    verificateur.examiner("sasi/SIM01/CAM-Z1/mesures", charge)
    assert verificateur.defauts["equipement_inconnu"] == 2


def test_verificateur_mesure_le_plus_grand_trou():
    verificateur = Verificateur("SIM01", REFERENTIEL)
    for secondes in (0, 10, 20, 200):
        verificateur.examiner("sasi/SIM01/CAM-Z1/mesures", mesures(horodatage=secondes))
    assert verificateur.cadences()["CAM-Z1"]["trou"] == 180


def test_rapport_sans_message_explique_quoi_verifier():
    rapport = Verificateur("SIM01", REFERENTIEL).rapport()
    assert "Aucun message reçu" in rapport


def test_rapport_conclut_sur_le_verdict():
    verificateur = Verificateur("SIM01", REFERENTIEL)
    verificateur.examiner("sasi/SIM01/CAM-Z1/mesures", mesures())
    assert "Contrat respecté" in verificateur.rapport()


# -------------------------------------------------------------- schémas JSON
def test_les_schemas_du_disque_ne_derivent_pas():
    """Les fichiers livrés doivent correspondre au contrat : à régénérer sinon.

        ./venv/bin/python integration/schemas.py
    """
    for nom, attendu in schemas.tous().items():
        chemin = schemas.DOSSIER / f"{nom}.json"
        assert chemin.exists(), f"{chemin.name} absent : régénérez les schémas"
        sur_disque = json.loads(chemin.read_text(encoding="utf-8"))
        assert sur_disque == attendu, f"{nom}.json a dérivé du contrat"


def test_les_schemas_couvrent_tous_les_messages():
    """Un sujet du contrat sans schéma serait un trou dans le kit."""
    sujets = contrat.sujets("SIM01")
    attendus = set(sujets["entrants"]) | set(sujets["sortants"])
    assert set(schemas.tous()) == attendus


def test_les_enumerations_viennent_du_contrat():
    tous = schemas.tous()
    assert tous["niveaux"]["properties"]["niveaux"][
        "additionalProperties"]["enum"] == list(contrat.NIVEAUX)
    assert tous["mesures"]["properties"]["source"]["enum"] == list(contrat.SOURCES)
    assert tous["contexte"]["properties"]["equipements"]["items"][
        "properties"]["etat"]["enum"] == list(contrat.ETATS_MARCHE)
    assert tous["pannes"]["properties"]["evenement"]["enum"] == list(
        contrat.EVENEMENTS_PANNE)


def test_les_schemas_acceptent_l_emetteur_de_reference():
    """Un schéma exigeant un champ que personne n'envoie ne vaut rien."""
    tous = schemas.tous()
    vus = set()
    for sujet, charge in collecter(pannes=["Z1-ELV-01:derive_lente:8"]):
        nature = contrat.genre(sujet)
        schema = tous[nature]
        vus.add(nature)
        for champ in schema["required"]:
            assert champ in charge, f"{nature} : champ « {champ} » exigé, non envoyé"
        for champ, regle in schema["properties"].items():
            if "enum" in regle and champ in charge:
                assert charge[champ] in regle["enum"], \
                    f"{nature}.{champ} = {charge[champ]!r} hors énumération"
    assert vus == {"mesures", "contexte", "pannes", "horloge"}


def test_les_schemas_acceptent_une_alerte_reelle():
    from alertes.moteur import MoteurAlertes
    moteur = MoteurAlertes()
    moteur.signaler("Z1-ELV-01", "inspection", 1789000000.0, {"raison": "essai"})
    resume = moteur.ouvertes["Z1-ELV-01"].resume()
    schema = schemas.tous()["alertes"]
    for champ in schema["required"]:
        assert champ in resume, f"champ « {champ} » exigé, absent du résumé publié"
    assert resume["niveau"] in schema["properties"]["niveau"]["enum"]
    assert resume["etat"] in schema["properties"]["etat"]["enum"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    echecs = 0
    for t in tests:
        try:
            t()
            print(f"  OK   {t.__name__}")
        except AssertionError as e:
            echecs += 1
            print(f"  ECHEC {t.__name__} : {e}")
    print(f"\n{len(tests) - echecs}/{len(tests)} tests réussis")
    sys.exit(1 if echecs else 0)
