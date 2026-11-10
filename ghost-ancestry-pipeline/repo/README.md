# Ghost-ancestry pipeline: ADK skills for a small agent model

Runs the approach of Zhang et al., *Science* 2026 (doi:10.1126/science.aef8874) on one
person's genome: align, genotype and phase it, add it to the paper's 503-sample
1000 Genomes cohort, build genealogies (ARGs) with Relate, run TRACE, then label segments as
Neanderthal / Denisovan / Ghost and screen Denisovan segments for super-archaic pieces.

Input is **either** two FASTQ files (`FASTQ_R1`, `FASTQ_R2`) **or** one CRAM/BAM
(`INPUT_FILE`, plus `INPUT_REFERENCE` for a CRAM). A GRCh38 alignment with `chr` names is used
directly; anything else is converted back to reads and realigned to GRCh38.

## Check it works before running a real genome

A full run takes days, so test the whole chain first on simulated data with a
known answer:

```
pip install msprime
python testdata/make_test_data.py --out testdata/fixture
cp testdata/fixture/config.env.test config.env     # then set RELATE_DIR and BEAGLE_JAR
# run skills 00-16, then:
python testdata/check_result.py --fixture testdata/fixture
```

This runs in minutes on a simulated 5 Mb region carrying a planted archaic
introgression event, using the real tools, and reports how much of the planted
signal was recovered. See `testdata/README.md` for what it does and does not
prove.

## Before publishing this anywhere

Read `repo/THIRD-PARTY.md`. The short version: the pipeline bundles no other
program or dataset, and the top-level `.gitignore` keeps your genetic data,
downloaded data and third-party programs out of git. Relate is licensed for
academic non-commercial use and must not be redistributed, so never commit
`repo/tools/`. Do not commit the paper PDF.

## Layout

The agent's working directory holds two folders: `.agent/skills/` (the skills) and
`repo/` (everything else). The skill scripts read settings **only** from
`repo/config.env`, and everything they write stays under `repo/`.

```
<working directory>/          start the agent here
├── .agent/skills/
│   └── NN-name/              one ADK skill per folder (17 in all)
│       ├── SKILL.md            frontmatter `name: NN-name` (matches the folder)
│       └── scripts/
│           ├── NN-name.py        the skill's script
│           └── pipeline_common.py  shared library (identical copy in every skill)
└── repo/
    ├── config.env            your settings (copy of config.env.example)
    ├── config.env.example
    ├── AGENTS.md             instructions for the agent (use as its instruction)
    ├── adk_agent_example.py  example ADK agent wiring
    ├── requirements.txt      Python packages (pip)
    ├── testdata/             simulated test data with known truth, and a checker
    ├── README.md
    ├── build_skills.py       regenerates .agent/skills from lib/ (maintenance only)
    ├── lib/                  master copy of pipeline_common.py
    └── results/ logs/ work/ data/ tools/ .skill_runtime/   created by the skills
```

Skill names follow ADK's rule: lowercase letters, digits and single hyphens, matching the
folder name. The agent calls `run_skill_script` with `skill_name` = `NN-name` and
`file_path` = `scripts/NN-name.py`; the JSON result comes back in the tool's `stdout`.

## How the scripts work under ADK

- **Finding repo/.** ADK copies the skill into a temporary folder, runs the script there
  and deletes the folder afterwards, so a script can't find `repo/` from its own location.
  It looks for the folder that contains both `.agent/skills/` and `repo/`, starting from
  the agent's working directory (`$PWD`) and moving up through its parents. Setting
  `PIPELINE_ROOT` to the repo folder overrides this; `adk_agent_example.py` does so.
  A `config.env` anywhere other than `repo/` is ignored, and skill 00 refuses `DATA_DIR`,
  `WORK_DIR` or `TOOLS_DIR` settings that point outside `repo/`.
- **Timeouts.** ADK's local executor stops a call after 300 s by default. No pipeline call
  comes close: skills 02–15 start a background worker (from a persistent copy in
  `.skill_runtime/`) and return `RUNNING` within a second; later calls report progress.
- **Code executor.** `run_skill_script` needs a code executor on the `SkillToolset` or the
  agent; `UnsafeLocalCodeExecutor` runs scripts on this machine with the agent's
  environment, so run the agent from the virtual environment that has CrossMap.
- **Output.** Scripts print only one JSON object and always exit 0; the status is in the
  JSON. Skill 09 includes the start of the TRACE README, and skill 16 includes the full
  report, because the agent cannot open files.

## Before the first run

No conda needed. Python 3.8+ is required.

1. System programs (samtools, bcftools, tabix/bgzip, bwa, curl, Java), version 1.13 or
   newer for samtools and bcftools:
   - Debian/Ubuntu: `sudo apt install samtools bcftools tabix bwa curl default-jre`
   - Fedora: `sudo dnf install samtools bcftools htslib-tools bwa curl java-21-openjdk`
   - macOS (Homebrew): `brew install samtools bcftools htslib bwa openjdk`
   Ubuntu 22.04 or newer ships recent enough versions; skill 00 checks this.
2. Python packages: `python3 -m venv .venv && . .venv/bin/activate && pip install -r repo/requirements.txt`
   (run the agent from this activated environment so CrossMap is on the PATH).
3. Download Relate from https://myersgroup.github.io/relate/ (prebuilt binaries, e.g.
   `relate_v1.2.4_x86_64_static`), unpack it under `repo/tools/`, and set `RELATE_DIR` to that
   folder, relative to `repo/`. Relate is free for academic, non-commercial use only; read its
   licence before other use. To use SINGER instead, set `ARG_METHOD=singer` and `SINGER_DIR`.
4. `cp repo/config.env.example repo/config.env`, set the input files and `SAMPLE_NAME`.
   Leave `CHROMOSOMES=22` for the pilot run.
5. Install TRACE into the same environment (it is a Python package, MIT licence):
   `pip install 'git+https://github.com/YulinZhang9806/trace.git'`. It provides
   `trace-extract`, `trace-infer` and `trace-summarize`, which skills 11 and 14 call
   themselves, so there is no TRACE command to configure.
6. Optional: install `bedtools` if you want to use an accessibility mask
   (`TRACE_INCLUDE_REGIONS`), which is what the paper did and which TRACE needs bedtools for.

## Running

Skills run in order 00 → 16. Each one checks that the earlier skills it needs finished.

Skills 02–15 run **in the background**: the first call starts a worker and
returns `RUNNING`; later calls report progress; the result is OK/WARN/FAIL/SKIPPED once it
ends. This keeps the agent's tool calls short even when a step takes days. Finished work is
kept, so after a FAIL, fixing the cause and running the skill again continues where it
stopped. To force a fresh run of a finished skill, delete its `repo/results/NN-name.json`.
Set `PIPELINE_FOREGROUND=1` to run everything in the foreground instead (not under ADK:
long skills would then hit the executor timeout).

## What has been tested, and what you must check

All 17 skills were run end to end through ADK 2.13's own skill loader and script executor
(`load_skills_from_dir` + `UnsafeLocalCodeExecutor`), on a synthetic genome: a 300 kb region
of chr22, simulated reads, a mini panel, stand-in ARG/TRACE/Beagle programs and planted
archaic segments. Earlier rounds also covered all three input types (FASTQ pair, GRCh38 CRAM,
non-`chr` BAM). The pipeline recovered the planted segments, labels and genes; a wrong
starting folder and a failing skill both return a clear FAIL in the JSON.
The final round ran in this layout: the agent started in a working directory holding only
`.agent/skills/` and `repo/`, with no `PIPELINE_ROOT`. All output landed in `repo/`, and a
`config.env` placed in the working directory instead of `repo/` was correctly ignored.
Skill 10 was then tested with the **real Relate 1.2.4 binaries**: input preparation and
polarisation, the parallel build, population-size recalibration, and conversion to tskit, all
through ADK with no `.venv` on the search path. The converted trees load in tskit, the user's
haplotypes are the last two sample nodes as skill 08 assumes, and an interrupted run resumes at
the right stage. The synthetic genotypes are random, so this checks that the steps work, not how
many archaic segments Relate lets TRACE find.
Skills 09, 11 and 14 were then tested with the **real TRACE** (installed from its GitHub
repository): all three of its commands, at both time cutoffs (t = 15,000 and t = 31,500), with
the resulting segments flowing through labelling, gene annotation and the report. TRACE's own
example data reproduces its documented output.
It has **not** run against the real Beagle or the download sites, which were unreachable from
my sandbox, nor with a live model driving the calls. Check these first, on the chr22 pilot:

| Item | Where | Why |
|---|---|---|
| Accessibility mask | `TRACE_INCLUDE_REGIONS` | Empty by default, so poorly mappable regions are kept; the paper used the 1000 Genomes strict mask (needs bedtools) |
| Posterior threshold | `TRACE_POSTERIOR` | TRACE's own default (0.9); the paper's value is in its supplementary text |
| Relate parameters | `RELATE_MU`, `RELATE_N` | `RELATE_N` is the HAPLOID Ne (2x diploid); defaults are Relate's own documented example values |
| Mappability mask | `RELATE_MASK` | Optional but recommended for real data; without it, poorly mappable regions are kept |
| SINGER options (with `ARG_METHOD=singer`) | `SINGER_CMD_TEMPLATE`, `SINGER_CONVERT_TEMPLATE` | Written from SINGER's documented usage; compare with `singer_master -h` |
| Haplotype node IDs | skill 08 warning | Assumes the user's haplotypes are the last two sample nodes |
| Source labelling rule | `LABEL_DELTA` | Simplified version of supplementary S4.2 |
| Download URLs | `config.env.example` defaults | Beagle's jar name changes per release; others may move |

## Scale

A whole genome needs roughly 300–500 GB of free disk. Alignment takes about a day at 30x
on 8 threads. Building the genealogies is the slowest step: with Relate, plan on hours per
large chromosome; with SINGER, days. Use a cloud machine with many cores for the full 1–22 run.

Results are research output on a single genome with a method of limited recall: in the paper's
simulations TRACE recovered under 10% of true archaic segments from Relate genealogies and about
50% from SINGER, so totals are underestimates either way. A segment overlapping a gene says nothing about the gene's function.
