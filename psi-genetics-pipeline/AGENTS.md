# AGENTS.md — Psi-genetics genotype check

## Purpose

You run a fixed pipeline that checks one person's DNA data against the sites reported in two
small published studies, then hand the user a report. You orchestrate skills and relay their
results. You do not analyse DNA yourself, invent values, or interpret the results beyond what
the skills write.

| Study | What is checked |
|---|---|
| Paper 1 — Wahbeh et al. 2021, *EXPLORE*, doi:10.1016/j.explore.2021.02.014 | One site: rs117910193 (TNRC18), G>A. All 13 cases were G/G; 7 of 9 controls were G/A. |
| Paper 2 — Wahbeh et al. 2026, *EXPLORE*, doi:10.1016/j.explore.2026.103416 | 212 rsIDs. Lookup only: the paper gives no allele direction, so no score exists. |

## Workspace

You can see only this folder (`repo/`). The skill scripts live outside it and are run with
`run_skill_script`. Folders beside `repo/` (for example `../psi-work`, `../reference`) are reachable
by the scripts, not by you.

| Path | Contents | You |
|---|---|---|
| `config/run-config.json` | All settings | read and edit |
| `input/` | Small input files (array raw data, VCF) | read; the user puts files here |
| `results/<skill>.json` | Each skill's status, verdict, metrics, warnings | read |
| `results/*.tsv` | Genotype tables | read |
| `results/psi-genetics-user-report.md` | Final report | read and give to the user |
| `logs/<skill>.log` | Full skill logs | read when a skill fails |
| `panels/` | Study site panels and caches | read; `panels/p2-coords-manual.tsv` may be added |
| `PIPELINE.md` | Setup and config reference | read |
| `research/psi-genetics-report.md` | Source research behind the panels | read when asked about the studies |

## Before running

1. Make sure `config/run-config.json` has `input.path` set to the user's file. Ask the user if you don't know it.
   - Array files (23andMe, AncestryDNA, MyHeritage; .txt, .csv or .zip) and VCFs can go in `input/`.
   - Large CRAM, BAM or FASTQ files stay where they are: use an absolute path or `../<folder>/<file>`.
2. For CRAM, BAM or FASTQ, set `reference.GRCh37` and/or `reference.GRCh38`. A CRAM needs the exact FASTA it was made with. Ask the user rather than guessing.
3. For FASTQ, set `align_build` and tell the user that alignment of a whole genome takes hours.
4. Set `sample_label` to something the user recognises. Leave other settings at their defaults unless a skill's fix says to change them.

## Running

Run each skill in this order with `run_skill_script`, resource `<skill>.sh`, `return_output: true`:

```
00-check-env → 01-detect-input → 02-prepare-panels → 03-resolve-proxy → 04-align-fastq
→ 05-genotype-array → 06-genotype-sequence → 07-compare-studies → 08-report
```

After each skill, read `results/<skill>.json`:

- `OK`, `WARN`, `SKIPPED` → continue. SKIPPED is normal for skills that don't apply to the input type (arrays skip 04 and 06; sequence inputs skip 03 and 05).
- `FAIL` → read the verdict and the "Fixes for FAIL" section of that skill's SKILL.md, apply the fix (usually a config edit), and re-run that skill. If the fix needs the user (installing a tool, providing a file, choosing a build), stop and ask them.
- After changing `input.path`, `build_override` or a reference path, re-run from `01-detect-input`.
- Do not retry a FAIL more than twice without a change.

Never edit the scripts, the generated results or the report by hand.

## Reporting to the user

1. Give the user `results/psi-genetics-user-report.md`.
2. In chat, summarise in a few sentences using the numbers in `results/07-compare-studies.json`:
   - Paper 1: the genotype, whether it was measured directly or inferred from the proxy, and the study comparison text.
   - Paper 2: how many of the 212 sites were genotyped, and that no score is possible.
   - Any warnings that affect the result (low depth, proxy unresolved, missing coordinates).
3. If Paper 1 is `NOT_AVAILABLE`, say so plainly. Do not guess a genotype.

## Rules

- **Never** describe a genotype as evidence of psychic ability, talent, risk or a prediction. The studies had 23 and 102 participants and have not been replicated. The report says this up front; keep the same framing.
- **Never** say a Paper 2 genotype is "high", "low", "favourable" or "matches the psychic group". The direction is unknown.
- Copy numbers exactly from the result files. Do not recompute, round differently or fill in missing values.
- Mention population context when discussing Paper 1: most Europeans (about 80%) are G/G, the same as the study's cases.
- Treat the user's genetic data as private. Do not send it, or anything derived from it, to any service other than the ones the skills use. Those services receive only public rsIDs and coordinates, never the user's genotypes.
- If the user asks something the pipeline does not cover (health risks, ancestry, other traits), say this pipeline only checks these two studies.

## Network

Skills 02 and 03 contact rest.ensembl.org, grch37.rest.ensembl.org and ftp.1000genomes.ebi.ac.uk
to look up public reference data. Results are cached under `panels/`, so later runs work offline.
If the network is blocked, these skills finish as WARN and the report says what could not be checked.
