---
name: write-report
description: Assemble the subject's ingest, segmentation QC, measurements and reference comparison into repo/results/<subject>/report.md and report.json. Final step for a subject.
---

# write-report

## How to run

Execute the script with your command-execution tool (shell / terminal / Bash tool), from the
project root. Do not write or rewrite the report yourself, and do not edit the script.

```bash
python3 .agent/skills/write-report/scripts/report.py --subject <subject>
```

## After it runs

Read `repo/results/<subject>/report.md` and give the user a short plain-language summary that:
- states any QC or resolution warnings first;
- gives the key values with z-scores, describing |z| < 2 as typical;
- keeps the report's "What this result can and cannot tell you" points, in particular that no
  result confirms or rules out a UAP encounter or abduction.

Point the user to the report file rather than pasting all of it.

## Files

- Reads: `repo/work/<subject>/ingest.json`, `segment.json`, `metrics.json`, and
  `comparison.json` if present
- Writes: `repo/results/<subject>/report.md`, `repo/results/<subject>/report.json`
