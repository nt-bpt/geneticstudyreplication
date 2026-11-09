#!/usr/bin/env bash
# SKILL 05 — compare families named in resources/rempel_families.txt with all other trios.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 05_compare_rempel
need_state NPA_DIR
F="$PIPE_ROOT/resources/rempel_families.txt"
if ! grep -v '^\s*#' "$F" 2>/dev/null | grep -q '[A-Za-z0-9]'; then
  log "resources/rempel_families.txt has no IDs. Fill it with the sample IDs of the families named in the preprint (one per line) to enable this comparison."
  write_result SKIPPED "no family list supplied (IDs from the preprint were not verified, so none are bundled)"; exit 0
fi
run_py_helper "$PIPE_ROOT/py/compare_rempel.py" "$NPA_DIR" "$F" "$FOCUS_START" "$FOCUS_END"
[ $PY_RC -eq 0 ] || { warn "comparison not done: $(tail -1 "$WORK/tmp/05_compare_rempel.py.err")"; write_result SKIPPED "listed IDs not usable: $(tail -1 "$WORK/tmp/05_compare_rempel.py.err")"; exit 0; }
done_ok "$PY_VERDICT" "${PY_METRICS[@]}"
