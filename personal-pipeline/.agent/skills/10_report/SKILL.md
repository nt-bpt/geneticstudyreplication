---
name: 10_report
description: assemble all skill results into one final report
---

#  10_report Skill

SKILL 10 — Combine every results JSON into a plain-text report with the verdict, the evidence for each test and the limits.

Expected workflow:

1. Call `run_skill_script` with the skill name 10_report and the resource 10_report.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/10_report.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/10_report.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

This skill finishes in seconds to a few minutes.

Outputs:

results/FINAL_REPORT.txt

If it fails:

- a skill shows NOT RUN: run it, or report it as not run; never fill it in.
