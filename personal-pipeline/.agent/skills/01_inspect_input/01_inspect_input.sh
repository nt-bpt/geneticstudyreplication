#!/usr/bin/env bash
# SKILL 01 — inspect the input (CRAM, BAM or FASTQ): is it readable, which assembly, what does it call chr3?
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 01_inspect_input
need_cmds samtools

case "$INPUT_TYPE" in
cram|bam)
  [ -f "$INPUT_FILE" ] || fail "INPUT_FILE not found: '$INPUT_FILE'"
  if [ ! -f "$INPUT_FILE.crai" ] && [ ! -f "${INPUT_FILE%.cram}.crai" ] && [ ! -f "$INPUT_FILE.bai" ] && [ ! -f "${INPUT_FILE%.bam}.bai" ]; then
    log "no index found — building one"; samtools index -@ "$THREADS" "$INPUT_FILE" 2>>"$LOGFILE" || fail "could not index $INPUT_FILE"
  fi
  log "contigs in header (first 25):"; contig_table "$INPUT_FILE" | head -25 | sed 's/^/    /' | tee -a "$LOGFILE"
  name="$(detect_chr3 "$INPUT_FILE")" || fail "no contig looks like chromosome 3 (names tried: chr3, 3, CM000665.2, NC_000003.12, or length $CHR3_LEN_GRCH38). Contigs are listed in $LOGFILE"
  len="$(contig_length "$INPUT_FILE" "$name")"; asm="$(assembly_of_length "$len")"; style="$(chr3_style_of "$name")"
  log "chromosome 3 is called '$name' ($style), length ${len:-unknown}, assembly $asm"
  [ "$asm" = GRCh37 ] && fail "this data is GRCh37; the hotspot coordinates here are GRCh38"
  [ "$asm" = other ] && warn "chr3 length $len matches neither GRCh38 nor GRCh37 — coordinates may be wrong"
  refarg=(); [ -n "$INPUT_REFERENCE" ] && refarg=(--reference "$INPUT_REFERENCE")
  probe="${name}:${PRIMARY_START}-$((PRIMARY_START+200))"
  out="$(samtools view -c "${refarg[@]}" "$INPUT_FILE" "$probe" 2>&1)"; rc=$?
  [ $rc -eq 0 ] || fail "cannot read reads at $probe: $out   (a CRAM may need INPUT_REFERENCE=<the FASTA it was encoded with>)"
  log "readable: $out reads in the first 200 bp of the primary hotspot"
  state_set INPUT_KIND "$INPUT_TYPE"; state_set INPUT_PATH "$INPUT_FILE"
  state_set CHR3_NAME "$name"; state_set CHR3_STYLE "$style"; state_set ASSEMBLY "$asm"
  done_ok "$INPUT_TYPE readable; chr3 is '$name' ($style), $asm" chr3_name="$name" chr3_style="$style" assembly="$asm" ;;
fastq)
  for f in "$FASTQ_R1" "$FASTQ_R2"; do [ -f "$f" ] || fail "FASTQ not found: '$f'"; done
  rl1=$(zcat -f "$FASTQ_R1" 2>/dev/null | head -4 | awk 'NR==2{print length($0)}')
  rl2=$(zcat -f "$FASTQ_R2" 2>/dev/null | head -4 | awk 'NR==2{print length($0)}')
  [ -n "$rl1" ] && [ -n "$rl2" ] || fail "could not read the first record of the FASTQ files (corrupt or not FASTQ?)"
  log "read length R1=$rl1 R2=$rl2"
  state_set INPUT_KIND fastq; state_set READ_LEN "$rl1"
  done_ok "FASTQ pair readable (read length $rl1); chr3 naming is decided by the reference in skill 02" read_len="$rl1" ;;
esac
