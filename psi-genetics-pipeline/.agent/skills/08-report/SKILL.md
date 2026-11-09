---
name: 08-report
description: write the user-facing markdown report comparing the sample with both psi-genetics studies
---

#  08-report Skill

SKILL 08 — Write `results/psi-genetics-user-report.md` from the earlier results: a clear statement that the report does not measure psychic ability, the Paper 1 genotype with the study pattern, population context and the study's weaknesses, the Paper 2 top-20 table with coverage and the reason no score exists, and every skill's status and warnings.

Expected workflow:

1. Call `run_skill_script` with the skill name 08-report and the resource 08-report.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/08-report.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/08-report.log`.
   - Give the user the report file. Summarise it in a few sentences using its own wording; do not add interpretation beyond it.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

Outputs:

- `results/psi-genetics-user-report.md`.

Fixes for FAIL:

- `07-compare-studies has not been run` or FAIL: run it first.
- If the report looks wrong, fix the upstream skill and re-run from there; do not edit the report by hand.

General expectations:

- Run the skills in order: 00-check-env, 01-detect-input, 02-prepare-panels, 03-resolve-proxy, 04-align-fastq, 05-genotype-array, 06-genotype-sequence, 07-compare-studies, 08-report. Skills that do not apply to the input type finish as SKIPPED; that is normal.
- All paths in these instructions are inside your workspace, `repo/`. All settings live in `config/run-config.json`; change behaviour only by editing that file. Relative paths in it are relative to `repo/`, so `../name` means a folder next to `repo/` that only the scripts can reach.
- Report numbers exactly as they appear in the result JSON and TSV files. Do not recompute, round differently or fill in values that are missing.
- These studies are small and unreplicated. Never describe a genotype as evidence of psychic ability, a risk, a talent or a prediction. Paper 2 has no allele direction, so never say a Paper 2 genotype is "high" or "low".
- Large files (alignments, indexes, downloads) go in `work_dir` (default `../psi-work`, beside `repo/`), which you do not need to read. Everything you need is under `results/`, `logs/`, `panels/` and `config/`.
