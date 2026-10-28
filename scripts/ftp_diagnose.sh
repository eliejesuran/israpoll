#!/usr/bin/env bash
# Diagnostic SANS identifiants : quels modes de connexion le serveur FTP propose-t-il ? (aucun mot de passe n'est envoyé)
# Lancé automatiquement par le workflow quand le dépôt des fichiers échoue. Variable : FTP_HOST (nom d'hôte seul).
set -u
: "${FTP_HOST:?variable manquante : FTP_HOST}"
probe() { echo; echo "== $1"; shift; "$@" 2>&1 | head -"${LINES_MAX:-14}"; }

probe "FTP sur TLS explicite (port 21, commande AUTH TLS) — le mode attendu par le déploiement" \
  timeout 25 openssl s_client -starttls ftp -connect "${FTP_HOST}:21" -brief </dev/null
probe "FTPS implicite (port 990)" \
  timeout 15 openssl s_client -connect "${FTP_HOST}:990" -brief </dev/null
probe "FTP en clair (port 21) : bannière seule" \
  timeout 10 bash -c 'exec 3<>/dev/tcp/$0/21 && head -c 300 <&3' "$FTP_HOST"
probe "SSH/SFTP (port 22) : bannière" \
  timeout 10 bash -c 'exec 3<>/dev/tcp/$0/22 && head -c 120 <&3' "$FTP_HOST"
echo
echo "Lecture : « Verification: OK » + « CONNECTION ESTABLISHED » sur la 1re sonde = FTP sur TLS explicite disponible."
echo "Sinon, si la bannière SSH apparaît, le dépôt peut passer en SFTP ; si seul le FTP en clair répond, il ne faut PAS l'utiliser."
