"""Contrôle de structure des fichiers JSX, sans rien installer.

Ce n'est pas un compilateur : c'est un analyseur qui parcourt le fichier
caractère par caractère, en tenant compte des chaînes, des commentaires et des
accolades imbriquées. Il détecte ce qui casse le plus souvent une page :
balise non fermée, balise fermée en trop, accolade ou parenthèse orpheline.

    python3 outils/verifier_jsx.py frontend/src
"""

import re
import sys
from pathlib import Path

BALISE = re.compile(r"[A-Za-z][A-Za-z0-9.]*")


def analyser(texte):
    """Renvoie la liste des anomalies trouvées dans un fichier."""
    anomalies = []
    pile = []                      # balises ouvertes
    profondeurs = {"{": 0, "(": 0, "[": 0}
    fermants = {"}": "{", ")": "(", "]": "["}
    i, n, ligne = 0, len(texte), 1

    while i < n:
        c = texte[i]

        if c == "\n":
            ligne += 1
            i += 1
            continue

        # commentaires
        if texte.startswith("//", i):
            i = texte.find("\n", i)
            if i == -1:
                break
            continue
        if texte.startswith("/*", i):
            fin = texte.find("*/", i + 2)
            ligne += texte.count("\n", i, fin if fin > 0 else n)
            i = (fin + 2) if fin > 0 else n
            continue

        # chaînes
        if c in "\"'`":
            fin = i + 1
            while fin < n:
                if texte[fin] == "\\":
                    fin += 2
                    continue
                if texte[fin] == c:
                    break
                fin += 1
            ligne += texte.count("\n", i, fin)
            i = fin + 1
            continue

        if c in "{([":
            profondeurs[c] += 1
            i += 1
            continue
        if c in ")]}":
            ouvrant = fermants[c]
            profondeurs[ouvrant] -= 1
            if profondeurs[ouvrant] < 0:
                anomalies.append(f"ligne {ligne} : « {c} » en trop")
                profondeurs[ouvrant] = 0
            i += 1
            continue

        # balises
        if c == "<":
            reste = texte[i + 1:]
            fermante = reste.startswith("/")
            debut_nom = i + 2 if fermante else i + 1
            correspondance = BALISE.match(texte, debut_nom)
            if not correspondance:
                i += 1
                continue
            nom = correspondance.group(0)
            # on avance jusqu'au « > » correspondant, en ignorant chaînes et accolades
            j, accolades = correspondance.end(), 0
            while j < n:
                d = texte[j]
                if d == "\n":
                    ligne += 1
                elif d in "\"'`":
                    k = j + 1
                    while k < n and texte[k] != d:
                        k += 2 if texte[k] == "\\" else 1
                    ligne += texte.count("\n", j, k)
                    j = k
                elif d == "{":
                    accolades += 1
                elif d == "}":
                    accolades -= 1
                elif d == ">" and accolades == 0:
                    break
                j += 1
            autoferme = texte[j - 1] == "/" if j < n else False
            if fermante:
                if not pile:
                    anomalies.append(f"ligne {ligne} : </{nom}> sans balise ouvrante")
                elif pile[-1][0] != nom:
                    anomalies.append(
                        f"ligne {ligne} : </{nom}> alors que <{pile[-1][0]}> "
                        f"(ligne {pile[-1][1]}) est encore ouverte")
                    pile.pop()
                else:
                    pile.pop()
            elif not autoferme:
                pile.append((nom, ligne))
            i = j + 1
            continue

        i += 1

    for nom, ouverture in pile:
        anomalies.append(f"ligne {ouverture} : <{nom}> jamais fermée")
    for ouvrant, profondeur in profondeurs.items():
        if profondeur:
            anomalies.append(f"{profondeur} « {ouvrant} » non refermé(s)")
    return anomalies


def principal(cible):
    fichiers = sorted(Path(cible).rglob("*.jsx")) if Path(cible).is_dir() else [Path(cible)]
    total = 0
    for fichier in fichiers:
        anomalies = analyser(fichier.read_text(encoding="utf-8"))
        etat = "OK   " if not anomalies else "ECHEC"
        print(f"  {etat} {fichier}")
        for anomalie in anomalies:
            print(f"          {anomalie}")
        total += len(anomalies)
    print(f"\n{len(fichiers)} fichier(s), {total} anomalie(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv[1] if len(sys.argv) > 1 else "frontend/src"))
