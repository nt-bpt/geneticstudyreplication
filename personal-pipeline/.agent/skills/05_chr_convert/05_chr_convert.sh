#!/usr/bin/env bash
# SKILL 05 — chromosome-3 name converter (chr3 <-> 3 <-> CM000665.2 <-> NC_000003.12). A utility, not a pipeline step.
#
#   05_chr_convert.sh aliases
#   05_chr_convert.sh detect  FILE                         # what does this BAM/CRAM/VCF/FASTA call chr3?
#   05_chr_convert.sh name    NAME   --to STYLE            # chr3 -> CM000665.2
#   05_chr_convert.sh region  chr3:75440000-75600000 --to genbank
#   05_chr_convert.sh vcf     IN.vcf.gz  OUT.vcf.gz  --to STYLE
#   05_chr_convert.sh bam     IN.{bam,cram} OUT.bam --to STYLE [--region R] [--reference FASTA]
#   05_chr_convert.sh fasta   IN.fa OUT.fa --to STYLE
#   05_chr_convert.sh bed     IN.bed OUT.bed --to STYLE
# STYLE = ucsc | ensembl | genbank | refseq   (or the literal names chr3, 3, CM000665.2, NC_000003.12)
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"
usage() { sed -n '2,15p' "$0" | sed 's/^# \?//'; exit 2; }
die() { echo "ERROR: $*" >&2; exit 1; }
cmd="${1:-}"; [ -n "$cmd" ] || usage; shift
pos=(); STYLE=""; REGION=""; REFERENCE_FA=""
while [ $# -gt 0 ]; do case "$1" in
  --to) STYLE="$2"; shift 2 ;; --region) REGION="$2"; shift 2 ;; --reference) REFERENCE_FA="$2"; shift 2 ;;
  -h|--help) usage ;; *) pos+=("$1"); shift ;; esac; done
need() { command -v "$1" >/dev/null 2>&1 || die "$1 not installed"; }
target_name() { [ -n "$STYLE" ] || die "--to STYLE is required"; chr3_style_name "$STYLE" || die "unknown style '$STYLE'"; }

case "$cmd" in
aliases) column -t -s$'\t' "$PIPE_ROOT/resources/chr3_aliases.tsv" 2>/dev/null || cat "$PIPE_ROOT/resources/chr3_aliases.tsv" ;;
detect)  [ -n "${pos[0]:-}" ] || usage; n="$(detect_chr3 "${pos[0]}")" || die "no chromosome-3 contig found in ${pos[0]}"
         echo "$n  (style: $(chr3_style_of "$n"), length: $(contig_length "${pos[0]}" "$n"))" ;;
name|region) [ -n "${pos[0]:-}" ] || usage; target_name >/dev/null; chr3_to "${pos[0]}" "$STYLE"; [ $? -le 2 ] || exit 1 ;;
vcf) need bcftools; [ ${#pos[@]} -ge 2 ] || usage; new="$(target_name)"
     old="$(detect_chr3 "${pos[0]}")" || die "no chr3 contig in ${pos[0]}"
     if [ "$old" = "$new" ]; then cp "${pos[0]}" "${pos[1]}"; else
       printf '%s\t%s\n' "$old" "$new" > "${pos[1]}.map"
       bcftools annotate --rename-chrs "${pos[1]}.map" -O z -o "${pos[1]}" "${pos[0]}" || die "bcftools annotate failed"; rm -f "${pos[1]}.map"; fi
     bcftools index -t -f "${pos[1]}" && echo "wrote ${pos[1]}  ($old -> $new)" ;;
bam) need samtools; [ ${#pos[@]} -ge 2 ] || usage; new="$(target_name)"
     old="$(detect_chr3 "${pos[0]}")" || die "no chr3 contig in ${pos[0]}"
     refarg=(); [ -n "$REFERENCE_FA" ] && refarg=(--reference "$REFERENCE_FA")
     tmpb="${pos[1]}.tmp.bam"
     if [ -n "$REGION" ]; then samtools view -b "${refarg[@]}" -o "$tmpb" "${pos[0]}" "$REGION" || die "extract failed"
     else samtools view -b "${refarg[@]}" -o "$tmpb" "${pos[0]}" || die "conversion to BAM failed"; fi
     samtools view -H "$tmpb" | awk -F'\t' -v OFS='\t' -v o="$old" -v n="$new" '$1=="@SQ"{for(i=2;i<=NF;i++) if($i=="SN:"o) $i="SN:"n} {print}' > "${pos[1]}.hdr"
     samtools reheader "${pos[1]}.hdr" "$tmpb" > "${pos[1]}" || die "reheader failed"
     samtools index "${pos[1]}"; rm -f "$tmpb" "${pos[1]}.hdr"; echo "wrote ${pos[1]}  ($old -> $new)" ;;
fasta) need samtools; [ ${#pos[@]} -ge 2 ] || usage; new="$(target_name)"
     awk -v n="$new" '/^>/{split(substr($0,2),a," "); if(a[1]=="chr3"||a[1]=="3"||a[1]=="CM000665"||a[1]=="CM000665.2"||a[1]=="NC_000003.12"){print ">" n; next}} {print}' "${pos[0]}" > "${pos[1]}"
     samtools faidx "${pos[1]}" && echo "wrote ${pos[1]}" ;;
bed) [ ${#pos[@]} -ge 2 ] || usage; new="$(target_name)"
     awk -F'\t' -v OFS='\t' -v n="$new" '{if($1=="chr3"||$1=="3"||$1=="CM000665"||$1=="CM000665.2"||$1=="NC_000003.12")$1=n; print}' "${pos[0]}" > "${pos[1]}" && echo "wrote ${pos[1]}" ;;
*) usage ;;
esac
