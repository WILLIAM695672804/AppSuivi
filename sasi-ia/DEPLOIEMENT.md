# Mise en service sur un serveur en ligne

Pour un VPS neuf chez n'importe quel hébergeur. Les commandes sont à exécuter
sur le serveur, en SSH. Le serveur de référence est un **Netcup VPS 500 ARM
G12.5** — 2 cœurs ARM64, 4 Go de mémoire, 64 Go NVMe — dont la compatibilité a
été vérifiée composant par composant.

## Ce que l'on obtient

Un système complet joignable en HTTPS : interface, serveur d'application, IA,
moteur d'alertes, serveur de messages et base de données. Seuls les ports **80**
et **443** sont ouverts ; ni la base ni le serveur de messages ne sont joignables
depuis Internet.

Le serveur peut héberger **plusieurs applications**. Deux ne pouvant pas occuper
les ports 80 et 443 en même temps, un **frontal partagé** les détient et
achemine chaque requête selon le nom de domaine demandé :

```
                            ┌─ sasi.the7ing.site  ──► SASI      (sasi-api:8000)
Internet ──► Caddy (80/443) ┤
     frontal partagé        └─ autre.the7ing.site ──► seconde application
```

SASI ne publie donc aucun port : elle rejoint le réseau `frontal` sous le nom
`sasi-api` et se laisse appeler. Le frontal vit à part des applications,
volontairement — redémarrer SASI n'interrompt pas l'autre application.

## Ce que l'on n'obtient pas

| Manque | Pourquoi | Conséquence |
|---|---|---|
| Les **SMS** d'escalade | Le modem 4G est sur le site industriel, pas dans un centre de données | L'escalade s'arrête aux notifications de l'application |
| Les **comptes réels** | Pas encore développés : le rôle se choisit dans une liste | Un mot de passe unique au niveau du proxy protège l'accès |
| Les **vraies caméras** | Le jumeau numérique n'est pas prêt | Le jumeau provisoire produit les mesures (`--demo`) |

Le mot de passe du proxy n'est pas un détail d'esthétique : l'application permet
d'acquitter et de clôturer des alertes. Tant que l'authentification n'est pas
faite, il est la seule chose qui sépare un visiteur de la console de surveillance.

## Avant de commencer

1. **Un sous-domaine qui désigne déjà le serveur.** Un enregistrement `A` vers
   l'adresse IPv4 du VPS — un sous-domaine par application, la racine restant
   libre pour une vitrine. À vérifier avant toute autre chose :

   ```bash
   dig +short sasi.votredomaine.site
   ```

   La réponse doit être exactement l'IPv4 du serveur. Caddy demande le certificat
   à Let's Encrypt en prouvant qu'il contrôle le domaine ; si celui-ci ne résout
   pas encore, la demande échoue — et les échecs sont limités par heure et par
   domaine. Quinze minutes d'attente valent mieux qu'un refus.

2. **Un accès SSH au serveur**, de préférence par clé.

## 1. Préparer le système

```bash
# Mises à jour, puis les quelques outils nécessaires
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ca-certificates

# Docker, par le script officiel : il choisit seul le paquet ARM64 ou x86-64
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"      # puis se déconnecter et se reconnecter
```

**Mémoire d'échange** — 2 Go, par prudence. Le système consomme 1,2 Go en régime
établi, mais un entraînement culmine à 1,5 Go : sur une machine à 4 Go, un pic
simultané pourrait faire tuer un service par le noyau.

```bash
sudo fallocate -l 2G /echange && sudo chmod 600 /echange
sudo mkswap /echange && sudo swapon /echange
echo '/echange none swap sw 0 0' | sudo tee -a /etc/fstab
```

**Pare-feu** — on n'ouvre que le strict nécessaire.

```bash
sudo apt install -y ufw
sudo ufw allow 22/tcp      # SSH : à autoriser AVANT d'activer, sans quoi
sudo ufw allow 80/tcp      #       vous vous coupez l'accès à la machine
sudo ufw allow 443/tcp
sudo ufw --force enable
```

> En cas de coupure d'accès, Netcup offre une **console à distance** dans son
> panneau : c'est le filet de sécurité. Repérez-la avant d'activer le pare-feu.

## 2. Récupérer le projet et le régler

```bash
git clone https://github.com/WILLIAM695672804/AppSuivi.git
cd AppSuivi/sasi-ia
cp .env.exemple .env
```

Un script écrit ce fichier pour vous ; c'est la voie recommandée :

```bash
bash outils/regler.sh
```

Il demande le domaine, le compte et le mot de passe de l'interface, calcule
l'empreinte, engendre les deux mots de passe internes, écrit `.env` en `600` et
vérifie que docker compose le relit sans erreur. Il refuse d'écraser un `.env`
existant sans `--forcer`, et en garde alors une copie sous `.env.precedent`.

**Pourquoi un script plutôt que des commandes à coller.** Un terminal distant
dénature le collage de trois façons, chacune constatée sur le serveur : il
indente les lignes, et le délimiteur d'un *heredoc* n'est plus reconnu en début
de ligne ; il coupe les lignes longues en y insérant de vrais retours à la
ligne, qui scindent la commande ; et `read` consomme la ligne suivante du
collage au lieu d'attendre une frappe. Le script ne traverse pas le collage :
tout se passe dans un seul processus.

Les secrets à la main, si vous y tenez — **ne les choisissez pas vous-même** :

```bash
openssl rand -hex 24                        # pour MOT_DE_PASSE_BASE
openssl rand -hex 24                        # pour MQTT_MOT_DE_PASSE
docker run --rm caddy:2-alpine caddy hash-password --plaintext 'votre-mot-de-passe'
```

`-hex` et non `-base64` : le mot de passe de la base voyage dans une URL
(`postgresql://sasi:…@base:5432/sasi`), où un `/` — que l'alphabet base64
produit une fois sur deux — clôt l'autorité. La connexion échouerait alors sur
un message sans rapport avec sa cause. `outils/deployer.sh` refuse d'avancer si
le mot de passe contient un tel caractère.

Puis `nano .env` et remplir les six lignes. **L'empreinte bcrypt doit être entre
guillemets simples** : elle contient des `$` que docker compose et bash
prendraient sinon pour des variables, et le mot de passe serait refusé sans
explication.

## 3. Mettre en service

```bash
./outils/deployer.sh --demo
```

Le script contrôle les prérequis, refuse d'avancer si le domaine ne désigne pas
cette machine, crée le compte du serveur de messages, bâtit les images, démarre
les services, attend la base et y verse la description du site. Il est
idempotent : on le relance sans dommage.

**L'interface est bâtie sur le serveur**, pas sur votre poste : le VPS télécharge
les dépendances Node à sa vitesse, et votre connexion n'envoie que du code
source. Comptez quelques minutes la première fois.

Sans `--demo`, aucune source de mesures n'est active et les écrans restent vides
— c'est le mode qui conviendra quand le vrai jumeau publiera.

## 4. Ajouter la seconde application

Rien à refaire côté SASI. Deux conditions pour l'application qui arrive :

1. **Ne publier aucun port** — pas de `ports:` dans sa composition, sinon elle
   se disputera les ports 80 et 443 avec le frontal.
2. **Rejoindre le réseau `frontal`** avec un alias stable :

   ```yaml
   services:
     son-serveur:
       networks:
         frontal:
           aliases: [autre-app]
   networks:
     frontal:
       name: frontal
       external: true
   ```

Puis déposer son fichier d'acheminement et recharger :

```bash
cp config/proxy/sites/exemple-seconde-app.caddy.modele \
   config/proxy/sites/autre.caddy
nano config/proxy/sites/autre.caddy      # nom de domaine et alias
./outils/deployer.sh --frontal
```

Le rechargement relit la configuration **sans couper les connexions en cours** :
l'autre application ne s'en aperçoit pas, et SASI non plus.

N'oubliez pas l'enregistrement `A` du nouveau sous-domaine : le frontal répond
`421 Hôte inconnu` à tout nom qu'il ne connaît pas, ce qui évite qu'un tiers
fasse pointer son domaine vers votre serveur et obtienne un certificat en votre nom.

## 5. Vérifier

```bash
./outils/deployer.sh --etat
curl -u william:motdepasse https://sasi.votredomaine.site/api/etat
```

Puis ouvrir `https://sasi.votredomaine.site` dans un navigateur. Les niveaux et
les alertes arrivent par WebSocket, donc instantanément ; les courbes se
rafraîchissent toutes les 10 secondes, soit la cadence même des mesures.

## 6. Sauvegarder

Deux niveaux, complémentaires :

**Les instantanés Netcup**, dans son panneau. Ils capturent la machine entière et
permettent de revenir en arrière après une mauvaise manipulation. À prendre
avant chaque opération risquée.

**La base**, chaque nuit — un instantané de machine est trop grossier pour
récupérer une seule table :

```bash
mkdir -p ~/sauvegardes
cat > ~/sauvegarder.sh <<'FIN'
#!/usr/bin/env bash
set -eu
cd ~/AppSuivi/sasi-ia
jour=$(date +%F)
docker compose -f docker-compose.production.yml exec -T base \
    pg_dump -U sasi -d sasi --format=custom > ~/sauvegardes/sasi-$jour.dump
find ~/sauvegardes -name 'sasi-*.dump' -mtime +14 -delete
FIN
chmod +x ~/sauvegarder.sh
(crontab -l 2>/dev/null; echo "30 2 * * * $HOME/sauvegarder.sh") | crontab -
```

Une sauvegarde qui n'a jamais été restaurée n'est pas une sauvegarde : essayez
la restauration une fois, sur une base jetable.

## Mettre à jour

```bash
cd ~/AppSuivi && git pull && cd sasi-ia && ./outils/deployer.sh
```

Les données vivent dans des volumes : elles survivent à la reconstruction des
images. Le script ne touche jamais à la base.

## Si quelque chose ne va pas

| Symptôme | Cause probable | Vérification |
|---|---|---|
| Pas de HTTPS, erreur de certificat | Le domaine ne résout pas, ou le port 80 est fermé | `dig +short <domaine>` et `sudo ufw status` |
| Mot de passe refusé | Empreinte bcrypt tronquée par un `$` non protégé | Guillemets simples dans `.env` |
| Écrans vides | Aucune source de mesures | `./outils/deployer.sh --demo` |
| Un service redémarre en boucle | Mot de passe du serveur de messages désaccordé | `docker compose -f docker-compose.production.yml logs ia` |
| `421 Hôte inconnu` | Aucun fichier d'acheminement pour ce domaine | `ls config/proxy/sites/` |
| Le frontal refuse de démarrer | Les ports 80 ou 443 sont déjà pris | `sudo ss -tlnp \| grep -E ':80\|:443'` |
| Interface lente | Mémoire saturée pendant un entraînement | `free -h`, et vérifier l'échange |

Journaux d'un service : `docker compose -f docker-compose.production.yml logs -f <service>`,
où `<service>` vaut `api`, `ia`, `alertes`, `connecteur`, `base`, `mosquitto` ou
`jumeau`. Pour le frontal, qui vit à part :
`docker compose -f config/proxy/docker-compose.yml logs -f caddy`.

## Compatibilité ARM64, vérifiée

| Composant | État |
|---|---|
| LightGBM 4.7.0 | roue `manylinux_2_17_aarch64` publiée |
| psycopg-binary, pydantic-core | roues `aarch64` publiées |
| TimescaleDB PG16 | image `arm64` publiée |
| PostgreSQL 16 (repli) | image `arm64` publiée |
| Mosquitto, Caddy, Python, Node | images officielles multi-architecture |

Aucune compilation à prévoir. Si l'image TimescaleDB venait à manquer, le schéma
fonctionne sur `postgres:16` seul — sans compression ni purge automatique, mais
toutes les tables et toutes les écritures restent opérantes.
