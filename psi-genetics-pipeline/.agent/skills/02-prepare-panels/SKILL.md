---
name: 02-prepare-panels
description: build the Paper 1 (TNRC18) and Paper 2 (212 SNP) site panels and resolve Paper 2 rsIDs to GRCh37/GRCh38 coordinates
---

#  02-prepare-panels Skill

SKILL 02 — Write the study panels to `panels/`. Paper 1 (rs117910193 and its LD proxy rs78262442) ships with verified coordinates for both builds. The 212 Paper 2 rsIDs are resolved through the Ensembl REST API and cached in `panels/cache/`; a manual file `panels/p2-coords-manual.tsv` (columns rsid, build, chrom, pos, ref, alt) overrides the lookup.

Expected workflow:

1. Call `run_skill_script` with the skill name 02-prepare-panels and the resource 02-prepare-panels.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/02-prepare-panels.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/02-prepare-panels.log`.
   - Arrays only need rsIDs. For VCF/BAM/CRAM/FASTQ, check `metrics.p2_with_GRCh37` / `p2_with_GRCh38` for the input build; sites without coordinates are reported as NO_COORDS.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

Outputs:

- `panels/p1-tnrc18.json`, `panels/p2-212-snps.tsv` (with coordinates), `panels/p2-study.json`, `panels/cache/p2-coords-<build>.json`.

Fixes for FAIL:

- `bundled P2 list has N rows`: the skill's bundled resource file was changed. Ask the user to reinstall the 02-prepare-panels skill folder.
- `01-detect-input has not been run` or its status is FAIL: run 01-detect-input first.
- Ensembl lookups failing is a WARN, not a FAIL. If the user's network blocks rest.ensembl.org, either allow it, set `network` to false and supply `panels/p2-coords-manual.tsv`, or accept that Paper 2 is checked only for array input.

General expectations:

- Run the skills in order: 00-check-env, 01-detect-input, 02-prepare-panels, 03-resolve-proxy, 04-align-fastq, 05-genotype-array, 06-genotype-sequence, 07-compare-studies, 08-report. Skills that do not apply to the input type finish as SKIPPED; that is normal.
- All paths in these instructions are inside your workspace, `repo/`. All settings live in `config/run-config.json`; change behaviour only by editing that file. Relative paths in it are relative to `repo/`, so `../name` means a folder next to `repo/` that only the scripts can reach.
- Report numbers exactly as they appear in the result JSON and TSV files. Do not recompute, round differently or fill in values that are missing.
- These studies are small and unreplicated. Never describe a genotype as evidence of psychic ability, a risk, a talent or a prediction. Paper 2 has no allele direction, so never say a Paper 2 genotype is "high" or "low".
- Large files (alignments, indexes, downloads) go in `work_dir` (default `../psi-work`, beside `repo/`), which you do not need to read. Everything you need is under `results/`, `logs/`, `panels/` and `config/`.
