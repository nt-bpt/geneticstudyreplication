#!/usr/bin/env bash
# SKILL 00 — verify tools and configuration before anything slow runs.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 00_check_env

miss=()
for c in samtools bcftools tabix bgzip curl python3; do
  if command -v "$c" >/dev/null 2>&1; then log "ok  $c: $($c --version 2>&1 | head -1)"; else miss+=("$c"); fi
done
if [ "$INPUT_TYPE" = fastq ]; then
  command -v bwa >/dev/null 2>&1 && log "ok  bwa" || { command -v bwa-mem2 >/dev/null 2>&1 && log "ok  bwa-mem2" || miss+=("bwa"); }
fi
[ ${#miss[@]} -eq 0 ] || fail "missing tools: ${miss[*]}  (conda install -c bioconda samtools bcftools bwa htslib)"

case "$INPUT_TYPE" in
  cram|bam) [ -n "$INPUT_FILE" ] || fail "INPUT_FILE is empty in config.env" ;;
  fastq)    [ -n "$FASTQ_R1" ] && [ -n "$FASTQ_R2" ] || fail "FASTQ_R1 / FASTQ_R2 are empty in config.env" ;;
  *)        fail "INPUT_TYPE must be cram, bam or fastq (got '$INPUT_TYPE')" ;;
esac
case "$ALIGN_SCOPE" in full|chr3_only) ;; *) fail "ALIGN_SCOPE must be full or chr3_only" ;; esac
[ -z "$OUTPUT_CHR_STYLE" ] || chr3_style_name "$OUTPUT_CHR_STYLE" >/dev/null || fail "OUTPUT_CHR_STYLE '$OUTPUT_CHR_STYLE' is not ucsc|ensembl|genbank|refseq"

free_gb=$(df -Pk "$WORK" | awk 'NR==2{printf "%d", $4/1048576}')
log "free disk in workspace: ${free_gb} GB"
if [ "$INPUT_TYPE" = fastq ] && [ "$ALIGN_SCOPE" = full ] && [ "${free_gb:-0}" -lt 120 ]; then
  warn "full-genome alignment of a whole-genome FASTQ needs roughly 100+ GB free; you have ${free_gb} GB"
fi
done_ok "environment ready" input_type="$INPUT_TYPE" threads="$THREADS" free_gb="${free_gb:-0}"
