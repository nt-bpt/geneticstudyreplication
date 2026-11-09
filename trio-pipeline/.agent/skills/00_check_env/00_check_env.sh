#!/usr/bin/env bash
# SKILL 00 — verify tools, python modules, disk space.
source "${PROC_ROOT:-$PWD}/workspace/lib/common.sh"; load_config; skill_begin 00_check_env
miss=()
for c in bcftools tabix bgzip curl python3; do
  if command -v "$c" >/dev/null 2>&1; then log "ok  $c"; else miss+=("$c"); fi
done
[ ${#miss[@]} -eq 0 ] || fail "missing tools: ${miss[*]}  (conda install -c bioconda bcftools htslib)"
pm=()
for m in numpy cyvcf2; do python3 -c "import $m" 2>/dev/null && log "ok  python: $m" || pm+=("$m"); done
[ ${#pm[@]} -eq 0 ] || fail "missing python modules: ${pm[*]}  (pip install ${pm[*]})"
python3 -c "import scipy" 2>/dev/null && log "ok  python: scipy (optional, used for Fisher test)" || warn "scipy not installed — optional comparisons will be skipped"
free_gb=$(df -Pk "$WORK" | awk 'NR==2{printf "%d", $4/1048576}')
log "free disk: ${free_gb} GB"
n=$(( 1 + $(echo "$BASELINE_CHROMS" | wc -w) ))
[ "${free_gb:-0}" -ge $(( n * 8 )) ] || warn "each chromosome VCF can be several GB; $n chromosome(s) planned and only ${free_gb} GB free"
done_ok "environment ready" free_gb="${free_gb:-0}" chromosomes_planned="$n"
