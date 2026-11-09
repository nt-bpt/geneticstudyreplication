---
name: 07_rempel_method
description: re-run the preprint's own published method (fixed 60 kb windows, any record type) on the same VCF
---

#  07_rempel_method Skill

SKILL 07 — Re-run the method exactly as it is written in the author's published code (github.com/maxrempel/xg1-2024), not my own definition. An NPA is any VCF record (SNV, indel or SV) where the child's two alleles are not both among the parents' four alleles. Windows are fixed 60,000 bp long with a 20,000 bp step (the code assumes 1,000 bp per "SNP"), kept at 5 or more NPAs. Families are classed by their largest window: under 10 normal, 10-19 possible hybrid, 20 or more definite hybrid. Overlapping windows are collapsed with the author's 50 kb rule, and the skill also reports the number of UNIQUE NPA records in each collapsed region next to the summed window counts.

Expected workflow:

1. Call `run_skill_script` with the skill name 07_rempel_method and the resource 07_rempel_method.sh, setting `return_output` to true so the classification table and the focus-window regions come back to you.
2. Read `results/07_rempel_method.json` for the verdict and metrics. The full text is in `results/07_rempel_method.txt`.
3. Compare the classification with the paper's (570 normal / 7 possible / 4 definite of 581) and report both numbers.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

It reads every record in the scan range for all samples, so it takes as long as skill 03 (tens of minutes to a few hours). It can run any time after skill 02.

Outputs:

results/07_rempel_method.json
results/07_rempel_method.txt
npa/chr<N>/rempel_families.tsv, rempel_regions.tsv, rempel_windows.tsv

If it fails:

- no trio has all three members in the VCF: rerun skill 02.
- 0 records read: wrong contig or SCAN_START/SCAN_END.
