"""Chaîne complète sur un site simulé.

    ./venv/bin/python lancer_site.py [nom du site]

Le site par défaut est « brasserie ». Tout fichier sites/<nom>.json convient.

Étapes :
  1. lecture du lot A (fonctionnement normal) et du lot B (avec pannes)
  2. entraînement d'un modèle par famille d'équipements, sur le lot A seulement
  3. calibrage de chaque équipement (l'équivalent de la période d'apprentissage)
  4. détection sur le lot B, jamais vu à l'entraînement
  5. comparaison au journal des pannes et rédaction du rapport
"""

from datetime import datetime
from pathlib import Path

import sys

from ia import chaine, evaluation
from ia import modeles_en_service

RACINE = Path(__file__).resolve().parent
RESULTATS = RACINE / "resultats"


def principal(nom_site="brasserie", lot_essai="B"):
    site = chaine.definir_site(nom_site)
    print(f"=== {site.resume()} ===")
    print("  Lecture du lot A (fonctionnement normal)...")
    # une mesure par minute suffit pour l'entraînement
    lot_a, controle_a = chaine.controler_lot(chaine.charger_lot("A", pas_secondes=60))
    lot_a = chaine.ajouter_entrees(lot_a)
    print(f"    {len(lot_a):,} mesures, {lot_a['equipement'].nunique()} équipements"
          .replace(",", " "))
    ecartees = controle_a["recues"] - controle_a["conservees"]
    print(f"    contrôles : {ecartees} mesure(s) écartée(s)")

    print("  Entraînement d'un modèle par famille :")
    modeles, erreurs = chaine.entrainer_par_famille(lot_a)
    calibrages = chaine.calibrer_par_equipement(lot_a, modeles)
    cible = modeles_en_service.enregistrer(site, modeles, calibrages, chaine.ENTREES, erreurs)
    print(f"    modèles enregistrés dans {cible.relative_to(Path.cwd())}"
          if str(cible).startswith(str(Path.cwd())) else f"    modèles enregistrés dans {cible}")

    print(f"  Lecture du lot {lot_essai} (avec pannes)...")
    lot_b, controle_b = chaine.controler_lot(chaine.charger_lot(lot_essai, pas_secondes=10))
    lot_b = chaine.ajouter_entrees(lot_b)
    print(f"    {len(lot_b):,} mesures".replace(",", " ")
          + f", {controle_b['recues'] - controle_b['conservees']} écartée(s) par les contrôles")

    print("  Détection...")
    episodes, depart, etats = chaine.detecter(lot_b, modeles, calibrages)
    episodes = chaine.expliquer_episodes(episodes, etats, lot_b, modeles)
    fenetres = chaine.fenetres_journal(depart, lot_essai)
    resultat = evaluation.evaluer_episodes(episodes, fenetres)

    print(f"\n  Pannes détectées : {resultat['pannes_detectees']}/{resultat['pannes']} "
          f"({evaluation.pourcentage(resultat['taux_detection'])})")
    print(f"  Épisodes d'alerte : {resultat['alertes']} "
          f"— dont {resultat['suites_de_panne']} pendant le refroidissement qui suit une panne")
    print(f"  Fausses alertes : {resultat['fausses_alertes']} "
          f"({evaluation.pourcentage(resultat['part_fausses_alertes'])})")
    print(f"  Délai médian de détection : {evaluation.duree(resultat['delai_median_s'])}")
    print("\n  Détail par panne :")
    for ligne in resultat["detail"]:
        etat = "détectée en " + evaluation.duree(ligne["delai_s"]) if ligne["detectee"] else "NON détectée"
        print(f"    {ligne['id']} {ligne['equipement']:12s} {ligne['type']:22s} {etat}")

    print("\n  Exemple d'alerte expliquée :")
    for episode in episodes:
        if episode.get("raison") and episode["niveau_max"] in ("inspection", "urgence"):
            print(f"    Niveau     : {episode['niveau_max'].upper()}")
            print(f"    Raison     : {episode['raison']}")
            for facteur in episode.get("facteurs", []):
                print(f"    Facteur    : {facteur}")
            print(f"    Action     : {episode['action']}")
            break

    ecrire_rapport(resultat, erreurs, episodes, lot_essai)
    return resultat


def ecrire_rapport(resultat, erreurs, episodes=(), lot_essai="B"):
    RESULTATS.mkdir(parents=True, exist_ok=True)
    lignes = [
        f"# Projet SASI — IA version 0 : résultats sur {chaine.SITE.nom}",
        "",
        f"Date : {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        "",
        "## Méthode",
        "",
        "Un modèle par famille apprend la température normale de chaque équipement à partir de "
        "son contexte (charge, marche/arrêt, ambiance, temps depuis le démarrage, heure). "
        "Chaque équipement est ensuite calibré sur ses propres mesures. Les écarts persistants "
        "déclenchent une alerte (cahier des charges technique, chapitre 6).",
        "",
        "- Entraînement : lot A, 14 jours de fonctionnement normal, aucune panne.",
        f"- Test : lot {lot_essai}, jamais vu, contenant {resultat['pannes']} pannes.",
        "",
        "## Erreur de prédiction par famille",
        "",
        "| Famille | Erreur moyenne |",
        "|---|---|",
    ]
    for nom, erreur in sorted(erreurs.items()):
        lignes.append(f"| {nom} | {erreur:.2f} °C |")
    lignes += [
        "",
        "## Résultats de détection",
        "",
        evaluation.ligne_rapport(f"Lot {lot_essai} — {resultat['pannes']} pannes simulées", resultat),
        "## Détail par panne",
        "",
        "| Panne | Équipement | Type | Détectée | Délai |",
        "|---|---|---|---|---|",
    ]
    for ligne in resultat["detail"]:
        lignes.append(
            f"| {ligne['id']} | {ligne['equipement']} | {ligne['type']} | "
            f"{'oui' if ligne['detectee'] else 'non'} | {evaluation.duree(ligne['delai_s'])} |")
    exemples = [e for e in episodes
                if e.get("raison") and e["niveau_max"] in ("inspection", "urgence")][:3]
    if exemples:
        lignes += ["", "## Exemples d'alertes expliquées", ""]
        for episode in exemples:
            lignes += [f"**{episode['niveau_max'].upper()} — {episode['equipement']}**", "",
                       f"- Raison : {episode['raison']}"]
            for facteur in episode.get("facteurs", []):
                lignes.append(f"- Facteur : {facteur}")
            lignes += [f"- Action conseillée : {episode['action']}", ""]

    lignes += [
        "",
        "## Limites",
        "",
        "- Les données sont simulées par nos soins : elles suivent nos propres hypothèses.",
        "- Un bon résultat prouve que la chaîne fonctionne, pas que l'IA réussira sur site.",
        "- Étape suivante : rejouer cette évaluation sur les lots livrés par le jumeau "
        "numérique, puis sur les mesures d'un site réel.",
        "",
    ]
    suffixe = "" if lot_essai == "B" else f"_{lot_essai.lower()}"
    chemin = RESULTATS / f"rapport_{chaine.SITE.identifiant.lower()}{suffixe}.md"
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    print(f"\nRapport écrit : {chemin}")


if __name__ == "__main__":
    principal(sys.argv[1] if len(sys.argv) > 1 else "brasserie",
              sys.argv[2] if len(sys.argv) > 2 else "B")
