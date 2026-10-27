#!/usr/bin/env bash
# Superviseur du collecteur israpoll pour une petite machine Linux (testé : Jetson Orin Nano, Ubuntu 22.04).
#  - relancé chaque minute par cron ; `flock` garantit un seul superviseur (le verrou disparaît avec le processus) ;
#  - tout vit sous ~/israpoll-collector/work (disque : quelques Ko écrits par relevé). Ne PAS utiliser /dev/shm ni
#    /run/user : systemd-logind les vide à la fermeture de la dernière session SSH (RemoveIPC=yes par défaut), ce qui
#    supprimait le clone, les verrous et les logs en cours de route ;
#  - se remet à jour depuis `main` toutes les heures (corrections de code sans intervention sur la machine).
set -u
DIR="$HOME/israpoll-collector"
WORK="$DIR/work"
REPO="$WORK/repo"
LOG="$WORK/live.log"
mkdir -p "$WORK/tmp"
exec 9> "$WORK/supervisor.lock"
flock -n 9 || exit 0            # déjà en cours (le descripteur 9 reste hérité par live.sh : un orphelin bloque aussi un doublon)
export TMPDIR="$WORK/tmp"
export COLLECTOR_ID=jetson
KEY="$DIR/deploy_key"
SSH_BASE="ssh -i $KEY -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=$DIR/known_hosts -o ConnectTimeout=15"
trap 'exit 143' TERM INT HUP

log() { echo "$(date -u +%FT%TZ) $*" >> "$LOG"; }

pick_remote() {          # GitHub en SSH sur le port 22, sinon sur le 443 (réseaux qui filtrent le 22)
  if $SSH_BASE -T git@github.com 2>&1 | grep -q -E "successfully authenticated|Permission denied"; then
    echo "git@github.com:eliejesuran/israpoll.git"
  else
    echo "ssh://git@ssh.github.com:443/eliejesuran/israpoll.git"
  fi
}

while :; do
  export GIT_SSH_COMMAND="$SSH_BASE"
  if [ ! -d "$REPO/.git" ]; then
    rm -rf "$REPO"
    git clone -q --depth 1 "$(pick_remote)" "$REPO" >> "$LOG" 2>&1 || { log "clone impossible, nouvel essai dans 60 s"; sleep 60; continue; }
  else
    git -C "$REPO" fetch -q --depth 1 origin main >> "$LOG" 2>&1 && git -C "$REPO" reset -q --hard FETCH_HEAD >> "$LOG" 2>&1
  fi
  started=$(date +%s)
  nice -n 10 "$REPO/scripts/live.sh" 3600 30 >> "$LOG" 2>&1
  [ "$(stat -c %s "$LOG" 2>/dev/null || echo 0)" -gt 1000000 ] && tail -c 300000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
  [ $(( $(date +%s) - started )) -lt 20 ] && { log "le collecteur s'est arrêté aussitôt, pause de 30 s"; sleep 30; }
  sleep 2
done
