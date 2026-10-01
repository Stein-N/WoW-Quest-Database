#!/usr/bin/env bash
# Fetches quest texts (name, objectivesText, details, progress, completion, endText) from
# wowhead.com in all languages, one quest every 15 seconds, and stores them in
# etl/corrections/wowhead/<flavor>/<locale>.json for etl/build.py.
#
#   scripts/wowhead-texts.sh                    # every quest, only the languages that lack texts
#   scripts/wowhead-texts.sh 94485 92642        # just these quests, all languages
#   scripts/wowhead-texts.sh --test 33          # fetch English + German once, print, store nothing
#
# Options (environment):
#   DELAY=15        seconds per quest; its language pages are spread evenly over this window
#   FLAVOR=forever  data flavor the texts are stored for
#   ALL_LANGS=1     fetch all languages of a quest, not only those without texts
#   REFRESH=1       fetch again even if a quest/language was already fetched
#
# Stopping and restarting is safe: every page is stored right away and not fetched again.
# Afterwards rebuild the site data (make site-data) so the texts show up.
#
# Etiquette: the script identifies itself, follows robots.txt, never fetches a page twice and
# stops at the first sign of being blocked (HTTP 403/429/503, bot check, captcha) - it does not
# try to get around it. Wowhead's terms of use apply; running it is your decision.

set -euo pipefail
export LC_NUMERIC=C  # "0.5" for sleep, also under a German locale

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HELPER=(python3 "$ROOT/etl/wowhead_texts.py" --flavor "${FLAVOR:-forever}")
DELAY="${DELAY:-15}"
UA="WoW-Quest-Database-text-import/1.0 (private use; +https://github.com/Stein-N/WoW-Quest-Database)"
BASE="${WOWHEAD_BASE:-https://www.wowhead.com/forever}"
ROBOTS="${WOWHEAD_ROBOTS:-https://www.wowhead.com/robots.txt}"

# site locale  wowhead path segment ("" = English)
declare -A SEGMENT=(
  [enUS]="" [deDE]=de [esES]=es [esMX]=mx [frFR]=fr
  [ptBR]=pt [ruRU]=ru [koKR]=ko [zhCN]=cn [zhTW]=tw
)

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

url_for() {  # $1 = path segment, $2 = quest id
  if [ -z "$1" ]; then echo "$BASE/quest=$2"; else echo "$BASE/$1/quest=$2"; fi
}

fetch() {  # $1 = url, $2 = output file; prints the HTTP status
  curl -sS -L --compressed --max-time 30 -A "$UA" -o "$2" -w '%{http_code}' "$1" || echo 000
}

stop() {
  echo "STOP: $*" >&2
  echo "Wowhead is refusing requests. Wait (hours, not minutes) before trying again, ideally with a larger DELAY." >&2
  exit 2
}

check_robots() {
  curl -sS -A "$UA" -o "$TMP/robots.txt" "$ROBOTS" || stop "robots.txt not reachable"
  python3 - "$TMP/robots.txt" "$UA" "$(url_for de 1)" <<'EOF' || stop "robots.txt disallows quest pages for this script"
import sys, urllib.robotparser
rp = urllib.robotparser.RobotFileParser()
rp.parse(open(sys.argv[1]).read().splitlines())
sys.exit(0 if rp.can_fetch(sys.argv[2], sys.argv[3]) else 1)
EOF
}

# ------------------------------------------------------------------------------ test mode
if [ "${1:-}" = "--test" ]; then
  quest="${2:?usage: $0 --test QUEST_ID}"
  check_robots
  for locale in enUS deDE; do
    seg="${SEGMENT[$locale]}"
    status=$(fetch "$(url_for "$seg" "$quest")" "$TMP/page.html")
    echo "== $locale $(url_for "$seg" "$quest") -> HTTP $status"
    mkdir -p "$ROOT/build"
    cp "$TMP/page.html" "$ROOT/build/wowhead-test-$quest-$locale.html"
    [ "$status" = 200 ] || stop "HTTP $status"
    "${HELPER[@]}" block-check "$TMP/page.html" >/dev/null || stop "$("${HELPER[@]}" block-check "$TMP/page.html")"
    "${HELPER[@]}" parse "$locale" "$quest" "$TMP/page.html" --dry-run
    sleep 3
  done
  echo "Saved the raw pages to build/wowhead-test-$quest-*.html for checking the parser."
  exit 0
fi

# ------------------------------------------------------------------------------ main loop
plan_args=()
[ -n "${ALL_LANGS:-}" ] && plan_args+=(--all-langs)
[ -n "${REFRESH:-}" ] && plan_args+=(--refresh)
mapfile -t plan < <("${HELPER[@]}" plan "${plan_args[@]}" "$@")
total=${#plan[@]}
if [ "$total" -eq 0 ]; then
  echo "Nothing to fetch."
  exit 0
fi
pages=$(printf '%s\n' "${plan[@]}" | awk '{ n += split($2, a, ",") } END { print n }')
echo "$total quests, $pages pages, one quest every ${DELAY}s (about $(( total * DELAY / 3600 ))h $(( total * DELAY % 3600 / 60 ))min)."
echo "Ctrl+C stops; everything fetched so far is kept and skipped next time."
check_robots

n=0
for line in "${plan[@]}"; do
  n=$((n + 1))
  quest="${line%% *}"
  IFS=, read -r -a locales <<< "${line#* }"
  pause=$(awk -v d="$DELAY" -v n="${#locales[@]}" 'BEGIN { printf "%.2f", d / n }')
  start=$(date +%s)
  for locale in "${locales[@]}"; do
    url="$(url_for "${SEGMENT[$locale]}" "$quest")"
    status=$(fetch "$url" "$TMP/page.html")
    case "$status" in
      200)
        if ! reason=$("${HELPER[@]}" block-check "$TMP/page.html"); then
          stop "$reason ($url)"
        fi
        echo -n "[$n/$total] "
        "${HELPER[@]}" parse "$locale" "$quest" "$TMP/page.html" 2>/dev/null || true
        ;;
      404)
        # remembered as notFound, so the page is not requested again
        echo "[$n/$total] $locale $quest: not on Wowhead"
        echo "<html></html>" > "$TMP/page.html"
        "${HELPER[@]}" parse "$locale" "$quest" "$TMP/page.html" >/dev/null 2>&1 || true
        ;;
      403|429|503) stop "HTTP $status for $url" ;;
      *) echo "[$n/$total] $locale $quest: HTTP $status, skipped (retried next run)" ;;
    esac
    sleep "$pause"
  done
  # keep the rhythm of one quest per DELAY seconds
  rest=$(( DELAY - ($(date +%s) - start) ))
  if [ "$rest" -gt 0 ]; then sleep "$rest"; fi
done
echo "Done. Rebuild the site data with: make site-data"
