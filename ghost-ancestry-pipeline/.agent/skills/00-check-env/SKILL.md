---
name: 00-check-env
description: verify tools, configuration and disk space before any slow step
---

#  00-check-env Skill

SKILL 00 — Check that the required programs, the input settings in repo/config.env and the free disk space are all in order.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `00-check-env` and `file_path` set to `scripts/00-check-env.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/00-check-env.json`).
2. Read that JSON. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

This skill finishes in seconds.

Installing system programs needs the user's permission (sudo). Do not run install commands yourself; give the user the command from the verdict.

A WARN listing tools needed by later skills (java, SINGER, CrossMap) is normal at this point; mention it in the report.

Outputs:

results/00-check-env.json

If it fails:

- missing tools: tell the user to install them with the system package manager, e.g. `sudo apt install samtools bcftools tabix bwa curl` (Debian/Ubuntu) or `brew install samtools bcftools htslib bwa` (macOS). The exact command is in the verdict.
- no input set, or both FASTQ and INPUT_FILE set: ask the user to set it in repo/config.env. Use FASTQ_R1 + FASTQ_R2 for FASTQ files, or INPUT_FILE (+ INPUT_REFERENCE for a CRAM).
- repo/config.env not found: ask the user to create it by copying repo/config.env.example.
- low disk space: ask the user to free space or point WORK_DIR and DATA_DIR at a larger disk.

Next skill: 01-inspect-input
