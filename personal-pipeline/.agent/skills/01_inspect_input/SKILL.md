---
name: 01_inspect_input
description: inspect the CRAM, BAM or FASTQ input and detect the chr3 name and assembly
---

#  01_inspect_input Skill

SKILL 01 — Check the input is readable, work out which genome build it uses and what it calls chromosome 3 (chr3, 3, CM000665.2 or NC_000003.12). All later skills use the name found here.

Expected workflow:

1. Call `run_skill_script` with the skill name 01_inspect_input and the resource 01_inspect_input.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/01_inspect_input.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/01_inspect_input.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

This skill finishes in seconds to a few minutes.

Outputs:

results/01_inspect_input.json
state.env  <- INPUT_KIND, INPUT_PATH, CHR3_NAME, CHR3_STYLE, ASSEMBLY

If it fails:

- CRAM cannot be read: set INPUT_REFERENCE to the FASTA the CRAM was written with.
- no chr3 found: the file may be GRCh37 or lack chromosome 3; report that and stop.
