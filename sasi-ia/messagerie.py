"""Liaison avec le serveur de messages : identité, mot de passe, chiffrement.

Sur l'ordinateur de développement, Mosquitto accepte tout le monde sans mot de
passe : c'est commode et sans conséquence. Dès que le système tourne sur une
machine accessible depuis Internet, cette ouverture devient une porte d'entrée —
n'importe qui pourrait publier de fausses mesures, ou lire toutes les alertes
d'un site industriel.

Les quatre services passent donc par ce module plutôt que d'appeler `connect()`
directement. Le réglage se fait par l'environnement, sans toucher au code :

    SASI_MQTT              adresse du serveur        (défaut : localhost)
    SASI_MQTT_PORT         port                      (défaut : 1883, ou 8883 en TLS)
    SASI_MQTT_UTILISATEUR  compte                    (défaut : aucun, accès anonyme)
    SASI_MQTT_MOT_DE_PASSE mot de passe
    SASI_MQTT_TLS          « 1 » pour chiffrer la liaison

Sans compte défini, le comportement reste celui d'aujourd'hui : rien ne change
pour qui développe en local.
"""

import os

PORT_CLAIR = 1883
PORT_CHIFFRE = 8883


def adresse():
    return os.environ.get("SASI_MQTT", "localhost")


def tls_demande():
    return os.environ.get("SASI_MQTT_TLS", "").strip() in ("1", "oui", "true")


def port():
    defaut = PORT_CHIFFRE if tls_demande() else PORT_CLAIR
    try:
        return int(os.environ.get("SASI_MQTT_PORT", defaut))
    except ValueError:
        return defaut


def identite():
    """(compte, mot de passe), ou (None, None) si l'accès est anonyme."""
    compte = os.environ.get("SASI_MQTT_UTILISATEUR") or None
    return compte, os.environ.get("SASI_MQTT_MOT_DE_PASSE") or None


def client(nom=None):
    """Client MQTT réglé par l'environnement, pas encore connecté.

    `nom` sert d'identifiant auprès du serveur : il rend les journaux lisibles
    et évite que deux services se chassent mutuellement en réutilisant le même.
    """
    import paho.mqtt.client as mqtt

    client_mqtt = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                              client_id=nom or "")
    compte, mot_de_passe = identite()
    if compte:
        client_mqtt.username_pw_set(compte, mot_de_passe)
    if tls_demande():
        client_mqtt.tls_set()                  # autorités de certification du système
    return client_mqtt


def connecter(client_mqtt, hote=None, numero=None, keepalive=60):
    """Ouvre la liaison. L'adresse donnée l'emporte sur celle de l'environnement.

    Les outils en ligne de commande acceptent une adresse en argument ; le compte
    et le chiffrement, eux, viennent toujours de l'environnement, pour qu'un mot
    de passe ne traîne jamais dans un historique de commandes.
    """
    client_mqtt.connect(hote or adresse(), numero or port(), keepalive=keepalive)
    return client_mqtt


def resume(hote=None, numero=None):
    """Ce vers quoi on se connecte, pour l'afficher au démarrage.

    Le mot de passe n'y figure jamais : ces lignes finissent dans les journaux.
    """
    compte, _ = identite()
    return (f"{hote or adresse()}:{numero or port()}"
            + (f" en tant que « {compte} »" if compte else " (accès anonyme)")
            + (", liaison chiffrée" if tls_demande() else ""))
