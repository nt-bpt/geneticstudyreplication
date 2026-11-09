---
name: 08-build-cohort
description: join the user's phased genome to the 1000 Genomes study cohort
---

#  08-build-cohort Skill

SKILL 08 — Combine the 503 cohort genomes and the user's phased genome into one VCF per chromosome, ready for ARG building.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `08-build-cohort` and `file_path` set to `scripts/08-build-cohort.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/08-build-cohort.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

About 5-20 minutes per chromosome. The tool call itself returns within seconds.

This skill always gives one WARN about haplotype node numbering; that is expected. Mention it in the report.

Outputs:

results/08-build-cohort.json (`metrics.user_hap_nodes` are the user's haplotype IDs)
work/cohort/<chrom>/cohort.vcf and cohort.vcf.gz

If it fails:

- SAMPLE_NAME clashes with a 1000 Genomes ID: ask the user to change SAMPLE_NAME in repo/config.env, then rerun from 06-call-variants.
- sites not phased: rerun 07-phase, then this skill.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 09-fetch-trace
