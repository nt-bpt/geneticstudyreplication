#!/usr/bin/env bash
# SKILL 03 — scan CHROM for windows rich in nonparental alleles (NPAs) in every trio.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 03_npa_scan
need_cmds python3
need_state TRIOS_TSV
vp="VCF_PATH_$CHROM"; vc="VCF_CONTIG_$CHROM"; [ -n "${!vp:-}" ] || fail "no VCF recorded for chr$CHROM — run skill 01"
OUT="$WORK/npa/chr$CHROM"; mkdir -p "$OUT"
opts=(); [ "$INCLUDE_INDELS" = yes ] && opts+=(--include-indels)
log "scanning chr$CHROM:$SCAN_START-$SCAN_END (this reads every record in range; chr3 to 77 Mb is on the order of tens of minutes to hours)"
run_py_helper "$PIPE_ROOT/py/npa_scan.py" --vcf "${!vp}" --contig "${!vc}" --start "$SCAN_START" --end "$SCAN_END" \
  --trios "$TRIOS_TSV" --outdir "$OUT" --window "$WINDOW_SNPS" --min-window-npa "$MIN_WINDOW_NPA" \
  --high-bg-factor "$HIGH_BG_FACTOR" "${opts[@]}"
[ $PY_RC -eq 0 ] || fail "npa_scan.py failed: $(tail -3 "$WORK/tmp/03_npa_scan.py.err")"
[ -s "$OUT/npa_per_trio.tsv" ] || fail "no output produced"
state_set NPA_DIR "$OUT"
rec=$(printf '%s\n' "${PY_METRICS[@]}" | sed -n 's/^records_read=//p')
[ "${rec:-0}" -gt 0 ] || warn "0 records read — region empty or contig wrong"
done_ok "$PY_VERDICT" "${PY_METRICS[@]}"
