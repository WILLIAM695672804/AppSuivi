"""Liste de référence des équipements : la seule source de vérité des noms.

L'application la tient, le jumeau la relit au démarrage (conventions, 6.6). On
évite ainsi la double saisie, qui produit tôt ou tard « Z4-ARM-1 » d'un côté et
« Z4-ARM-01 » de l'autre.

    from integration import referentiel
    fiche = referentiel.charger()                       # l'API, sinon le fichier de site
    fiche = referentiel.charger("http://boitier:8000/api/referentiel")
    fiche = referentiel.charger("referentiel_SIM01.json")
"""

import json
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
ADRESSE_PAR_DEFAUT = "http://localhost:8000/api/referentiel"

VERSION = 1              # à incrémenter dès qu'un équipement est ajouté ou renommé


def depuis_site(site, version=VERSION):
    """Construit la liste de référence à partir d'un objet Site."""
    equipements = []
    for identifiant in site.liste():
        fiche = site.equipements[identifiant]
        inspection, urgence = site.seuils_fixes(identifiant)
        equipements.append({
            "id": identifiant,
            "nom": site.nom_equipement(identifiant),
            "zone": site.zone(identifiant),
            "famille": site.famille(identifiant),
            "camera": site.camera(identifiant),
            "criticite": site.criticite(identifiant),
            # Position sur le plan : renseignée depuis l'écran d'administration,
            # absente tant que personne ne l'a placé.
            "position_plan": fiche.get("position_plan"),
            "t_normale_indicative": [fiche["plage_basse"], fiche["plage_haute"]],
            "temps_montee_min": fiche["temps_montee_min"],
            "seuil_inspection": inspection,
            "seuil_urgence": urgence,
        })
    return {
        "site": site.identifiant,
        "nom_site": site.nom,
        "version": version,
        "zones": {str(numero): nom for numero, nom in site.zones.items()},
        "familles": dict(site.familles),
        "equipements": equipements,
    }


def charger(source=None, site_defaut="brasserie", delai=3.0):
    """Charge la liste de référence : adresse HTTP, fichier, ou site local.

    Sans argument, on interroge l'application ; si elle ne répond pas, on se
    rabat sur le fichier de site, ce qui permet de travailler hors ligne.
    """
    if source and str(source).startswith(("http://", "https://")):
        return _par_http(source, delai)
    if source:
        return json.loads(Path(source).read_text(encoding="utf-8"))
    try:
        return _par_http(ADRESSE_PAR_DEFAUT, delai)
    except OSError:
        from ia.site import Site
        return depuis_site(Site.charger(site_defaut))


def _par_http(adresse, delai):
    import urllib.request
    with urllib.request.urlopen(adresse, timeout=delai) as reponse:
        return json.loads(reponse.read().decode("utf-8"))


def ecrire(chemin, fiche):
    """Enregistre la liste, pour la remettre à l'équipe du jumeau."""
    chemin = Path(chemin)
    chemin.write_text(json.dumps(fiche, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    return chemin


if __name__ == "__main__":
    import sys

    nom_site = sys.argv[1] if len(sys.argv) > 1 else "brasserie"
    sys.path.insert(0, str(RACINE))
    from ia.site import Site

    fiche = depuis_site(Site.charger(nom_site))
    chemin = ecrire(Path(__file__).parent / f"referentiel_{fiche['site']}.json", fiche)
    print(f"{len(fiche['equipements'])} équipements, {len(fiche['zones'])} zones "
          f"→ {chemin.relative_to(RACINE)}")
