---
name: 02_prepare_reference
description: choose and prepare the reference FASTA for alignment and variant calling
---

#  02_prepare_reference Skill

SKILL 02 — Decide which reference FASTA is used to align FASTQ and to call variants; download and index it if needed (GRCh38 full analysis set for FASTQ).

Expected workflow:

1. Call `run_skill_script` with the skill name 02_prepare_reference and the resource 02_prepare_reference.sh, setting `return_output` to false so the script output is not returned.
2. Read `results/02_prepare_reference.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/02_prepare_reference.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

Downloading a full GRCh38 reference is about 3 GB and indexing for bwa can take 1 to 2 hours; the step is skipped when files already exist.

Outputs:

results/02_prepare_reference.json
ref/  <- reference FASTA and indexes
state.env  <- CALL_REF_SOURCE, CALL_REF_CHR3

If it fails:

- download blocked: download the file in a browser, put it in ref/ and set REFERENCE.
- GRCh37 detected: stop; the hotspot coordinates are GRCh38.
