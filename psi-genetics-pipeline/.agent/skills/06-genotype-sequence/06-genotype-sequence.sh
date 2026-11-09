#!/usr/bin/env bash
# Entry point for skill 06-genotype-sequence. Runs 06-genotype-sequence.py and passes its exit code through.
# Result: repo/results/06-genotype-sequence.json   Log: repo/logs/06-genotype-sequence.log
set -u
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
REPO="$ROOT/repo"
export PSI_ROOT="$ROOT" PSI_REPO="$REPO"
mkdir -p "$REPO" && cd "$REPO" || exit 1
if ! command -v python3 >/dev/null 2>&1; then
  mkdir -p results logs
  echo "python3 not found on PATH" > "logs/06-genotype-sequence.log"
  printf '{"skill":"%s","status":"FAIL","verdict":"python3 not found on PATH; install Python 3.8+","metrics":{},"warnings":[]}\n' "06-genotype-sequence" > "results/06-genotype-sequence.json"
  cat "results/06-genotype-sequence.json"
  exit 1
fi
python3 "$SKILL_DIR/06-genotype-sequence.py" "$@"
