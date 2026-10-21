"""Lance tous les tests du projet.

    python3 tests/lancer_tests.py            (tests qui n'ont besoin de rien)
    ./venv/bin/python tests/lancer_tests.py  (tous les tests)
"""

import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
FICHIERS = ["test_site.py", "test_detection.py", "test_explication.py", "test_controles.py",
            "test_evaluation.py", "test_simulateur.py", "test_connecteur.py", "test_moteur_alertes.py",
            "test_entrainement.py", "test_scenario_chaudiere.py", "test_chaine.py", "test_versions.py", "test_retours.py",
            "test_integration.py", "test_messagerie.py"]


def principal():
    total_ok = total = 0
    echecs = []
    for nom in FICHIERS:
        chemin = RACINE / "tests" / nom
        resultat = subprocess.run([sys.executable, str(chemin)],
                                  capture_output=True, text=True, cwd=RACINE)
        sortie = resultat.stdout.strip().splitlines()
        resume = next((l for l in reversed(sortie) if "tests réussis" in l or "IGNORÉ" in l), "")
        etat = "OK   " if resultat.returncode == 0 else "ECHEC"
        print(f"  {etat} {nom:24s} {resume.strip()}")
        if resultat.returncode != 0:
            echecs.append(nom)
            for ligne in sortie:
                if ligne.strip().startswith("ECHEC"):
                    print(f"          {ligne.strip()}")
        if "tests réussis" in resume:
            reussis, sur = resume.strip().split()[0].split("/")
            total_ok += int(reussis); total += int(sur)

    print(f"\n{total_ok}/{total} tests réussis dans {len(FICHIERS)} fichiers")
    if echecs:
        print("Fichiers en échec : " + ", ".join(echecs))
    return 1 if echecs else 0


if __name__ == "__main__":
    sys.exit(principal())
