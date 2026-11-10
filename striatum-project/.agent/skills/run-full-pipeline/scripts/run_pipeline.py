#!/usr/bin/env python3
"""Run ingest -> segment -> measure -> compare -> report for one subject, stopping at the first failure.

Each stage is the same script its own skill uses, so results are identical to running them one by one.
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
SKILLS = ROOT / ".agent" / "skills"

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--subject", required=True)
ap.add_argument("--age", type=float)
ap.add_argument("--sex", choices=["M", "F"])
ap.add_argument("--t1", help="force this NIfTI (path under repo/) as the T1")
ap.add_argument("--threads", type=int, default=4)
ap.add_argument("--bridge-mm", type=float, default=4.0)
ap.add_argument("--skip-compare", action="store_true", help="report raw measurements only")
a = ap.parse_args()

stages = [
    ("ingest-mri", "ingest.py", ["--t1", a.t1] if a.t1 else []),
    ("segment-synthseg", "segment.py", ["--threads", str(a.threads)]),
    ("measure-striatum", "measure.py", ["--bridge-mm", str(a.bridge_mm)]),
]
if not a.skip_compare:
    extra = (["--age", str(a.age)] if a.age is not None else []) + (["--sex", a.sex] if a.sex else [])
    stages.append(("compare-reference", "compare.py", extra))
stages.append(("write-report", "report.py", []))

for skill, script, extra in stages:
    print(f"\n=== {skill} ===", flush=True)
    r = subprocess.run([sys.executable, str(SKILLS / skill / "scripts" / script), "--subject", a.subject, *extra],
                       cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"\nStopped: {skill} failed (exit {r.returncode}). Fix the problem above and re-run "
                 f"from that stage using its own skill, or re-run this pipeline.")
print(f"\nDone. Report: repo/results/{a.subject}/report.md")
