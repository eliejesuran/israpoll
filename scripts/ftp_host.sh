#!/usr/bin/env bash
# Nettoie la valeur du secret FTP_HOST : accepte « hôte », « hôte:port » ou « ftp://hôte/dossier » collé par erreur et ne garde que
# « hôte[:port] » (le dossier va dans FTP_PATH). Refuse tout autre caractère. Utilisé par deploy_ftp.sh et ftp_diagnose.sh.
ftp_host_clean() {
  local h="$1"
  h="${h//[$'\r\n\t ']/}"            # espaces et retours à la ligne collés avec la valeur
  h="${h#*://}"; h="${h%%/*}"        # schéma et chemin éventuels
  [[ "$h" =~ ^[A-Za-z0-9._-]+(:[0-9]{1,5})?$ ]] || return 1
  printf '%s' "$h"
}
