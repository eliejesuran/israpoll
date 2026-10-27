#!/usr/bin/env bash
# Installe le collecteur israpoll sur la machine courante (sans sudo).
# Écrit sur le disque : ~/israpoll-collector (quelques Ko : script + clé de déploiement) et deux lignes de crontab.
# Le clone du dépôt, les fichiers temporaires et les logs vivent dans /dev/shm (RAM).
set -euo pipefail
DIR="$HOME/israpoll-collector"
mkdir -p "$DIR"
install -m 755 "$(dirname "$0")/run.sh" "$DIR/run.sh"
[ -f "$DIR/deploy_key" ] || ssh-keygen -q -t ed25519 -N "" -C "israpoll-collector" -f "$DIR/deploy_key"
chmod 600 "$DIR/deploy_key"
echo "Clé publique à ajouter comme « deploy key » (avec droit d'écriture) du dépôt :"
cat "$DIR/deploy_key.pub"
( crontab -l 2>/dev/null | grep -v "israpoll-collector" || true
  echo "@reboot $DIR/run.sh >/dev/null 2>&1 # israpoll-collector"
  echo "* * * * * $DIR/run.sh >/dev/null 2>&1 # israpoll-collector" ) | crontab -
echo "Installé. Démarrage immédiat : nohup $DIR/run.sh >/dev/null 2>&1 &"
