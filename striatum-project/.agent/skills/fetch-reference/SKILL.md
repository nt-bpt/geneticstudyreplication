---
name: fetch-reference
description: Download reference-cohort T1 scans (IXI and DLBS) into repo/reference/, keeping only subjects in the requested age and sex band, and write each cohort's demographics CSV. Run before build-reference.
---

# fetch-reference

## Before running

- Only run this when the user has asked for the reference data to be downloaded.
- Get the age band and sex from the user, or derive them from the subject: by default use the
  subject's age ±15 years and the subject's sex (e.g. a 47-year-old man → `--age-min 32
  --age-max 62 --sex M`). The extra margin lets compare-reference widen its ±10-year window if it
  needs more people.
- Needs about 6 GB free disk during the IXI step (the archive is deleted after extracting).

## How to run

Execute the script with your command-execution tool (shell / terminal / Bash tool), from the
project root. Do not download, filter or extract the files yourself, and do not edit the script.

```bash
python3 .agent/skills/fetch-reference/scripts/fetch_reference.py --age-min 32 --age-max 62 --sex M
```

Use `--cohorts ixi` or `--cohorts dlbs` to fetch one cohort. It is safe to re-run after an
interruption; finished files are skipped. If your command tool has a time limit, run it in the
background — the IXI archive is ~4.5 GB.

## Reading the result

- Each cohort prints how many subjects are in band and writes its demographics CSV.
- `Could not download …`: relay the URL and error to the user. The machine may have no internet
  access to that host; the user can download the file manually into `repo/reference/downloads/`
  with the same file name and re-run.
- `MD5 mismatch`: the IXI archive is corrupt or partial; delete it and re-run.

## Files

- Writes: `repo/reference/downloads/` (IXI.xls, dlbs_participants.tsv, IXI-T1.tar temporarily),
  `repo/reference/ixi/T1/`, `repo/reference/ixi_demographics.csv`, `repo/reference/dlbs/T1/`,
  `repo/reference/dlbs_demographics.csv`
