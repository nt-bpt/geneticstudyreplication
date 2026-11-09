---
name: 04-qc-alignment
description: check depth of coverage and alignment quality
---

#  04-qc-alignment Skill

SKILL 04 — Measure depth of coverage on the chosen chromosomes and check that it is enough for reliable genotypes.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `04-qc-alignment` and `file_path` set to `scripts/04-qc-alignment.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/04-qc-alignment.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

This skill finishes in a few minutes. The tool call itself returns within seconds.

Outputs:

results/04-qc-alignment.json (`metrics.mean_depth`, `metrics.inferred_sex`)

If it fails:

- depth too low: the genome cannot be genotyped reliably; tell the user and stop. Lowering MIN_MEAN_DEPTH in repo/config.env only hides the problem.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 05-fetch-panel
