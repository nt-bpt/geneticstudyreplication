---
name: 06_call_variants
description: call variants in the control and extended hotspot windows with bcftools
---

#  06_call_variants Skill

SKILL 06 — Call variants with bcftools mpileup/call, normalise and filter. The calling FASTA is rebuilt so its chr3 name matches the BAM exactly (the cause of the earlier 'sequence CM000665.2 was not found' error). Set OUTPUT_CHR_STYLE to also write a copy of the VCF with another chr3 spelling.

Expected workflow:

1. Call `run_skill_script` with the skill name 06_call_variants and the resource 06_call_variants.sh, setting `return_output` to false so the script output is not returned.
2. Read `results/06_call_variants.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/06_call_variants.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

Calling the 4 Mb extended window at high depth can take from several minutes to an hour. Maximum depth is raised to 10000 so deep regions are not silently capped.

Outputs:

results/06_call_variants.json
vcf/calls.vcf.gz  <- CALLS_VCF in state.env
results/06_primary_variants.tsv  <- every call in the primary hotspot

If it fails:

- 'BAM and reference disagree on chr3 length': different assembly; stop and report.
- no variants in the extended window: check depth and that region.bam has reads.
