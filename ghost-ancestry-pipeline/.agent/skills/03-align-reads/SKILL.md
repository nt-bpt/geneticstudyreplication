---
name: 03-align-reads
description: align FASTQ reads to GRCh38, or realign a non-GRCh38 CRAM/BAM
---

#  03-align-reads Skill

SKILL 03 — Align the reads to GRCh38 and produce a sorted, duplicate-marked CRAM. A GRCh38 CRAM/BAM is used as it is and the skill reports SKIPPED.

Expected workflow:

1. Call `run_skill_script` with `skill_name` set to `03-align-reads` and `file_path` set to `scripts/03-align-reads.py`. Pass no other arguments. The tool result's `stdout` is a JSON object (the same content is saved in `results/03-align-reads.json`).
2. Read that JSON. `status` is OK, WARN, FAIL, SKIPPED or RUNNING; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. On a failed command the verdict ends with the last lines of the log.
3. RUNNING means the work continues in the background. Wait (at least 30 minutes), then call this skill again the same way to check progress. Never start the next skill while this one is RUNNING.
4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script finds the repo folder (next to .agent/skills in your working directory) by itself; all paths below are relative to repo/.

Alignment takes many hours (roughly 1 hour per 10x of coverage with 8 threads). SKIPPED inputs finish in minutes. The tool call itself returns within seconds.

Outputs:

results/03-align-reads.json (`metrics.alignment` is the CRAM/BAM used by later skills)
work/align/<SAMPLE_NAME>.GRCh38.cram (when aligned here)

If it fails:

- not enough disk space: ask the user to free space or move WORK_DIR to a larger disk.
- bwa or samtools killed: lower THREADS or MEMORY_GB in repo/config.env and run again.
- command failed: the verdict ends with the last log lines; report them to the user.
- cannot find the repo folder: ask the user to start the agent from the working directory that contains .agent/skills/ and repo/.

Next skill: 04-qc-alignment
