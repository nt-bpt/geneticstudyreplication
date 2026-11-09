---
name: 03_align_fastq
description: align paired FASTQ reads to the reference with bwa-mem; skipped for CRAM or BAM
---

#  03_align_fastq Skill

SKILL 03 — Align FASTQ to the reference, fix mates, sort and mark duplicates. Reports SKIPPED when the input is already CRAM or BAM.

Expected workflow:

1. Call `run_skill_script` with the skill name 03_align_fastq and the resource 03_align_fastq.sh, setting `return_output` to false so the script output is not returned.
2. Read `results/03_align_fastq.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/03_align_fastq.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

This is a very long-running skill for whole-genome FASTQ (many hours to over a day, depending on threads). Run it once; do not restart unless it reports FAIL.

Outputs:

results/03_align_fastq.json
bam/aligned.bam  <- ALIGNED_BAM in state.env

If it fails:

- out of disk: free 100+ GB and rerun.
- chr3_only warning: aligning only chr3 can inflate depth and false variants; mention it in the report.
