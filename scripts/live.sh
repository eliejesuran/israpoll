#!/usr/bin/env bash
# Boucle de collecte : résultats CEC -> live.json, publié sur la branche orpheline `data`
# (le site la lit via l'API GitHub, ~1 min de latence, et raw.githubusercontent.com, 5 min de cache, en repli).
#
#   scripts/live.sh [durée_en_secondes=0] [intervalle=30]
#   CSV_FILE=~/Downloads/expc.csv scripts/live.sh      # un passage avec le fichier téléchargé à la main sur le site de la CEC
#
# Sans argument : un seul passage. À lancer depuis une IP que la CEC ne filtre pas ; nécessite `git push` vers le dépôt.
# La CEC protège ses fichiers par un défi anti-bot : on ne le contourne pas (voir fetch_cec.py). Un seul collecteur à
# la fois par machine (verrou). Plusieurs machines peuvent publier : chacune adopte les chiffres plus avancés des autres.
set -uo pipefail
DURATION=${1:-0}
INTERVAL=${2:-30}
HEARTBEAT=4            # republie au moins tous les 4 tours (~2 min) même sans changement : le site en déduit que le collecteur est vivant
NEWS_EVERY=20          # relève aussi les titres de presse (« À lire ») tous les 20 tours (~10 min) : les tâches planifiées de GitHub
                       # Actions ne se déclenchent pas de façon fiable sur ce dépôt (aucune exécution `schedule` en 3 h)
cd "$(dirname "$0")/.."

LOCK="${TMPDIR:-/tmp}/israpoll-live.lock"
if ! mkdir "$LOCK" 2>/dev/null; then
  old=$(cat "$LOCK/pid" 2>/dev/null || echo 0)
  if kill -0 "$old" 2>/dev/null; then echo "un collecteur tourne déjà (pid $old)" >&2; exit 1; fi
  rm -rf "$LOCK"; mkdir "$LOCK"             # verrou périmé (processus mort)
fi
echo $$ > "$LOCK/pid"
WORK=$(mktemp -d)
trap 'rm -rf "$WORK" "$LOCK"' EXIT
trap 'exit 143' TERM INT HUP

TO=""; command -v timeout >/dev/null 2>&1 && TO="timeout 150"        # absent sur macOS : on s'en passe
PUSH_URL=$(git config --get remote.origin.url)
SUPERVISED=0; [[ "$PWD" == */israpoll-collector/work/repo ]] && SUPERVISED=1   # clone géré par deploy/jetson/run.sh : se met à jour seul

sync_refs() {                                 # met à jour `main` (manual.json) et `data` (relevé des autres collecteurs)
  git fetch -q origin +main:refs/remotes/origin/main +data:refs/remotes/origin/data 2>/dev/null
}
if sync_refs && git show origin/data:live.json > "$WORK/prev.json" 2>/dev/null; then :; else echo '{}' > "$WORK/prev.json"; fi

publish() {                                   # publish <branche> <fichier> <nom dans la branche> ; branche orpheline, force-push
  local t; t=$(mktemp -d)
  cp "$2" "$t/$3"
  if ( cd "$t" && git init -q -b "$1" && git add "$3" \
       && git -c user.name=israpoll-bot -c user.email=israpoll-bot@users.noreply.github.com commit -qm "$1 $(date -u +%FT%TZ)" \
       && git push -q -f "$PUSH_URL" "$1" ); then
    rm -rf "$t"; return 0
  fi
  rm -rf "$t"; echo "push $1 échoué" >&2; return 1
}
push() { publish data "$WORK/live.json" live.json; }   # renvoie 0 si la branche `data` a bien été mise à jour

news_cycle() {                                # titres de presse -> branche `news` (les flux RSS n'ont pas de défi anti-bot)
  [[ -f scripts/fetch_news.py ]] || return 0
  git fetch -q origin +news:refs/remotes/origin/news 2>/dev/null
  local prevn=(); git show origin/news:news.json > "$WORK/news_prev.json" 2>/dev/null && prevn=(--prev "$WORK/news_prev.json")
  rm -f "$WORK/news.json"
  $TO python3 -I scripts/fetch_news.py --out "$WORK/news.json" ${prevn[@]+"${prevn[@]}"} || { echo "actualités : aucun relevé" >&2; return 0; }
  [[ -s "$WORK/news.json" ]] && publish news "$WORK/news.json" news.json
  return 0
}

end=$(( $(date +%s) + DURATION )); n=0; last=""
while :; do
  # data/manual.json (participation, sorties des urnes…) est lu sur `main` à chaque tour : on peut l'éditer en direct.
  if sync_refs && git show origin/main:data/manual.json > "$WORK/manual.json" 2>/dev/null; then :; else cp data/manual.json "$WORK/manual.json"; fi
  peer=(); if git show origin/data:live.json > "$WORK/peer.json" 2>/dev/null; then peer=(--peer "$WORK/peer.json"); fi

  # Sur le clone supervisé : applique les corrections publiées sur `main` ; si ce script a changé, il se relance.
  if (( SUPERVISED && n > 0 && n % 10 == 0 )); then
    before=$(sha1sum scripts/live.sh | cut -d' ' -f1)
    if git fetch -q --depth 1 origin main 2>/dev/null && git reset -q --hard FETCH_HEAD 2>/dev/null; then
      after=$(sha1sum scripts/live.sh | cut -d' ' -f1)
      if [[ "$before" != "$after" ]]; then rm -rf "$WORK" "$LOCK"; exec "$0" "$(( end - $(date +%s) ))" "$INTERVAL"; fi
    fi
  fi

  if (( n % NEWS_EVERY == 0 )) && [[ -z "${CSV_FILE:-}" ]]; then news_cycle; fi
  skip=(); (( n % 6 != 0 )) && skip=(--skip-html)
  csv=(); [[ -n "${CSV_FILE:-}" ]] && csv=(--csv-file "$CSV_FILE")
  rm -f "$WORK/live.json"
  $TO python3 -I scripts/fetch_cec.py --out "$WORK/live.json" --manual "$WORK/manual.json" --prev "$WORK/prev.json" ${peer[@]+"${peer[@]}"} ${csv[@]+"${csv[@]}"} ${skip[@]+"${skip[@]}"} || echo "relevé échoué" >&2
  if [[ -s "$WORK/live.json" ]]; then
    d=$(python3 -I -c "import json,sys;print(json.load(open(sys.argv[1])).get('digest',''))" "$WORK/live.json" 2>/dev/null || echo "")
    if [[ -n "$d" ]]; then
      if [[ "$d" != "$last" ]] || (( n % HEARTBEAT == 0 )); then push && last="$d"; fi
      cp "$WORK/live.json" "$WORK/prev.json"
    fi
  fi
  n=$((n + 1))
  (( $(date +%s) >= end )) && break
  sleep "$INTERVAL"
done
