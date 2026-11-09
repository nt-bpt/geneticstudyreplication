# AGENT.md — Personal hotspot check (CRAM / BAM / FASTQ)


## How skills are called
Each skill is a folder under `.agent/skills/<name>/` with a `SKILL.md` and one script. Run a skill with the `run_skill_script` tool: skill name = folder name, resource = `<name>.sh`. The tool runs from the process folder, one level above your workspace. Read the skill's `SKILL.md` first for its expected workflow, then `results/<name>.json` after it finishes. 
**Your world is the workspace folder.** You can see `lib/`, `py/`, `resources/`, `run_all.sh` and everything the skills produce (`data/`, `bam/`, `vcf/`, `ref/`, `results/`, `logs/`, `tmp/`, `state.env`). You cannot see `config.env` or `.agent/`: settings are changed by the user, so when a skill's failure fix says to change a setting, tell the user which one and why. All paths in this file and in the SKILL.md files are relative to your workspace folder.

## Your job
Check whether ONE person's genome looks unusual at a region of chromosome 3 (GRCh38) that a preprint (Rempel 2025)
flagged in 1000 Genomes trios. You run skills in order, read their result files, and report what they say.
You do not theorise about causes. You never invent numbers: every number you report must come from a
`results/*.json` or `results/*.tsv` file.

## Rules
1. Run skills with the `run_skill_script` tool (see above).
2. After EVERY skill read `results/<skill>.json`. Its `status` is one of:
   `OK` (continue) · `WARN` (continue, but tell the user each line in `warnings`) · `FAIL` (stop) · `SKIPPED` (fine).
3. On `FAIL`: read `verdict` and the last lines of `logs/<skill>.log`, tell the user the cause in plain words,
   apply the fix table below if it matches, otherwise STOP and ask. Do not edit the scripts. Do not retry blindly.
4. Never delete anything in your workspace; skills reuse earlier work (set `FORCE=1` only to redo an alignment on purpose).
5. `config.env` belongs to the user and is outside your workspace. Never try to read around that; ask the user for values you need.
6. Without parental DNA nothing here can test inheritance. Never say a result supports or refutes
   "genetic manipulation", "alien" origin, or any cause. Say what was measured.

## Setup (user fills in `config.env`)
| set | when |
|---|---|
| `INPUT_TYPE=cram` or `bam`, `INPUT_FILE=/path/file.cram` | you have an aligned file |
| `INPUT_REFERENCE=/path/ref.fa` | the CRAM cannot be read without its reference (skill 01 will say so) |
| `INPUT_TYPE=fastq`, `FASTQ_R1`, `FASTQ_R2` | you have raw reads |
| `REFERENCE=/path/GRCh38.fa` | you already have a GRCh38 FASTA (else skill 02 downloads one) |
| `ALIGN_SCOPE=full` (default) or `chr3_only` | FASTQ only. `chr3_only` is fast but biased — see Limits |
| `OUTPUT_CHR_STYLE=ucsc\|ensembl\|genbank\|refseq` | you want an extra copy of the VCF with chr3 renamed |
| `SAMPLE`, `THREADS`, `WORKDIR` | labels / resources |

## Skills, in order
| # | command | does | success means | usual failure → fix |
|---|---|---|---|---|
| 00 | `.agent/skills/00_check_env/SKILL.md` → `00_check_env.sh` | tools + config sanity | status OK/WARN | missing tool → `conda install -c bioconda samtools bcftools bwa htslib` |
| 01 | `.agent/skills/01_inspect_input/SKILL.md` → `01_inspect_input.sh` | reads header, finds what the file calls chr3, checks assembly, checks it is readable | `chr3_name`, `assembly=GRCh38` | "cannot read reads" on a CRAM → set `INPUT_REFERENCE`; assembly GRCh37 → stop, wrong coordinates |
| 02 | `.agent/skills/02_prepare_reference/SKILL.md` → `02_prepare_reference.sh` | picks/downloads the FASTA for alignment and for calling; builds bwa index | `call_ref_chr3` set | download failed → user sets `REFERENCE=` to a local GRCh38 FASTA |
| 03 | `.agent/skills/03_align_fastq/SKILL.md` → `03_align_fastq.sh` | FASTQ → BAM (SKIPPED for CRAM/BAM). **Hours to days on a whole genome.** | `mapped_pct` > 90 | mapped 0 → wrong reference/FASTQ |
| 04 | `.agent/skills/04_extract_region/SKILL.md` → `04_extract_region.sh` | copies control + extended windows to `bam/region.bam` using the file's own chr3 name; reports depth | reads > 0, depths printed | "no reads in window" → coordinates/name problem: show the contig list from the log |
| 05 | `.agent/skills/05_chr_convert/SKILL.md` → `05_chr_convert.sh` | **utility**: convert chr3 spelling (see below) | — | — |
| 06 | `.agent/skills/06_call_variants/SKILL.md` → `06_call_variants.sh` | bcftools calling in control + extended windows | variants_extended > 0 | length mismatch → BAM and reference are different assemblies |
| 07 | `.agent/skills/07_read_signals/SKILL.md` → `07_read_signals.sh` | soft-clips, split reads, discordant pairs, MAPQ, **local depth windows, breakpoint clusters**, each vs control | verdict line lists flags | — |
| 08 | `.agent/skills/08_allele_balance/SKILL.md` → `08_allele_balance.sh` | exact binomial test of het-site ref/alt balance, hotspot vs control | `primary_call` NORMAL/FLAG/LOW_POWER | — |
| 09 | `.agent/skills/09_gnomad_frequency/SKILL.md` → `09_gnomad_frequency.sh` | joins PASS calls to gnomAD v4.1 frequencies (no API; streams a ~100 kb slice) | `gnomad_records` > 0 | no source reachable → user sets `GNOMAD_LOCAL_VCF` or fixes network/proxy |
| 10 | `.agent/skills/10_report/SKILL.md` → `10_report.sh` | writes `results/FINAL_REPORT.txt` | file exists | — |

Order: 00 → 01 → 02 → 03 → 04 → 06 → 07 → 08 → 09 → 10 (05 is only called on demand).
Resume after a fix: run the failed skill again, then the later ones in order.

## Chromosome 3 has four spellings — you must never assume one
| style | name | typical source |
|---|---|---|
| ucsc | `chr3` | UCSC, 1000 Genomes GRCh38 reference, gnomAD |
| ensembl | `3` | Ensembl |
| genbank | `CM000665.2` | NCBI GenBank FASTA (the user's first alignment used this) |
| refseq | `NC_000003.12` | NCBI RefSeq FASTA |

Skills detect the name automatically (`state.env` → `CHR3_NAME`) and build every region string from it.
To translate yourself, use skill 05:
```
<run_skill_script 05_chr_convert 05_chr_convert.sh with args:> detect  FILE                       # what does this file call chr3?
<run_skill_script 05_chr_convert 05_chr_convert.sh with args:> region  chr3:75440000-75600000 --to genbank
<run_skill_script 05_chr_convert 05_chr_convert.sh with args:> vcf  in.vcf.gz out.vcf.gz --to ucsc
<run_skill_script 05_chr_convert 05_chr_convert.sh with args:> bam  in.cram out.bam --to ensembl --region CM000665.2:74000000-77000000 --reference ref.fa
<run_skill_script 05_chr_convert 05_chr_convert.sh with args:> fasta in.fa out.fa --to ucsc
<run_skill_script 05_chr_convert 05_chr_convert.sh with args:> bed   in.bed out.bed --to refseq
```
A mismatch between a BAM's chr3 name and the reference's chr3 name is what produced
"sequence CM000665.2 was not found". Skill 06 now rebuilds the calling FASTA with the BAM's name, so you should not see it again;
if you do, run `05_chr_convert.sh detect` on both files and report the two names.

## How to report
Give: (1) the status line of every skill, (2) every `warnings` entry, (3) the "SIGNALS IN THE PRIMARY HOTSPOT" block and
"OVERALL" line from `FINAL_REPORT.txt`, (4) the path of `results/09_gnomad_annotated.tsv` and the rows marked `in_primary=YES` with
class `absent` or `rare`. Then give the limits below in one or two sentences.

## Limits you must state
* **Alignment scope.** If `ALIGN_SCOPE=chr3_only` (state key `ALIGN_BIAS`), reads from similar regions elsewhere are forced onto chr3;
  depth, read-level and variant results are unreliable. A control-region depth far above the sample's expected genome coverage
  (~30x for typical whole-genome data) is the symptom.
* **Hotspot coordinates.** The paper says only "chr3:75.5 Mb"; the configured window (75,440,000–75,600,000) was set from where the trio scan found the nonparental regions. Report it that way.
* **Low power.** A small region can have few heterozygous sites; `LOW_POWER` means allele balance cannot say anything.
* **Thresholds** in `config.env` are conventions, not validated cut-offs.
* **gnomAD "absent"** only means not seen in ~76k genomes; everyone carries private variants. Indels may be absent
  only because of different normalisation.
* No parents → no inheritance test.

## Files
`resources/urls.env` download URLs · `lib/common.sh` shared helpers (naming, results) · `py/` analysis code · everything produced is in your workspace (`state.env`, `results/`, `logs/`, `bam/`, `vcf/`). Settings are in `config.env`, which only the user can edit.
