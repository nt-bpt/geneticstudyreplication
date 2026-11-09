#!/usr/bin/env bash
# SKILL 10 — assemble all skill results into results/FINAL_REPORT.txt
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 10_report
python3 "$PIPE_ROOT/py/report.py" "$WORK" || fail "report.py failed"
done_ok "report written to $WORK/results/FINAL_REPORT.txt"
