#!/usr/bin/env bash
# Mise en service de SASI sur un serveur en ligne.
#
#     ./outils/deployer.sh              met en service, ou met à jour
#     ./outils/deployer.sh --demo       y ajoute le jumeau de démonstration
#     ./outils/deployer.sh --etat       montre l'état, sans rien changer
#     ./outils/deployer.sh --frontal    recharge le seul frontal (après avoir
#                                       ajouté une application dans
#                                       config/proxy/sites/)
#
# À exécuter sur le serveur, depuis le dossier sasi-ia du dépôt. Le script est
# idempotent : on peut le relancer autant de fois qu'on veut, il ne recrée pas
# ce qui existe et ne touche jamais aux données.

set -euo pipefail

COMPOSITION="docker-compose.production.yml"
FRONTAL="config/proxy/docker-compose.yml"
RESEAU="frontal"
OBLIGATOIRES=(DOMAINE ACCES_UTILISATEUR ACCES_EMPREINTE MOT_DE_PASSE_BASE
              MQTT_UTILISATEUR MQTT_MOT_DE_PASSE)

cd "$(dirname "$0")/.."

rouge() { printf '\033[31m%s\033[0m\n' "$*"; }
vert()  { printf '\033[32m%s\033[0m\n' "$*"; }
titre() { printf '\n\033[1m%s\033[0m\n' "$*"; }

composer() { docker compose -f "$COMPOSITION" "$@"; }
frontal()  { docker compose -f "$FRONTAL" --env-file .env "$@"; }

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
    # Le mot de passe de la base voyage dans une URL (postgresql://sasi:…@base).
    # Un « / » y clôt l'autorité : la connexion échouerait sur un message obscur.
    case "$MOT_DE_PASSE_BASE" in
        *[/@:?\#\[\]%\ ]*)
           rouge "MOT_DE_PASSE_BASE contient un caractère interdit dans une URL."
           echo "    Caractères à éviter : / @ : ? # [ ] % et l'espace."
           echo "    Engendrez-le ainsi :  openssl rand -hex 24"
           exit 1;;
    esac

    # SASI_SITE désigne le fichier sites/<nom>.json. Un nom inventé ne se verrait
    # qu'au versement du référentiel, après dix minutes de construction.
    local site="${SASI_SITE:-brasserie}"
    [ -f "sites/$site.json" ] || {
        rouge "SASI_SITE=$site, or sites/$site.json n'existe pas."
        echo "    Sites décrits : $(cd sites && ls *.json | sed 's/\.json$//' | tr '\n' ' ')"
        echo "    Corrigez .env, ou réglez tout à neuf : bash outils/regler.sh --forcer"
        exit 1; }

    vert "  .env complet — domaine $DOMAINE, site $site"

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

# ------------------------------------------------------------------ frontal
preparer_le_reseau() {
    titre "Réseau partagé"
    # Deux applications ne peuvent pas occuper les ports 80 et 443 à la fois :
    # un frontal unique les détient et achemine selon le nom de domaine. Les
    # applications le rejoignent sur ce réseau, sans publier aucun port.
    if docker network inspect "$RESEAU" >/dev/null 2>&1; then
        vert "  réseau « $RESEAU » déjà présent"
    else
        docker network create "$RESEAU" >/dev/null
        vert "  réseau « $RESEAU » créé"
    fi
}

demarrer_le_frontal() {
    titre "Frontal partagé"
    frontal up -d
    vert "  Caddy écoute sur 80 et 443"
    echo "  Applications desservies :"
    for fichier in config/proxy/sites/*.caddy; do
        [ -e "$fichier" ] || continue
        echo "    $(basename "$fichier" .caddy)"
    done
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
    titre "État du frontal"
    frontal ps
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
        --frontal)
            set -a; . ./.env; set +a
            titre "Rechargement du frontal"
            frontal up -d
            # reload relit la configuration sans couper les connexions en cours
            frontal exec -T caddy caddy reload --config /etc/caddy/Caddyfile \
                && vert "  configuration rechargée, sans interruption"
            exit 0;;
        -h|--help) sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit 0;;
        *) rouge "Argument inconnu : $argument"; exit 1;;
    esac
done

verifier_prealables
preparer_le_reseau
creer_compte_mqtt
construire_et_demarrer
demarrer_le_frontal
verser_le_referentiel
etat

titre "Terminé"
echo "  Interface : https://$DOMAINE  (compte « $ACCES_UTILISATEUR »)"
echo "  Suivre les journaux : docker compose -f $COMPOSITION logs -f"
[ "$AVEC_DEMONSTRATION" = "1" ] \
    && echo "  Le jumeau de démonstration produit des mesures : les écrans doivent vivre." \
    || echo "  Aucune source de mesures n'est active. Pour une démonstration : ./outils/deployer.sh --demo"
