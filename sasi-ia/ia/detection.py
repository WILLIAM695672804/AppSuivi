"""Détection des anomalies de température.

Ce fichier ne dépend d'aucune bibliothèque extérieure : il n'utilise que Python.
C'est volontaire, pour qu'il puisse tourner tel quel sur le boîtier du site.

Principe (chapitre 6 du cahier des charges technique) :
  - signal S1 : écart normalisé entre la température mesurée et la température attendue
  - signal S2 : vitesse de montée sur les 5 dernières minutes
  - signal S3 : écart avec un équipement jumeau (facultatif)
  - score     : le plus fort des trois signaux, multiplié par la criticité
  - risque    : probabilité d'atteindre le seuil dangereux (ia/risque.py)
  - niveaux   : information, surveillance, inspection, urgence, avec confirmation et hystérésis

Deux questions, deux réponses, un seul niveau. « Est-ce anormal maintenant ? »
relève du score ; « où cela va-t-il ? » relève du risque. Le niveau retenu est le
plus élevé des deux : une surchauffe installée mais stable doit être signalée,
même sans risque d'emballement, et une montée rapide doit l'être bien avant
d'être dangereuse.
"""

from collections import deque

from ia import risque as module_risque

NIVEAUX = ["normal", "information", "surveillance", "inspection", "urgence"]

# Seuils d'entrée dans chaque niveau, et durée de confirmation en secondes.
# La confirmation est exprimée en durée, et non en nombre de mesures : ainsi le
# comportement ne change pas si les mesures arrivent toutes les 10 s ou toutes
# les minutes.
SEUILS_ENTREE = {"information": 2.0, "surveillance": 3.0, "inspection": 4.5, "urgence": 6.0}
SEUILS_SORTIE = {"information": 1.5, "surveillance": 2.5, "inspection": 4.0}
CONFIRMATION_S = {"information": 60, "surveillance": 60, "inspection": 90, "urgence": 120}

# L'écart est lissé sur cette durée : une température ne fait pas de bond, et une
# prédiction peut avoir un à-coup passager.
LISSAGE_ECART_S = 60

FACTEUR_CRITICITE = {1: 1.0, 2: 1.25, 3: 1.5}

# Écart de vitesse servant de référence : monter 0,5 °C/min plus vite que prévu
# donne un signal de 1.
PENTE_REFERENCE = 0.5
# Écart de référence avec un équipement jumeau : 4 °C donne un signal de 1.
ECART_JUMEAU_REFERENCE = 4.0
# La vitesse de montée n'est prise en compte qu'au-dessus de cet écart normalisé.
SEUIL_PRISE_EN_COMPTE_PENTE = 1.0

FENETRE_PENTE_S = 300      # 5 minutes
DUREE_SORTIE_S = 300       # 5 minutes en dessous du seuil de sortie

# Paliers de probabilité d'atteindre le seuil dangereux. Ils commandent le
# niveau d'alerte au même titre que le score : une probabilité de 75 % appelle
# une inspection, même si la température n'a encore rien d'anormal.
PALIERS_RISQUE = {"information": 0.25, "surveillance": 0.50,
                  "inspection": 0.75, "urgence": 0.90}

# Seuil visé par la prévision. « inspection » annonce plus tôt (la température à
# partir de laquelle on va voir la machine), « urgence » annonce le danger lui-même.
CIBLE_RISQUE = "inspection"
# Marge de redescente : sans elle, une probabilité qui oscille autour d'un palier
# ferait clignoter le niveau.
MARGE_SORTIE_RISQUE = 0.10


class DetecteurEquipement:
    """Suit un équipement et décide de son niveau d'alerte."""

    def __init__(self, equipement, biais=0.0, dispersion=1.0, criticite=1,
                 seuil_fixe_inspection=None, seuil_fixe_urgence=None,
                 cloture_auto_s=None, temps_montee_min=30):
        self.equipement = equipement
        self.biais = biais
        self.dispersion = max(dispersion, 0.2)      # jamais zéro
        self.criticite = criticite
        self.seuil_fixe_inspection = seuil_fixe_inspection
        self.seuil_fixe_urgence = seuil_fixe_urgence
        # Inertie thermique : elle fixe l'horizon sur lequel la prévision a un sens.
        self.temps_montee_min = temps_montee_min
        # Sur site, une urgence est clôturée par une personne. Pour les essais
        # automatiques, on la clôture après ce délai de retour à la normale.
        self.cloture_auto_s = cloture_auto_s

        self.historique = deque()          # (secondes, température mesurée)
        self.historique_attendue = deque()  # (secondes, température attendue)
        self.ecarts = deque()              # (secondes, écart brut) pour le lissage
        self.niveau = "normal"
        self.depuis = {n: None for n in SEUILS_ENTREE}
        self.depuis_risque = {n: None for n in PALIERS_RISQUE}
        self.debut_sortie = None
        self.debut_alerte = None
        self.risque = None                 # dernière évaluation du risque

    # ---------- signaux ----------
    def _signal_ecart(self, secondes, mesuree, attendue):
        """Écart normalisé, lissé sur une minute (médiane)."""
        self.ecarts.append((secondes, mesuree - attendue))
        while self.ecarts and secondes - self.ecarts[0][0] > LISSAGE_ECART_S:
            self.ecarts.popleft()
        valeurs = sorted(v for _, v in self.ecarts)
        milieu = len(valeurs) // 2
        mediane = (valeurs[milieu] if len(valeurs) % 2
                   else (valeurs[milieu - 1] + valeurs[milieu]) / 2.0)
        return (mediane - self.biais) / self.dispersion

    @staticmethod
    def _pente(historique):
        """Vitesse de montée sur la fenêtre, en °C par minute.

        On compare la moyenne des trois dernières valeurs à celle des trois
        premières. Cette moyenne évite qu'un point isolé ne donne une vitesse
        démesurée.
        """
        if len(historique) < 6:
            return None
        duree_min = (historique[-1][0] - historique[0][0]) / 60.0
        if duree_min <= 0:
            return None
        debut = sum(v for _, v in list(historique)[:3]) / 3.0
        fin = sum(v for _, v in list(historique)[-3:]) / 3.0
        return (fin - debut) / duree_min

    def _signal_pente(self, secondes, mesuree, attendue):
        """Compare la vitesse de montée mesurée à la vitesse attendue.

        Une machine qui démarre monte parfois de plusieurs degrés par minute :
        c'est normal, et le modèle le prévoit. Seule compte la montée qui va
        plus vite que prévu.
        """
        self.historique.append((secondes, mesuree))
        self.historique_attendue.append((secondes, attendue))
        for file in (self.historique, self.historique_attendue):
            while file and secondes - file[0][0] > FENETRE_PENTE_S:
                file.popleft()

        pente = self._pente(self.historique)
        pente_attendue = self._pente(self.historique_attendue)
        if pente is None or pente_attendue is None:
            return 0.0, 0.0
        surplus = pente - pente_attendue
        return pente, max(surplus, 0.0) / PENTE_REFERENCE

    def _signal_jumeau(self, mesuree, mediane_jumeaux):
        if mediane_jumeaux is None:
            return 0.0, 0.0
        ecart = mesuree - mediane_jumeaux
        return ecart, max(ecart, 0.0) / ECART_JUMEAU_REFERENCE

    # ---------- décision ----------
    def _niveau_seuils_fixes(self, mesuree):
        if self.seuil_fixe_urgence is not None and mesuree >= self.seuil_fixe_urgence:
            return "urgence"
        if self.seuil_fixe_inspection is not None and mesuree >= self.seuil_fixe_inspection:
            return "inspection"
        return "normal"

    def _niveau_risque(self, secondes, probabilite):
        """Niveau appelé par la probabilité, une fois la durée de confirmation écoulée.

        La redescente demande de repasser sous le palier moins une marge : une
        probabilité qui oscille autour de 75 % ne doit pas faire clignoter le
        niveau d'alerte.
        """
        vise = "normal"
        for niveau in ("information", "surveillance", "inspection", "urgence"):
            palier = PALIERS_RISQUE[niveau]
            atteint = probabilite >= palier
            if self.depuis_risque[niveau] is not None:
                atteint = probabilite >= palier - MARGE_SORTIE_RISQUE
            if atteint:
                if self.depuis_risque[niveau] is None:
                    self.depuis_risque[niveau] = secondes
                if secondes - self.depuis_risque[niveau] >= CONFIRMATION_S[niveau]:
                    vise = niveau
            else:
                self.depuis_risque[niveau] = None
        return vise

    def traiter(self, secondes, mesuree, attendue, mediane_jumeaux=None):
        """Traite une mesure et renvoie l'état courant.

        secondes : horodatage en secondes (n'importe quelle origine, du moment qu'elle est constante)
        """
        s1 = self._signal_ecart(secondes, mesuree, attendue)
        pente, s2 = self._signal_pente(secondes, mesuree, attendue)
        ecart_jumeau, s3 = self._signal_jumeau(mesuree, mediane_jumeaux)

        # La vitesse de montée n'est prise en compte que si la température est
        # déjà au-dessus de ce qui est attendu. Sinon, une montée normale
        # (démarrage d'une machine, par exemple) déclencherait une alerte.
        if s1 < SEUIL_PRISE_EN_COMPTE_PENTE:
            s2 = 0.0

        score = max(s1, s2, s3) * FACTEUR_CRITICITE.get(self.criticite, 1.0)

        # Niveau visé par le score, une fois la durée de confirmation écoulée
        vise = "normal"
        for niveau in ("information", "surveillance", "inspection", "urgence"):
            if score >= SEUILS_ENTREE[niveau]:
                if self.depuis[niveau] is None:
                    self.depuis[niveau] = secondes
                if secondes - self.depuis[niveau] >= CONFIRMATION_S[niveau]:
                    vise = niveau
            else:
                self.depuis[niveau] = None

        # Où cela va-t-il ? Probabilité d'atteindre le seuil dangereux.
        # L'évaluation est gardée dans une variable : une clôture automatique
        # peut survenir plus bas et remettre l'état du détecteur à zéro.
        seuil_vise = (self.seuil_fixe_inspection if CIBLE_RISQUE == "inspection"
                      and self.seuil_fixe_inspection else self.seuil_fixe_urgence)
        evaluation = module_risque.evaluer(
            mesuree, seuil_vise, self.historique,
            temps_montee_min=self.temps_montee_min, criticite=self.criticite,
            incertitude_mesure=self.dispersion,
            historique_attendu=self.historique_attendue)

        # Le risque ne se prédit qu'à partir d'une anomalie constatée. Sans cette
        # condition, chaque démarrage de chaudière ou de pasteurisateur — montée
        # franche mais parfaitement normale — serait annoncé comme un emballement.
        # D'abord constater, ensuite prévoir.
        evaluation["anomalie_constatee"] = s1 >= SEUIL_PRISE_EN_COMPTE_PENTE
        if not evaluation["anomalie_constatee"]:
            evaluation["probabilite"] = 0.0
            evaluation["pourcentage"] = 0
        self.risque = evaluation
        vise_risque = self._niveau_risque(secondes, evaluation["probabilite"])
        if NIVEAUX.index(vise_risque) > NIVEAUX.index(vise):
            vise = vise_risque

        # Les seuils fixes s'appliquent en permanence, sans confirmation
        fixe = self._niveau_seuils_fixes(mesuree)
        if NIVEAUX.index(fixe) > NIVEAUX.index(vise):
            vise = fixe

        ancien = self.niveau
        if NIVEAUX.index(vise) > NIVEAUX.index(self.niveau):
            # montée immédiate
            self.niveau = vise
            self.debut_sortie = None
            if ancien == "normal":
                self.debut_alerte = secondes
        elif self.niveau != "normal":
            # descente : seulement sous le seuil de sortie, et pendant assez longtemps
            if self.niveau == "urgence":
                if self.cloture_auto_s is None:
                    pass                               # une urgence ne se lève que par une personne
                elif score < SEUILS_SORTIE["inspection"] and fixe == "normal":
                    if self.debut_sortie is None:
                        self.debut_sortie = secondes
                    elif secondes - self.debut_sortie >= self.cloture_auto_s:
                        self.cloturer()
                else:
                    self.debut_sortie = None
            else:
                seuil_sortie = SEUILS_SORTIE[self.niveau]
                risque_retombe = (NIVEAUX.index(vise_risque) < NIVEAUX.index(self.niveau))
                if score < seuil_sortie and fixe == "normal" and risque_retombe:
                    if self.debut_sortie is None:
                        self.debut_sortie = secondes
                    elif secondes - self.debut_sortie >= DUREE_SORTIE_S:
                        indice = NIVEAUX.index(self.niveau) - 1
                        self.niveau = NIVEAUX[indice]
                        self.debut_sortie = None
                        if self.niveau == "normal":
                            self.debut_alerte = None
                else:
                    self.debut_sortie = None

        return {
            "equipement": self.equipement,
            "secondes": secondes,
            "t_mesuree": mesuree,
            "t_attendue": attendue,
            "ecart": mesuree - attendue,
            "s1_ecart_normalise": s1,
            "s2_pente": pente,
            "s3_ecart_jumeau": ecart_jumeau,
            "score": score,
            "risque": evaluation["probabilite"],
            "risque_pourcentage": evaluation["pourcentage"],
            "risque_horizon_min": evaluation["horizon_min"],
            "risque_minutes_avant_seuil": evaluation["minutes_avant_seuil"],
            "risque_pente": evaluation["pente"],
            "risque_seuil": evaluation["seuil"],
            "risque_detail": evaluation,
            "niveau_par_le_score": vise,
            "niveau_par_le_risque": vise_risque,
            "niveau": self.niveau,
            "niveau_precedent": ancien,
            "changement": self.niveau != ancien,
            "debut_alerte": self.debut_alerte,
        }

    def cloturer(self):
        """Remise à zéro : correspond à la clôture d'une alerte par une personne."""
        self.ecarts = deque()              # (secondes, écart brut) pour le lissage
        self.niveau = "normal"
        self.depuis = {n: None for n in SEUILS_ENTREE}
        self.depuis_risque = {n: None for n in PALIERS_RISQUE}
        self.debut_sortie = None
        self.debut_alerte = None
        self.risque = None                 # dernière évaluation du risque


def parcourir(mesures, biais=0.0, dispersion=1.0, criticite=1,
              seuil_fixe_inspection=None, seuil_fixe_urgence=None,
              cloture_auto_s=None, temps_montee_min=30):
    """Passe une série complète de mesures dans le détecteur.

    mesures : liste de dictionnaires {secondes, t_mesuree, t_attendue, equipement}
    Chaque mesure peut porter ses propres « biais » et « dispersion » : c'est utile
    lorsqu'une machine vient de démarrer, période où la prédiction est moins sûre.
    Renvoie (etats, alertes) : tous les états, et la liste des alertes ouvertes.
    """
    detecteurs = {}
    etats, alertes = [], []
    for m in mesures:
        eq = m.get("equipement", "EQ")
        if eq not in detecteurs:
            detecteurs[eq] = DetecteurEquipement(
                eq, biais=biais, dispersion=dispersion, criticite=criticite,
                seuil_fixe_inspection=seuil_fixe_inspection,
                seuil_fixe_urgence=seuil_fixe_urgence,
                cloture_auto_s=cloture_auto_s,
                temps_montee_min=temps_montee_min)
        if m.get("dispersion") is not None:
            detecteurs[eq].dispersion = max(m["dispersion"], 0.2)
        if m.get("biais") is not None:
            detecteurs[eq].biais = m["biais"]
        etat = detecteurs[eq].traiter(m["secondes"], m["t_mesuree"], m["t_attendue"],
                                      m.get("mediane_jumeaux"))
        etats.append(etat)
        if etat["changement"] and etat["niveau"] != "normal":
            alertes.append({
                "equipement": eq,
                "secondes": etat["secondes"],
                "niveau": etat["niveau"],
                "score": etat["score"],
                "t_mesuree": etat["t_mesuree"],
                "t_attendue": etat["t_attendue"],
            })
    return etats, alertes


ORDRE = {niveau: i for i, niveau in enumerate(NIVEAUX)}


def episodes(etats, niveau_minimum="surveillance"):
    """Regroupe les états en épisodes d'alerte.

    Un épisode commence quand l'équipement atteint le niveau minimum et se termine
    quand il redescend en dessous. C'est l'unité qui compte pour l'utilisateur :
    une anomalie qui dure deux heures est une alerte, pas deux cents.
    """
    seuil = ORDRE[niveau_minimum]
    resultat, courant = [], {}
    for etat in etats:
        equipement = etat["equipement"]
        actif = ORDRE[etat["niveau"]] >= seuil
        ouvert = courant.get(equipement)
        if actif and ouvert is None:
            courant[equipement] = {"equipement": equipement, "debut": etat["secondes"],
                                   "fin": etat["secondes"], "niveau_max": etat["niveau"],
                                   "score_max": etat["score"]}
        elif actif:
            ouvert["fin"] = etat["secondes"]
            if ORDRE[etat["niveau"]] > ORDRE[ouvert["niveau_max"]]:
                ouvert["niveau_max"] = etat["niveau"]
            ouvert["score_max"] = max(ouvert["score_max"], etat["score"])
        elif ouvert is not None:
            resultat.append(ouvert)
            courant[equipement] = None
    resultat += [e for e in courant.values() if e]
    return sorted(resultat, key=lambda e: e["debut"])
