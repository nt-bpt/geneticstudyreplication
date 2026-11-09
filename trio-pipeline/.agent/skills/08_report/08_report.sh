#!/usr/bin/env bash
# SKILL 08 — assemble results/FINAL_REPORT.txt
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 08_report
python3 "$PIPE_ROOT/py/report.py" "$WORK" "$CHROM" "$FOCUS_START" "$FOCUS_END" > "$WORK/tmp/07.out" 2>"$WORK/tmp/07.err" || fail "report.py failed: $(tail -3 "$WORK/tmp/07.err")"
grep -v '^METRIC \|^VERDICT ' "$WORK/tmp/07.out"
done_ok "report at $WORK/results/FINAL_REPORT.txt"
