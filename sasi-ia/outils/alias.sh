# Raccourcis du serveur. À charger une fois pour toutes :
#
#     echo 'source ~/AppSuivi/sasi-ia/outils/alias.sh' >> ~/.bashrc
#
# Pourquoi des raccourcis : les commandes « docker compose -f … » dépassent la
# largeur que le terminal distant supporte au collage — il coupe les lignes
# longues en y insérant de vrais retours à la ligne, et la commande se scinde.

SASI_RACINE="$HOME/AppSuivi/sasi-ia"

# Les sept services de SASI.
alias sasi="docker compose -f $SASI_RACINE/docker-compose.production.yml"

# Le frontal partagé, qui détient les ports 80 et 443 des deux applications.
alias frontal="docker compose -f $SASI_RACINE/config/proxy/docker-compose.yml --env-file $SASI_RACINE/.env"

# Relevé d'état : services, frontal, certificat, derniers journaux.
alias etat="$SASI_RACINE/outils/deployer.sh --etat"
