#!/usr/bin/env bash
# Dépose le site statique sur un hébergement FTPS (Infomaniak) avec curl, puis vérifie que le site publié correspond au dépôt.
#
#  - FTP **chiffré obligatoire** (--ssl-reqd) : le mot de passe ne part jamais en clair ; le certificat du serveur est vérifié.
#  - Seuls les fichiers du site sont déposés (liste FILES) ; **rien n'est jamais supprimé** sur le serveur.
#  - Les scripts et styles partent avant les pages HTML : un visiteur ne voit jamais une page neuve avec d'anciens scripts.
#  - Le mot de passe passe par un fichier de configuration curl temporaire (chmod 600), jamais par la ligne de commande.
#
# Variables : FTP_HOST, FTP_USER, FTP_PASSWORD, FTP_PATH (dossier distant du site, relatif à la racine FTP, ex. sites/eliejesuran.be/israpoll)
#             SITE_URL (facultatif, ex. https://eliejesuran.be/israpoll : active la vérification finale)
# Réglages de test : FTP_TLS=off (tests locaux uniquement), VERIFY_RETRIES (défaut 6), VERIFY_DELAY (défaut 10 s)
set -euo pipefail
cd "$(dirname "$0")/.."

for v in FTP_HOST FTP_USER FTP_PASSWORD FTP_PATH; do
  [[ -n "${!v:-}" ]] || { echo "variable manquante : $v" >&2; exit 2; }
done
# shellcheck source=scripts/ftp_host.sh
source "$(dirname "$0")/ftp_host.sh"
clean=$(ftp_host_clean "$FTP_HOST") || { echo "FTP_HOST invalide : il doit contenir un nom d'hôte (lettres, chiffres, points, tirets), par exemple xxxxx.ftp.infomaniak.com" >&2; exit 2; }
[[ "$clean" == "$FTP_HOST" ]] || echo "FTP_HOST contenait autre chose qu'un nom d'hôte (schéma, dossier, espaces) : seul le nom d'hôte est utilisé ; le dossier se règle dans FTP_PATH." >&2
FTP_HOST="$clean"

# Scripts et styles d'abord, pages HTML ensuite. Tout fichier local référencé par une page doit figurer ici (tests/test_deploy.py).
ASSETS=(css/site.css js/seats.js js/data2022.js js/compare.js js/common.js)
PAGES=(resultats.html analyse.html index.html)
HTACCESS=deploy/eliejesuran/.htaccess

base="${FTP_PATH#/}"; base="${base%/}"
tls=(--ssl-reqd); [[ "${FTP_TLS:-required}" == "off" ]] && tls=()

cfg=$(mktemp); chmod 600 "$cfg"; trap 'rm -f "$cfg"' EXIT
esc() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }
printf 'user = "%s:%s"\n' "$(esc "$FTP_USER")" "$(esc "$FTP_PASSWORD")" > "$cfg"

hint() {   # explication en français du code de sortie de curl
  case "$1" in
    64)       echo "→ le serveur n'accepte pas le FTP sur TLS explicite (AUTH TLS) à cette adresse. Vérifie que FTP_HOST est le nom du serveur FTP de l'hébergeur (pas le nom de domaine du site). Le diagnostic ci-dessous liste les modes que le serveur propose." >&2 ;;
    67|10)   echo "→ identifiant ou mot de passe FTP refusé (FTP_USER / FTP_PASSWORD)." >&2 ;;
    35|51|58|59|60|77|83) echo "→ échec du chiffrement ou certificat non reconnu : FTP_HOST doit être le nom officiel du serveur FTP (pas son adresse IP)." >&2 ;;
    6|7|28)   echo "→ serveur injoignable (nom inconnu, connexion refusée ou délai dépassé) : vérifie FTP_HOST." >&2 ;;
    9|78)     echo "→ dossier ou fichier refusé par le serveur : vérifie FTP_PATH et les droits de l'utilisateur FTP." >&2 ;;
  esac
}

upload() {   # upload <fichier local> <chemin distant relatif au dossier du site>
  local rc=0
  curl --silent --show-error --fail ${tls[@]+"${tls[@]}"} --ftp-create-dirs --connect-timeout 20 --retry 3 --retry-delay 2 \
       -K "$cfg" -T "$1" "ftp://${FTP_HOST}/${base}/$2" || rc=$?
  if (( rc )); then echo "échec du dépôt de $2 (curl : code $rc)" >&2; hint "$rc"; exit "$rc"; fi
  echo "déposé : $2"
}

for f in "${ASSETS[@]}" "${PAGES[@]}"; do
  [[ -f "$f" ]] || { echo "fichier introuvable : $f" >&2; exit 1; }
done
[[ -f "$HTACCESS" ]] && upload "$HTACCESS" ".htaccess"
for f in "${ASSETS[@]}" "${PAGES[@]}"; do upload "$f" "$f"; done

# Vérification : le site publié sert exactement les fichiers du dépôt (le cache du serveur peut mettre quelques secondes à tomber)
if [[ -n "${SITE_URL:-}" ]]; then
  site="${SITE_URL%/}"; tries="${VERIFY_RETRIES:-6}"; delay="${VERIFY_DELAY:-10}"
  for f in js/common.js index.html; do
    want=$(shasum -a 256 "$f" 2>/dev/null | cut -d' ' -f1 || sha256sum "$f" | cut -d' ' -f1)
    ok=0
    for ((i = 1; i <= tries; i++)); do
      got=$(curl --silent --fail --location -H 'Cache-Control: no-cache' "${site}/${f}?v=$RANDOM" 2>/dev/null | { shasum -a 256 2>/dev/null || sha256sum; } | cut -d' ' -f1 || true)
      [[ "$got" == "$want" ]] && { ok=1; break; }
      (( i < tries )) && sleep "$delay"
    done
    (( ok )) || { echo "vérification échouée : ${site}/${f} ne correspond pas au dépôt" >&2; exit 1; }
    echo "vérifié : ${site}/${f}"
  done
fi
echo "déploiement terminé."
