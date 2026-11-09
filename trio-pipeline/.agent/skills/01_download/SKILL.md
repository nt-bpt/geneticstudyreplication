---
name: 01_download
description: download and verify the 1000 Genomes phased VCF, pedigree and population table
---

#  01_download Skill

SKILL 01 — Fetch the phased VCF and index for CHROM, the pedigree and the population table; verify tabix can read the file and find the contig name used inside it ('3' or 'chr3').

Expected workflow:

1. Call `run_skill_script` with the skill name 01_download and the resource 01_download.sh, setting `return_output` to false so the script output is not returned.
2. Read `results/01_download.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/01_download.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

A phased VCF for one chromosome is several GB; the download is resumable, so rerun after an interruption. If the shell has no internet, download the files in a browser into one folder and set MANUAL_DIR to it (same file names).

Outputs:

results/01_download.json
data/  <- VCF, .tbi, pedigree.txt, population.txt, vcf_samples.txt
state.env  <- VCF_PATH_<chrom>, VCF_CONTIG_<chrom>

If it fails:

- not reachable: use MANUAL_DIR.
- 'tabix cannot read': truncated download; delete the file and rerun.
- pedigree is an HTML page: the URL is blocked or wrong.
