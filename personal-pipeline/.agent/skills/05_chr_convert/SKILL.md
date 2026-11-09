---
name: 05_chr_convert
description: convert chromosome 3 names between chr3, 3, CM000665.2 and NC_000003.12 in names, regions, VCF, BAM, FASTA and BED
---

#  05_chr_convert Skill

SKILL 05 — Utility (not a pipeline step): detect what a file calls chromosome 3 and convert names or whole files between the four spellings.

Expected workflow:

1. Call `run_skill_script` with the skill name 05_chr_convert and the resource 05_chr_convert.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/05_chr_convert.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/05_chr_convert.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

This skill finishes in seconds to a few minutes.
The script takes a subcommand and arguments. Pass them as the script arguments in `run_skill_script`:

  aliases                                       list the four spellings
  detect FILE                                   what does this BAM/CRAM/VCF/FASTA call chr3?
  name NAME --to STYLE                          chr3 -> CM000665.2
  region chr3:75440000-75600000 --to genbank    -> CM000665.2:75440000-75600000
  vcf IN.vcf.gz OUT.vcf.gz --to STYLE
  bam IN.{bam,cram} OUT.bam --to STYLE [--region R] [--reference FASTA]
  fasta IN.fa OUT.fa --to STYLE
  bed IN.bed OUT.bed --to STYLE

STYLE is ucsc (chr3), ensembl (3), genbank (CM000665.2) or refseq (NC_000003.12). If your tool cannot pass arguments, run the script from a shell instead.
This skill does not write a results JSON; read the printed output (hence `return_output` true).

Outputs:

the converted file or printed name

If it fails:

- 'unknown style': use ucsc, ensembl, genbank or refseq.
- BAM header conversion needs samtools; VCF conversion needs bcftools.
