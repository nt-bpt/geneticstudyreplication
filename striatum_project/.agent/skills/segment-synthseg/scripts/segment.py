#!/usr/bin/env python3
"""Run SynthSeg on the T1 chosen by ingest-mri.

Reads  repo/work/<subject>/ingest.json
Writes repo/work/<subject>/synthseg.nii.gz, t1_resampled.nii.gz, synthseg_volumes.csv,
       synthseg_qc.csv and segment.json
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "repo" / "lib"))

from striatum.paths import abs_path, load_state, rel, save_state, subject_dirs  # noqa: E402
from striatum.steps import icv_from_volumes, qc_summary, read_synthseg_csv, segment  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--subject", required=True)
ap.add_argument("--threads", type=int, default=4)
a = ap.parse_args()

info = load_state(a.subject, "ingest", "segment-synthseg")
work = subject_dirs(a.subject)["work"]
try:
    out = segment(str(abs_path(info["t1_path"])), work, a.threads)
except (RuntimeError, subprocess.CalledProcessError) as e:
    sys.exit(f"Segmentation failed: {e}")

vols = read_synthseg_csv(out["volumes_csv"])
qc = qc_summary(read_synthseg_csv(out["qc_csv"]))
state = {k: rel(v) for k, v in out.items()}
state.update({"icv_mm3": icv_from_volumes(vols), "qc": qc})
p = save_state(a.subject, "segment", state)
print(json.dumps(state, indent=2))
print(f"Saved {rel(p)}")
if not qc["passed"]:
    print("WARNING: SynthSeg QC flagged: " + ", ".join(qc["flagged"]))
