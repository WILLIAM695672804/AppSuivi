#!/bin/bash
# Démonstration complète : remise à zéro, démarrage, flux continu.
#
#     ./outils/demonstration.sh                      brasserie, une panne toutes les 5 min
#     ./outils/demonstration.sh minoterie            un autre site
#     ./outils/demonstration.sh brasserie 180        une panne toutes les 3 minutes
#
# Les trois services gardent leur état en mémoire (détecteurs, alertes, courbes) :
# les arrêter et les relancer suffit à repartir d'une page blanche. Avec une base
# de données, voir la commande de vidage rappelée en fin de fichier.
#
# Arrêt : Ctrl+C (le rejeu s'arrête ; les services continuent de tourner).

set -u
RACINE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RACINE" || exit 1

SITE="${1:-brasserie}"
PERIODE_PANNE="${2:-300}"      # secondes entre deux pannes
JOURNAUX="$RACINE/journaux"
PYTHON="$RACINE/venv/bin/python"

export SASI_SITE="$SITE"
export SASI_MQTT="${SASI_MQTT:-localhost}"

mkdir -p "$JOURNAUX"

echo "› Arrêt des services et remise à zéro de la mémoire"
pkill -f "connecteur.main|ia.service|alertes.service|uvicorn api.serveur" 2>/dev/null
pkill -f "outils/rejeu.py" 2>/dev/null
sleep 2

if ! systemctl is-active --quiet mosquitto 2>/dev/null; then
  echo "  ! Le serveur de messages ne tourne pas : sudo systemctl start mosquitto"
fi

echo "› Démarrage du connecteur, de l'IA, des alertes et du serveur"
# « -u » : sans cela, les messages des services restent en mémoire et les
# journaux paraissent vides tant que le tampon n'est pas plein.
nohup "$PYTHON" -u -m connecteur.main  >"$JOURNAUX/connecteur.log" 2>&1 &
nohup "$PYTHON" -u -m ia.service       >"$JOURNAUX/ia.log"         2>&1 &
nohup "$PYTHON" -u -m alertes.service  >"$JOURNAUX/alertes.log"    2>&1 &
nohup "$RACINE/venv/bin/uvicorn" api.serveur:app --host 0.0.0.0 --port 8000 \
      >"$JOURNAUX/api.log" 2>&1 &

for _ in $(seq 1 20); do
  sleep 1
  etat="$(curl -s --max-time 2 localhost:8000/api/etat)" && [ -n "$etat" ] && break
done
echo "  $etat"
echo

echo "› Interface : http://localhost:8000     (Ctrl+Maj+R pour recharger sans cache)"
echo "› Jumeau en direct : site $SITE, une mesure toutes les 10 s,"
echo "  une panne toutes les $PERIODE_PANNE s. Les courbes se redemandent toutes les 10 s."
echo

exec "$PYTHON" outils/direct.py "$SITE" --panne "$PERIODE_PANNE"

# Avec une base de données (docker compose up -d base), la remise à zéro des
# mesures et des alertes conservées se fait par :
#   psql "$SASI_BASE" -c "TRUNCATE mesure, contexte, ambiance, prediction, alerte,
#        alerte_evenement, intervention, notification, alerte_technique;"
