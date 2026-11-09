---
name: 03_npa_scan
description: scan for windows rich in nonparental alleles in every trio
---

#  03_npa_scan Skill

SKILL 03 — For each trio count child alleles absent from both parents at informative SNVs, slide a window of WINDOW_SNPS sites, call windows with at least MIN_WINDOW_NPA nonparental alleles hot, merge them and compute a Poisson p-value against the trio's own background.

Expected workflow:

1. Call `run_skill_script` with the skill name 03_npa_scan and the resource 03_npa_scan.sh, setting `return_output` to false so the script output is not returned.
2. Read `results/03_npa_scan.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/03_npa_scan.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

This reads every record in the scan range for all 3,000+ samples and is long-running (tens of minutes to a few hours for chr3 to 77 Mb).

Outputs:

results/03_npa_scan.json
npa/chr<N>/npa_per_trio.tsv, npa_regions.tsv, npa_region_events.tsv

If it fails:

- 0 records read: wrong contig or SCAN_START/SCAN_END.
- no trio has all members in the VCF: rerun 02.
