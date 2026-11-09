#!/usr/bin/env bash
# SKILL 03 — FASTQ -> sorted, duplicate-marked BAM. SKIPPED for CRAM/BAM input.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 03_align_fastq
need_state INPUT_KIND
if [ "$INPUT_KIND" != fastq ]; then write_result SKIPPED "input is $INPUT_KIND; nothing to align"; log "SKIPPED (input is $INPUT_KIND)"; exit 0; fi
need_cmds samtools bwa
need_state ALIGN_REF

OUT="$WORK/bam/${SAMPLE}.aligned.bam"
if [ -s "$OUT" ] && [ -s "$OUT.bai" ] && [ -z "${FORCE:-}" ]; then
  log "aligned BAM already exists — reusing (set FORCE=1 to redo): $OUT"
else
  log "aligning to $ALIGN_REF with $THREADS threads. This is the long step; progress goes to $WORK/logs/03_bwa.log"
  [ "$ALIGN_SCOPE" = full ] && log "whole-genome FASTQ on a full reference commonly takes many hours; chr3_only is faster but biased"
  set -o pipefail
  bwa mem -t "$THREADS" -R "@RG\tID:${SAMPLE}\tSM:${SAMPLE}\tPL:ILLUMINA\tLB:${SAMPLE}" "$ALIGN_REF" "$FASTQ_R1" "$FASTQ_R2" 2>"$WORK/logs/03_bwa.log" \
    | samtools fixmate -m -u - - 2>>"$LOGFILE" \
    | samtools sort -u -@ 2 -T "$WORK/tmp/sort" - 2>>"$LOGFILE" \
    | samtools markdup -@ 2 -T "$WORK/tmp/mkdup" - "$OUT.part.bam" 2>>"$LOGFILE"
  rc=$?; set +o pipefail
  [ $rc -eq 0 ] && [ -s "$OUT.part.bam" ] || fail "alignment pipeline failed (see $WORK/logs/03_bwa.log and $LOGFILE)"
  mv "$OUT.part.bam" "$OUT"; samtools index -@ "$THREADS" "$OUT" || fail "index failed"
fi
samtools flagstat "$OUT" > "$WORK/results/03_flagstat.txt" 2>/dev/null
mapped=$(awk '/ mapped \(/{print $1; exit}' "$WORK/results/03_flagstat.txt")
total=$(awk 'NR==1{print $1}' "$WORK/results/03_flagstat.txt")
[ "${mapped:-0}" -gt 0 ] || fail "zero mapped reads — wrong reference or wrong FASTQ?"
pct=$(python3 -c "print(round(100*$mapped/max($total,1),2))")
log "mapped $mapped of $total reads (${pct}%)"
name="$(detect_chr3 "$OUT")" || fail "aligned BAM has no chr3 contig"
state_set ALIGNED_BAM "$OUT"; state_set CHR3_NAME "$name"; state_set CHR3_STYLE "$(chr3_style_of "$name")"
[ "$ALIGN_SCOPE" = chr3_only ] && { state_set ALIGN_BIAS "chr3_only"; warn "alignment was chr3-only: interpret depth and variant results with caution"; }
done_ok "aligned: ${pct}% mapped; chr3 is '$name'" mapped_reads="$mapped" total_reads="$total" mapped_pct="$pct" align_scope="$ALIGN_SCOPE"
