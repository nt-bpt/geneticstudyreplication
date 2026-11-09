#!/usr/bin/env bash
# SKILL 02 — build trios.tsv (child, father, mother) from the pedigree, keeping only trios present in the VCF.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 02_build_trios
need_state PED_PATH
[ -s "$WORK/data/vcf_samples.txt" ] || fail "vcf_samples.txt missing — run skill 01"
run_py_helper "$PIPE_ROOT/py/prepare_trios.py" "$PED_PATH" "$WORK/data/vcf_samples.txt" "$WORK/data/trios.tsv"
[ $PY_RC -eq 0 ] || fail "trio building failed: $(tail -2 "$WORK/tmp/02_build_trios.py.err")"
state_set TRIOS_TSV "$WORK/data/trios.tsv"
done_ok "$PY_VERDICT" "${PY_METRICS[@]}"
