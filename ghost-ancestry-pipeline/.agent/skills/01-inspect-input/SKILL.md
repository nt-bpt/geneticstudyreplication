---
name: 01-inspect-input
description: identify the input files (FASTQ pair or CRAM/BAM) and the genome build
---

#  01-inspect-input Skill

SKILL 01 — Work out whether the input is a FASTQ pair or a CRAM/BAM, and for an alignment which genome build it uses.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `01-inspect-input` and `file_path` set to `scripts/01-inspect-input.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/01-inspect-input.json`).
2. Read that JSON. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

This skill finishes in seconds to a minute.

Outputs:

results/01-inspect-input.json (`metrics.mode` is fastq, alignment_grch38 or realign)

If it fails:

- read names do not match: the two FASTQ files may not be a pair; ask the user to check FASTQ_R1 and FASTQ_R2 in repo/config.env.
- could not read alignments from a CRAM: INPUT_REFERENCE must be the exact FASTA the CRAM was made with; ask the user to set it in repo/config.env.
- unknown genome build: ask the user which reference the file was aligned to.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 02-prepare-reference
