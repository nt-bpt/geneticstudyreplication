#!/usr/bin/env python3
"""Find the subject's scan under repo/input/<subject>/, convert DICOM to NIfTI, pick the T1.

Writes repo/work/<subject>/ingest.json.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "repo" / "lib"))

from striatum.paths import abs_path, rel, save_state, subject_dirs  # noqa: E402
from striatum.steps import ingest  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--subject", required=True, help="folder name under repo/input/")
ap.add_argument("--t1", help="force this NIfTI as the T1 (path under repo/)")
a = ap.parse_args()

d = subject_dirs(a.subject)
if not d["input"].exists() or not any(d["input"].iterdir()):
    sys.exit(f"No scan found. Put the DICOM folder or NIfTI file in {rel(d['input'])}/")

try:
    info = ingest(str(d["input"]), d["work"], str(abs_path(a.t1)) if a.t1 else None)
except RuntimeError as e:
    sys.exit(str(e).replace(str(ROOT) + "/", ""))

info["t1_path"] = rel(info["t1_path"])
info["subject"] = a.subject
out = save_state(a.subject, "ingest", info)
print(json.dumps(info, indent=2))
print(f"Saved {rel(out)}")
