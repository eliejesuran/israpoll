#!/usr/bin/env bash
# Boucle de collecte : résultats CEC -> live.json, publié sur la branche orpheline `data`
# (le site la lit via raw.githubusercontent.com, qui autorise le CORS).
#
#   scripts/live.sh [durée_en_secondes=0] [intervalle=30]
#
# Sans argument : un seul passage. À lancer depuis une IP que la CEC ne filtre pas (les serveurs GitHub reçoivent un
# défi anti-bot) ; nécessite `git push` vers le dépôt.
set -uo pipefail
DURATION=${1:-0}
INTERVAL=${2:-30}
cd "$(dirname "$0")/.."

WORK=$(mktemp -d)
PUSH_URL=$(git config --get remote.origin.url)
SLUG=$(echo "$PUSH_URL" | sed -E 's#^(git@github.com:|https://github.com/)##; s#\.git$##')

if git fetch -q origin data 2>/dev/null; then git show FETCH_HEAD:live.json > "$WORK/prev.json" 2>/dev/null || echo '{}' > "$WORK/prev.json"; else echo '{}' > "$WORK/prev.json"; fi

push() {
  local t; t=$(mktemp -d)
  cp "$WORK/live.json" "$t/live.json"
  ( cd "$t" && git init -q -b data && git add live.json \
    && git -c user.name=israpoll-bot -c user.email=israpoll-bot@users.noreply.github.com commit -qm "live $(date -u +%FT%TZ)" \
    && git push -q -f "$PUSH_URL" data ) || echo "push échoué" >&2
  # raw.githubusercontent.com garde 5 min en cache ; jsDelivr se rafraîchit en quelques secondes une fois purgé.
  sleep 3   # laisse GitHub exposer le nouveau commit avant de purger
  curl -s -m 10 -o /dev/null "https://purge.jsdelivr.net/gh/${SLUG}@data/live.json" || true
}

end=$(( $(date +%s) + DURATION )); n=0; last=""
while :; do
  # data/manual.json (participation, sondages sortie des urnes…) est lu sur `main` à chaque tour : on peut l'éditer en direct.
  if git fetch -q origin main 2>/dev/null && git show FETCH_HEAD:data/manual.json > "$WORK/manual.json" 2>/dev/null; then :; else cp data/manual.json "$WORK/manual.json"; fi
  skip=""; (( n % 6 != 0 )) && skip="--skip-html"
  python3 -I scripts/fetch_cec.py --out "$WORK/live.json" --manual "$WORK/manual.json" --prev "$WORK/prev.json" $skip || true
  d=$(python3 -I -c "import json,sys;print(json.load(open(sys.argv[1])).get('digest',''))" "$WORK/live.json" 2>/dev/null || echo "")
  if [[ -s "$WORK/live.json" ]] && { [[ "$d" != "$last" ]] || (( n % 10 == 0 )); }; then push; last="$d"; fi
  [[ -s "$WORK/live.json" ]] && cp "$WORK/live.json" "$WORK/prev.json"
  n=$((n + 1))
  (( $(date +%s) >= end )) && break
  sleep "$INTERVAL"
done
