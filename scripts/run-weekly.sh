#!/usr/bin/env bash
# Cron entrypoint. Cron fires daily; this builds the current ISO week's digest only once,
# so a Monday missed because the machine was off is caught up on the next run.
# A failed run leaves no digest, so the next day's run retries automatically.
#   FORCE=1 scripts/run-weekly.sh   rebuild this week's digest anyway
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"

mkdir -p logs
exec 9>logs/.lock
flock -n 9 || { echo "$(date -Is) another run is in progress"; exit 0; }

WEEK="$(TZ=UTC date +%G-W%V)"   # must match iso_week() in pipeline.py (UTC)
if [[ -f "digests/$WEEK.md" && "${FORCE:-0}" != 1 ]]; then
  echo "$(date -Is) $WEEK already built"
  exit 0
fi

echo "=== $(date -Is) building $WEEK"
uv run --frozen weekly-digest

git add digests state
if ! git diff --cached --quiet; then
  git commit -q -m "digest: $WEEK"
fi
git push -q origin main || echo "WARN: push failed; digest is committed locally"
echo "=== $(date -Is) done $WEEK"
