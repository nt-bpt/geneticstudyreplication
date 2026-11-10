---
name: ingest-mri
description: Convert a subject's brain MRI (DICOM folder or NIfTI) from repo/input/<subject>/ to NIfTI, pick the T1 series, and record its geometry and warnings. First processing step for a subject.
---

# ingest-mri

## Before running

The subject's scan must be in `repo/input/<subject>/` (a DICOM folder tree as exported by the
scanner or provider, or one or more `.nii` / `.nii.gz` files). `<subject>` is any short name
without spaces, e.g. `me`.

## How to run

Execute the script with your command-execution tool (shell / terminal / Bash tool), from the
project root. Do not convert files, choose series, or read DICOM headers yourself, and do not
edit the script.

```bash
python3 .agent/skills/ingest-mri/scripts/ingest.py --subject <subject>
```

If it reports that no series looks like a T1, show the user the listed series, ask which is the
T1-weighted scan, then run again with that file:

```bash
python3 .agent/skills/ingest-mri/scripts/ingest.py --subject <subject> --t1 repo/work/<subject>/nifti/<file>.nii.gz
```

## Reading the result

- `voxel_mm`: if any value is above 1.5, tell the user the bridge-zone metrics will be unreliable
  (the script also adds this to `warnings`).
- `dwi_present`: whether a diffusion series exists (relevant to the optional diffusion analysis in
  `AGENTS.md`).

## Files

- Reads: `repo/input/<subject>/`
- Writes: `repo/work/<subject>/nifti/` (converted series), `repo/work/<subject>/ingest.json`
