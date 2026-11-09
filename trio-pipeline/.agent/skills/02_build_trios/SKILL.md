---
name: 02_build_trios
description: build the child-father-mother trio table from the pedigree
---

#  02_build_trios Skill

SKILL 02 — Keep the pedigree rows with both parents listed and all three people present in the VCF; write data/trios.tsv.

Expected workflow:

1. Call `run_skill_script` with the skill name 02_build_trios and the resource 02_build_trios.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/02_build_trios.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/02_build_trios.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

This skill finishes in seconds to a few minutes.

Outputs:

results/02_build_trios.json
data/trios.tsv  <- TRIOS_TSV

If it fails:

- 'no usable trios': the pedigree columns were mis-detected; read the printed first rows and fix py/prepare_trios.py.
