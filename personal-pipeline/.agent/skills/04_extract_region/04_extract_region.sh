#!/usr/bin/env bash
# SKILL 04 — pull the control + extended-hotspot windows out of the CRAM/BAM into one small BAM, using the name
#            the data really uses for chr3 (chr3, 3, CM000665.2 ...), and verify it is not empty.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 04_extract_region
need_cmds samtools
need_state INPUT_KIND CHR3_NAME
SRC="${ALIGNED_BAM:-$INPUT_PATH}"; [ -f "$SRC" ] || fail "source file missing: '$SRC'"
refarg=(); [ "$INPUT_KIND" = cram ] && [ -n "$INPUT_REFERENCE" ] && refarg=(--reference "$INPUT_REFERENCE")

BED="$WORK/tmp/regions.bed"
printf '%s\t%s\t%s\n%s\t%s\t%s\n' "$CHR3_NAME" $((CONTROL_START-1)) "$CONTROL_END" "$CHR3_NAME" $((EXT_START-1)) "$EXT_END" | sort -k2,2n > "$BED"
OUT="$WORK/bam/region.bam"
log "extracting from $SRC using contig '$CHR3_NAME': control ${CONTROL_START}-${CONTROL_END}, extended ${EXT_START}-${EXT_END}"
samtools view -b -M -L "$BED" "${refarg[@]}" -@ "$THREADS" -o "$OUT" "$SRC" 2>"$WORK/tmp/extract.err"
rc=$?; [ $rc -eq 0 ] || fail "samtools view failed: $(head -3 "$WORK/tmp/extract.err")"
samtools index "$OUT" || fail "could not index $OUT"

cnt() { samtools view -c "$OUT" "$1" 2>/dev/null; }
RP="$(region_str "$CHR3_NAME" "$PRIMARY_START" "$PRIMARY_END")"
RE="$(region_str "$CHR3_NAME" "$EXT_START" "$EXT_END")"
RC="$(region_str "$CHR3_NAME" "$CONTROL_START" "$CONTROL_END")"
nP=$(cnt "$RP"); nE=$(cnt "$RE"); nC=$(cnt "$RC")
log "alignments: primary=$nP extended=$nE control=$nC"
if [ "${nE:-0}" -eq 0 ] || [ "${nC:-0}" -eq 0 ]; then
  log "contigs with reads in the source:"; samtools idxstats "$SRC" 2>/dev/null | awk '$3>0{print "    "$1"\t"$3}' | head -10 | tee -a "$LOGFILE"
  fail "extracted BAM has no reads in the extended or control window (name used: '$CHR3_NAME'). See the contig list above."
fi
depth() { samtools coverage -r "$1" "$OUT" 2>/dev/null | awk 'NR>1{print $7}' | head -1; }
dP=$(depth "$RP"); dE=$(depth "$RE"); dC=$(depth "$RC")
log "mean depth: primary=${dP}x extended=${dE}x control=${dC}x"
python3 - "$dC" "$dP" <<'PY' 2>/dev/null
import sys
c = float(sys.argv[1] or 0)
if c > 120: print("NOTE: control-region depth is very high; a normal whole-genome sample is ~30x.")
PY
state_set REGION_BAM "$OUT"
[ "$(python3 -c "print(1 if float('${dC:-0}')>120 else 0)")" = 1 ] && warn "control-region depth ${dC}x is far above typical whole-genome coverage (~30x). If this was aligned to a single-chromosome reference, reads from other regions are probably piled onto chr3."
[ "${dP:-0}" = 0 ] && warn "primary hotspot has zero depth"
done_ok "region BAM ready with $nE reads" reads_primary="$nP" reads_extended="$nE" reads_control="$nC" depth_primary="${dP:-0}" depth_extended="${dE:-0}" depth_control="${dC:-0}"
