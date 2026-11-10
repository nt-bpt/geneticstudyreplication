#!/usr/bin/env python3
"""Compute caudate, putamen and bridge-zone metrics from the SynthSeg output.

Reads  repo/work/<subject>/segment.json
Writes repo/work/<subject>/metrics.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "repo" / "lib"))

from striatum.metrics import compute_metrics  # noqa: E402
from striatum.paths import abs_path, load_state, rel, save_state  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--subject", required=True)
ap.add_argument("--bridge-mm", type=float, default=4.0,
                help="must match the value used to build repo/reference/reference.csv")
a = ap.parse_args()

seg = load_state(a.subject, "segment", "measure-striatum")
if seg.get("icv_mm3") is None:
    print("WARNING: no intracranial volume in SynthSeg output; %ICV metrics will be missing")
m = compute_metrics(str(abs_path(seg["seg"])), str(abs_path(seg["resampled"])), seg.get("icv_mm3"), a.bridge_mm)
p = save_state(a.subject, "metrics", m)
print(json.dumps(m, indent=2, default=float))
print(f"Saved {rel(p)}")
