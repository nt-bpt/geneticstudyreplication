---
name: compare-reference
description: Compare a subject's striatal metrics with the age- and sex-matched reference cohort, giving z-scores and percentiles. Run after measure-striatum and build-reference.
---

# compare-reference

## Before running

Ask the user for their age at the time of the scan and their sex (M/F) if you don't have them.
Without them the comparison is against the whole cohort and much less precise.

## How to run

Execute the script with your command-execution tool (shell / terminal / Bash tool), from the
project root. Do not calculate z-scores or percentiles yourself, compare against numbers from
papers or memory, or edit the script.

```bash
python3 .agent/skills/compare-reference/scripts/compare.py --subject <subject> --age <years> --sex <M|F>
```

## Reading the result

- |z| < 2: within the typical range for this reference group.
- |z| ≥ 2: unusual relative to this group. With ~11 metrics, one such value occurs by chance in
  many healthy people; say so whenever you mention one.
- `reference n` below ~30 or `sex-matched=False`: say the comparison is weak.
- The reference was scanned on different machines than the subject; small differences are expected
  from that alone.

## Files

- Reads: `repo/work/<subject>/metrics.json`, `repo/reference/reference.csv`
- Writes: `repo/work/<subject>/comparison.json`
