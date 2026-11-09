---
name: 04-align-fastq
description: align FASTQ reads to the configured reference with bwa-mem2 or bwa, mark duplicates and index the BAM
---

#  04-align-fastq Skill

SKILL 04 — FASTQ input only. Aligns R1 (and R2) to `reference.<align_build>`, runs samtools fixmate, sort and markdup, indexes the BAM, and records flagstat numbers. Output goes to `work_dir`. A finished alignment with the same inputs is reused, so re-running is cheap. Skipped for all other inputs.

Expected workflow:

1. Call `run_skill_script` with the skill name 04-align-fastq and the resource 04-align-fastq.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/04-align-fastq.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/04-align-fastq.log`.
   - A 30x genome takes several hours with 8+ threads. Tell the user before starting, and raise `threads` in the config if the machine allows.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

Outputs:

- `<work_dir>/<label>.<build>.bam` and `.bai`; `metrics.total_reads`, `mapped`, `duplicates`.

Fixes for FAIL:

- `index ... is missing`: the aligner index for the reference does not exist. Either ask the user to run `bwa-mem2 index <ref>` (about 1 hour, ~64 GB RAM) or `bwa index <ref>`, or set `build_aligner_index` to true and re-run.
- `no aligner found`: ask the user to install bwa-mem2 or bwa.
- `command failed` during alignment: read `logs/04-align-fastq.log`. Common causes are running out of disk in `work_dir` (move it) or out of memory (lower `threads`).

General expectations:

- Run the skills in order: 00-check-env, 01-detect-input, 02-prepare-panels, 03-resolve-proxy, 04-align-fastq, 05-genotype-array, 06-genotype-sequence, 07-compare-studies, 08-report. Skills that do not apply to the input type finish as SKIPPED; that is normal.
- All paths in these instructions are inside your workspace, `repo/`. All settings live in `config/run-config.json`; change behaviour only by editing that file. Relative paths in it are relative to `repo/`, so `../name` means a folder next to `repo/` that only the scripts can reach.
- Report numbers exactly as they appear in the result JSON and TSV files. Do not recompute, round differently or fill in values that are missing.
- These studies are small and unreplicated. Never describe a genotype as evidence of psychic ability, a risk, a talent or a prediction. Paper 2 has no allele direction, so never say a Paper 2 genotype is "high" or "low".
- Large files (alignments, indexes, downloads) go in `work_dir` (default `../psi-work`, beside `repo/`), which you do not need to read. Everything you need is under `results/`, `logs/`, `panels/` and `config/`.
