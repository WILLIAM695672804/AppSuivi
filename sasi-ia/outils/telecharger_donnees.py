"""Téléchargement des jeux de données publics.

N'utilise que Python : à lancer AVANT d'installer les bibliothèques.

    python3 outils/telecharger_donnees.py

Télécharge :
  - SKAB : banc de pompe (température, courant, tension, pression, vibration)
           avec anomalies étiquetées.   ~ 15 à 30 Mo
  - NAB  : température d'une machine industrielle réelle, pannes connues.
           ~ 1 Mo
"""

import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
DOSSIER = RACINE / "donnees"

SKAB_ZIP = "https://github.com/waico/SKAB/archive/refs/heads/master.zip"
NAB_MESURES = ("https://raw.githubusercontent.com/numenta/NAB/master/"
               "data/realKnownCause/machine_temperature_system_failure.csv")
NAB_ETIQUETTES = ("https://raw.githubusercontent.com/numenta/NAB/master/"
                  "labels/combined_windows.json")


def telecharger(url, description):
    print(f"  Téléchargement : {description}")
    print(f"    {url}")
    try:
        with urllib.request.urlopen(url, timeout=120) as reponse:
            contenu = reponse.read()
        print(f"    reçu : {len(contenu) / 1_000_000:.1f} Mo")
        return contenu
    except Exception as erreur:
        print(f"    ECHEC : {erreur}")
        return None


def installer_skab():
    cible = DOSSIER / "skab"
    if (cible / "anomaly-free").exists():
        print("  SKAB déjà présent, téléchargement ignoré.")
        return True
    contenu = telecharger(SKAB_ZIP, "SKAB (archive complète)")
    if contenu is None:
        return False
    cible.mkdir(parents=True, exist_ok=True)
    nb = 0
    with zipfile.ZipFile(io.BytesIO(contenu)) as archive:
        for nom in archive.namelist():
            if not nom.lower().endswith(".csv") or "/data/" not in nom.replace("\\", "/"):
                continue
            chemin_interne = nom.split("/data/", 1)[1]
            destination = cible / chemin_interne
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(nom))
            nb += 1
    print(f"    {nb} fichiers de mesures enregistrés dans {cible}")
    return nb > 0


def installer_nab():
    cible = DOSSIER / "nab"
    cible.mkdir(parents=True, exist_ok=True)
    mesures = telecharger(NAB_MESURES, "NAB (température d'une machine)")
    if mesures is None:
        return False
    (cible / "machine_temperature_system_failure.csv").write_bytes(mesures)

    etiquettes = telecharger(NAB_ETIQUETTES, "NAB (périodes de panne connues)")
    if etiquettes is None:
        return False
    toutes = json.loads(etiquettes)
    clef = "realKnownCause/machine_temperature_system_failure.csv"
    fenetres = toutes.get(clef, [])
    (cible / "fenetres_pannes.json").write_text(json.dumps(fenetres, indent=2))
    print(f"    {len(fenetres)} périodes de panne connues enregistrées")
    return True


if __name__ == "__main__":
    DOSSIER.mkdir(parents=True, exist_ok=True)
    print("Téléchargement des jeux de données publics\n")
    ok_skab = installer_skab()
    print()
    ok_nab = installer_nab()
    print()
    if ok_skab and ok_nab:
        print("Terminé. Les données sont dans le dossier donnees/.")
    else:
        print("Certains téléchargements ont échoué.")
        print("Vous pouvez aussi télécharger les fichiers à la main :")
        print(f"  SKAB : {SKAB_ZIP}  (décompresser le dossier data/ dans donnees/skab/)")
        print(f"  NAB  : {NAB_MESURES}  (enregistrer dans donnees/nab/)")
        sys.exit(1)
