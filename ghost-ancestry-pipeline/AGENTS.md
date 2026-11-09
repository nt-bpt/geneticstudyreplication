# AGENTS.md — Personal ghost-ancestry analysis

## Your job

Your working directory holds `.agent/skills/` (the skills) and `repo/`
(settings, results and all data). Start every skill from this working
directory; the scripts find `repo/` themselves.

Run the skills in this project, in order, to find archaic DNA segments
(Neanderthal, Denisovan, "ghost" and super-archaic) in the user's genome, then
give the user the final report. The method follows Zhang et al., *Science* 2026,
doi:10.1126/science.aef8874. You do not need to read the paper; every parameter
it uses is already built into the skills.

You run skills and read their results. The scripts do all the analysis. Do not
write your own analysis code, do not run bioinformatics commands yourself, and
do not change the scripts.

## Skill order

Run exactly this order. Each skill tells you the next one at the bottom of its
SKILL.md.

| # | Skill | What it does | Typical time |
|---|---|---|---|
| 00 | 00-check-env | checks tools, repo/config.env, disk | seconds |
| 01 | 01-inspect-input | FASTQ pair or CRAM/BAM? which genome build? | seconds |
| 02 | 02-prepare-reference | GRCh38 reference and indexes | up to 2 h |
| 03 | 03-align-reads | aligns reads (SKIPPED for a GRCh38 CRAM/BAM) | hours |
| 04 | 04-qc-alignment | depth of coverage | minutes |
| 05 | 05-fetch-panel | 1000 Genomes panel and 503-sample cohort | 10-30 min per chromosome |
| 06 | 06-call-variants | genotypes at panel sites | 15-60 min per chromosome |
| 07 | 07-phase | splits genotypes into two haplotypes | 10-60 min per chromosome |
| 08 | 08-build-cohort | joins the user to the cohort | minutes |
| 09 | 09-fetch-trace | downloads TRACE from Zenodo | minutes |
| 10 | 10-build-arg | builds the genealogies (ARGs) with Relate | hours per large chromosome |
| 11 | 11-run-trace | finds archaic segments | hours |
| 12 | 12-fetch-archaic | Neanderthal/Denisovan allele tables | 30-90 min per chromosome |
| 13 | 13-label-segments | labels each segment by source | minutes |
| 14 | 14-super-archaic | screens Denisovan segments | minutes to hours |
| 15 | 15-annotate-genes | genes inside the segments | minutes |
| 16 | 16-report | writes results/report.md | seconds |

## How to run a skill

1. Call `run_skill_script` with `skill_name` set to the skill name (for
   example `00-check-env`) and `file_path` set to `scripts/` plus the skill name
   plus `.py` (for example `scripts/00-check-env.py`). Pass no other arguments.
   You do not need to call `load_skill` first; the table above and this file
   tell you everything, but you may load a skill to read its "If it fails" list.
2. The tool result's `stdout` is a JSON object. Use its `status` to decide what
   to do next:

| status | What to do |
|---|---|
| OK | go to the next skill |
| WARN | go to the next skill; keep the warnings for the final message |
| SKIPPED | go to the next skill (the step did not apply) |
| RUNNING | the work continues in the background; wait at least 30 minutes, then call the same skill again; never start the next skill meanwhile |
| FAIL | read `verdict`, apply the matching fix from that skill's "If it fails" list, then run the same skill again |

3. Never run two skills at the same time.
4. A skill that is already OK prints its old result again. That is normal.
5. Every call returns within seconds, even for skills that take days: long
   work runs in the background (status RUNNING). If a call ever returns an
   error instead of JSON (for example a timeout or `NO_CODE_EXECUTOR`), stop and
   show the user the error; the agent setup needs fixing, not the pipeline.

## When to stop and ask the user

Stop and ask the user, with the exact `verdict` text, when:

- a fix says "ask the user", or needs a change in repo/config.env. Never try to
  edit, create or move repo/config.env yourself;
- the same skill fails twice in a row with the same verdict;
- 09-fetch-trace reports that TRACE_CMD_TEMPLATE is empty. Tell the user to
  install TRACE and set the template. The start of the TRACE README is in
  `trace_readme_preview` in the tool result; you may use it to suggest a
  template, but the user decides and sets it;
- 10-build-arg is about to start on more than one chromosome and no pilot run
  on chromosome 22 has been finished yet. Ask before committing days of compute;
- a fix needs a program installed. Give the user the install command from the
  verdict; do not run install commands (they need the user's permission);
- a fix would delete files. You have no tool for this; the user does it.

## Rules

- **Genetic data stays on this machine.** Never upload, paste or send the
  user's FASTQ, CRAM, BAM, VCF or segment files anywhere, and never pass them to
  an online service. The skills only download public reference data.
- **Do not invent results.** Every number you report must come from a skill's
  JSON result or from the report text.
- **Do not interpret genes medically.** A segment overlapping a gene does not
  mean the gene works differently. Do not say a result affects health, ability
  or behaviour.
- **Be clear about uncertainty.** TRACE finds only 30-50% of real archaic
  segments with inferred ARGs, the source labels use a simplified rule, and one
  added genome gives noisy numbers. Results from one or a few chromosomes are not
  genome-wide estimates and cannot be compared with the paper's 0.5-1.1% ghost
  figure.
- **Genes named in the paper versus genes from other literature.** The report
  separates genes the paper itself names (column `named_in_paper`) from genes
  with a known role in brain development in the wider literature (column
  `neuro_role_in_literature`). Keep that distinction when you talk about them.

## Expected warnings (normal, mention briefly)

- 00-check-env: tools needed by later skills are missing (if the user will
  install them before those skills).
- 08-build-cohort: haplotype node numbering is assumed.
- 10-build-arg: some windows had too few sites (centromeres, gaps).
- 13-label-segments: labelling rule is simplified; few chromosomes give noisy
  proportions.
- 14-super-archaic: candidates are unconfirmed. SKIPPED is common and normal for
  people without Oceanian or East/South-East Asian ancestry.

## When to warn the user about data quality

Tell the user plainly, before continuing, if any of these appear:

- 04-qc-alignment: mean depth below 10x;
- 06-call-variants: called fraction below 70% or an unusual het/hom-alt ratio;
- 11-run-trace: zero segments kept.

## Finishing

After 16-report is OK:

1. Give the user the text in `report` from the 16-report tool result (it is
   the full content of results/report.md).
2. Add, in a few lines: the chromosomes analysed, every warning collected, and
   whether this was a pilot run.
3. If this was the chromosome 22 pilot, say that the full run means setting
   `CHROMOSOMES=1-22` in repo/config.env and deleting the files
   `repo/results/05-*.json` to `repo/results/16-*.json`. The user does both; then you run
   every skill again from 00. Finished chromosome 22 work is reused.

## Files (all under repo/; you see their content only through tool results)

- `results/<skill>.json`: the same JSON the skill printed
- `logs/<skill>.log`: full log, for the user; failing verdicts quote its last lines
- `results/report.md`: final report
- `work/labels/segments.labeled.tsv`: every archaic segment with its label
- `work/annotation/segment_genes.tsv`: every gene inside a segment
