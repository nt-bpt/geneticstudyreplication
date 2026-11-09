---
name: 06_baseline
description: scan other chromosomes with the same settings to get a baseline
---

#  06_baseline Skill

SKILL 06 — Run the same NPA scan on each chromosome in BASELINE_CHROMS and tabulate hot regions per record, so chr3 can be compared with normal chromosomes.

Expected workflow:

1. Call `run_skill_script` with the skill name 06_baseline and the resource 06_baseline.sh, setting `return_output` to false so the script output is not returned.
2. Read `results/06_baseline.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/06_baseline.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

This is long-running: each baseline chromosome is a multi-GB download plus a full scan. SKIPPED when BASELINE_CHROMS is empty; say in the report that no baseline was run.

Outputs:

results/06_baseline.json
results/06_baseline.tsv

If it fails:

- fewer than two chromosomes scanned: check the log for download failures or use MANUAL_DIR.
