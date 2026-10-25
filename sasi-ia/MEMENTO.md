# Mémento du serveur

Serveur : `152.53.116.238` — Netcup VPS 500 ARM, Debian 13, ARM64.
Interface : `https://sasi.the7ing.site` (accès libre, sans mot de passe).

## À faire une fois

| Commande | Rôle |
|---|---|
| `echo 'source ~/AppSuivi/sasi-ia/outils/alias.sh' >> ~/.bashrc` | installe les raccourcis `sasi`, `frontal`, `etat` |
| `source ~/.bashrc` | les charge sans se reconnecter |

Tout ce qui suit suppose ces raccourcis en place.

## Se connecter

| Commande | Rôle | Quand |
|---|---|---|
| `ssh root@152.53.116.238` | ouvrir une session | à chaque fois |
| `tmux new -s sasi` | session qui survit à une coupure | avant toute commande longue |
| `tmux attach -t sasi` | y revenir | après une déconnexion |
| `Ctrl+B` puis `D` | en sortir sans rien arrêter | — |
| `exit` | fermer la session SSH | — |

## Voir l'état

| Commande | Rôle | Quand |
|---|---|---|
| `etat` | services, frontal, certificat, journaux | premier réflexe |
| `sasi ps` | les sept services | vérifier un `Restarting` |
| `sasi logs -f` | tous les journaux, en direct | pendant un essai |
| `sasi logs --tail 30 ia` | les 30 dernières lignes d'un service | une panne précise |
| `free -h` | mémoire vive et échange | lenteurs |
| `df -h /` | espace disque | mensuellement |
| `docker stats --no-stream` | charge par conteneur | lenteurs |

Services : `api`, `connecteur`, `ia`, `alertes`, `base`, `mosquitto`, `jumeau`.

## Mettre à jour le code

| Commande | Rôle |
|---|---|
| `cd ~/AppSuivi/sasi-ia && git pull` | récupérer les corrections |
| `sasi up -d --build` | reconstruire et redémarrer ce qui a changé |
| `sasi --profile demonstration up -d --build` | idem, jumeau de démonstration inclus |
| `etat` | contrôler le résultat |

## Démarrer, arrêter, relancer

| Commande | Rôle | Attention |
|---|---|---|
| `sasi restart ia` | relancer un seul service | sans effet sur les autres |
| `sasi stop` | arrêter SASI | les données restent |
| `sasi up -d` | redémarrer | — |
| `sasi down` | supprimer les conteneurs | les volumes restent |
| `sasi down -v` | **supprime aussi la base et les modèles** | irréversible |

## Le frontal (ports 80 et 443, partagé)

| Commande | Rôle | Attention |
|---|---|---|
| `frontal exec caddy caddy reload --config /etc/caddy/Caddyfile` | prendre en compte un fichier de `sites/` | n'interrompt rien |
| `frontal logs --tail 30` | certificats, requêtes refusées | — |
| `frontal up -d --force-recreate` | appliquer un changement de composition | coupe les **deux** applications quelques secondes |
| `frontal restart` | relancer | idem |

Ne jamais supprimer le volume `frontal_caddy_data` : il contient les certificats, et Let's Encrypt limite à cinq certificats identiques par semaine.

## La base de données

| Commande | Rôle |
|---|---|
| `sasi exec base psql -U sasi -d sasi` | ouvrir une session SQL (`\q` pour sortir) |
| `sasi exec base psql -U sasi -d sasi -c "select count(*) from mesure;"` | les mesures arrivent-elles ? |
| `sasi exec base psql -U sasi -d sasi -c "select count(*) from alerte;"` | combien d'alertes |
| `~/sauvegarder.sh` | sauvegarde immédiate (voir `DEPLOIEMENT.md`, § 6) |

Le compte est toujours `sasi`, le mot de passe est dans `.env` et n'est demandé qu'en dehors du conteneur.

## Réglages et secrets

| Commande | Rôle | Attention |
|---|---|---|
| `cat .env` | lire les réglages | contient les mots de passe |
| `bash outils/regler.sh --forcer` | tout régler à neuf | garde une copie en `.env.precedent` |
| `grep SASI_SITE .env` | quel site est surveillé | `brasserie` ou `minoterie` |

`.env` n'est jamais suivi par Git, et le dépôt est public.

## Remettre un mot de passe sur l'interface

1. `nano config/proxy/sites/sasi.caddy` — décommenter le bloc `basic_auth` voulu : sur tout le site, ou sur les seules requêtes qui modifient.
2. `bash outils/regler.sh --forcer` si `.env` n'a pas d'empreinte.
3. `frontal exec caddy caddy reload --config /etc/caddy/Caddyfile`

## Pannes courantes

| Symptôme | Commande | Cause fréquente |
|---|---|---|
| un service en `Restarting` | `sasi logs --tail 30 <service>` | dépendance absente, adresse erronée |
| `HTTPS : aucune réponse` | `frontal logs --tail 30` | DNS, ou port 80 fermé |
| `HTTPS 502` | `sasi logs --tail 30 api` | l'application ne répond pas |
| écrans figés | `sasi logs --tail 20 connecteur jumeau` | plus de mesures publiées |
| `permission denied` sur un fichier | `sasi exec api ls -l retours` | identifiants d'utilisateur différents entre images |
| serveur lent | `docker stats --no-stream` | entraînement en cours (deux cœurs) |

## Système

| Commande | Rôle | Quand |
|---|---|---|
| `apt update && apt upgrade -y` | correctifs de sécurité | une fois par mois |
| `ufw status` | ports ouverts (22, 80, 443) | après tout changement réseau |
| `docker system prune -f` | effacer images et caches inutiles | disque plein |
| `reboot` | redémarrer la machine | les services repartent seuls |

## Seconde application

Conditions pour partager le serveur : aucun port publié, réseau externe `frontal` avec un alias stable, un fichier `config/proxy/sites/<nom>.caddy` puis un rechargement du frontal. Modèle : `config/proxy/sites/exemple-seconde-app.caddy.modele`.

Plus de détail dans `DEPLOIEMENT.md` ; les décisions et les pannes rencontrées sont dans `JOURNAL.md`.
