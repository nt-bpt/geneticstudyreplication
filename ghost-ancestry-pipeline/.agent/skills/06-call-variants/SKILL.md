---
name: 06-call-variants
description: genotype the user's genome at every 1000 Genomes SNP site
---

#  06-call-variants Skill

SKILL 06 — Genotype the user's alignment at every SNP position in the 1000 Genomes panel, keeping only confident calls.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `06-call-variants` and `file_path` set to `scripts/06-call-variants.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/06-call-variants.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

About 15-60 minutes per chromosome. The tool call itself returns within seconds.

Outputs:

results/06-call-variants.json (`metrics.per_chromosome` has call rates and het/hom ratios)
work/calls/<SAMPLE_NAME>.<chrom>.vcf.gz

If it fails:

- CRAM decoding error: the reference in results/02-prepare-reference.json is not the one the CRAM was made with; ask the user to set INPUT_REFERENCE correctly, then rerun 02 and this skill.
- low call rate or unusual het/hom ratio (WARN): mention it in the report; it can mean low coverage or a sample problem.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 07-phase
