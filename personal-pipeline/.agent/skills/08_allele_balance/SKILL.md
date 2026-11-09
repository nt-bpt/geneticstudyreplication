---
name: 08_allele_balance
description: test heterozygous calls for allele balance with an exact binomial test
---

#  08_allele_balance Skill

SKILL 08 — At heterozygous calls, test whether the ref/alt read split is consistent with 50:50, in the hotspot versus the control. Reports LOW_POWER when there are under 10 het sites.

Expected workflow:

1. Call `run_skill_script` with the skill name 08_allele_balance and the resource 08_allele_balance.sh, setting `return_output` to false so the script output is not returned.
2. Read `results/08_allele_balance.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/08_allele_balance.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

This skill finishes in seconds to a few minutes.

Outputs:

results/08_allele_balance.json

If it fails:

- CALLS_VCF empty: run 06 first.
