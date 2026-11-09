---
name: 12-fetch-archaic
description: build tables of ancestral, Neanderthal and Denisovan alleles at the cohort sites
---

#  12-fetch-archaic Skill

SKILL 12 — Download the Neanderthal and Denisovan genomes and ancestral alleles, and record their alleles at every cohort SNP site.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `12-fetch-archaic` and `file_path` set to `scripts/12-fetch-archaic.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/12-fetch-archaic.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

About 30-90 minutes per chromosome, mostly downloads. The tool call itself returns within seconds.

Outputs:

results/12-fetch-archaic.json
work/archaic/<chrom>.archaic.tsv

If it fails:

- CrossMap not found: tell the user to run `pip install -r requirements.txt`.
- an archaic genome URL failed: ask the user to check the ARCHAIC_URL_* entries in repo/config.env.
- no ancestral FASTA: ask the user to check ANCESTRAL_URL in repo/config.env.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 13-label-segments
