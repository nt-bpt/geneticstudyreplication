---
name: 04_context_checks
description: tag hot regions with testable mundane explanations
---

#  04_context_checks Skill

SKILL 04 — For the best TOP_N regions, check overlap with segmental duplications, structural variants in the same trio, recurrence across trios, allele frequency of the nonparental alleles and whether the trio has a high background rate.

Expected workflow:

1. Call `run_skill_script` with the skill name 04_context_checks and the resource 04_context_checks.sh, setting `return_output` to false so the script output is not returned.
2. Read `results/04_context_checks.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/04_context_checks.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

This skill finishes in seconds to a few minutes.

Outputs:

results/04_context_checks.json
npa/chr<N>/npa_region_context.tsv

If it fails:

- segdup track not downloadable: the step continues with a warning and that tag is unavailable.
- SKIPPED means there were no hot regions.
