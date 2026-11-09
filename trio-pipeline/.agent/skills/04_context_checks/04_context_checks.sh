#!/usr/bin/env bash
# SKILL 04 — tag the best hot regions with the mundane explanations that can be tested from public files.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; source "$PIPE_ROOT/resources/urls.env"; skill_begin 04_context_checks
need_cmds python3
need_state NPA_DIR TRIOS_TSV
vp="VCF_PATH_$CHROM"; vc="VCF_CONTIG_$CHROM"
SEG="-"
if [ "$USE_SEGDUP" = yes ]; then
  SEG="$WORK/data/genomicSuperDups.txt.gz"
  [ -s "$SEG" ] || fetch_file "$SEGDUP_URL" "$SEG" || { warn "segmental-duplication track not downloaded — segdup check skipped"; SEG="-"; }
  [ "$SEG" = "-" ] || gzip -t "$SEG" 2>/dev/null || { warn "segdup file is not valid gzip — skipped"; rm -f "$SEG"; SEG="-"; }
fi
[ -s "$NPA_DIR/npa_regions.tsv" ] && [ "$(wc -l < "$NPA_DIR/npa_regions.tsv")" -gt 1 ] || { write_result SKIPPED "no hot regions to examine"; log "no hot regions — nothing to check"; exit 0; }
run_py_helper "$PIPE_ROOT/py/context_checks.py" "$NPA_DIR" "${!vp}" "${!vc}" "$TRIOS_TSV" "$SEG" "chr$CHROM" "$TOP_N" "$PAD_BP" "$FOCUS_START" "$FOCUS_END" "$COMMON_AF"
[ $PY_RC -eq 0 ] || fail "context_checks.py failed: $(tail -3 "$WORK/tmp/04_context_checks.py.err")"
[ "$SEG" != "-" ] || warn "no segdup annotation was used"
done_ok "$PY_VERDICT" "${PY_METRICS[@]}"
