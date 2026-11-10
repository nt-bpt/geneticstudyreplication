---
name: segment-synthseg
description: Segment the subject's T1 into brain structures with FreeSurfer SynthSeg, producing labels, intracranial volume and per-region QC scores. Run after ingest-mri.
---

# segment-synthseg

## How to run

Execute the script with your command-execution tool (shell / terminal / Bash tool), from the
project root. Do not call `mri_synthseg` yourself, segment or estimate volumes any other way
(including by looking at images), or edit the script.

```bash
python3 .agent/skills/segment-synthseg/scripts/segment.py --subject <subject> [--threads 8]
```

It takes roughly 1–5 minutes on CPU and needs plenty of RAM (see check-environment).

## Reading the result

- `qc.passed: false` / `WARNING: SynthSeg QC flagged …`: segmentation of those regions is suspect.
  Tell the user. If caudate, putamen or white matter is among them, do not interpret the striatal
  metrics for this scan.
- `icv_mm3: null`: %ICV metrics will be missing downstream; mention it.
- A non-zero exit means SynthSeg failed; relay the error. Common causes: FreeSurfer not sourced,
  missing license, out of memory.

## Files

- Reads: `repo/work/<subject>/ingest.json` and the T1 it points to
- Writes in `repo/work/<subject>/`: `synthseg.nii.gz`, `t1_resampled.nii.gz`,
  `synthseg_volumes.csv`, `synthseg_qc.csv`, `segment.json`
