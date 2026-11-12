# AGENTS.md — 1000 Genomes trio check (nonparental-allele clusters)


## How skills are called
Each skill is a folder under `.agent/skills/<name>/` with a `SKILL.md` and one script. Run a skill with the `run_skill_script` tool: skill name = folder name, resource = `<name>.sh`. The tool runs from the process folder, one level above your workspace. Read the skill's `SKILL.md` first for its expected workflow, then `results/<name>.json` after it finishes. 
**Your world is the workspace folder.** You can see `lib/`, `py/`, `resources/`, `run_all.sh` and everything the skills produce (`data/`, `bam/`, `vcf/`, `ref/`, `results/`, `logs/`, `tmp/`, `state.env`). You cannot see `config.env` or `.agent/`: settings are changed by the user, so when a skill's failure fix says to change a setting, tell the user which one and why. All paths in this file and in the SKILL.md files are relative to your workspace folder.

Goal: reproduce, with public files and open tools only, the pattern described in an unreviewed preprint (Rempel 2025):
clusters of child alleles that neither parent carries ("nonparental alleles", NPAs), reported by the preprint at chr3:75.5 Mb (HG01505, HG02293) in some 1000 Genomes trios.
Do not theorise about cause. Report what the data show and which mundane explanations the checks can or cannot exclude.

## Rules
1. Run skills in order with `run_skill_script`. Each skill writes `results/<skill>.json` and `logs/<skill>.log`.
2. Status is OK, WARN, FAIL or SKIPPED. Read the log on FAIL, apply the fix below, rerun from that skill. Never edit results to make a step pass.
3. Never state a number you did not read from `results/` or the TSVs. Never describe a SKIPPED step as done.
4. No network from the shell? Ask the user to download files in a browser and set `MANUAL_DIR` to the folder (same file names).

## Skills
| # | Skill | Does | If it fails |
|---|-------|------|-------------|
| 00 | check_env | tools (bcftools, tabix, bgzip, curl, python3), python numpy + cyvcf2, disk | install what is named |
| 01 | download | phased VCF + .tbi for `CHROM`, pedigree, population table; checks tabix can read it, finds the contig name inside (`3` or `chr3`), counts samples | URL unreachable → download manually, set `MANUAL_DIR`. "tabix cannot read" → truncated file, delete and rerun |
| 02 | build_trios | child/father/mother table from the pedigree, trios whose three members are in the VCF | prints the pedigree's first rows; if columns are mis-detected, fix `py/prepare_trios.py` |
| 03 | npa_scan | per-trio NPA counts; sliding windows of `WINDOW_SNPS` informative SNVs; hot if ≥ `MIN_WINDOW_NPA` NPAs; merged regions; Poisson p against the trio's own background | `0 records read` → wrong contig/range |
| 04 | context_checks | tags the best `TOP_N` regions: segdup_overlap, sv_in_trio, sv_nearby, recurrent_xN, common_alleles, rare_alleles, high_background_trio, overlaps_focus | segdup download failure only removes that tag (WARN) |
| 05 | compare_rempel | listed families vs all other trios (needs `resources/rempel_families.txt`; empty by design) | SKIPPED until the user supplies IDs |
| 06 | baseline | same scan on `BASELINE_CHROMS` (e.g. "2 4") for a comparison | SKIPPED if empty; needs ≥2 chromosomes scanned |
| 07 | rempel_method | the preprint's own published method (fixed 60 kb windows, any record type, classes <10 / 10-19 / ≥20) on the same VCF; also unique vs summed NPA counts per collapsed region | classification vs paper's 570/7/4 | no trio in VCF → rerun 02 |
| 08 | report | `results/FINAL_REPORT.txt` | — |

## Interpreting
- A hot region = many NPAs in a short stretch, above that trio's own background. It is not by itself a finding.
- `segdup_overlap`, `sv_*`, `common_alleles`, `high_background_trio` point to mapping/CNV/pedigree/genotyping explanations. `recurrent_xN` (same place in several trios) points to a systematic cause (reference, mapping, cell line).
- Regions with no tag deserve a read-level look (IGV, or the personal pipeline on the raw CRAM). They are unexplained by these checks, not evidence of any cause.
- Without a baseline (skill 06) say so: "hot" is relative to each trio only.

## Report in this order
1. Files used and how many trios. 2. Did hot regions exist; how many in the focus window. 3. What the tags say. 4. Baseline and family comparison, or that they were not run. 5. Limits below.

## Limits to state every time
- Only the simulated data and the code paths were tested; the 1000G URLs were taken from directory listings and not downloaded when this was written.
- The NPA definition is a re-implementation; the preprint's exact definition and focus coordinates are unconfirmed; no family IDs are bundled.
- The phased panel can hide Mendelian errors; raw genotypes (`working/20201028_3202_raw_GT_with_annot`) are the alternative.
- Cell-line (EBV) artifacts cannot be judged from VCFs.
