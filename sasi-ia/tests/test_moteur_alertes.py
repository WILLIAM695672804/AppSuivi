"""Tests du moteur d'alertes. N'utilise que Python."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from alertes.moteur import MoteurAlertes

EQ = "Z1-ELV-01"
EXPLICATION = {"raison": "Le moteur est 18 °C plus chaud que d'habitude.",
               "action": "Contrôler les roulements."}


def test_creation_d_alerte():
    m = MoteurAlertes()
    m.signaler(EQ, "surveillance", 100, EXPLICATION)
    ouvertes = m.alertes_ouvertes()
    assert len(ouvertes) == 1 and ouvertes[0]["niveau"] == "surveillance", ouvertes
    assert ouvertes[0]["raison"] == EXPLICATION["raison"]


def test_une_seule_alerte_par_equipement():
    m = MoteurAlertes()
    m.signaler(EQ, "surveillance", 100)
    m.signaler(EQ, "surveillance", 200)
    assert len(m.alertes_ouvertes()) == 1


def test_montee_de_niveau():
    m = MoteurAlertes()
    m.signaler(EQ, "surveillance", 100)
    envois = m.signaler(EQ, "urgence", 300)
    assert m.alertes_ouvertes()[0]["niveau"] == "urgence"
    assert any(e["canal"] == "sms" for e in envois), envois


def test_niveau_ne_redescend_pas_seul():
    m = MoteurAlertes()
    m.signaler(EQ, "urgence", 100)
    m.signaler(EQ, "information", 200)
    assert m.alertes_ouvertes()[0]["niveau"] == "urgence"


def test_information_ne_notifie_pas():
    m = MoteurAlertes()
    envois = m.signaler(EQ, "information", 100)
    assert envois == [], envois


def test_inspection_envoie_un_sms():
    m = MoteurAlertes()
    envois = m.signaler(EQ, "inspection", 100)
    assert {e["canal"] for e in envois} == {"notification", "sms"}, envois


def test_anti_rafale():
    m = MoteurAlertes()
    m.signaler(EQ, "inspection", 100)
    m.cloturer(EQ, 200, "technicien", "vérifié", True)
    envois = m.signaler(EQ, "inspection", 300)          # 200 s plus tard seulement
    assert not any(e["canal"] == "sms" for e in envois), envois


def test_parcours_complet():
    m = MoteurAlertes()
    m.signaler(EQ, "inspection", 100, EXPLICATION)
    assert m.acquitter(EQ, 200, "technicien").etat == "acquittee"
    assert m.assigner(EQ, 300, "securite", "Paul").assignee_a == "Paul"
    alerte = m.cloturer(EQ, 900, "Paul", "Roulement remplacé", justifiee=True)
    assert alerte.etat == "cloturee" and alerte.justifiee is True
    assert m.alertes_ouvertes() == []
    types = [e["type"] for e in alerte.evenements]
    assert types == ["creation", "acquittement", "assignation", "cloture"], types


def test_cloture_sans_compte_rendu_refusee():
    m = MoteurAlertes()
    m.signaler(EQ, "inspection", 100)
    try:
        m.cloturer(EQ, 200, "technicien", "", justifiee=True)
    except ValueError:
        pass
    else:
        raise AssertionError("une clôture sans compte rendu doit être refusée")


def test_cloture_sans_reponse_justifiee_refusee():
    m = MoteurAlertes()
    m.signaler(EQ, "inspection", 100)
    try:
        m.cloturer(EQ, 200, "technicien", "vérifié", justifiee=None)
    except ValueError:
        pass
    else:
        raise AssertionError("la question « alerte justifiée » est obligatoire")


def test_escalade_apres_dix_minutes():
    m = MoteurAlertes()
    m.signaler(EQ, "inspection", 0)
    assert m.controler(300) == []
    escalade = m.controler(600)
    assert len(escalade) == 1 and escalade[0]["destinataire"] == "personne_suivante", escalade


def test_escalade_finale():
    m = MoteurAlertes()
    m.signaler(EQ, "urgence", 0)
    m.controler(600)
    finale = m.controler(1200)
    assert finale and finale[0]["destinataire"] == "responsable_securite", finale


def test_pas_d_escalade_si_acquittee():
    m = MoteurAlertes()
    m.signaler(EQ, "inspection", 0)
    m.acquitter(EQ, 60, "technicien")
    assert m.controler(900) == []


def test_maintenance_supprime_les_alertes():
    m = MoteurAlertes()
    m.mettre_en_maintenance(EQ)
    m.signaler(EQ, "inspection", 100)
    assert m.alertes_ouvertes() == []


def test_maintenance_laisse_passer_le_seuil_fixe_d_urgence():
    m = MoteurAlertes()
    m.mettre_en_maintenance(EQ)
    m.signaler(EQ, "urgence", 100, seuil_fixe_depasse=True)
    assert len(m.alertes_ouvertes()) == 1


def test_historique_conserve_les_alertes_cloturees():
    m = MoteurAlertes()
    m.signaler(EQ, "surveillance", 100)
    m.cloturer(EQ, 200, "technicien", "rien à signaler", justifiee=False)
    assert len(m.toutes()) == 1 and m.toutes()[0]["etat"] == "cloturee"


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
