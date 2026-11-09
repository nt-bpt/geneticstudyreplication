#!/usr/bin/env bash
# SKILL 08 — allele balance at heterozygous calls (exact binomial test), hotspot vs control.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 08_allele_balance
need_cmds bcftools python3
need_state CALLS_VCF CHR3_NAME
export AB_MIN_DEPTH AB_P_THRESHOLD RATIO_FLAG
run_py_helper "$PIPE_ROOT/py/allele_balance.py" "$CALLS_VCF" \
  "$(region_str "$CHR3_NAME" "$PRIMARY_START" "$PRIMARY_END")" \
  "$(region_str "$CHR3_NAME" "$EXT_START" "$EXT_END")" \
  "$(region_str "$CHR3_NAME" "$CONTROL_START" "$CONTROL_END")"
[ $PY_RC -eq 0 ] || fail "allele_balance.py failed"
done_ok "$PY_VERDICT" "${PY_METRICS[@]}"
