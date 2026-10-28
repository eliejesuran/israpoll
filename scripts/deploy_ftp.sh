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
[[ "$FTP_HOST" != */* && "$FTP_HOST" != *:* ]] || { echo "FTP_HOST doit être un nom d'hôte seul (sans schéma, port ni chemin)" >&2; exit 2; }

# Scripts et styles d'abord, pages HTML ensuite. Tout fichier local référencé par une page doit figurer ici (tests/test_deploy.py).
ASSETS=(css/site.css js/seats.js js/data2022.js js/compare.js js/common.js)
PAGES=(resultats.html analyse.html index.html)
HTACCESS=deploy/eliejesuran/.htaccess

base="${FTP_PATH#/}"; base="${base%/}"
tls=(--ssl-reqd); [[ "${FTP_TLS:-required}" == "off" ]] && tls=()

cfg=$(mktemp); chmod 600 "$cfg"; trap 'rm -f "$cfg"' EXIT
esc() { printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e 's/"/\\"/g'; }
printf 'user = "%s:%s"\n' "$(esc "$FTP_USER")" "$(esc "$FTP_PASSWORD")" > "$cfg"

upload() {   # upload <fichier local> <chemin distant relatif au dossier du site>
  curl --silent --show-error --fail ${tls[@]+"${tls[@]}"} --ftp-create-dirs --connect-timeout 20 --retry 3 --retry-delay 2 \
       -K "$cfg" -T "$1" "ftp://${FTP_HOST}/${base}/$2"
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
