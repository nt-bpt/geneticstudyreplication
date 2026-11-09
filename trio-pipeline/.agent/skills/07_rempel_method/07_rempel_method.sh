#!/usr/bin/env bash
# SKILL 07 — run the preprint's method AS PUBLISHED (read from github.com/maxrempel/xg1-2024) on the same VCF.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 07_rempel_method
need_cmds python3
need_state TRIOS_TSV
vp="VCF_PATH_$CHROM"; vc="VCF_CONTIG_$CHROM"; [ -n "${!vp:-}" ] || fail "no VCF recorded for chr$CHROM — run skill 01"
OUT="$WORK/npa/chr$CHROM"; mkdir -p "$OUT"
run_py_helper "$PIPE_ROOT/py/rempel_replicate.py" --vcf "${!vp}" --contig "${!vc}" --start "$SCAN_START" --end "$SCAN_END" \
  --trios "$TRIOS_TSV" --outdir "$OUT" --focus-start "$FOCUS_START" --focus-end "$FOCUS_END"
[ $PY_RC -eq 0 ] || fail "rempel_replicate.py failed: $(tail -3 "$WORK/tmp/07_rempel_method.py.err")"
cp "$WORK/tmp/07_rempel_method.py.out" "$WORK/results/07_rempel_method.txt"
done_ok "$PY_VERDICT" "${PY_METRICS[@]}"
