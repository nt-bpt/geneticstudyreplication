---
name: 05-genotype-array
description: extract genotypes at the Paper 1 and Paper 2 rsIDs from a 23andMe, AncestryDNA or MyHeritage/FTDNA raw data file
---

#  05-genotype-array Skill

SKILL 05 — Array input only. Streams the raw file (plain, .gz or .zip), pulls out every panel rsID, converts no-calls and indel codes, and checks alleles against the panel (complementing minus-strand calls when that is unambiguous). Skipped for sequence input.

Expected workflow:

1. Call `run_skill_script` with the skill name 05-genotype-array and the resource 05-genotype-array.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/05-genotype-array.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/05-genotype-array.log`.
   - `metrics.p1_target_status` / `p1_proxy_status` say whether Paper 1 can be checked. `p2_called` counts the Paper 2 sites found.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

Outputs:

- `results/05-genotypes-array.tsv` — one row per panel site: study, rsid, genotype, status (CALLED, NO_CALL, NOT_ON_CHIP), strand_check.

Fixes for FAIL:

- `none of the 212 Paper 2 rsIDs were found`: the file is not a supported raw-data export, or it was truncated. Ask the user for the full raw-data download.
- `05-genotype-array` FAILs if 02-prepare-panels has not run; run it first.

General expectations:

- Run the skills in order: 00-check-env, 01-detect-input, 02-prepare-panels, 03-resolve-proxy, 04-align-fastq, 05-genotype-array, 06-genotype-sequence, 07-compare-studies, 08-report. Skills that do not apply to the input type finish as SKIPPED; that is normal.
- All paths in these instructions are inside your workspace, `repo/`. All settings live in `config/run-config.json`; change behaviour only by editing that file. Relative paths in it are relative to `repo/`, so `../name` means a folder next to `repo/` that only the scripts can reach.
- Report numbers exactly as they appear in the result JSON and TSV files. Do not recompute, round differently or fill in values that are missing.
- These studies are small and unreplicated. Never describe a genotype as evidence of psychic ability, a risk, a talent or a prediction. Paper 2 has no allele direction, so never say a Paper 2 genotype is "high" or "low".
- Large files (alignments, indexes, downloads) go in `work_dir` (default `../psi-work`, beside `repo/`), which you do not need to read. Everything you need is under `results/`, `logs/`, `panels/` and `config/`.
