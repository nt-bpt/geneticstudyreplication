---
name: 16-report
description: write the final report from all skill results
---

#  16-report Skill

SKILL 16 — Collect the results of all skills into one readable report.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `16-report` and `file_path` set to `scripts/16-report.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/16-report.json`).
2. Read that JSON. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

This skill finishes in seconds.

After this skill, give the user the text in `report` from the tool result. Do not add claims that are not in it.

Outputs:

results/report.md, also returned in full as `report` in the tool result
results/16-report.json

If it fails:

- 13-label-segments has not run: run the skills in order up to 13 first.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

This is the last skill.
