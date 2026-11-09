#!/usr/bin/env bash
# SKILL 07 — read-level signals (soft-clips, split reads, discordant pairs, MAPQ, depth) vs a control region.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 07_read_signals
need_cmds samtools python3
need_state REGION_BAM CHR3_NAME
export MIN_MAPQ RATIO_FLAG SOFTCLIP_FLOOR_PCT SPLIT_FLOOR_PCT DISCORDANT_FLOOR_PCT MIN_FLAG_READS
run_py_helper "$PIPE_ROOT/py/read_signals.py" "$REGION_BAM" \
  "$(region_str "$CHR3_NAME" "$PRIMARY_START" "$PRIMARY_END")" \
  "$(region_str "$CHR3_NAME" "$EXT_START" "$EXT_END")" \
  "$(region_str "$CHR3_NAME" "$CONTROL_START" "$CONTROL_END")"
[ $PY_RC -eq 0 ] || fail "read_signals.py failed"
done_ok "$PY_VERDICT" "${PY_METRICS[@]}"
