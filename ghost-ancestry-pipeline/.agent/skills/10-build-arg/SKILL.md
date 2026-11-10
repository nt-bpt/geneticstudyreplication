---
name: 10-build-arg
description: build the cohort's genealogies (ARGs) with Relate, or SINGER if ARG_METHOD=singer
---

#  10-build-arg Skill

SKILL 10 — Build ancestral recombination graphs (ARGs) for the cohort, one chromosome at a time with Relate (default), and convert them to the tree files TRACE reads.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `10-build-arg` and `file_path` set to `scripts/10-build-arg.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/10-build-arg.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

With Relate: roughly 1-4 hours per large chromosome on 8 threads, plus population-size recalibration. With ARG_METHOD=singer: days per large chromosome. Finished stages are kept, so running it again after a stop continues where it left off. The tool call itself returns within seconds.

With ARG_METHOD=singer this skill merges the per-window SINGER output into whole-chromosome ARGs, one per chosen posterior sample, because TRACE needs whole chromosomes. Merging reuses sampling already done, so after a failed conversion there is no need to resample.

With Relate this skill always gives one WARN that TRACE finds far fewer segments with Relate than with SINGER (under 10% versus about 50% in the paper's simulations). That is expected; mention it in the report.

A WARN that population-size recalibration failed means the trees use a constant population size; the run can continue.

Outputs:

results/10-build-arg.json (`metrics.arg_method`, `metrics.analysed_bp`)
work/arg/trees_index.tsv
work/arg/<chrom>/relate/<chrom>.trees and relate.log (Relate)
work/arg/<chrom>/w<start>/ (SINGER, one folder per window)
work/arg/<chrom>/merged/<chrom>_sample<i>.trees and merge.log (SINGER)

If it fails:

- RELATE_DIR is empty or Relate file not found: ask the user to download Relate from https://myersgroup.github.io/relate/, unpack it, and set RELATE_DIR in repo/config.env to the folder holding bin/ and scripts/.
- a Relate file is not executable: give the user the chmod command from the verdict.
- a Relate command failed: the verdict ends with the last lines of relate.log; report them to the user.
- few sites kept after polarising (WARN): the ancestral genome may not match GRCh38; mention it in the report.
- worker stopped (FAIL after RUNNING): the machine may have run out of memory; lower THREADS or MEMORY_GB in repo/config.env and run again.
- with ARG_METHOD=singer, SINGER not found: install SINGER and ask the user to set SINGER_DIR in repo/config.env.
- merge_ARG.py not found: SINGER_DIR must be a versioned SINGER release folder, not the releases/ directory itself.
- windows have no output for a posterior sample: lower SINGER_MERGE_SAMPLES, or check SINGER_N_SAMPLES matches what was sampled.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 11-run-trace
