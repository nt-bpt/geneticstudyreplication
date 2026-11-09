---
name: 07-compare-studies
description: compare the sample's genotypes with what Paper 1 and Paper 2 reported, with population context
---

#  07-compare-studies Skill

SKILL 07 — Paper 1: classify the rs117910193 genotype (direct, or inferred from the proxy when 03-resolve-proxy resolved it) against the study's pattern (all 13 cases G/G, 7 of 9 controls G/A), and add Hardy–Weinberg population expectations from gnomAD. Paper 2: list the genotype at each of the 212 sites. No score is produced, because the paper gives no allele direction.

Expected workflow:

1. Call `run_skill_script` with the skill name 07-compare-studies and the resource 07-compare-studies.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/07-compare-studies.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/07-compare-studies.log`.
   - `metrics.paper1.class` is GG, GA, AA, another genotype, or NOT_AVAILABLE. `metrics.paper2.n_called` counts usable Paper 2 sites.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

Outputs:

- `results/07-compare-studies.json` (`metrics.paper1`, `metrics.paper2`), `results/07-p2-genotypes.tsv`.

Fixes for FAIL:

- `results/05-genotypes-array.tsv missing` or `results/06-genotypes-sequence.tsv missing`: run the genotyping skill that matches the input type.
- A WARN with `Paper 1 could not be checked` is a valid outcome. Report it plainly; do not guess the genotype.

General expectations:

- Run the skills in order: 00-check-env, 01-detect-input, 02-prepare-panels, 03-resolve-proxy, 04-align-fastq, 05-genotype-array, 06-genotype-sequence, 07-compare-studies, 08-report. Skills that do not apply to the input type finish as SKIPPED; that is normal.
- All paths in these instructions are inside your workspace, `repo/`. All settings live in `config/run-config.json`; change behaviour only by editing that file. Relative paths in it are relative to `repo/`, so `../name` means a folder next to `repo/` that only the scripts can reach.
- Report numbers exactly as they appear in the result JSON and TSV files. Do not recompute, round differently or fill in values that are missing.
- These studies are small and unreplicated. Never describe a genotype as evidence of psychic ability, a risk, a talent or a prediction. Paper 2 has no allele direction, so never say a Paper 2 genotype is "high" or "low".
- Large files (alignments, indexes, downloads) go in `work_dir` (default `../psi-work`, beside `repo/`), which you do not need to read. Everything you need is under `results/`, `logs/`, `panels/` and `config/`.
