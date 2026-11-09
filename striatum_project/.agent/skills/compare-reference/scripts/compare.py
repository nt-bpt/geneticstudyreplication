#!/usr/bin/env python3
"""Compare a subject's metrics with the reference cohort (z-scores, percentiles).

Reads  repo/work/<subject>/metrics.json, repo/reference/reference.csv
Writes repo/work/<subject>/comparison.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "repo" / "lib"))

from striatum.paths import REFERENCE_CSV, abs_path, load_state, rel, save_state  # noqa: E402
from striatum.steps import compare  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--subject", required=True)
ap.add_argument("--age", type=float, help="subject age in years at the time of the scan")
ap.add_argument("--sex", choices=["M", "F"])
ap.add_argument("--reference", default=rel(REFERENCE_CSV), help="reference CSV under repo/")
a = ap.parse_args()

ref = abs_path(a.reference)
if not ref.exists():
    sys.exit(f"{rel(ref)} not found. Build it with the build-reference skill first.")
metrics = load_state(a.subject, "metrics", "compare-reference")
if a.age is None or a.sex is None:
    print("WARNING: age and/or sex not given; comparing against the whole cohort, which is much less precise")

c = compare(metrics, str(ref), a.age, a.sex)
c.update({"age": a.age, "sex": a.sex, "reference_csv": rel(ref)})
p = save_state(a.subject, "comparison", c)
for k, v in c["metrics"].items():
    z = v.get("z")
    print(f"{k:28s} value={v['value']!s:>10.10}  z={'–' if z is None else f'{z:+.2f}'}")
print(f"reference n={c['reference_n']}  sex-matched={c['sex_matched']}")
print(f"Saved {rel(p)}")
