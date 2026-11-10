#!/usr/bin/env python3
"""Write the final report.

Reads  repo/work/<subject>/ingest.json, segment.json, metrics.json, comparison.json (optional)
Writes repo/results/<subject>/report.md and report.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "repo" / "lib"))

from striatum.paths import WORK, load_state, rel, subject_dirs  # noqa: E402
from striatum.steps import write_report  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--subject", required=True)
a = ap.parse_args()

info = load_state(a.subject, "ingest", "write-report")
seg = load_state(a.subject, "segment", "write-report")
metrics = load_state(a.subject, "metrics", "write-report")
comp_path = WORK / a.subject / "comparison.json"
comparison = json.loads(comp_path.read_text()) if comp_path.exists() else None
if comparison is None:
    print("NOTE: no comparison.json; the report will contain raw measurements only")

p = write_report(subject_dirs(a.subject)["results"], info, metrics, seg.get("qc"), comparison)
print(f"Saved {rel(p)} and {rel(p.with_suffix('.json'))}")
