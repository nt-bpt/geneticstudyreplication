---
name: build-reference
description: Build the healthy reference cohort (repo/reference/reference.csv) by running SynthSeg and the striatal measurements on reference T1 scans (IXI, DLBS), one cohort per run. Needed once before compare-reference; resumable.
---

# build-reference

## Before running

Each cohort needs a T1 folder and a demographics CSV (columns `subject,age,sex[,cohort]`, where
`subject` is the T1 file name without `.nii.gz`). The fetch-reference skill creates these:

| Cohort | T1 folder | Demographics |
|---|---|---|
| IXI | `repo/reference/ixi/T1/` | `repo/reference/ixi_demographics.csv` |
| DLBS | `repo/reference/dlbs/T1/` | `repo/reference/dlbs_demographics.csv` |

If they're missing, run fetch-reference (only if the user has asked for the download) or tell the
user. Don't write the demographics files yourself.

## How to run

Execute the script with your command-execution tool (shell / terminal / Bash tool), from the
project root. Do not build or edit the reference CSV by hand, substitute published norms, or edit
the script.

Trial run on a few subjects first:

```bash
python3 .agent/skills/build-reference/scripts/build_reference.py --limit 3
```

Then each cohort in full, into the same `repo/reference/reference.csv` (safe to stop and re-run;
it resumes and skips subjects already processed):

```bash
python3 .agent/skills/build-reference/scripts/build_reference.py --threads 8
python3 .agent/skills/build-reference/scripts/build_reference.py --threads 8 \
    --t1-dir repo/reference/dlbs/T1 --demographics repo/reference/dlbs_demographics.csv
```

If the tool you use to run commands has a time limit, run it in the background or in repeated
`--limit` batches.

## Reading the result

The last line gives counts added, skipped and total. Fewer than ~100 usable subjects makes the
age/sex-matched comparison weak; tell the user. Skips for QC are normal for a few scans.

## Files

- Reads: each cohort's T1 folder and demographics CSV under `repo/reference/`
- Writes: `repo/reference/reference.csv`, `repo/work/reference/<subject>/`
