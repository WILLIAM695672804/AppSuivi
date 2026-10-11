"""Importe le système visuel SASI dans l'application.

Le système de design vit dans un artefact ; ce programme en recopie les fichiers
dans web/systeme/ et reconstruit la feuille de jetons (tokens.css), que
l'artefact produit de son côté et ne publie pas.

    python3 outils/importer_systeme.py [dossier du systeme]

Sans argument, il régénère seulement tokens.css à partir de web/systeme/tokens.json.
"""

import json
import re
import shutil
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
CIBLE = RACINE / "web" / "systeme"

FAMILLES = ("color", "spacing", "radius", "shadow", "size")


def jetons_css(tokens, theme):
    lignes = []
    for famille in FAMILLES:
        for jeton in tokens.get(famille, {}).get("tokens", []):
            valeur = jeton["value"]
            if isinstance(valeur, dict):
                valeur = valeur.get(theme, valeur.get("light"))
            lignes.append(f"  --{jeton['name']}: {valeur};")
    for nom, valeur in tokens["type"]["families"].items():
        lignes.append(f"  --font-{nom}: {valeur};")
    return lignes


def construire_tokens_css(chemin_tokens=None):
    chemin_tokens = Path(chemin_tokens or CIBLE / "tokens.json")
    tokens = json.loads(chemin_tokens.read_text(encoding="utf-8"))
    texte = "\n".join(
        ["/* Produit par outils/importer_systeme.py — ne pas modifier à la main. */",
         ":root {"] + jetons_css(tokens, "light") + ["}", '[data-theme="dark"] {']
        + jetons_css(tokens, "dark") + ["}"])
    # les alias « {autre-jeton} » deviennent des var(--autre-jeton)
    for _ in range(3):
        texte = re.sub(r"\{([a-z0-9-]+)\}", lambda m: f"var(--{m.group(1)})", texte)
    (CIBLE / "tokens.css").write_text(texte, encoding="utf-8")
    return CIBLE / "tokens.css"


def importer(source):
    """Recopie bundle, bibliothèques et jetons depuis un dossier « project/ »."""
    source = Path(source)
    (CIBLE / "lib").mkdir(parents=True, exist_ok=True)
    for chemin in ("components/bundle.css", "components/bundle.js", "tokens.json"):
        shutil.copy(source / chemin, CIBLE / Path(chemin).name)
    for chemin in (source / "components" / "lib").glob("*.js"):
        shutil.copy(chemin, CIBLE / "lib" / chemin.name)
    return construire_tokens_css()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        chemin = importer(sys.argv[1])
    else:
        chemin = construire_tokens_css()
    print(f"Système visuel prêt : {chemin}")
