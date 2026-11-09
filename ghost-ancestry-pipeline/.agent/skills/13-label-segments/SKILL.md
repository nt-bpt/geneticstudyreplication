---
name: 13-label-segments
description: label archaic segments as Neanderthal, Denisovan or Ghost
---

#  13-label-segments Skill

SKILL 13 — Label each archaic segment as Neanderthal, Denisovan or Ghost from how many of its derived alleles it shares with the sequenced archaic genomes.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `13-label-segments` and `file_path` set to `scripts/13-label-segments.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/13-label-segments.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

This skill finishes in a few minutes. The tool call itself returns within seconds.

This skill always gives a WARN that the labelling rule is simplified; mention it in the report.

Outputs:

results/13-label-segments.json (`metrics.by_label` has segment counts and genome shares)
work/labels/segments.labeled.tsv

If it fails:

- archaic table missing: run 12-fetch-archaic first.
- no segments: 11-run-trace kept nothing; report that and stop.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 14-super-archaic
