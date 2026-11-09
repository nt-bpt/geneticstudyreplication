---
name: 15-annotate-genes
description: list genes inside the archaic segments and compare with the published tracts
---

#  15-annotate-genes Skill

SKILL 15 — List the genes inside the user's archaic segments, flag genes named in the paper, and compare ghost segments with the published tracts.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `15-annotate-genes` and `file_path` set to `scripts/15-annotate-genes.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/15-annotate-genes.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

This skill finishes in a few minutes. The tool call itself returns within seconds.

Outputs:

results/15-annotate-genes.json (`metrics.paper_genes_in_user_segments`)
work/annotation/segment_genes.tsv

If it fails:

- GENCODE download failed: run again; if it keeps failing ask the user to check GENCODE_URL in repo/config.env.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 16-report
