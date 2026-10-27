#!/usr/bin/env bash
# Boucle de collecte : résultats CEC -> live.json, publié sur la branche orpheline `data`
# (le site la lit via raw.githubusercontent.com, qui autorise le CORS).
#
#   scripts/live.sh [durée_en_secondes=0] [intervalle=30]
#
# Sans argument : un seul passage (cron GitHub Actions). Fonctionne aussi en local si `git push` est configuré.
set -uo pipefail
DURATION=${1:-0}
INTERVAL=${2:-30}
cd "$(dirname "$0")/.."

WORK=$(mktemp -d)
if [[ -n "${GITHUB_TOKEN:-}" && -n "${GITHUB_REPOSITORY:-}" ]]; then
  PUSH_URL="https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.git"
else
  PUSH_URL=$(git config --get remote.origin.url)
fi

if git fetch -q origin data 2>/dev/null; then git show FETCH_HEAD:live.json > "$WORK/prev.json" 2>/dev/null || echo '{}' > "$WORK/prev.json"; else echo '{}' > "$WORK/prev.json"; fi

push() {
  local t; t=$(mktemp -d)
  cp "$WORK/live.json" "$t/live.json"
  ( cd "$t" && git init -q -b data && git add live.json \
    && git -c user.name=israpoll-bot -c user.email=israpoll-bot@users.noreply.github.com commit -qm "live $(date -u +%FT%TZ)" \
    && git push -q -f "$PUSH_URL" data ) || echo "push échoué" >&2
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
