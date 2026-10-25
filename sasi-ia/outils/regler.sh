#!/usr/bin/env bash
#
# Écrit le fichier « .env » du serveur en ligne.
#
# Pourquoi un script plutôt que les commandes de DEPLOIEMENT.md : le fichier
# contient une empreinte bcrypt pleine de « $ » et deux mots de passe
# engendrés. Les coller à la main dans un terminal distant échoue de trois
# façons — le terminal indente le collage et le délimiteur d'un heredoc n'est
# plus reconnu, il coupe les lignes longues en y insérant de vrais retours à
# la ligne, et « read » avale la ligne suivante du collage au lieu d'attendre
# une frappe. Ici tout se passe dans un seul processus, à l'abri du collage.
#
#     bash outils/regler.sh
#
# Rien n'est écrasé sans que vous l'ayez demandé : si « .env » existe déjà, le
# script s'arrête, sauf avec --forcer.

set -euo pipefail

cd "$(dirname "$0")/.."

# Sur la sortie d'erreur : plusieurs de ces messages sont émis depuis une
# substitution de commande, qui capturerait la sortie standard dans la valeur.
rouge() { printf '\033[31m%s\033[0m\n' "$*" >&2; }
vert()  { printf '\033[32m%s\033[0m\n' "$*"; }
titre() { printf '\n\033[1m%s\033[0m\n' "$*"; }

FORCER=0
[ "${1:-}" = "--forcer" ] && FORCER=1

if [ -f .env ] && [ "$FORCER" = 0 ]; then
    rouge "Le fichier .env existe déjà."
    echo "    Pour le remplacer :  bash outils/regler.sh --forcer"
    echo "    Une copie de l'ancien sera gardée sous .env.precedent"
    exit 1
fi

command -v docker >/dev/null || { rouge "Docker absent."; exit 1; }
command -v openssl >/dev/null || { rouge "openssl absent : apt install -y openssl"; exit 1; }

titre "Réglages du serveur SASI"

demander() {           # demander <invite> <valeur par défaut>
    local invite="$1" defaut="$2" reponse
    read -rp "  $invite [$defaut] : " reponse </dev/tty
    printf '%s' "${reponse:-$defaut}"
}

# Une valeur avec espace ou guillemet traverse .env, puis échoue bien plus loin,
# sur un message qui ne la mentionne pas. Autant la refuser ici.
sans_espace() {        # sans_espace <invite> <valeur par défaut>
    local valeur
    while :; do
        valeur=$(demander "$1" "$2")
        case "$valeur" in
            '')      rouge "  Valeur vide. Recommencez." ;;
            *[\ \'\"]*) rouge "  Ni espace ni guillemet ici. Recommencez." ;;
            *)       printf '%s' "$valeur"; return ;;
        esac
    done
}

DOMAINE=$(sans_espace "Nom de domaine" "sasi.the7ing.site")
ACCES_UTILISATEUR=$(sans_espace "Compte pour ouvrir l'interface" "william")
COURRIEL_ADMINISTRATEUR=$(demander "Courriel (avis d'expiration du certificat)" "")

# SASI_SITE n'est pas un nom libre : c'est le fichier sites/<nom>.json qui
# décrit les équipements et les caméras. Un nom inventé ferait échouer le
# chargement de la base, à l'étape suivante, sur une erreur sans rapport.
disponibles=$(cd sites && ls *.json 2>/dev/null | sed 's/\.json$//' | tr '\n' ' ')
echo "  Sites décrits dans sites/ : $disponibles"
while :; do
    SASI_SITE=$(demander "Site surveillé (l'un de ceux-ci)" "brasserie")
    [ -f "sites/$SASI_SITE.json" ] && break
    rouge "  sites/$SASI_SITE.json n'existe pas. Choisissez parmi : $disponibles"
done

# Le mot de passe ne s'affiche pas, et il est demandé deux fois : une faute de
# frappe ici ne se verrait qu'au moment de la connexion, sans message utile.
while :; do
    printf "  Mot de passe pour ouvrir l'interface : "
    read -rs MDP </dev/tty; echo
    printf "  Confirmez : "
    read -rs MDP2 </dev/tty; echo
    [ -n "$MDP" ] || { rouge "  Vide. Recommencez."; continue; }
    [ "$MDP" = "$MDP2" ] || { rouge "  Les deux saisies diffèrent. Recommencez."; continue; }
    [ ${#MDP} -ge 8 ] || { rouge "  Huit caractères au minimum. Recommencez."; continue; }
    break
done

titre "Calcul de l'empreinte du mot de passe"
EMPREINTE=$(docker run --rm caddy:2-alpine caddy hash-password --plaintext "$MDP")
unset MDP MDP2
case "$EMPREINTE" in
    '$2a$'*|'$2b$'*|'$2y$'*) vert "  empreinte bcrypt obtenue" ;;
    *) rouge "Caddy n'a pas rendu une empreinte bcrypt :"; echo "$EMPREINTE"; exit 1 ;;
esac

# « -hex » et non « -base64 » : le mot de passe de la base voyage dans une URL
# (postgresql://sasi:…@base:5432/sasi), où un « / » clôt l'autorité.
MOT_DE_PASSE_BASE=$(openssl rand -hex 24)
MQTT_MOT_DE_PASSE=$(openssl rand -hex 24)

[ -f .env ] && cp -f .env .env.precedent

{
    echo "# Engendré par outils/regler.sh le $(date -Is)"
    echo "DOMAINE=$DOMAINE"
    echo "ACCES_UTILISATEUR=$ACCES_UTILISATEUR"
    echo "ACCES_EMPREINTE='$EMPREINTE'"
    echo "MOT_DE_PASSE_BASE=$MOT_DE_PASSE_BASE"
    echo "MQTT_UTILISATEUR=sasi"
    echo "MQTT_MOT_DE_PASSE=$MQTT_MOT_DE_PASSE"
    echo "COURRIEL_ADMINISTRATEUR=$COURRIEL_ADMINISTRATEUR"
    echo "SASI_SITE=$SASI_SITE"
    echo "PERIODE_PANNE_S=900"
} > .env
chmod 600 .env

titre "Relecture"
# docker compose relit le fichier à sa façon : mieux vaut le constater ici que
# devant un mot de passe refusé sans explication.
if docker compose -f docker-compose.production.yml config >/dev/null 2>&1; then
    vert "  docker compose relit .env sans erreur"
else
    rouge "  docker compose refuse la composition. Détail :"
    docker compose -f docker-compose.production.yml config 2>&1 | tail -5
    exit 1
fi

sed 's/^\(MOT_DE_PASSE_BASE\|MQTT_MOT_DE_PASSE\)=.*/\1=…/' .env | sed 's/^/  /'

titre "Fichier .env écrit"
echo "  Conservez le mot de passe de l'interface : il n'est stocké nulle part,"
echo "  seule son empreinte l'est. Pour le changer : bash outils/regler.sh --forcer"
echo
echo "  Étape suivante :  ./outils/deployer.sh --demo"
