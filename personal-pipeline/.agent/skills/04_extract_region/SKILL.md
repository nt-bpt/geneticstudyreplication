---
name: 04_extract_region
description: extract the control and hotspot regions into one small BAM
---

#  04_extract_region Skill

SKILL 04 — Pull the control window and the extended hotspot window out of the CRAM/BAM into one small working BAM, using the file's own chr3 name, and verify it is not empty.

Expected workflow:

1. Call `run_skill_script` with the skill name 04_extract_region and the resource 04_extract_region.sh, setting `return_output` to false so the script output is not returned.
2. Read `results/04_extract_region.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/04_extract_region.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

Extraction reads a whole-genome CRAM through its index and can take from minutes to an hour. The step fails if the result contains no reads, rather than passing silently.

Outputs:

results/04_extract_region.json
bam/region.bam  <- REGION_BAM in state.env (small file used by every later test)

If it fails:

- empty BAM: the chr3 name or coordinates were wrong; rerun 01 and check CHR3_NAME.
- control depth over 120x: warning only; note it, since paralogous reads may be piled onto chr3.
