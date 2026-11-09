#!/usr/bin/env bash
# SKILL 06 — call variants in the control + extended windows with bcftools.
# The calling FASTA is rebuilt so its chr3 header matches the BAM exactly — the cause of the earlier
# "sequence CM000665.2 was not found" failure.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 06_call_variants
need_cmds samtools bcftools tabix bgzip
need_state REGION_BAM CHR3_NAME CALL_REF_SOURCE CALL_REF_CHR3

CALLREF="$WORK/ref/chr3_calling.fa"
make_chr3_fasta "$CALL_REF_SOURCE" "$CALL_REF_CHR3" "$CALLREF" "$CHR3_NAME" || fail "could not build calling reference from $CALL_REF_SOURCE"
bl="$(contig_length "$REGION_BAM" "$CHR3_NAME")"; rl="$(contig_length "$CALLREF" "$CHR3_NAME")"
log "contig '$CHR3_NAME': BAM length ${bl:-?}, reference length ${rl:-?}"
[ -n "$bl" ] && [ -n "$rl" ] && [ "$bl" != "$rl" ] && fail "BAM and reference disagree on chr3 length ($bl vs $rl): different assembly"

RP="$(region_str "$CHR3_NAME" "$PRIMARY_START" "$PRIMARY_END")"
RE="$(region_str "$CHR3_NAME" "$EXT_START" "$EXT_END")"
RC="$(region_str "$CHR3_NAME" "$CONTROL_START" "$CONTROL_END")"
VCF="$WORK/vcf/calls.vcf.gz"
log "calling in $RC and $RE (max depth raised to 10000 — bcftools' default of 250 would silently cap deep regions)"
set -o pipefail
bcftools mpileup -f "$CALLREF" -r "$RC,$RE" -d 10000 -q "$MIN_MAPQ" -Q 20 -a FORMAT/AD,FORMAT/DP -Ou "$REGION_BAM" 2>"$WORK/tmp/mpileup.err" \
  | bcftools call -mv -Ou 2>"$WORK/tmp/call.err" \
  | bcftools norm -f "$CALLREF" -m -any -Ou 2>"$WORK/tmp/norm.err" \
  | bcftools filter -s LowQual -e "QUAL<$MIN_QUAL || FMT/DP<$MIN_DP" -Oz -o "$VCF" 2>"$WORK/tmp/filter.err"
rc=$?; set +o pipefail
[ $rc -eq 0 ] && [ -s "$VCF" ] || fail "calling failed: $(cat "$WORK"/tmp/mpileup.err "$WORK"/tmp/call.err "$WORK"/tmp/norm.err "$WORK"/tmp/filter.err 2>/dev/null | grep -v '^Note' | head -3)"
bcftools index -t -f "$VCF" || fail "could not index $VCF"

count()  { bcftools view -H -r "$1" "$VCF" 2>/dev/null | wc -l; }
countp() { bcftools view -H -f PASS,. -r "$1" "$VCF" 2>/dev/null | wc -l; }
nP=$(count "$RP"); nE=$(count "$RE"); nC=$(count "$RC"); pP=$(countp "$RP"); pE=$(countp "$RE"); pC=$(countp "$RC")
log "variants (all/PASS): primary $nP/$pP, extended $nE/$pE, control $nC/$pC"
bcftools query -r "$RP" -f '%CHROM\t%POS\t%REF\t%ALT\t%QUAL\t%FILTER\t[%GT]\t[%DP]\t[%AD]\n' "$VCF" > "$WORK/results/06_primary_variants.tsv"
log "primary-hotspot variants written to results/06_primary_variants.tsv"
state_set CALLS_VCF "$VCF"

if [ -n "$OUTPUT_CHR_STYLE" ] && [ "$(chr3_style_name "$OUTPUT_CHR_STYLE")" != "$CHR3_NAME" ]; then
  conv="$WORK/vcf/calls.${OUTPUT_CHR_STYLE}.vcf.gz"
  bash "$PROC_ROOT/.agent/skills/05_chr_convert/05_chr_convert.sh" vcf "$VCF" "$conv" --to "$OUTPUT_CHR_STYLE" >>"$LOGFILE" 2>&1 \
    && { log "also wrote $conv with chr3 named '$(chr3_style_name "$OUTPUT_CHR_STYLE")'"; state_set CALLS_VCF_CONVERTED "$conv"; } \
    || warn "OUTPUT_CHR_STYLE conversion failed (see log)"
fi
[ "$nE" -gt 0 ] || warn "no variants at all in the extended window — unusual for a whole-genome sample; check depth and reference"
done_ok "called $nE variants in the extended window ($nP in the primary hotspot)" variants_primary="$nP" variants_extended="$nE" variants_control="$nC" pass_primary="$pP" pass_extended="$pE" pass_control="$pC"
