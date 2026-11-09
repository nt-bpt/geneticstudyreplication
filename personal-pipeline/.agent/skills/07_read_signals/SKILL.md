---
name: 07_read_signals
description: measure soft-clips, split reads, discordant pairs, mapping quality and local depth against a control
---

#  07_read_signals Skill

SKILL 07 — Look at the reads themselves in the hotspot and compare with a control region: soft-clip, split-read and discordant-pair rates, MAPQ, local depth shifts and breakpoint clusters. These point to structural variants or mapping artifacts.

Expected workflow:

1. Call `run_skill_script` with the skill name 07_read_signals and the resource 07_read_signals.sh, setting `return_output` to false so the script output is not returned.
2. Read `results/07_read_signals.json`. `status` is OK, WARN, FAIL or SKIPPED; `verdict` is the one-line finding; `metrics` holds the numbers; `warnings` lists anything to mention in the report. The full log is `logs/07_read_signals.log`.
3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On FAIL, apply the fix below and run this skill again.

General expectations:

The script runs from the process root; all paths below are relative to your workspace folder.

This skill finishes in seconds to a few minutes.

Outputs:

results/07_read_signals.json (verdict lists the flags raised, e.g. softclip, depth_shift, breakpoint_cluster)

If it fails:

- no reads in region: rerun 04.
- thresholds live in config.env, which the user edits (SOFTCLIP_FLOOR_PCT, MIN_FLAG_READS ...).
