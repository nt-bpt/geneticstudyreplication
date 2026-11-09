---
name: 09-fetch-trace
description: download TRACE software, the authors' pipeline and published tracts from Zenodo
---

#  09-fetch-trace Skill

SKILL 09 — Download the TRACE software, the authors' analysis pipeline and the published archaic tracts from Zenodo.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `09-fetch-trace` and `file_path` set to `scripts/09-fetch-trace.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/09-fetch-trace.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

A few minutes to an hour, depending on download size. The tool call itself returns within seconds.

If TRACE_CMD_TEMPLATE is empty this skill gives a WARN. Tell the user they must install TRACE and set TRACE_CMD_TEMPLATE in repo/config.env before skill 11. The start of the TRACE README is in `trace_readme_preview` in the tool result; you may use it to suggest a template, but the user sets it.

Outputs:

results/09-fetch-trace.json (`trace_readme_preview` holds the start of the TRACE README)
tools/trace_software/, tools/trace_pipeline/, data/trace_data/

If it fails:

- Zenodo listing failed: ask the user to download the three Zenodo records by hand into tools/trace_software, tools/trace_pipeline and data/trace_data, then run again.
- not enough disk space for Trace_data: ask the user to free space.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 10-build-arg
