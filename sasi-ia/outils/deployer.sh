#!/usr/bin/env bash
# Mise en service de SASI sur un serveur en ligne.
#
#     ./outils/deployer.sh              met en service, ou met à jour
#     ./outils/deployer.sh --demo       y ajoute le jumeau de démonstration
#     ./outils/deployer.sh --etat       montre l'état, sans rien changer
#
# À exécuter sur le serveur, depuis le dossier sasi-ia du dépôt. Le script est
# idempotent : on peut le relancer autant de fois qu'on veut, il ne recrée pas
# ce qui existe et ne touche jamais aux données.

set -euo pipefail

COMPOSITION="docker-compose.production.yml"
OBLIGATOIRES=(DOMAINE ACCES_UTILISATEUR ACCES_EMPREINTE MOT_DE_PASSE_BASE
              MQTT_UTILISATEUR MQTT_MOT_DE_PASSE)

cd "$(dirname "$0")/.."

rouge() { printf '\033[31m%s\033[0m\n' "$*"; }
vert()  { printf '\033[32m%s\033[0m\n' "$*"; }
titre() { printf '\n\033[1m%s\033[0m\n' "$*"; }

composer() { docker compose -f "$COMPOSITION" "$@"; }

# ------------------------------------------------------------------ contrôles
verifier_prealables() {
    titre "Contrôles préalables"

    command -v docker >/dev/null || { rouge "Docker absent. Voir DEPLOIEMENT.md."; exit 1; }
    docker compose version >/dev/null 2>&1 || {
        rouge "Le greffon « docker compose » est absent."; exit 1; }
    vert "  Docker et docker compose présents"

    [ -f .env ] || {
        rouge "Fichier .env absent."
        echo "    cp .env.exemple .env && nano .env"
        exit 1; }

    set -a; . ./.env; set +a
    local manquantes=()
    for nom in "${OBLIGATOIRES[@]}"; do
        [ -n "${!nom:-}" ] || manquantes+=("$nom")
    done
    if [ ${#manquantes[@]} -gt 0 ]; then
        rouge "Réglages manquants dans .env : ${manquantes[*]}"
        exit 1
    fi
    case "$ACCES_EMPREINTE" in
        '$2a$'*|'$2b$'*|'$2y$'*) ;;
        *) rouge "ACCES_EMPREINTE ne ressemble pas à une empreinte bcrypt."
           echo "    docker run --rm caddy:2-alpine caddy hash-password --plaintext 'votre-mot-de-passe'"
           exit 1;;
    esac
    vert "  .env complet — domaine $DOMAINE"

    # Le certificat ne s'obtient que si le domaine désigne déjà cette machine.
    local attendue resolue
    attendue=$(curl -fsS --max-time 10 https://api.ipify.org 2>/dev/null || echo inconnue)
    resolue=$(getent hosts "$DOMAINE" 2>/dev/null | awk '{print $1; exit}')
    if [ -z "$resolue" ]; then
        rouge "  $DOMAINE ne se résout pas encore."
        echo "    Let's Encrypt refusera le certificat. Attendez la propagation DNS."
        echo "    Pour poursuivre malgré tout : PASSER_DNS=1 $0"
        [ "${PASSER_DNS:-}" = "1" ] || exit 1
    elif [ "$attendue" != inconnue ] && [ "$resolue" != "$attendue" ]; then
        rouge "  $DOMAINE pointe vers $resolue, or cette machine est $attendue."
        echo "    Corrigez l'enregistrement A, ou poursuivez : PASSER_DNS=1 $0"
        [ "${PASSER_DNS:-}" = "1" ] || exit 1
    else
        vert "  $DOMAINE → $resolue, c'est bien cette machine"
    fi
}

# ------------------------------------- compte du serveur de messages
creer_compte_mqtt() {
    titre "Compte du serveur de messages"
    # Le fichier vit dans un volume : on le fabrique dans un conteneur jetable
    # qui monte ce même volume. Le mot de passe ne traverse jamais le disque en
    # clair, et l'opération se répète sans dommage.
    docker run --rm \
        -v sasi_mosquitto_config:/mosquitto/config \
        -e COMPTE="$MQTT_UTILISATEUR" -e SECRET="$MQTT_MOT_DE_PASSE" \
        --entrypoint sh eclipse-mosquitto:2 -c '
            touch /mosquitto/config/passwd
            mosquitto_passwd -b /mosquitto/config/passwd "$COMPTE" "$SECRET"
            chmod 0700 /mosquitto/config/passwd
            chown 1883:1883 /mosquitto/config/passwd
        ' >/dev/null
    vert "  compte « $MQTT_UTILISATEUR » enregistré"
}

# ------------------------------------------------------------------ mise en route
construire_et_demarrer() {
    titre "Construction des images"
    echo "  L'interface est bâtie ici, sur le serveur : votre connexion n'envoie"
    echo "  que du code source. Comptez quelques minutes la première fois."
    composer build

    titre "Démarrage"
    local profils=()
    [ "${AVEC_DEMONSTRATION:-}" = "1" ] && profils=(--profile demonstration)
    composer "${profils[@]}" up -d

    titre "Attente de la base"
    local essais=0
    until composer exec -T base pg_isready -U sasi -d sasi >/dev/null 2>&1; do
        essais=$((essais + 1))
        [ "$essais" -gt 30 ] && { rouge "  La base ne répond pas."; composer logs --tail 30 base; exit 1; }
        sleep 2
    done
    vert "  base prête"
}

verser_le_referentiel() {
    titre "Description du site"
    # Sans les tables de référence, la première mesure est refusée : une mesure
    # renvoie à un équipement, qui renvoie à une zone et à une caméra.
    composer run --rm --no-deps -T api python outils/initialiser_base.py "${SASI_SITE:-brasserie}"
}

etat() {
    titre "État des services"
    composer ps
    titre "Certificat et accès"
    local domaine="${DOMAINE:-}"
    if [ -n "$domaine" ]; then
        if curl -fsS --max-time 15 -o /dev/null -w '  HTTPS : %{http_code}\n' \
                "https://$domaine/api/etat" 2>/dev/null; then :; else
            echo "  HTTPS : pas encore de réponse (le certificat peut prendre une minute)"
        fi
        echo "  Interface : https://$domaine"
    fi
    titre "Derniers journaux"
    composer logs --tail 8 ia alertes connecteur 2>/dev/null || true
}

# ------------------------------------------------------------------ exécution
AVEC_DEMONSTRATION=0
for argument in "$@"; do
    case "$argument" in
        --demo|--demonstration) AVEC_DEMONSTRATION=1;;
        --etat|--status) set -a; . ./.env; set +a; etat; exit 0;;
        -h|--help) sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
        *) rouge "Argument inconnu : $argument"; exit 1;;
    esac
done

verifier_prealables
creer_compte_mqtt
construire_et_demarrer
verser_le_referentiel
etat

titre "Terminé"
echo "  Interface : https://$DOMAINE  (compte « $ACCES_UTILISATEUR »)"
echo "  Suivre les journaux : docker compose -f $COMPOSITION logs -f"
[ "$AVEC_DEMONSTRATION" = "1" ] \
    && echo "  Le jumeau de démonstration produit des mesures : les écrans doivent vivre." \
    || echo "  Aucune source de mesures n'est active. Pour une démonstration : ./outils/deployer.sh --demo"
