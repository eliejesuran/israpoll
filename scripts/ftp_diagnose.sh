#!/usr/bin/env bash
# Diagnostic SANS identifiants : le serveur FTP propose-t-il le FTP chiffré (TLS explicite) ? Aucun mot de passe n'est envoyé.
# Lancé automatiquement par le workflow quand le dépôt des fichiers échoue. Variable : FTP_HOST (nom d'hôte seul).
# À la main (le nom du serveur reste alors chez vous, pas dans un journal public) :  FTP_HOST=xxxx.exemple.ch scripts/ftp_diagnose.sh
# NB : les journaux d'une Action d'un dépôt public sont publics (adresse IP et bannière du serveur FTP visibles ; les secrets sont masqués).
set -u
: "${FTP_HOST:?variable manquante : FTP_HOST}"
source "$(dirname "$0")/ftp_host.sh"
FTP_HOST=$(ftp_host_clean "$FTP_HOST") || { echo "FTP_HOST invalide : un nom d'hôte est attendu (par exemple xxxxx.ftp.infomaniak.com)"; exit 2; }
HOST_ONLY="${FTP_HOST%%:*}"
T() { if command -v timeout >/dev/null 2>&1; then timeout "$@"; else perl -e 'alarm shift; exec @ARGV' "$@"; fi; }   # `timeout` absent sur macOS : repli perl

echo "== Réponse du serveur à « AUTH TLS » (FTP chiffré) — seul un identifiant anonyme est tenté, jamais le vôtre"
out=$(T 25 curl -sv --ssl-reqd --max-time 20 "ftp://${FTP_HOST}/" 2>&1 || true)
echo "$out" | grep -E '^(\* (Connected|SSL connection|TLSv)|< 220 |> AUTH|< [0-9]{3} )' | grep -v -i 'pass' | head -12

verdict="Indéterminé : relis les lignes ci-dessus."
if echo "$out" | grep -q -E '^< (500|502|504|534) .*(security|not implemented|TLS|SSL)'; then
  verdict="CE SERVEUR NE PROPOSE PAS LE FTP CHIFFRÉ (il répond « non implémenté » à AUTH TLS) : il n'accepte que le FTP en clair, donc le déploiement refuse (à raison) d'y envoyer le mot de passe. Prends dans le Manager de l'hébergeur le « serveur FTP » dédié (du type xxxxx.ftp.infomaniak.com, souvent différent du nom de domaine du site) et mets-le dans le secret FTP_HOST."
elif echo "$out" | grep -q -E '^\* (SSL connection|TLSv)'; then
  verdict="Le FTP chiffré fonctionne sur ce serveur : le problème vient des identifiants (FTP_USER / FTP_PASSWORD) ou du dossier (FTP_PATH)."
fi

echo; echo "== FTPS implicite (port 990)"
r=$({ T 12 bash -c 'exec 3<>/dev/tcp/$0/990 && echo "port ouvert"' "$HOST_ONLY"; } 2>/dev/null | head -2); echo "${r:-pas de réponse (port fermé ou filtré)}"
echo "== SSH/SFTP (port 22) : bannière"
r=$({ T 10 bash -c 'exec 3<>/dev/tcp/$0/22 && head -c 80 <&3' "$HOST_ONLY"; } 2>/dev/null | head -2); echo "${r:-pas de réponse (SSH non activé, port fermé ou filtré)}"
echo; echo "CONCLUSION : $verdict"
