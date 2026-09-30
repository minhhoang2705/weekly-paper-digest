#!/usr/bin/env bash
# Cron entrypoint. Cron fires daily; this builds the current ISO week's digest only once,
# so a Monday missed because the machine was off is caught up on the next run.
# A failed run leaves no digest, so the next day's run retries automatically.
#   FORCE=1 scripts/run-weekly.sh   rebuild this week's digest anyway
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
export PATH="$HOME/.local/bin:/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin"

mkdir -p logs
exec 9>logs/.lock
flock -n 9 || { echo "$(date -Is) another run is in progress"; exit 0; }

push_pending() {
  if [[ "$(git rev-list --count origin/main..main 2>/dev/null || echo 0)" -gt 0 ]]; then
    git push -q origin main || echo "WARN: push failed; digest is committed locally"
  fi
}

WEEK="$(TZ=UTC date +%G-W%V)"   # must match iso_week() in pipeline.py (UTC)
if [[ -f "digests/$WEEK.md" && "${FORCE:-0}" != 1 ]]; then
  echo "$(date -Is) $WEEK already built"
  push_pending   # retry a push that failed on the day the digest was built
  exit 0
fi

# gh is authenticated on this machine: its token lifts GitHub Search to 30 req/min.
export GITHUB_TOKEN="${GITHUB_TOKEN:-$(gh auth token 2>/dev/null || true)}"

echo "=== $(date -Is) building $WEEK"
uv run --frozen weekly-digest
uv run --frozen weekly-site      # static UI in docs/, served by GitHub Pages

git add digests state data docs
if ! git diff --cached --quiet; then
  git commit -q -m "digest: $WEEK"
fi
push_pending
echo "=== $(date -Is) done $WEEK"
