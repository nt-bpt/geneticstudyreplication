#!/usr/bin/env bash
# Entry point for skill 01-detect-input. Runs 01-detect-input.py and passes its exit code through.
# Result: repo/results/01-detect-input.json   Log: repo/logs/01-detect-input.log
set -u
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
REPO="$ROOT/repo"
export PSI_ROOT="$ROOT" PSI_REPO="$REPO"
mkdir -p "$REPO" && cd "$REPO" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  mkdir -p results logs
  echo "python3 not found on PATH" > "logs/01-detect-input.log"
  printf '{"skill":"%s","status":"FAIL","verdict":"python3 not found on PATH; install Python 3.8+","metrics":{},"warnings":[]}\n' "01-detect-input" > "results/01-detect-input.json"
  cat "results/01-detect-input.json"
  exit 1
fi
python3 "$SKILL_DIR/01-detect-input.py" "$@"
