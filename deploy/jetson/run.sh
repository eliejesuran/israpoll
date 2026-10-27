#!/usr/bin/env bash
# Superviseur du collecteur israpoll pour une petite machine Linux (testé : Jetson Orin Nano, Ubuntu 22.04).
#  - le dépôt est cloné en RAM (/dev/shm) : aucune écriture sur la microSD, hormis ce script et la clé de déploiement ;
#  - relancé chaque minute par cron : si un superviseur tourne déjà, il sort tout de suite (watchdog) ;
#  - se remet à jour depuis `main` toutes les heures (corrections de code sans intervention sur la machine).
set -u
DIR="$HOME/israpoll-collector"
RAM=/dev/shm/israpoll
LOCK=/dev/shm/israpoll-supervisor.lock
LOG=/dev/shm/israpoll-live.log
export TMPDIR=/dev/shm
export COLLECTOR_ID=jetson
KEY="$DIR/deploy_key"
SSH_BASE="ssh -i $KEY -o IdentitiesOnly=yes -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=$DIR/known_hosts -o ConnectTimeout=15"

if ! mkdir "$LOCK" 2>/dev/null; then
  old=$(cat "$LOCK/pid" 2>/dev/null || echo 0)
  kill -0 "$old" 2>/dev/null && exit 0
  rm -rf "$LOCK"; mkdir "$LOCK" || exit 1
fi
echo $$ > "$LOCK/pid"
trap 'rm -rf "$LOCK"' EXIT
trap 'exit 143' TERM INT HUP

pick_remote() {          # GitHub en SSH sur le port 22, sinon sur le 443 (réseaux qui filtrent le 22)
  if $SSH_BASE -T git@github.com 2>&1 | grep -q -E "successfully authenticated|Permission denied"; then
    echo "git@github.com:eliejesuran/israpoll.git"
  else
    echo "ssh://git@ssh.github.com:443/eliejesuran/israpoll.git"
  fi
}

while :; do
  export GIT_SSH_COMMAND="$SSH_BASE"
  if [ ! -d "$RAM/.git" ]; then
    rm -rf "$RAM"
    git clone -q --depth 1 "$(pick_remote)" "$RAM" >> "$LOG" 2>&1 || { echo "$(date -u +%FT%TZ) clone impossible, nouvel essai dans 60 s" >> "$LOG"; sleep 60; continue; }
  else
    git -C "$RAM" fetch -q --depth 1 origin main >> "$LOG" 2>&1 && git -C "$RAM" reset -q --hard FETCH_HEAD >> "$LOG" 2>&1
  fi
  nice -n 10 "$RAM/scripts/live.sh" 3600 30 >> "$LOG" 2>&1
  [ "$(stat -c %s "$LOG" 2>/dev/null || echo 0)" -gt 2000000 ] && tail -c 500000 "$LOG" > "$LOG.tmp" && mv "$LOG.tmp" "$LOG"
  sleep 2
done
