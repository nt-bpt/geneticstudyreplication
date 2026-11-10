---
name: check-environment
description: Verify that FreeSurfer/SynthSeg, dcm2niix, the Python libraries and the FreeSurfer license are installed before running any other skill in this project. Use first in every new session or container.
---

# check-environment

## How to run

Execute the script with your command-execution tool (shell / terminal / Bash tool), from the
project root. Do not perform the checks yourself, re-implement them, or edit the script.

```bash
python3 .agent/skills/check-environment/scripts/check_env.py
```

## Reading the result

- Exit code 0: ready. Continue with the next skill.
- Exit code 1: one or more lines say `MISSING` with a `fix:` hint. Report the missing items to the
  user with the fix and stop. Don't try other skills until this passes.
- `[INFO] RAM` under 32 GB: tell the user SynthSeg may run out of memory.
- `[INFO] reference cohort: not built yet`: the build-reference skill must run before
  compare-reference.

## Files

- Reads: nothing under `repo/` except checking for `repo/reference/reference.csv`.
- Writes: nothing.
