#!/usr/bin/env bash
# SKILL 01 — get + verify the phased VCF for CHROM, the pedigree and the population table.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; source "$PIPE_ROOT/lib/trio.sh"; source "$PIPE_ROOT/resources/urls.env"
skill_begin 01_download
need_cmds tabix bcftools curl
PED="$WORK/data/pedigree.txt"; POP="$WORK/data/population.txt"
[ -s "$PED" ] || { [ -n "$MANUAL_DIR" ] && [ -s "$MANUAL_DIR/1kGP.3202_samples.pedigree_info.txt" ] && cp "$MANUAL_DIR/1kGP.3202_samples.pedigree_info.txt" "$PED"; }
[ -s "$PED" ] || fetch_file "$PED_URL" "$PED" || fail "pedigree download failed: $PED_URL (download it manually, save as $PED)"
[ -s "$POP" ] || fetch_file "$POPTABLE_URL" "$POP" || warn "population table download failed (optional)"
head -c 400 "$PED" | grep -qi '<html' && { rm -f "$PED"; fail "pedigree file is an HTML page, not data — the URL is wrong or blocked"; }
log "pedigree: $(wc -l < "$PED") lines"
get_vcf "$CHROM" || fail "VCF for chr$CHROM not available — see log"
ns=$(bcftools query -l "$GV_PATH" 2>/dev/null | wc -l)
[ "$ns" -gt 0 ] || fail "bcftools cannot read the sample list of $GV_PATH"
nrec=$(tabix "$GV_PATH" "$GV_CONTIG:$SCAN_START-$((SCAN_START+200000))" 2>/dev/null | wc -l)
log "VCF ok: contig '$GV_CONTIG', $ns samples, $nrec records in the first 200 kb of the scan range"
state_set "VCF_PATH_$CHROM" "$GV_PATH"; state_set "VCF_CONTIG_$CHROM" "$GV_CONTIG"
state_set PED_PATH "$PED"
bcftools query -l "$GV_PATH" > "$WORK/data/vcf_samples.txt"
[ "$nrec" -gt 0 ] || warn "no records near SCAN_START — check SCAN_START/SCAN_END"
done_ok "chr$CHROM VCF verified" samples="$ns" contig="$GV_CONTIG"
