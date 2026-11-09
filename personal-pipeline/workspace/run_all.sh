#!/usr/bin/env bash
# Run every skill in order; stop at the first FAIL. Usage: bash workspace/run_all.sh   (or: FROM=04 bash workspace/run_all.sh)
cd "$(dirname "$0")/.." || exit 1   # run from the process root
FROM="${FROM:-00}"
for s in 00_check_env 01_inspect_input 02_prepare_reference 03_align_fastq 04_extract_region 06_call_variants 07_read_signals 08_allele_balance 09_gnomad_frequency 10_report; do
  [[ "${s%%_*}" < "$FROM" ]] && continue
  bash ".agent/skills/$s/$s.sh" || { echo; echo "STOPPED: skill $s failed. Read workspace/logs/$s.log, fix the cause, then: FROM=${s%%_*} bash workspace/run_all.sh"; exit 1; }
done
