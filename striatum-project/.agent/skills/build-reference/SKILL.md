---
name: build-reference
description: Build the healthy reference cohort (repo/reference/reference.csv) by running SynthSeg and the striatal measurements on IXI T1 scans. Needed once before compare-reference; resumable.
---

# build-reference

## Before running

The user must have placed:
- IXI T1 images in `repo/reference/ixi/T1/` (`IXI###-<site>-####-T1.nii.gz`)
- `repo/reference/ixi_demographics.csv` with columns `subject,age,sex`, where `subject` is the file
  name without `.nii.gz` and `sex` is `M` or `F`

`repo/docs/README.md` explains where to download these and how to make the CSV. If they're
missing, tell the user that and stop. Don't download data or write the demographics file
yourself unless the user asks.

## How to run

Execute the script with your command-execution tool (shell / terminal / Bash tool), from the
project root. Do not build or edit the reference CSV by hand, substitute published norms, or edit
the script.

Trial run on a few subjects first:

```bash
python3 .agent/skills/build-reference/scripts/build_reference.py --limit 3
```

Then the full cohort (several hours on CPU; safe to stop and re-run, it resumes):

```bash
python3 .agent/skills/build-reference/scripts/build_reference.py --threads 8
```

If the tool you use to run commands has a time limit, run it in the background or in repeated
`--limit` batches.

## Reading the result

The last line gives counts added, skipped and total. Fewer than ~100 usable subjects makes the
age/sex-matched comparison weak; tell the user. Skips for QC are normal for a few scans.

## Files

- Reads: `repo/reference/ixi/T1/`, `repo/reference/ixi_demographics.csv`
- Writes: `repo/reference/reference.csv`, `repo/work/reference/<subject>/`
