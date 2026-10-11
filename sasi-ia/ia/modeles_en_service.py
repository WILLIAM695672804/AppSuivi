"""Enregistrement et chargement des modèles en service.

Après un entraînement, chaque famille reçoit son modèle et chaque équipement son
calibrage. Le service de l'IA les recharge au démarrage, ou sur demande.

Chaque entraînement crée une **version** ; l'une d'elles est en service. On peut
donc revenir à la précédente si la nouvelle se révèle moins bonne — la décision
appartient à la personne, jamais au programme.

    modeles/<site>/versions/v3/<famille>.txt   modèle LightGBM de la version 3
    modeles/<site>/versions/v3/modeles.json    entrées, erreurs, calibrages, date
    modeles/<site>/versions.json               liste des versions, celle en service
    modeles/<site>/<famille>.txt               copie de la version en service
"""

import json
import shutil
from datetime import datetime
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
MODELES = RACINE / "modeles"


def dossier(site):
    return MODELES / site.identifiant.lower()


def dossier_versions(site):
    return dossier(site) / "versions"


def fiche_versions(site):
    return dossier(site) / "versions.json"


def lire_versions(site):
    """Historique des entraînements. Le premier élément est le plus récent."""
    fiche = fiche_versions(site)
    if not fiche.exists():
        return {"en_service": None, "versions": []}
    return json.loads(fiche.read_text(encoding="utf-8"))


def _ecrire_versions(site, registre):
    fiche_versions(site).parent.mkdir(parents=True, exist_ok=True)
    fiche_versions(site).write_text(
        json.dumps(registre, ensure_ascii=False, indent=2), encoding="utf-8")


def prochaine_version(site):
    registre = lire_versions(site)
    numeros = [int(v["version"].lstrip("v")) for v in registre["versions"]
               if v["version"].lstrip("v").isdigit()]
    return f"v{max(numeros, default=0) + 1}"


def enregistrer_inspection(site, version, examen):
    """Range l'inspection auprès de la version qu'elle décrit."""
    cible = dossier_versions(site) / version
    cible.mkdir(parents=True, exist_ok=True)
    (cible / "inspection.json").write_text(
        json.dumps(examen, ensure_ascii=False, indent=2), encoding="utf-8")
    return cible / "inspection.json"


def lire_inspection(site, version=None):
    """Inspection d'une version, ou de celle en service. None si elle n'existe pas."""
    version = version or lire_versions(site)["en_service"]
    if not version:
        return None
    fiche = dossier_versions(site) / version / "inspection.json"
    if not fiche.exists():
        return None
    return json.loads(fiche.read_text(encoding="utf-8"))


def adopter_existant(site):
    """Récupère un modèle entraîné avant le versionnement, et en fait la version 1.

    Sans cela, l'historique commencerait à vide alors qu'un modèle tourne déjà.
    """
    registre = lire_versions(site)
    if registre["versions"]:
        return registre
    fiche = dossier(site) / "modeles.json"
    if not fiche.exists():
        return registre

    description = json.loads(fiche.read_text(encoding="utf-8"))
    version = "v1"
    cible = dossier_versions(site) / version
    cible.mkdir(parents=True, exist_ok=True)
    for famille in description.get("familles", []):
        source = dossier(site) / f"{famille}.txt"
        if source.exists():
            shutil.copy2(source, cible / f"{famille}.txt")
    description["version"] = version
    (cible / "modeles.json").write_text(
        json.dumps(description, ensure_ascii=False, indent=2), encoding="utf-8")

    erreurs = description.get("erreurs", {})
    registre = {"en_service": version, "versions": [{
        "version": version,
        "entraine_le": description.get("entraine_le"),
        "familles": description.get("familles", []),
        "erreurs": erreurs,
        "erreur_moyenne": (sum(erreurs.values()) / len(erreurs)) if erreurs else None,
        "periode": None, "mesures": None, "evaluation": None,
        "en_service": True,
    }]}
    _ecrire_versions(site, registre)
    return registre


def mettre_en_service(site, version):
    """Copie les fichiers de cette version à la racine, là où le service les lit."""
    registre = lire_versions(site)
    connues = {v["version"] for v in registre["versions"]}
    if version not in connues:
        raise ValueError(f"Version inconnue : {version}")

    source = dossier_versions(site) / version
    cible = dossier(site)
    for fichier in source.iterdir():
        shutil.copy2(fichier, cible / fichier.name)

    registre["en_service"] = version
    for fiche in registre["versions"]:
        fiche["en_service"] = fiche["version"] == version
    _ecrire_versions(site, registre)
    return cible


def enregistrer(site, modeles, calibrages, entrees, erreurs=None, en_service=True,
                periode=None, mesures=None, evaluation=None, retours=0):
    """Écrit une nouvelle version des modèles, et la met en service si demandé."""
    version = prochaine_version(site)
    cible = dossier_versions(site) / version
    cible.mkdir(parents=True, exist_ok=True)

    familles = []
    for famille, modele in sorted(modeles.items()):
        if hasattr(modele, "booster"):
            modele.booster.save_model(str(cible / f"{famille}.txt"))
            familles.append(famille)

    entraine_le = datetime.now().isoformat(timespec="seconds")
    (cible / "modeles.json").write_text(json.dumps({
        "site": site.identifiant,
        "version": version,
        "entraine_le": entraine_le,
        "entrees": list(entrees),
        "familles": familles,
        "erreurs": erreurs or {},
        "calibrages": calibrages,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    erreurs = erreurs or {}
    registre = lire_versions(site)
    registre["versions"].insert(0, {
        "version": version,
        "entraine_le": entraine_le,
        "familles": familles,
        "erreurs": erreurs,
        "erreur_moyenne": (sum(erreurs.values()) / len(erreurs)) if erreurs else None,
        "periode": periode,
        "mesures": mesures,
        "evaluation": evaluation,
        "retours": retours,          # corrections du terrain prises en compte
        "en_service": False,
    })
    _ecrire_versions(site, registre)

    if en_service:
        mettre_en_service(site, version)
    return cible


class ModeleEnService:
    """Modèle prêt à juger une mesure à la fois."""

    def __init__(self, booster, entrees):
        self.booster = booster
        self.entrees = list(entrees)

    def predire(self, valeurs):
        """valeurs : dictionnaire des entrées. Renvoie la température attendue."""
        return float(self.booster.predict(self._ligne(valeurs))[0])

    def predict(self, tableau):
        """Prédit un tableau entier de mesures, comme le modèle d'entraînement.

        Nécessaire pour inspecter le modèle en service sans le réentraîner.
        """
        valeurs = (tableau[self.entrees].to_numpy() if hasattr(tableau, "columns")
                   else tableau)
        return self.booster.predict(valeurs)

    def contributions(self, valeurs):
        """Part de chaque entrée dans la température attendue, en °C.

        LightGBM la calcule lui-même ; la dernière colonne est la valeur de
        départ du modèle, que l'explication ignore.
        """
        return self.booster.predict(self._ligne(valeurs), pred_contrib=True)[0]

    def _ligne(self, valeurs):
        return [[float(valeurs.get(nom, 0.0)) for nom in self.entrees]]


def charger(site):
    """Renvoie (modeles par famille, calibrages par équipement)."""
    import lightgbm as lgb

    cible = dossier(site)
    fiche = cible / "modeles.json"
    if not fiche.exists():
        raise FileNotFoundError(
            f"Aucun modèle pour {site.identifiant}. Lancez d'abord : "
            f"./venv/bin/python lancer_site.py {site.identifiant.lower()}")
    description = json.loads(fiche.read_text(encoding="utf-8"))
    entrees = description["entrees"]

    modeles = {}
    for famille in description["familles"]:
        chemin = cible / f"{famille}.txt"
        if chemin.exists():
            modeles[famille] = ModeleEnService(
                lgb.Booster(model_file=str(chemin)), entrees)
    return modeles, description.get("calibrages", {})
