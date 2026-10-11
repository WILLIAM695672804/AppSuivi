"""Verse la description d'un site dans la base : sites, zones, familles, caméras, équipements.

    ./venv/bin/python outils/initialiser_base.py
    ./venv/bin/python outils/initialiser_base.py minoterie --base postgresql://…
    ./venv/bin/python outils/initialiser_base.py --verifier      sans rien écrire

Sans cette étape, rien ne peut être enregistré : les mesures, les prédictions et
les alertes renvoient toutes à un équipement, qui renvoie lui-même à une zone, à
une famille et à une caméra. Une base dont les tables de référence sont vides
refuse la première mesure venue.

Le fichier `sites/<site>.json` fait foi. On peut relancer ce programme autant de
fois qu'on veut : les lignes déjà présentes sont mises à jour, jamais dupliquées.
Les mesures, elles, ne sont pas touchées.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ia.site import Site

RACINE = Path(__file__).resolve().parents[1]

TABLES_DE_REFERENCE = ("site", "zone", "famille", "camera", "equipement")


def verser(site, adresse):
    """Écrit la description du site. Renvoie le compte par table."""
    import psycopg

    comptes = {}
    with psycopg.connect(adresse) as connexion, connexion.cursor() as curseur:
        curseur.execute(
            "INSERT INTO site (id, nom, secteur) VALUES (%s, %s, %s)"
            " ON CONFLICT (id) DO UPDATE SET nom = EXCLUDED.nom,"
            " secteur = EXCLUDED.secteur",
            (site.identifiant, site.nom, site.secteur))
        comptes["site"] = 1

        for numero, nom in sorted(site.zones.items(), key=lambda z: int(z[0])):
            curseur.execute(
                "INSERT INTO zone (site, numero, nom) VALUES (%s, %s, %s)"
                " ON CONFLICT (site, numero) DO UPDATE SET nom = EXCLUDED.nom",
                (site.identifiant, int(numero), nom))
        comptes["zone"] = len(site.zones)

        for code, nom in sorted(site.familles.items()):
            curseur.execute(
                "INSERT INTO famille (code, nom) VALUES (%s, %s)"
                " ON CONFLICT (code) DO UPDATE SET nom = EXCLUDED.nom",
                (code, nom))
        comptes["famille"] = len(site.familles)

        # Les caméras ne sont pas décrites une à une dans le fichier de site :
        # on les déduit des équipements qu'elles surveillent.
        cameras = {}
        for identifiant in site.liste():
            cameras.setdefault(site.camera(identifiant), site.zone(identifiant))
        for nom_camera, zone in sorted(cameras.items()):
            curseur.execute(
                "INSERT INTO camera (id, site, zone, adaptateur) VALUES (%s, %s, %s, %s)"
                " ON CONFLICT (id) DO UPDATE SET site = EXCLUDED.site,"
                " zone = EXCLUDED.zone",
                (nom_camera, site.identifiant, zone, "jumeau"))
        comptes["camera"] = len(cameras)

        for identifiant in site.liste():
            fiche = site.equipements[identifiant]
            inspection, urgence = site.seuils_fixes(identifiant)
            curseur.execute(
                "INSERT INTO equipement (id, site, nom, zone, famille, camera,"
                " criticite, plage_basse, plage_haute, temps_montee_min,"
                " seuil_inspection, seuil_urgence, action_conseillee)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (id) DO UPDATE SET nom = EXCLUDED.nom,"
                " zone = EXCLUDED.zone, famille = EXCLUDED.famille,"
                " camera = EXCLUDED.camera, criticite = EXCLUDED.criticite,"
                " plage_basse = EXCLUDED.plage_basse,"
                " plage_haute = EXCLUDED.plage_haute,"
                " temps_montee_min = EXCLUDED.temps_montee_min,"
                " seuil_inspection = EXCLUDED.seuil_inspection,"
                " seuil_urgence = EXCLUDED.seuil_urgence,"
                " action_conseillee = EXCLUDED.action_conseillee",
                (identifiant, site.identifiant, site.nom_equipement(identifiant),
                 site.zone(identifiant), site.famille(identifiant),
                 site.camera(identifiant), site.criticite(identifiant),
                 fiche["plage_basse"], fiche["plage_haute"],
                 fiche["temps_montee_min"], inspection, urgence,
                 site.action_specifique(identifiant)))
        comptes["equipement"] = len(site.liste())

        # Groupes d'équipements jumeaux : les phases d'une même armoire se
        # comparent entre elles, encore faut-il savoir lesquelles vont ensemble.
        groupes = 0
        for identifiant in site.liste():
            jumeaux = site.jumeaux(identifiant)
            if not jumeaux:
                continue
            nom_groupe = identifiant.rsplit("-", 1)[0]
            curseur.execute(
                "INSERT INTO groupe_jumeaux (nom, equipement) VALUES (%s, %s)"
                " ON CONFLICT (nom, equipement) DO NOTHING",
                (nom_groupe, identifiant))
            groupes += 1
        comptes["groupe_jumeaux"] = groupes
        connexion.commit()
    return comptes


def verifier(adresse):
    """Compte ce que contient déjà la base, sans rien écrire."""
    import psycopg

    comptes = {}
    with psycopg.connect(adresse) as connexion, connexion.cursor() as curseur:
        for table in TABLES_DE_REFERENCE + ("mesure", "prediction", "alerte"):
            try:
                curseur.execute(f"SELECT count(*) FROM {table}")
                comptes[table] = curseur.fetchone()[0]
            except Exception:
                connexion.rollback()
                comptes[table] = None          # table absente
    return comptes


def principal(nom_site="brasserie", adresse=None, controle_seul=False):
    adresse = adresse or os.environ.get("SASI_BASE")
    if not adresse:
        print("Aucune adresse de base. Indiquez --base, ou définissez SASI_BASE :")
        print("  export SASI_BASE=postgresql://sasi:sasi@localhost:5432/sasi")
        return 1

    try:
        import psycopg                                        # noqa: F401
    except ImportError:
        print("psycopg manquant : ./venv/bin/pip install 'psycopg[binary]'")
        return 1

    if controle_seul:
        print("Contenu de la base :")
        for table, nombre in verifier(adresse).items():
            etat = "table absente" if nombre is None else f"{nombre} ligne(s)"
            print(f"  {table:16s} {etat}")
        return 0

    site = Site.charger(nom_site)
    print(f"Versement de « {site.nom} » ({site.identifiant}) dans la base…")
    comptes = verser(site, adresse)
    for table, nombre in comptes.items():
        print(f"  {table:16s} {nombre} ligne(s)")
    print("\nLa base connaît maintenant le site : les mesures peuvent y entrer.")
    return 0


if __name__ == "__main__":
    analyseur = argparse.ArgumentParser(
        description="Verse la description d'un site dans la base de données")
    analyseur.add_argument("site", nargs="?", default="brasserie")
    analyseur.add_argument("--base", default=None,
                           help="adresse PostgreSQL (défaut : variable SASI_BASE)")
    analyseur.add_argument("--verifier", action="store_true",
                           help="compter ce que contient la base, sans rien écrire")
    arguments = analyseur.parse_args()
    sys.exit(principal(arguments.site, arguments.base, arguments.verifier))
