---
name: 03-resolve-proxy
description: work out which rs78262442 allele travels with each rs117910193 allele, using phased 1000 Genomes EUR haplotypes
---

#  03-resolve-proxy Skill

SKILL 03 — Only for array files that contain the proxy rs78262442 but not rs117910193 itself. Reads phased 1000 Genomes phase 3 genotypes for the two positions (remote tabix, or local files set in `kg_phase3_chr7_vcf` and `kg_phase3_panel`) and writes the allele pairing to `panels/p1-proxy-pairing.json`. Skipped for all other inputs.

Expected workflow:

1. Call `run_skill_script` with the skill name 03-resolve-proxy and the resource 03-resolve-proxy.sh, setting `return_output` to true so the script output (including any errors) comes back to you.
2. Read `results/03-resolve-proxy.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/03-resolve-proxy.log`.
   - A WARN means the proxy cannot be used; Paper 1 will then be NOT_AVAILABLE for this array, which is an honest result, not an error.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

Outputs:

- `panels/p1-proxy-pairing.json` — `map_proxy_to_target`, concordance, computed r², haplotype counts.

Fixes for FAIL:

- `1000 Genomes reference alleles do not match the panel`: the local `kg_phase3_chr7_vcf` is not the GRCh37 phase 3 file. Point it at `ALL.chr7.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz` (with its .tbi).
- Network failures are WARN: allow ftp.1000genomes.ebi.ac.uk, or download the chr7 VCF, its .tbi and `integrated_call_samples_v3.20130502.ALL.panel` and set the two config paths.
- To redo the pairing, delete `panels/p1-proxy-pairing.json` and re-run.

General expectations:

- Run the skills in order: 00-check-env, 01-detect-input, 02-prepare-panels, 03-resolve-proxy, 04-align-fastq, 05-genotype-array, 06-genotype-sequence, 07-compare-studies, 08-report. Skills that do not apply to the input type finish as SKIPPED; that is normal.
- All paths in these instructions are inside your workspace, `repo/`. All settings live in `config/run-config.json`; change behaviour only by editing that file. Relative paths in it are relative to `repo/`, so `../name` means a folder next to `repo/` that only the scripts can reach.
- Report numbers exactly as they appear in the result JSON and TSV files. Do not recompute, round differently or fill in values that are missing.
- These studies are small and unreplicated. Never describe a genotype as evidence of psychic ability, a risk, a talent or a prediction. Paper 2 has no allele direction, so never say a Paper 2 genotype is "high" or "low".
- Large files (alignments, indexes, downloads) go in `work_dir` (default `../psi-work`, beside `repo/`), which you do not need to read. Everything you need is under `results/`, `logs/`, `panels/` and `config/`.
