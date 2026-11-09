---
name: 01-detect-input
description: identify the input type (23andMe/AncestryDNA array, VCF/gVCF, BAM, CRAM, FASTQ), genome build, chromosome naming and indexes
---

#  01-detect-input Skill

SKILL 01 — Inspect `input.path` and decide the input type, vendor (for arrays), genome build (from contig lengths, the array header or `build_override`), whether chromosomes are named `chr7` or `7`, whether an index exists, and which reference FASTA matches. For FASTQ it also finds the R2 file.

Expected workflow:

1. Call `run_skill_script` with the skill name 01-detect-input and the resource 01-detect-input.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/01-detect-input.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/01-detect-input.log`.
   - Note `metrics.input_type` and `metrics.build`; later skills depend on them.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

Outputs:

- `results/01-detect-input.json` — `metrics.input_type`, `vendor`, `build`, `build_evidence`, `chrom_prefix`, `index`, `reference`, `is_gvcf`.

Fixes for FAIL:

- `could not identify input type`: set `input.type` to one of `array`, `vcf`, `bam`, `cram`, `fastq`.
- `could not tell the build`: the header has no GRCh37/GRCh38 contig lengths. Set `build_override` to `GRCh37` or `GRCh38` (ask the user which reference their file was made with).
- `CRAM input needs reference.<build>`: set that reference path to the FASTA used to make the CRAM.
- `chr prefix` mismatch or `chr7 length differs`: the reference FASTA does not match the input. Ask the user for the correct reference.
- `array file has no genotype rows`: the file is not a raw-data export. Ask the user to download the raw data file (23andMe: Settings > 23andMe Data > Download; AncestryDNA: Settings > Download DNA data). Zip files are fine.
- `FASTQ input needs reference.<build>`: set the reference for `align_build`.

General expectations:

- Run the skills in order: 00-check-env, 01-detect-input, 02-prepare-panels, 03-resolve-proxy, 04-align-fastq, 05-genotype-array, 06-genotype-sequence, 07-compare-studies, 08-report. Skills that do not apply to the input type finish as SKIPPED; that is normal.
- All paths in these instructions are inside your workspace, `repo/`. All settings live in `config/run-config.json`; change behaviour only by editing that file. Relative paths in it are relative to `repo/`, so `../name` means a folder next to `repo/` that only the scripts can reach.
- Report numbers exactly as they appear in the result JSON and TSV files. Do not recompute, round differently or fill in values that are missing.
- These studies are small and unreplicated. Never describe a genotype as evidence of psychic ability, a risk, a talent or a prediction. Paper 2 has no allele direction, so never say a Paper 2 genotype is "high" or "low".
- Large files (alignments, indexes, downloads) go in `work_dir` (default `../psi-work`, beside `repo/`), which you do not need to read. Everything you need is under `results/`, `logs/`, `panels/` and `config/`.
