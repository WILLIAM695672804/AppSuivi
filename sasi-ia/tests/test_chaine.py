"""Tests de la chaîne complète, dans un seul programme.

Le serveur de messages est remplacé par l'aiguilleur en mémoire de
outils/verifier_chaine.py : connecteur → IA → alertes → registre → écrans, puis
les commandes dans l'autre sens. Aucun logiciel à installer.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ia.site import Site
from outils.verifier_chaine import EQUIPEMENT, Courtier, monter, jouer

SITE = Site.charger("brasserie")
DEBUT = 1767600000.0            # 5 janvier 2026, heure fixe : tests reproductibles


def chaine():
    """Monte la chaîne, joue l'échauffement, renvoie tout ce qui a circulé."""
    courtier, connecteur, ia, alertes, registre, ecrans = monter(SITE)
    fin = jouer(courtier, connecteur, ia, SITE, DEBUT)
    return courtier, connecteur, alertes, registre, ecrans, fin


def sujet(nom):
    return f"sasi/{SITE.identifiant}/{nom}"


def test_courtier_distribue_par_sujet():
    courtier = Courtier()
    recus = []
    courtier.abonner("a/b", lambda s, f: recus.append(f))
    courtier.publier("a/b", json.dumps({"x": 1}))
    courtier.publier("a/c", json.dumps({"x": 2}))
    assert recus == [{"x": 1}], recus


def test_mesures_traversent_le_connecteur():
    courtier, connecteur, *_ = chaine()
    assert connecteur.compteurs["ecartees"] == 0, connecteur.compteurs
    assert courtier.messages(sujet("interne/mesures_validees")), "aucune mesure republiée"


def test_ia_escalade_jusqu_a_urgence():
    courtier, *_ = chaine()
    niveaux = [m["niveau"] for m in courtier.messages(sujet("interne/niveaux"))]
    assert niveaux[0] == "surveillance", niveaux
    assert "urgence" in niveaux, niveaux


def test_chaque_changement_porte_une_explication():
    courtier, *_ = chaine()
    for message in courtier.messages(sujet("interne/niveaux")):
        assert message.get("raison"), message
        assert message.get("action"), message


def test_alerte_ouverte_et_publiee():
    _, _, alertes, registre, _, _ = chaine()
    assert EQUIPEMENT in alertes.moteur.ouvertes
    assert registre.liste_alertes(), "le registre du serveur ignore l'alerte"
    assert registre.niveaux[EQUIPEMENT] == "urgence", registre.niveaux[EQUIPEMENT]


def test_alerte_porte_les_chiffres_du_jugement():
    """La fiche d'alerte affiche la température mesurée, l'attendue et l'écart."""
    _, _, _, registre, _, _ = chaine()
    fiche = registre.liste_alertes()[0]
    assert fiche["t_mesuree"] is not None, fiche
    assert fiche["t_attendue"] is not None, fiche
    assert fiche["t_mesuree"] > fiche["t_attendue"], "l'alerte vient d'un échauffement"
    assert fiche["score"], fiche
    assert fiche["evenements"], "la fiche doit porter la vie de l'alerte"
    # les facteurs viennent de LightGBM : vides ici, le modèle d'essai n'en fournit pas
    assert "facteurs" in fiche, fiche


def test_ecrans_recoivent_les_changements():
    *_, ecrans, _ = chaine()
    types = [m["type"] for m in ecrans if m]
    assert "alerte" in types and "niveaux" in types, types


def test_acquittement_puis_assignation():
    courtier, _, alertes, registre, _, fin = chaine()
    courtier.publier(sujet("commandes"),
                     registre.commande("acquitter", EQUIPEMENT, par="agent", secondes=fin))
    assert registre.liste_alertes()[0]["etat"] == "acquittee"
    courtier.publier(sujet("commandes"),
                     registre.commande("assigner", EQUIPEMENT, par="agent",
                                       a_qui="technicien", secondes=fin + 60))
    assert registre.liste_alertes()[0]["assignee_a"] == "technicien"


def test_cloture_sans_compte_rendu_refusee():
    courtier, _, alertes, registre, _, fin = chaine()
    courtier.publier(sujet("commandes"),
                     registre.commande("acquitter", EQUIPEMENT, par="agent", secondes=fin))
    avant = len(courtier.messages(sujet("alertes")))
    courtier.publier(sujet("commandes"),
                     registre.commande("cloturer", EQUIPEMENT, par="agent",
                                       constat="", justifiee=True, secondes=fin + 60))
    refus = [m for m in courtier.messages(sujet("alertes"))[avant:] if m.get("erreur")]
    assert refus, "la clôture sans compte rendu doit être refusée"
    assert EQUIPEMENT in alertes.moteur.ouvertes, "l'alerte doit rester ouverte"


def test_cloture_complete_ferme_partout():
    courtier, _, alertes, registre, ecrans, fin = chaine()
    courtier.publier(sujet("commandes"),
                     registre.commande("acquitter", EQUIPEMENT, par="agent", secondes=fin))
    courtier.publier(sujet("commandes"),
                     registre.commande("cloturer", EQUIPEMENT, par="agent",
                                       constat="Roulement remplacé.", justifiee=True,
                                       secondes=fin + 60))
    assert EQUIPEMENT not in alertes.moteur.ouvertes
    assert registre.liste_alertes()[0]["etat"] == "cloturee"
    assert any(m and m["type"] == "alerte" and m["alerte"]["etat"] == "cloturee"
               for m in ecrans), "la clôture doit remonter aux écrans"


def test_serie_disponible_sans_base():
    """Les courbes de l'interface se servent du tampon du serveur."""
    _, _, _, registre, _, _ = chaine()
    serie = registre.serie(EQUIPEMENT, heures=24)
    assert len(serie) > 100, len(serie)
    assert serie[-1] is list(registre.series[EQUIPEMENT])[-1], "le dernier point doit être servi"
    assert all(p["t_max"] is not None and p["t_attendue"] is not None for p in serie)
    assert serie[0]["secondes"] < serie[-1]["secondes"], "les points doivent être dans l'ordre"


def test_serie_plafonnee_pour_le_navigateur():
    """Dix-sept courbes de milliers de points figeraient l'affichage."""
    _, _, _, registre, _, _ = chaine()
    serie = registre.serie(EQUIPEMENT, heures=24, maximum=50)
    assert len(serie) == 50, len(serie)
    secondes = [p["secondes"] for p in serie]
    assert secondes == sorted(secondes), "les points doivent rester dans l'ordre"


def test_jugements_non_diffuses_aux_ecrans():
    *_, ecrans, _ = chaine()
    assert all(m is None or m["type"] in ("alerte", "niveaux", "technique", "erreur")
               for m in ecrans)


def test_maintenance_transmise():
    courtier, _, alertes, registre, _, fin = chaine()
    courtier.publier(sujet("commandes"),
                     registre.commande("maintenance", EQUIPEMENT, en_maintenance=True,
                                       secondes=fin))
    assert EQUIPEMENT in alertes.moteur.en_maintenance


def test_mesure_impossible_ecartee_et_signalee():
    courtier, connecteur, _, registre, _, fin = chaine()
    ecartees = connecteur.compteurs["ecartees"]
    connecteur.traiter_message(
        sujet("CAM-Z1/mesures"),
        json.dumps({"camera": "CAM-Z1", "zones": [{"equipement": EQUIPEMENT, "t_max": 5000}]}),
        maintenant=fin)
    assert connecteur.compteurs["ecartees"] == ecartees + 1
    assert registre.techniques, "l'écart doit remonter en alerte technique"


def test_registre_ignore_un_message_illisible():
    _, _, _, registre, _, _ = chaine()
    assert registre.appliquer(sujet("alertes"), "{pas du json") is None


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
