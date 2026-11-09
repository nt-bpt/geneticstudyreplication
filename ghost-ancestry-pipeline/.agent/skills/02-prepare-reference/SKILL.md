---
name: 02-prepare-reference
description: download and index the GRCh38 reference genome
---

#  02-prepare-reference Skill

SKILL 02 — Get the GRCh38 reference genome and build the indexes needed for alignment and variant calling.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `02-prepare-reference` and `file_path` set to `scripts/02-prepare-reference.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/02-prepare-reference.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

Downloading takes 10-60 minutes; building the bwa index adds about 1 hour (only for FASTQ input or realignment). The tool call itself returns within seconds.

Outputs:

results/02-prepare-reference.json (`metrics.reference` is the FASTA used by later skills)

If it fails:

- download failed: run the skill again (downloads resume). If it keeps failing, ask the user to download REFERENCE_URL by hand and set REFERENCE_FASTA in repo/config.env.
- chromosome missing or wrong length: the reference is not chr-prefixed GRCh38; ask the user to clear REFERENCE_FASTA so the default GRCh38 is downloaded.
- bwa index failed: usually too little memory (needs about 5 GB) or disk.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 03-align-reads
