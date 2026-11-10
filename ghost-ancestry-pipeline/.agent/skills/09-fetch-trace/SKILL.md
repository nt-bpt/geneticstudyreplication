---
name: 09-fetch-trace
description: check that TRACE is installed and download the published archaic tracts
---

#  09-fetch-trace Skill

SKILL 09 — Check that TRACE's three commands are installed in this environment, and download the archaic tracts published with the paper (used for comparison in skill 15).

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `09-fetch-trace` and `file_path` set to `scripts/09-fetch-trace.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/09-fetch-trace.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

A few minutes, mostly download time. The tool call itself returns within seconds.

You do not need to configure any TRACE command: skills 11 and 14 call trace-extract, trace-infer and trace-summarize themselves.

Outputs:

results/09-fetch-trace.json (`metrics.trace_commands`, `metrics.trace_data_dir`)
data/trace_data/ (the published tracts)

If it fails:

- TRACE not installed: give the user the pip command from the verdict. TRACE is a Python package (MIT licence) that provides trace-extract, trace-infer and trace-summarize; it must go into the same environment that runs this pipeline.
- Zenodo download failed: this is only a WARN. The run continues without the comparison against published tracts; mention it in the report.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 10-build-arg
