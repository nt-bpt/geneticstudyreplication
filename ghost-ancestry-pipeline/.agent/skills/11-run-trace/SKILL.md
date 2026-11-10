---
name: 11-run-trace
description: run TRACE at t=15,000 generations to find archaic segments in the user's haplotypes
---

#  11-run-trace Skill

SKILL 11 — Run TRACE's three stages (extract, infer, summarize) on the user's two haplotypes at t = 15,000 generations, keeping archaic segments longer than 50 kb and 0.05 cM.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `11-run-trace` and `file_path` set to `scripts/11-run-trace.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/11-run-trace.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

Extraction takes minutes to an hour per chromosome; inference and summarising are quicker. The tool call itself returns within seconds.

A WARN about few chromosomes is expected on a chr22 pilot: TRACE trains its model on the chromosomes it is given, so a pilot checks the pipeline rather than measuring ancestry.

Finding no segments is possible on a small pilot and is not an error.

Outputs:

results/11-run-trace.json (`metrics.segments_kept`, `metrics.archaic_fraction_per_genome`)
work/trace/t15000/segments.filtered.tsv
work/trace/t15000/trace.log

If it fails:

- TRACE command not found: give the user the pip command from the verdict (see 09-fetch-trace).
- TRACE needs one tree sequence per chromosome: the verdict explains this; ask the user to set ARG_METHOD=relate in repo/config.env and rerun 10-build-arg.
- a TRACE command failed: the verdict ends with the last lines of work/trace/t15000/trace.log; report them to the user.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 12-fetch-archaic
