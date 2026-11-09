---
name: 09_gnomad_frequency
description: compare called variants with gnomAD v4.1 allele frequencies by direct file access
---

#  09_gnomad_frequency Skill

SKILL 09 — Stream only a small window (primary hotspot ± GNOMAD_FLANK) of the gnomAD v4.1 chr3 sites VCF and classify each of your calls as absent, rare (under 1%) or common. No API is used. Joins on position/ref/alt so chromosome names are not compared.

Expected workflow:

1. Call `run_skill_script` with the skill name 09_gnomad_frequency and the resource 09_gnomad_frequency.sh, setting `return_output` to false so the script output is not returned.
2. Read `results/09_gnomad_frequency.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/09_gnomad_frequency.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

The chr3 gnomAD file is about 159 GiB; only the small window is fetched over the network, which takes a minute or two. Set GNOMAD_LOCAL_VCF if you already have a copy.

Outputs:

results/09_gnomad_frequency.json

If it fails:

- both mirrors unreachable: download a region yourself or set GNOMAD_LOCAL_VCF; otherwise report SKIPPED/FAIL honestly.
