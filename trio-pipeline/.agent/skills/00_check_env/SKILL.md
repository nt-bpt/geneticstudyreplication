---
name: 00_check_env
description: verify tools, python modules and disk space for the trio analysis
---

#  00_check_env Skill

SKILL 00 — Check bcftools, tabix, bgzip, curl, python3 with numpy and cyvcf2, and the free disk space for the planned chromosomes.

Expected workflow:

1. Call `run_skill_script` with the skill name 00_check_env and the resource 00_check_env.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/00_check_env.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/00_check_env.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

This skill finishes in seconds to a few minutes.

Outputs:

results/00_check_env.json

If it fails:

- missing python modules: `pip install numpy cyvcf2`.
- missing tools: `conda install -c bioconda bcftools htslib`.
