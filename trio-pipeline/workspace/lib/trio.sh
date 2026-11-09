#!/usr/bin/env bash
# lib/trio.sh — trio-pipeline helpers (sourced after common.sh)

link_or_copy() { ln -sf "$1" "$2" 2>/dev/null || cp -f "$1" "$2"; }   # symlink if the filesystem allows, else copy
vcf_name_for() { echo "${VCF_NAME_PATTERN//@CHROM@/$1}"; }

# get_vcf CHROM  -> sets GV_PATH and GV_CONTIG (contig name used INSIDE the VCF); returns 1 on failure
get_vcf() {
  local chrom="$1" name path base ok=""
  name="$(vcf_name_for "$chrom")"; path="$WORK/data/$name"
  if [ -n "$MANUAL_DIR" ] && [ -s "$MANUAL_DIR/$name" ]; then
    log "using file from MANUAL_DIR: $MANUAL_DIR/$name"
    link_or_copy "$MANUAL_DIR/$name" "$path"
    if [ -s "$MANUAL_DIR/$name.tbi" ]; then link_or_copy "$MANUAL_DIR/$name.tbi" "$path.tbi"; fi
  fi
  if [ ! -s "$path" ]; then
    for base in $VCF_BASES; do
      log "probing $base/$name"
      if curl -sfI --max-time 60 "$base/$name" >/dev/null 2>&1; then
        local sz; sz=$(curl -sfI --max-time 60 "$base/$name" | tr -d '\r' | awk 'tolower($1)=="content-length:"{printf "%.1f", $2/1073741824}')
        log "found; size about ${sz:-?} GiB; downloading (resumable — re-run to continue)"
        fetch_file "$base/$name.tbi" "$path.tbi" || { warn "index download failed from $base"; continue; }
        fetch_file "$base/$name" "$path" && { ok=1; break; }
        warn "download failed from $base"
      else
        warn "not reachable: $base/$name"
      fi
    done
    [ -n "$ok" ] || { log "could not download $name. Download it yourself in a browser, put it (and the .tbi) in one folder and set MANUAL_DIR=/that/folder"; return 1; }
  fi
  [ -s "$path.tbi" ] || tabix -p vcf "$path" 2>>"$LOGFILE" || { log "no index and tabix -p vcf failed"; return 1; }
  # verification: BGZF/tabix readable, one contig, samples present
  local contigs; contigs="$(tabix -l "$path" 2>/dev/null)"
  [ -n "$contigs" ] || { log "tabix cannot read $path (truncated download? delete it and re-run)"; return 1; }
  GV_CONTIG=""
  for c in "$chrom" "chr$chrom"; do echo "$contigs" | grep -qx "$c" && { GV_CONTIG="$c"; break; }; done
  [ -n "$GV_CONTIG" ] || { log "contigs in file: $(echo "$contigs" | head -5 | tr '\n' ' ') — neither '$chrom' nor 'chr$chrom'"; return 1; }
  GV_PATH="$path"
  return 0
}
