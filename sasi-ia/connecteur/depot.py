"""Écriture des mesures dans la base (PostgreSQL + TimescaleDB).

Les écritures se font par paquets : une mesure toutes les 10 secondes pour
17 zones représente environ 147 000 lignes par jour.
"""

import json
from datetime import datetime, timezone


def _horodatage(texte):
    if isinstance(texte, datetime):
        return texte
    if not texte:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(str(texte).replace("Z", "+00:00"))


class Depot:
    def __init__(self, adresse, taille_paquet=200):
        import psycopg                         # importé ici : inutile pour les tests
        self.connexion = psycopg.connect(adresse, autocommit=True)
        self.taille_paquet = taille_paquet
        self.en_attente = []

    # ---------- mesures ----------
    def enregistrer_mesures(self, mesures):
        self.en_attente.extend(mesures)
        if len(self.en_attente) >= self.taille_paquet:
            self.vider()

    def vider(self):
        if not self.en_attente:
            return 0
        lignes = [(_horodatage(m["horodatage"]), m["equipement"], m["t_max"],
                   m.get("t_moy"), m.get("t_min"), m.get("source", "camera"))
                  for m in self.en_attente]
        with self.connexion.cursor() as curseur:
            curseur.executemany(
                "INSERT INTO mesure (horodatage, equipement, t_max, t_moy, t_min, source)"
                " VALUES (%s, %s, %s, %s, %s, %s)", lignes)
        nombre = len(lignes)
        self.en_attente.clear()
        return nombre

    # ---------- contexte ----------
    def enregistrer_contexte(self, horodatage, lignes):
        valeurs = [(_horodatage(horodatage), l["equipement"], l.get("etat", "marche"),
                    l.get("charge_pct")) for l in lignes]
        with self.connexion.cursor() as curseur:
            curseur.executemany(
                "INSERT INTO contexte (horodatage, equipement, etat, charge_pct)"
                " VALUES (%s, %s, %s, %s)", valeurs)
        return len(valeurs)

    def enregistrer_ambiance(self, horodatage, site, lignes):
        valeurs = [(_horodatage(horodatage), site, l["zone"], l.get("t_ambiante"),
                    l.get("humidite_pct")) for l in lignes]
        with self.connexion.cursor() as curseur:
            curseur.executemany(
                "INSERT INTO ambiance (horodatage, site, zone, t_ambiante, humidite_pct)"
                " VALUES (%s, %s, %s, %s, %s)", valeurs)
        return len(valeurs)

    # ---------- IA et alertes ----------
    def enregistrer_prediction(self, horodatage, equipement, etat):
        with self.connexion.cursor() as curseur:
            curseur.execute(
                "INSERT INTO prediction (horodatage, equipement, t_attendue, ecart,"
                " pente, score, niveau) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (_horodatage(horodatage), equipement, etat["t_attendue"], etat["ecart"],
                 etat.get("s2_pente"), etat["score"], etat["niveau"]))

    def enregistrer_alerte(self, alerte, explication=None):
        explication = explication or {}
        with self.connexion.cursor() as curseur:
            curseur.execute(
                "INSERT INTO alerte (id, equipement, niveau, etat, debut, t_mesuree,"
                " t_attendue, raison, facteurs, action_conseillee)"
                " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
                " ON CONFLICT (id) DO UPDATE SET niveau = EXCLUDED.niveau,"
                " etat = EXCLUDED.etat",
                (alerte["id"], alerte["equipement"], alerte["niveau"], alerte["etat"],
                 _horodatage(alerte.get("debut")), alerte.get("t_mesuree"),
                 alerte.get("t_attendue"), explication.get("raison"),
                 json.dumps(explication.get("facteurs", [])),
                 explication.get("action")))

    def enregistrer_evenement(self, identifiant_alerte, evenement):
        with self.connexion.cursor() as curseur:
            curseur.execute(
                "INSERT INTO alerte_evenement (alerte, horodatage, type, par, details)"
                " VALUES (%s, %s, %s, %s, %s)",
                (identifiant_alerte, _horodatage(evenement.get("horodatage")),
                 evenement["type"], evenement.get("par"), json.dumps(evenement)))

    def enregistrer_alerte_technique(self, alerte):
        with self.connexion.cursor() as curseur:
            curseur.execute(
                "INSERT INTO alerte_technique (horodatage, camera, type, message)"
                " VALUES (%s, %s, %s, %s)",
                (_horodatage(alerte.get("horodatage")), alerte.get("camera"),
                 alerte["type"], alerte.get("message")))

    def enregistrer_intervention(self, alerte):
        """Compte rendu d'une alerte clôturée."""
        with self.connexion.cursor() as curseur:
            curseur.execute(
                "INSERT INTO intervention (alerte, horodatage, par, constat, justifiee)"
                " VALUES (%s, %s, %s, %s, %s)",
                (alerte.identifiant, _horodatage(None),
                 alerte.evenements[-1].get("par", "inconnu"),
                 alerte.compte_rendu or "", bool(alerte.justifiee)))

    def lire_alertes(self, depuis_jours=30):
        """Alertes de la période, pour l'application."""
        with self.connexion.cursor() as curseur:
            curseur.execute(
                "SELECT id, equipement, niveau, etat, debut, fin, t_mesuree, t_attendue,"
                " raison, facteurs, action_conseillee, assignee_a FROM alerte"
                " WHERE debut >= now() - (%s || ' days')::interval ORDER BY debut DESC",
                (str(depuis_jours),))
            colonnes = ["id", "equipement", "niveau", "etat", "debut", "fin", "t_mesuree",
                        "t_attendue", "raison", "facteurs", "action", "assignee_a"]
            return [dict(zip(colonnes, ligne)) for ligne in curseur.fetchall()]

    def fermer(self):
        self.vider()
        self.connexion.close()
