#!/usr/bin/env bash
# Importe le fichier « résultats par localité » (expc.csv) que TU as téléchargé sur le site de la CEC, dans ton navigateur, et le publie.
#
#   scripts/import_csv.sh [fichier.csv] [--dry] [-y]
#
# Pourquoi : la CEC protège ses fichiers par un défi anti-bot que seul un vrai navigateur passe ; le projet ne le contourne pas
# (voir CLAUDE.md). Un humain qui télécharge le fichier — lien « תוצאות לפי יישובים (קובץ להורדה) » de
# https://votes26.bechirot.gov.il/nationalresults — reste la voie officielle et exacte (voix par liste, commune par commune).
#
# Sans argument : prend le CSV le plus récent de ~/Downloads dont l'en-tête est celui de la CEC. Affiche un résumé (communes, bulletins, premières
# listes), refuse un fichier qui n'est pas de la CEC, puis demande confirmation avant de publier. --dry : résumé seulement ; -y : sans question.
set -euo pipefail
cd "$(dirname "$0")/.."
dry=0; yes=0; file=""
for a in "$@"; do case "$a" in --dry) dry=1 ;; -y) yes=1 ;; *) file="$a" ;; esac; done

if [[ -z "$file" ]]; then
  while IFS= read -r f; do
    if head -c 600 "$f" 2>/dev/null | grep -q "כשרים"; then file="$f"; break; fi
  done < <(ls -t "${DOWNLOADS:-$HOME/Downloads}"/*.csv 2>/dev/null || true)
fi
[[ -n "$file" && -f "$file" ]] || { echo "aucun fichier CSV de la CEC trouvé (en-tête contenant « כשרים ») : télécharge-le depuis le site de la CEC ou passe son chemin en argument" >&2; exit 1; }

python3 -I - "$file" <<'PY'
import os, sys, time
sys.path.insert(0, "scripts")
import fetch_cec
path = sys.argv[1]
try:
    with open(path, encoding="utf-8-sig") as f:
        votes, totals, rows = fetch_cec.parse_csv(f.read())
except (OSError, ValueError) as e:
    sys.exit(f"fichier refusé : {e}")
age = (time.time() - os.path.getmtime(path)) / 60
print(f"fichier : {path}  (téléchargé il y a {age:.0f} min)")
print(f"communes : {rows} · bulletins valides : {totals['valid']:,} · votants : {totals['voters']:,} · inscrits : {totals['eligible']:,}".replace(",", " "))
if totals["valid"] <= 0:
    sys.exit("le fichier ne contient aucun bulletin dépouillé : rien à publier")
top = sorted(votes.items(), key=lambda kv: -kv[1])[:5]
print("premières listes (lettre de vote : voix, %) : " + " · ".join(f"{l} {v:,} ({v / totals['valid']:.1%})".replace(",", " ") for l, v in top))
if age > 90:
    print("ATTENTION : ce fichier date de plus de 90 min ; vérifie que c'est le dernier téléchargement.")
PY

(( dry )) && { echo "(--dry : rien n'est publié)"; exit 0; }
if (( ! yes )); then
  read -r -p "Publier ces chiffres sur le site ? [o/N] " ans
  [[ "$ans" == [oOyY]* ]] || { echo "annulé"; exit 0; }
fi
CSV_FILE="$file" scripts/live.sh 0
echo "publié : le site (et le collecteur du Jetson) reprennent ces chiffres dans la minute."
