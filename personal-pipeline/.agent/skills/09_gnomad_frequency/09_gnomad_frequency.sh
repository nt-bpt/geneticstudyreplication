#!/usr/bin/env bash
# SKILL 09 — compare your PASS calls with gnomAD v4.1 allele frequencies (direct file access, no API).
# Only a small window around the primary hotspot is fetched: the chr3 gnomAD file is ~159 GiB, roughly 0.8 GiB per Mb.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 09_gnomad_frequency
source "$PIPE_ROOT/resources/urls.env"
need_cmds bcftools tabix bgzip python3
need_state CALLS_VCF

SRC=""
if [ -n "$GNOMAD_LOCAL_VCF" ]; then
  [ -f "$GNOMAD_LOCAL_VCF" ] || fail "GNOMAD_LOCAL_VCF not found: $GNOMAD_LOCAL_VCF"; SRC="$GNOMAD_LOCAL_VCF"
  [ -f "$SRC.tbi" ] || [ -f "$SRC.csi" ] || fail "no index next to $SRC. Download $SRC.tbi from the same place as the VCF, or build it: tabix -p vcf $SRC  (reads the whole file, so it takes a while)"
else
  for u in $GNOMAD_URLS; do log "probing $u"; probe_vcf_url "$u" && { SRC="$u"; break; } || log "  not reachable"; done
fi
[ -n "$SRC" ] || fail "no gnomAD source reachable. Options: check internet/proxy; or fetch the region yourself and set GNOMAD_LOCAL_VCF=<indexed VCF> in config.env"
log "using gnomAD source: $SRC"

GCHR="$(detect_chr3 "$SRC")" || fail "gnomAD source has no chr3 contig"
FS=$((PRIMARY_START-GNOMAD_FLANK)); FE=$((PRIMARY_END+GNOMAD_FLANK))
GREG="$(chr3_to "chr3:${FS}-${FE}" "$(chr3_style_of "$GCHR")")"
GSUB="$WORK/data/gnomad_subset.vcf.gz"
log "fetching $GREG (gnomAD names chr3 '$GCHR'; your data names it '${CHR3_NAME:-?}' — positions are joined, names are not compared)"
bcftools view -r "$GREG" -Oz -o "$GSUB" "$SRC" 2>"$WORK/tmp/gnomad_fetch.err" \
  || { rm -f "$GSUB"; timeout 600 tabix -h "$SRC" "$GREG" 2>>"$WORK/tmp/gnomad_fetch.err" | bgzip > "$GSUB"; }
[ -s "$GSUB" ] || fail "could not fetch $GREG from gnomAD: $(head -2 "$WORK/tmp/gnomad_fetch.err")"
bcftools index -t -f "$GSUB" 2>/dev/null || tabix -f -p vcf "$GSUB"

has() { bcftools view -h "$GSUB" 2>/dev/null | grep -q "^##INFO=<ID=$1[,>]"; }
pick() { for f in "$@"; do has "$f" && { echo "$f"; return; }; done; }
AF="${GNOMAD_AF_FIELD:-$(pick AF AF_genomes AF_joint)}"; AC="${GNOMAD_AC_FIELD:-$(pick AC AC_genomes AC_joint)}"; AN="${GNOMAD_AN_FIELD:-$(pick AN AN_genomes AN_joint)}"; NH="${GNOMAD_NHOM_FIELD:-$(pick nhomalt nhomalt_genomes nhomalt_joint)}"
log "INFO fields used: AF=$AF AC=$AC AN=$AN nhomalt=${NH:-none}"
nrec=$(bcftools view -H "$GSUB" 2>/dev/null | wc -l)
if [ -z "$AF" ] && [ -z "$AC" ]; then
  ids=$(bcftools view -h "$GSUB" 2>/dev/null | sed -n 's/^##INFO=<ID=\([^,]*\),.*/\1/p' | head -60 | tr '\n' ' ')
  nh=$(bcftools view -h "$GSUB" 2>/dev/null | grep -c '^##INFO')
  log "subset has $nrec records and $nh INFO header lines. INFO IDs seen: ${ids:-<none>}"
  [ "$nh" -gt 0 ] || fail "the downloaded subset has no INFO header lines — it is probably not a gnomAD VCF (an error page or an empty fetch). Check $WORK/tmp/gnomad_fetch.err and: bcftools view -h $GSUB | head"
  fail "none of the usual allele-frequency fields exist in this gnomAD file. The INFO IDs seen are listed in the log above. Set GNOMAD_AF_FIELD / GNOMAD_AC_FIELD / GNOMAD_AN_FIELD (and optionally GNOMAD_NHOM_FIELD) in config.env to the right names and rerun this skill"
fi

run_py_helper "$PIPE_ROOT/py/gnomad_join.py" "$CALLS_VCF" "$GSUB" "$FS" "$FE" "$PRIMARY_START" "$PRIMARY_END" "$AF" "$AC" "$AN" "$NH" "$WORK/results/09_gnomad_annotated.tsv"
[ $PY_RC -eq 0 ] || fail "gnomad_join.py failed"
ng=$(printf '%s\n' "${PY_METRICS[@]}" | sed -n 's/^gnomad_records=//p')
[ "${ng:-0}" -gt 0 ] || warn "gnomAD subset contained no records — every variant would look 'absent'; do not trust this result"
case "$SRC" in *4.0*) warn "gnomAD v4.0 has a known allele-number issue fixed in v4.1" ;; esac
done_ok "$PY_VERDICT" "${PY_METRICS[@]}" gnomad_source="$(basename "$(dirname "$(dirname "$(dirname "$SRC")")")")"
