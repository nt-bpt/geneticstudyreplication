---
name: 08_report
description: assemble the final trio-analysis report
---

#  08_report Skill

SKILL 08 — Combine all results into results/FINAL_REPORT.txt covering hot regions, the focus window, explanatory tags, baseline, family comparison and limits.

Expected workflow:

1. Call `run_skill_script` with the skill name 08_report and the resource 08_report.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/08_report.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/08_report.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

This skill finishes in seconds to a few minutes.

Outputs:

results/FINAL_REPORT.txt

If it fails:

- an earlier step shows NOT RUN: run it or report it as not run.
