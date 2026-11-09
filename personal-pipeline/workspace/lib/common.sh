#!/usr/bin/env bash
# lib/common.sh — shared helpers for every skill. Source it; do not run it.
#
# Design rules
#  * No 'set -e' / 'set -u'. Each skill checks its own steps and reports OK / WARN / FAIL / SKIPPED.
#  * Every skill writes  results/<skill>.json  and a log in  logs/ (both inside workspace/).
#  * Findings are shared between skills through  state.env  (KEY="value" lines).

# Layout (process root = where config.env and AGENT.md live; skills are run FROM there):
#   <proc>/config.env  <proc>/AGENT.md  <proc>/.agent/skills/*      (not visible to the agent)
#   <proc>/workspace/{lib,py,resources,run_all.sh}  + data, bam, vcf, ref, results, logs, tmp, state.env  (the agent's world)
PROC_ROOT="${PROC_ROOT:-$PWD}"
[ -f "$PROC_ROOT/config.env" ] || PROC_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # fallback if started elsewhere
PIPE_ROOT="$PROC_ROOT/workspace"

load_config() {
  # shellcheck disable=SC1091
  source "$PROC_ROOT/config.env"
  WORK="$PIPE_ROOT"   # everything the pipeline writes lives inside workspace/
  mkdir -p "$WORK/data" "$WORK/bam" "$WORK/vcf" "$WORK/ref" "$WORK/results" "$WORK/logs" "$WORK/tmp"
  STATE="$WORK/state.env"; touch "$STATE"
  # shellcheck disable=SC1090
  source "$STATE"
}

state_set() {   # state_set KEY VALUE
  local k="$1" v="$2"
  grep -v "^${k}=" "$STATE" > "$STATE.tmp" 2>/dev/null
  mv "$STATE.tmp" "$STATE"
  printf '%s="%s"\n' "$k" "$v" >> "$STATE"
  export "$k=$v"
}

# ---------- logging / results ----------
skill_begin() {   # skill_begin NAME
  SKILL_NAME="$1"
  LOGFILE="$WORK/logs/${SKILL_NAME}.log"; : > "$LOGFILE"
  WARNFILE="$WORK/tmp/${SKILL_NAME}.warn"; : > "$WARNFILE"
  log "=== ${SKILL_NAME} ==="
}
log()  { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*" | tee -a "${LOGFILE:-/dev/null}"; }
warn() { log "WARN: $*"; echo "$*" >> "${WARNFILE:-/dev/null}"; }

write_result() {  # write_result STATUS VERDICT [key=value ...]
  local status="$1" verdict="$2"; shift 2
  python3 - "$WORK/results/${SKILL_NAME}.json" "$SKILL_NAME" "$status" "$verdict" "${WARNFILE:-/dev/null}" "$@" <<'PY'
import json, sys, datetime
out, name, status, verdict, warnfile, *kv = sys.argv[1:]
metrics = {}
for item in kv:
    k, _, v = item.partition("=")
    for cast in (int, float):
        try:
            v = cast(v); break
        except ValueError:
            pass
    metrics[k] = v
try:
    warnings = [l.strip() for l in open(warnfile) if l.strip()]
except OSError:
    warnings = []
json.dump({"skill": name, "status": status, "verdict": verdict,
           "time_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
           "warnings": warnings, "metrics": metrics}, open(out, "w"), indent=2)
PY
}

fail() { log "FAIL: $*"; write_result FAIL "$*"; exit 1; }
done_ok() { # done_ok VERDICT [key=value ...]  — status becomes WARN if any warning was raised
  local verdict="$1"; shift
  local st=OK; [ -s "$WARNFILE" ] && st=WARN
  write_result "$st" "$verdict" "$@"; log "RESULT: $st — $verdict"; exit 0
}

need_cmds() { local m=(); for c in "$@"; do command -v "$c" >/dev/null 2>&1 || m+=("$c"); done
  [ ${#m[@]} -eq 0 ] || fail "missing tools: ${m[*]}  (conda install -c bioconda samtools bcftools bwa htslib)"; }
need_state() { for k in "$@"; do [ -n "${!k:-}" ] || fail "state '$k' is empty — run the earlier skill first"; done; }

fetch_file() {   # fetch_file URL DEST  — resumable; returns 0 on success
  local url="$1" dest="$2"
  curl -fL --retry 5 --retry-delay 5 -C - -o "${dest}.part" "$url" 2>>"${LOGFILE:-/dev/null}" \
    && mv "${dest}.part" "$dest"
}
probe_vcf_url() { timeout 90 tabix -l "$1" 2>/dev/null | head -1 | grep -q . ; }   # remote VCF + index reachable?

# ---------- chromosome 3 naming ----------
# One chromosome, four spellings in the wild (GRCh38):
#   ucsc    chr3          (UCSC, 1000 Genomes GRCh38 reference, gnomAD)
#   ensembl 3             (Ensembl)
#   genbank CM000665.2    (NCBI GenBank accession, e.g. NCBI-downloaded FASTA)
#   refseq  NC_000003.12  (NCBI RefSeq accession)
CHR3_LEN_GRCH38=198295559
CHR3_LEN_GRCH37=198022430

chr3_is_alias() { case "$1" in chr3|3|CM000665|CM000665.2|NC_000003.12) return 0 ;; *) return 1 ;; esac; }
chr3_style_name() {   # style -> contig name
  case "$(echo "$1" | tr 'A-Z' 'a-z')" in
    ucsc|chr3)                   echo "chr3" ;;
    ensembl|3)                   echo "3" ;;
    genbank|cm000665|cm000665.2) echo "CM000665.2" ;;
    refseq|nc_000003.12)         echo "NC_000003.12" ;;
    *) return 1 ;;
  esac
}
chr3_style_of() {     # contig name -> style label
  case "$1" in chr3) echo ucsc ;; 3) echo ensembl ;; CM000665|CM000665.2) echo genbank ;;
               NC_000003.12) echo refseq ;; *) echo unknown ;; esac
}
chr3_to() {           # chr3_to NAME_OR_REGION STYLE   e.g.  chr3_to chr3:100-200 genbank -> CM000665.2:100-200
  local in="$1" target name rest=""
  target="$(chr3_style_name "$2")" || { echo "unknown style '$2'" >&2; return 1; }
  name="${in%%:*}"; [[ "$in" == *:* ]] && rest=":${in#*:}"
  chr3_is_alias "$name" || { echo "$in"; return 2; }      # not chr3: returned unchanged
  echo "${target}${rest}"
}
region_str() { echo "$1:$2-$3"; }                          # region_str NAME START END

contig_table() {      # FILE -> "name<TAB>length" per contig (length may be blank)
  local f="$1"
  case "$f" in
    *.bam|*.cram|*.sam)
      samtools view -H "$f" 2>/dev/null | awk -F'\t' '$1=="@SQ"{n="";l="";for(i=2;i<=NF;i++){if($i~/^SN:/)n=substr($i,4);if($i~/^LN:/)l=substr($i,4)} print n"\t"l}' ;;
    *.fai) cut -f1,2 "$f" ;;
    *.fa|*.fasta|*.fna) [ -f "$f.fai" ] || samtools faidx "$f" 2>/dev/null; cut -f1,2 "$f.fai" ;;
    *.vcf.gz|*.vcf.bgz|*.vcf|*.bcf)
      if [[ "$f" =~ ^https?:// ]] || [ -f "$f.tbi" ] || [ -f "$f.csi" ]; then
        timeout 90 tabix -l "$f" 2>/dev/null | awk '{print $1"\t"}'
      else
        bcftools view -h "$f" 2>/dev/null | sed -n 's/^##contig=<ID=\([^,>]*\)\(,length=\([0-9]*\)\)\?.*/\1\t\3/p'
      fi ;;
  esac
}
detect_chr3() {       # detect_chr3 FILE -> prints the contig name FILE uses for chr3; returns 1 if none found
  local tab n l; tab="$(contig_table "$1")"
  while IFS=$'\t' read -r n l; do chr3_is_alias "$n" && { echo "$n"; return 0; }; done <<< "$tab"
  while IFS=$'\t' read -r n l; do [ "$l" = "$CHR3_LEN_GRCH38" ] && { echo "$n"; return 0; }; done <<< "$tab"
  return 1
}
contig_length() { contig_table "$1" | awk -F'\t' -v n="$2" '$1==n{print $2; exit}'; }
assembly_of_length() { case "$1" in "$CHR3_LEN_GRCH38") echo GRCh38 ;; "$CHR3_LEN_GRCH37") echo GRCh37 ;; "") echo unknown ;; *) echo other ;; esac; }

make_chr3_fasta() {   # make_chr3_fasta SRC_FASTA SRC_NAME OUT_FASTA OUT_NAME — chr3 only, header renamed
  samtools faidx "$1" "$2" 2>/dev/null | awk -v n="$4" 'NR==1{print ">" n; next} {print}' > "$3"
  [ -s "$3" ] && samtools faidx "$3"
}

# Run a python helper, show its output, and collect its "METRIC k=v" / "VERDICT ..." lines.
#   run_py_helper SCRIPT ARGS...   -> sets PY_RC, PY_VERDICT, PY_METRICS (array of k=v)
run_py_helper() {
  local out="$WORK/tmp/${SKILL_NAME}.py.out"
  python3 "$@" 2>"$WORK/tmp/${SKILL_NAME}.py.err" | tee "$out" | grep -v '^METRIC \|^VERDICT ' | tee -a "$LOGFILE"
  PY_RC=${PIPESTATUS[0]}
  PY_VERDICT="$(grep '^VERDICT ' "$out" | sed 's/^VERDICT //' | head -1)"
  mapfile -t PY_METRICS < <(grep '^METRIC ' "$out" | sed 's/^METRIC //')
  [ $PY_RC -eq 0 ] || log "python stderr: $(tail -5 "$WORK/tmp/${SKILL_NAME}.py.err")"
}
