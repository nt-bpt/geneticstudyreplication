---
name: 14-super-archaic
description: screen the user's Denisovan segments for super-archaic pieces
---

#  14-super-archaic Skill

SKILL 14 — Run TRACE again with t = 31,500 generations inside the user's Denisovan segments to find candidate super-archaic pieces.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `14-super-archaic` and `file_path` set to `scripts/14-super-archaic.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/14-super-archaic.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

Minutes to hours. Reports SKIPPED at once when the genome has no Denisovan segments, which is common outside Oceania and Asia. The tool call itself returns within seconds.

Outputs:

results/14-super-archaic.json
work/labels/super_archaic_candidates.tsv

If it fails:

- TRACE errors: same fixes as 11-run-trace.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 15-annotate-genes
