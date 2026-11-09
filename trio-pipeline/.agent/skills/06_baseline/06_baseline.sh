#!/usr/bin/env bash
# SKILL 06 — run the same scan on other chromosomes to see what a "normal" chromosome looks like.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; source "$PIPE_ROOT/lib/trio.sh"; source "$PIPE_ROOT/resources/urls.env"; skill_begin 06_baseline
if [ -z "$BASELINE_CHROMS" ]; then
  log "BASELINE_CHROMS is empty. Without a baseline you cannot say whether chr$CHROM is unusual. Example: BASELINE_CHROMS=\"2 4\""
  write_result SKIPPED "no baseline chromosomes requested"; exit 0
fi
need_state TRIOS_TSV
T="$WORK/results/06_baseline.tsv"; printf 'chrom\ttrios_with_region\tregions\tinformative_records\thigh_background_trios\n' > "$T"
ok=0; bad=0
add_row() { # CHROM OUTDIR
  local m; m="$WORK/tmp/06_chr$1.out"
  printf '%s\t%s\t%s\t%s\t%s\n' "$1" "$(sed -n 's/^METRIC trios_with_region=//p' "$m")" "$(sed -n 's/^METRIC regions=//p' "$m")" \
    "$(sed -n 's/^METRIC informative_records=//p' "$m")" "$(sed -n 's/^METRIC high_background_trios=//p' "$m")" >> "$T"; }
cp "$WORK/tmp/03_npa_scan.py.out" "$WORK/tmp/06_chr$CHROM.out" 2>/dev/null && add_row "$CHROM" && ok=1 || warn "chr$CHROM results from skill 03 not found"
for c in $BASELINE_CHROMS; do
  if ! get_vcf "$c"; then warn "chr$c: VCF unavailable — skipped"; bad=$((bad+1)); continue; fi
  out="$WORK/npa/chr$c"; mkdir -p "$out"; opts=(); [ "$INCLUDE_INDELS" = yes ] && opts+=(--include-indels)
  log "scanning chr$c:$SCAN_START-$SCAN_END"
  python3 "$PIPE_ROOT/py/npa_scan.py" --vcf "$GV_PATH" --contig "$GV_CONTIG" --start "$SCAN_START" --end "$SCAN_END" --trios "$TRIOS_TSV" \
     --outdir "$out" --window "$WINDOW_SNPS" --min-window-npa "$MIN_WINDOW_NPA" --high-bg-factor "$HIGH_BG_FACTOR" "${opts[@]}" \
     > "$WORK/tmp/06_chr$c.out" 2>"$WORK/tmp/06_chr$c.err"
  if [ $? -eq 0 ]; then add_row "$c"; ok=$((ok+1)); grep '^trios with' "$WORK/tmp/06_chr$c.out" | tee -a "$LOGFILE"
  else warn "chr$c scan failed: $(tail -2 "$WORK/tmp/06_chr$c.err")"; bad=$((bad+1)); fi
done
[ $ok -gt 1 ] || fail "need at least two chromosomes scanned for a baseline comparison (got $ok)"
log "baseline table: $T"; cat "$T" | tee -a "$LOGFILE"
done_ok "scanned $ok chromosomes ($bad failed)" scanned="$ok" failed="$bad"
