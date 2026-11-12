# Psi-genetics genotype check

Checks one person's DNA data against the sites reported in two IONS studies:

| Study | What is checked | Possible from |
|---|---|---|
| Paper 1 — Wahbeh et al. 2021, *EXPLORE*, doi:10.1016/j.explore.2021.02.014 | rs117910193 (TNRC18), G>A. All 13 cases G/G; 7 of 9 controls G/A. | CRAM, BAM, FASTQ, VCF/gVCF; arrays only if the rsID or its proxy rs78262442 is on the chip |
| Paper 2 — Wahbeh et al. 2026, *EXPLORE*, doi:10.1016/j.explore.2026.103416 | Genotype at each of 212 rsIDs. **Lookup only — no score**, because the paper gives no allele direction. | All inputs (sequence inputs need coordinates from 02-prepare-panels) |

The output is `results/psi-genetics-user-report.md`. It reports genotypes beside what the studies found; it does not measure psychic ability.

## Layout

```
<root>/
├── AGENTS.md                instructions for the agent
├── .agent/                  scripts; run by the framework, not visible to the agent
│   ├── lib/psi-common.py
│   └── skills/<skill>/      SKILL.md, <skill>.sh, <skill>.py
└── repo/                    the agent's workspace
    ├── PIPELINE.md
    ├── config/run-config.json
    ├── input/               small input files
    ├── research/            source research report
    ├── panels/              created by 02 (panels, caches)
    ├── results/             created by the skills
    └── logs/                created by the skills
```

Large working files go in `work_dir` (default `../psi-work`, created next to `repo/`), which the agent never needs to read.

## Skills (run in order)

| Skill | Runs for | Does |
|---|---|---|
| 00-check-env | all | tools, Python, config, reference, disk space |
| 01-detect-input | all | input type, build, chr naming, indexes |
| 02-prepare-panels | all | study panels; Paper 2 coordinates via Ensembl (cached) |
| 03-resolve-proxy | arrays missing rs117910193 | proxy allele pairing from 1000 Genomes EUR haplotypes |
| 04-align-fastq | FASTQ | bwa-mem2/bwa alignment, markdup, index |
| 05-genotype-array | arrays | genotypes from 23andMe / AncestryDNA / MyHeritage files |
| 06-genotype-sequence | CRAM, BAM, FASTQ, VCF | forced genotyping at panel sites with read depth |
| 07-compare-studies | all | compare with both studies |
| 08-report | all | user report |

Each skill writes `results/<skill>.json` (`status`, `verdict`, `metrics`, `warnings`, `outputs`) and `logs/<skill>.log`. Skills that do not apply finish as SKIPPED.

## Setup

1. Tools: python3 ≥ 3.8 (standard library only), bcftools ≥ 1.10, samtools, htslib (tabix, bgzip), curl. For FASTQ also bwa-mem2 or bwa, plus an aligner index of the reference.
2. Edit `config/run-config.json`:
   - `input.path` — the raw file. Arrays can be dropped in `input/`. Large files can stay where they are (absolute path, or `../<folder>/<file>` beside `repo/`).
   - `reference.GRCh37` / `reference.GRCh38` — FASTA with `.fai`. Required for CRAM (must be the FASTA the CRAM was made with), BAM and FASTQ.
   - `work_dir` — scratch space for alignments and indexes (default `../psi-work`, beside `repo/`).
   - `align_build` — build to align FASTQ to.
   - `build_override` — only if the build cannot be read from the file.
   - `network` — set false to forbid lookups; then supply `panels/p2-coords-manual.tsv` and the local 1000 Genomes paths.
3. Network hosts used: rest.ensembl.org and grch37.rest.ensembl.org (02), ftp.1000genomes.ebi.ac.uk (03). Results are cached, so later runs work offline.

## Known limits

- Paper 1's original calls came from exome data at an intron edge; the paper's control group is unusual (7/9 carriers at a ~10% allele frequency). See the report text.
- Paper 2's build, strand, genotype encoding and allele direction were never published. Arrays are matched by rsID; strand is checked only where Ensembl alleles are available.
- A plain (non-g) VCF cannot show homozygous-reference sites; those are reported as NOT_IN_VCF.
- The research report behind these panels is `research/psi-genetics-report.md`.
