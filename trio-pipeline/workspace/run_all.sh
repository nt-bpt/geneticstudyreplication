#!/usr/bin/env bash
# Run the whole trio pipeline. FROM=NN restarts at skill NN. Stops on the first FAIL.
cd "$(dirname "$0")/..";  FROM="${FROM:-00}"
for s in 00_check_env 01_download 02_build_trios 03_npa_scan 04_context_checks 05_compare_rempel 06_baseline 07_rempel_method 08_report; do
  [ "${s%%_*}" \< "$FROM" ] && continue
  echo ">>> $s"; bash ".agent/skills/$s/$s.sh"
  st=$(python3 -c "import json;print(json.load(open('workspace/results/$s.json'))['status'])" 2>/dev/null || echo FAIL)
  echo "    status: $st"; [ "$st" = FAIL ] && { echo "stopped at $s — see workspace/logs/$s.log"; exit 1; }
done
echo; echo "Report: workspace/results/FINAL_REPORT.txt"
