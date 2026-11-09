#!/usr/bin/env bash
# SKILL 02 — decide which FASTA is used (a) to ALIGN FASTQ and (b) to CALL variants; download/index as needed.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 02_prepare_reference
source "$PIPE_ROOT/resources/urls.env"
need_cmds samtools curl
need_state INPUT_KIND

ucsc_chr3() {   # download UCSC chr3 once
  local f="$WORK/data/chr3.fa"
  [ -s "$f" ] && { echo "$f"; return 0; }
  fetch_file "$UCSC_CHR3_URL" "$f.gz" && gunzip -f "$f.gz" && echo "$f"
}

ALIGN_REF=""
if [ "$INPUT_KIND" = fastq ]; then
  need_cmds bwa
  if [ -n "$REFERENCE" ] && [ -f "$REFERENCE" ]; then
    ALIGN_REF="$REFERENCE"; log "using your reference: $ALIGN_REF"
  elif [ "$ALIGN_SCOPE" = full ]; then
    ALIGN_REF="$WORK/data/GRCh38_full_analysis_set_plus_decoy_hla.fa"
    if [ ! -s "$ALIGN_REF" ]; then
      ok=1; for u in $GRCH38_FULL_URLS; do log "downloading $u (about 3 GB, resumable)"; fetch_file "$u" "$ALIGN_REF" && { ok=0; break; }; log "that source failed"; done
      [ $ok -eq 0 ] || fail "could not download the GRCh38 reference. Download it yourself and set REFERENCE=<path> in config.env"
      for u in $GRCH38_FULL_URLS; do fetch_file "$u.alt" "$ALIGN_REF.alt" && { log "got .alt file (bwa alt-aware mapping)"; break; }; done
      [ -s "$ALIGN_REF.alt" ] || warn "no .alt file found; bwa will treat alt contigs as ordinary sequence (lower MAPQ near alt loci)"
    fi
  else
    ALIGN_REF="$(ucsc_chr3)" || fail "could not download UCSC chr3.fa.gz"
  fi
  samtools faidx "$ALIGN_REF" 2>>"$LOGFILE" || fail "cannot index $ALIGN_REF"
  refname="$(detect_chr3 "$ALIGN_REF")" || fail "$ALIGN_REF has no contig recognisable as chromosome 3"
  asm="$(assembly_of_length "$(contig_length "$ALIGN_REF" "$refname")")"
  [ "$asm" = GRCh37 ] && fail "reference chr3 is GRCh37; the hotspot coordinates are GRCh38"
  [ "$asm" = GRCh38 ] || warn "reference chr3 length matches neither GRCh38 nor GRCh37 (assembly: $asm); coordinates may not line up"
  nctg=$(wc -l < "$ALIGN_REF.fai")
  if [ "$ALIGN_SCOPE" = chr3_only ] && [ "$nctg" -gt 1 ]; then
    log "ALIGN_SCOPE=chr3_only: extracting chr3 from the multi-contig reference"
    make_chr3_fasta "$ALIGN_REF" "$refname" "$WORK/ref/chr3_only_align.fa" "$refname" || fail "could not extract chr3"
    ALIGN_REF="$WORK/ref/chr3_only_align.fa"
  fi
  [ "$ALIGN_SCOPE" = chr3_only ] && warn "chr3_only alignment: reads from paralogous regions elsewhere in the genome can be forced onto chr3 (this region is near segmental duplications). Treat read-depth and variant results with caution."
  if [ ! -s "$ALIGN_REF.bwt" ] && [ ! -s "$ALIGN_REF.0123" ]; then
    log "building bwa index (whole genome ~1 hour, ~6 GB RAM; chr3 only ~3 minutes)"
    bwa index "$ALIGN_REF" 2>>"$LOGFILE" || fail "bwa index failed (see $LOGFILE)"
  fi
  state_set ALIGN_REF "$ALIGN_REF"; state_set ALIGN_REF_CHR3 "$refname"
fi

# ---- reference used for VARIANT CALLING (chr3 sequence only is needed) ----
CALL_SRC=""
for cand in "$INPUT_REFERENCE" "$REFERENCE" "$ALIGN_REF"; do [ -n "$cand" ] && [ -f "$cand" ] && { CALL_SRC="$cand"; break; }; done
[ -n "$CALL_SRC" ] || { log "no local reference available for calling — fetching UCSC chr3"; CALL_SRC="$(ucsc_chr3)" || fail "could not download UCSC chr3.fa.gz; set REFERENCE=<GRCh38 FASTA> in config.env"; }
samtools faidx "$CALL_SRC" 2>>"$LOGFILE" || fail "cannot index $CALL_SRC"
callname="$(detect_chr3 "$CALL_SRC")" || fail "$CALL_SRC has no contig recognisable as chromosome 3"
state_set CALL_REF_SOURCE "$CALL_SRC"; state_set CALL_REF_CHR3 "$callname"
log "variant-calling reference: $CALL_SRC (chr3 is '$callname')"
done_ok "references ready (calling ref chr3='$callname'${ALIGN_REF:+; align ref $ALIGN_REF})" call_ref_chr3="$callname" align_scope="$ALIGN_SCOPE"
