---
name: 06-genotype-sequence
description: force-genotype the Paper 1 and Paper 2 sites from a BAM, CRAM or aligned FASTQ, or read them from a VCF/gVCF
---

#  06-genotype-sequence Skill

SKILL 06 — Sequence input only. For BAM/CRAM (including the BAM from 04-align-fastq) it checks the panel reference bases against the FASTA, then runs `bcftools mpileup` on just the panel sites and `bcftools call -m -C alleles`, so homozygous-reference sites get an explicit call and a read depth. For VCF/gVCF it looks the sites up; in a plain VCF an absent site is reported as NOT_IN_VCF because it cannot be assumed to be reference. Skipped for array input.

Expected workflow:

1. Call `run_skill_script` with the skill name 06-genotype-sequence and the resource 06-genotype-sequence.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/06-genotype-sequence.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/06-genotype-sequence.log`.
   - Check `metrics.p1_status` and `p1_depth`. Calls below `min_depth` (default 10, the threshold the 2021 study used) are kept but marked LOW_DEPTH.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

Outputs:

- `results/06-genotypes-sequence.tsv` — one row per panel site: genotype, status (CALLED, LOW_DEPTH, NO_COVERAGE, NOT_IN_VCF, NO_COORDS, REF_MISMATCH, OVERLAPPING_VARIANT), depth, allele depths.

Fixes for FAIL:

- `panel REF alleles disagree with the reference FASTA`: the input is not the build in `metrics.build`. Set `build_override` correctly or fix the reference path, then re-run from 01-detect-input.
- `reference.<build> is required`: set the reference FASTA for that build.
- `samtools faidx could not read the panel positions`: chromosome names in the reference do not match (for example `chr7` vs `7`). Use a matching reference.
- Index creation failing: the input is unsorted or corrupt. Ask the user for a coordinate-sorted BAM/CRAM.

General expectations:

- Run the skills in order: 00-check-env, 01-detect-input, 02-prepare-panels, 03-resolve-proxy, 04-align-fastq, 05-genotype-array, 06-genotype-sequence, 07-compare-studies, 08-report. Skills that do not apply to the input type finish as SKIPPED; that is normal.
- All paths in these instructions are inside your workspace, `repo/`. All settings live in `config/run-config.json`; change behaviour only by editing that file. Relative paths in it are relative to `repo/`, so `../name` means a folder next to `repo/` that only the scripts can reach.
- Report numbers exactly as they appear in the result JSON and TSV files. Do not recompute, round differently or fill in values that are missing.
- These studies are small and unreplicated. Never describe a genotype as evidence of psychic ability, a risk, a talent or a prediction. Paper 2 has no allele direction, so never say a Paper 2 genotype is "high" or "low".
- Large files (alignments, indexes, downloads) go in `work_dir` (default `../psi-work`, beside `repo/`), which you do not need to read. Everything you need is under `results/`, `logs/`, `panels/` and `config/`.
