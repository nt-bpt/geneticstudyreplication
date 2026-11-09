---
name: 11-run-trace
description: run TRACE at t=15,000 generations to find archaic segments in the user's haplotypes
---

#  11-run-trace Skill

SKILL 11 — Run TRACE (t = 15,000 generations) on the user's two haplotypes and keep archaic segments longer than 50 kb and 0.05 cM.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `11-run-trace` and `file_path` set to `scripts/11-run-trace.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/11-run-trace.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

Several hours, depending on TRACE speed and the number of windows. The tool call itself returns within seconds.

Outputs:

results/11-run-trace.json
work/trace/t15000/segments.filtered.tsv

If it fails:

- TRACE_CMD_TEMPLATE is empty: ask the user to set TRACE_CMD_TEMPLATE in repo/config.env (see 09-fetch-trace).
- cannot find start/end columns: TRACE output has an unexpected layout. Show the user the first lines of one file in work/trace/t15000/, and ask them to set TRACE_OUTPUT_COLUMNS (and TRACE_STATE_COLUMN if needed) in repo/config.env.
- TRACE did not write the output file: the template must write to `{out}`; tell the user.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 12-fetch-archaic
