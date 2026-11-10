---
name: run-full-pipeline
description: Run ingest-mri, segment-synthseg, measure-striatum, compare-reference and write-report for one subject in a single command. Use when the environment check passes and the reference cohort exists.
---

# run-full-pipeline

## Before running

- check-environment has passed.
- The scan is in `repo/input/<subject>/`.
- `repo/reference/reference.csv` exists (otherwise add `--skip-compare` and tell the user the
  report will have raw measurements only).
- You have the subject's age and sex, or have asked for them.

## How to run

Execute the script with your command-execution tool (shell / terminal / Bash tool), from the
project root. Do not run the stages' internals yourself or edit the script; it calls each
stage's own skill script in order and stops at the first failure.

```bash
python3 .agent/skills/run-full-pipeline/scripts/run_pipeline.py --subject <subject> --age <years> --sex <M|F>
```

Options: `--t1 repo/work/<subject>/nifti/<file>.nii.gz` to force the T1, `--threads N`,
`--skip-compare`.

## Reading the result

- If it stops, the `=== <skill> ===` header just above the error names the failed stage. Read that
  skill's SKILL.md for how to handle the error, fix it, then re-run that stage's skill or this one.
- On success, follow the "After it runs" steps in the write-report skill.

## Files

- Reads: `repo/input/<subject>/`, `repo/reference/reference.csv`
- Writes: `repo/work/<subject>/`, `repo/results/<subject>/`
