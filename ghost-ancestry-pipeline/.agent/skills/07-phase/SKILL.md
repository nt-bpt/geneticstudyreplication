---
name: 07-phase
description: phase the user's genotypes into two haplotypes with Beagle
---

#  07-phase Skill

SKILL 07 — Split the user's genotypes into two haplotypes (phasing) with Beagle, using the 1000 Genomes panel as reference.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `07-phase` and `file_path` set to `scripts/07-phase.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/07-phase.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

About 10-60 minutes per chromosome. The tool call itself returns within seconds.

Outputs:

results/07-phase.json
work/phased/<SAMPLE_NAME>.<chrom>.vcf.gz

If it fails:

- java not found: tell the user to install Java, e.g. `sudo apt install default-jre` (Debian/Ubuntu) or `brew install openjdk` (macOS).
- Beagle download failed: the jar name changes with each release; ask the user to set BEAGLE_URL or BEAGLE_JAR in repo/config.env.
- Beagle out of memory: lower THREADS or raise MEMORY_GB in repo/config.env, then run again.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 08-build-cohort
