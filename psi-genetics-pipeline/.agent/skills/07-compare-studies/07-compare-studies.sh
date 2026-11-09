#!/usr/bin/env bash
# Entry point for skill 07-compare-studies. Runs 07-compare-studies.py and passes its exit code through.
# Result: repo/results/07-compare-studies.json   Log: repo/logs/07-compare-studies.log
set -u
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
REPO="$ROOT/repo"
export PSI_ROOT="$ROOT" PSI_REPO="$REPO"
mkdir -p "$REPO" && cd "$REPO" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  mkdir -p results logs
  echo "python3 not found on PATH" > "logs/07-compare-studies.log"
  printf '{"skill":"%s","status":"FAIL","verdict":"python3 not found on PATH; install Python 3.8+","metrics":{},"warnings":[]}\n' "07-compare-studies" > "results/07-compare-studies.json"
  cat "results/07-compare-studies.json"
  exit 1
fi
python3 "$SKILL_DIR/07-compare-studies.py" "$@"
