---
name: measure-striatum
description: Measure left/right caudate and putamen volumes, %ICV, asymmetry, and the caudate–putamen bridge-zone volume and grey-matter index from the SynthSeg output. Run after segment-synthseg.
---

# measure-striatum

## How to run

Execute the script with your command-execution tool (shell / terminal / Bash tool), from the
project root. Do not compute volumes, distances or intensities yourself, and do not edit the
script or its library code in `repo/lib/striatum/`.

```bash
python3 .agent/skills/measure-striatum/scripts/measure.py --subject <subject>
```

Keep `--bridge-mm` at its default (4.0) unless the reference cohort in
`repo/reference/reference.csv` was built with a different value; the two must match.

## What the metrics mean

- `*_caudate_mm3`, `*_putamen_mm3`: structure volumes; `*_icv_pct`: as % of intracranial volume.
- `*_bridge_mm3`: white matter lying within 4 mm of both caudate and putamen (mostly the anterior
  limb of the internal capsule).
- `*_bridge_gm_index`: 0 = that tissue looks like ordinary white matter on T1, 1 = it looks like
  striatal grey matter. This is the project's operationalization of Nolan's description, not his
  (unpublished) method.
- `*_asymmetry_pct`: (left − right) / mean × 100.

Raw values can't be called high or low on their own; use compare-reference.

## Files

- Reads: `repo/work/<subject>/segment.json` and the files it points to
- Writes: `repo/work/<subject>/metrics.json`
