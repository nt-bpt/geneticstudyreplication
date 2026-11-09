---
name: 05_compare_rempel
description: compare families named in the preprint with all other trios
---

#  05_compare_rempel Skill

SKILL 05 — Using IDs listed in resources/rempel_families.txt, compare how often those trios have hot regions (and at the focus window) versus all other trios.

Expected workflow:

1. Call `run_skill_script` with the skill name 05_compare_rempel and the resource 05_compare_rempel.sh, setting `return_output` to false so the script output is not returned.
2. Read `results/05_compare_rempel.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/05_compare_rempel.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

This skill finishes in seconds to a few minutes.
The family list is empty by design because the IDs from the preprint were not verified. The skill reports SKIPPED until the user fills the file; report it as not done.

Outputs:

results/05_compare_rempel.json

If it fails:

- listed IDs not matching any trio: check spelling and that they are in the VCF.
