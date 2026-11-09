---
name: 00-check-env
description: verify tools, python version, config, reference files and disk space for the psi-genetics genotype check
---

#  00-check-env Skill

SKILL 00 — Check python3 (3.8+), bcftools (1.10+), samtools, tabix, bgzip and curl; bwa-mem2 or bwa when the input is FASTQ; that `config/run-config.json` exists and `input.path` points to a file; that a reference FASTA is configured for CRAM, BAM or FASTQ input; and that `work_dir` has enough free space for the input type.

Expected workflow:

1. Call `run_skill_script` with the skill name 00-check-env and the resource 00-check-env.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/00-check-env.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/00-check-env.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

Outputs:

- `results/00-check-env.json` — `metrics.tools` (versions), `metrics.disk`, `metrics.references`, `metrics.input_type_guess`.

Fixes for FAIL:

- `config/run-config.json did not exist`: a default config was written. Set `input.path` (and `reference.GRCh37` / `reference.GRCh38` for CRAM, BAM or FASTQ), then re-run.
- `missing tool: X`: ask the user to install it (for example `apt install bcftools samtools tabix` or `conda install -c bioconda bcftools samtools htslib bwa-mem2`). You cannot install system tools yourself.
- `input file not found`: correct `input.path`. A small array file can go in `input/`; large CRAM/FASTQ files can stay where they are, given as an absolute path or as `../<folder>/<file>` beside `repo/`.
- `no reference FASTA configured`: set the matching `reference.GRCh37` or `reference.GRCh38` path. CRAM files can only be read with the exact FASTA they were compressed against.
- `not enough free space`: point `work_dir` at a larger disk, or free space.

General expectations:

- Run the skills in order: 00-check-env, 01-detect-input, 02-prepare-panels, 03-resolve-proxy, 04-align-fastq, 05-genotype-array, 06-genotype-sequence, 07-compare-studies, 08-report. Skills that do not apply to the input type finish as SKIPPED; that is normal.
- All paths in these instructions are inside your workspace, `repo/`. All settings live in `config/run-config.json`; change behaviour only by editing that file. Relative paths in it are relative to `repo/`, so `../name` means a folder next to `repo/` that only the scripts can reach.
- Report numbers exactly as they appear in the result JSON and TSV files. Do not recompute, round differently or fill in values that are missing.
- These studies are small and unreplicated. Never describe a genotype as evidence of psychic ability, a risk, a talent or a prediction. Paper 2 has no allele direction, so never say a Paper 2 genotype is "high" or "low".
- Large files (alignments, indexes, downloads) go in `work_dir` (default `../psi-work`, beside `repo/`), which you do not need to read. Everything you need is under `results/`, `logs/`, `panels/` and `config/`.
