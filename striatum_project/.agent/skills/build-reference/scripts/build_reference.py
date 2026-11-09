#!/usr/bin/env python3
"""Build the reference cohort CSV by running SynthSeg + measurement on healthy-volunteer T1s.

Reads  repo/reference/ixi/T1/*.nii.gz
       repo/reference/ixi_demographics.csv   (columns: subject,age,sex; subject = file name without extension)
Writes repo/reference/reference.csv          (resumable: subjects already in it are skipped)
       repo/work/reference/<subject>/        (intermediate files)
"""
import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "repo" / "lib"))

from striatum.metrics import compute_metrics  # noqa: E402
from striatum.paths import (REFERENCE_CSV, REFERENCE_DEMOGRAPHICS, REFERENCE_T1_DIR, WORK,  # noqa: E402
                            abs_path, rel)
from striatum.steps import icv_from_volumes, qc_summary, read_synthseg_csv, segment  # noqa: E402

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--t1-dir", default=rel(REFERENCE_T1_DIR))
ap.add_argument("--demographics", default=rel(REFERENCE_DEMOGRAPHICS))
ap.add_argument("--out", default=rel(REFERENCE_CSV))
ap.add_argument("--bridge-mm", type=float, default=4.0)
ap.add_argument("--threads", type=int, default=4)
ap.add_argument("--limit", type=int, help="stop after this many new subjects (for a trial run)")
a = ap.parse_args()

t1_dir, demo_path, out_path = abs_path(a.t1_dir), abs_path(a.demographics), abs_path(a.out)
for p, what in ((t1_dir, "T1 folder"), (demo_path, "demographics CSV")):
    if not p.exists():
        sys.exit(f"{what} not found: {rel(p)}. See repo/docs/README.md for how to get the IXI data.")

demo = {r["subject"]: r for r in csv.DictReader(open(demo_path, newline=""))}
rows = list(csv.DictReader(open(out_path, newline=""))) if out_path.exists() else []
done = {r["subject"] for r in rows}
out_path.parent.mkdir(parents=True, exist_ok=True)

new = skipped = 0
for t1 in sorted(t1_dir.glob("*.nii*")):
    sid = t1.name.replace(".nii.gz", "").replace(".nii", "")
    if sid in done:
        continue
    if sid not in demo:
        print(f"skip {sid}: not in demographics")
        skipped += 1
        continue
    work = WORK / "reference" / sid
    work.mkdir(parents=True, exist_ok=True)
    try:
        seg = segment(str(t1), work, a.threads)
        qc = qc_summary(read_synthseg_csv(seg["qc_csv"]))
        if not qc["passed"]:
            print(f"skip {sid}: QC flagged {list(qc['flagged'])}")
            skipped += 1
            continue
        m = compute_metrics(seg["seg"], seg["resampled"],
                            icv_from_volumes(read_synthseg_csv(seg["volumes_csv"])), a.bridge_mm)
    except Exception as e:  # one bad scan shouldn't stop the cohort
        print(f"skip {sid}: {e}")
        skipped += 1
        continue
    rows.append({"subject": sid, "age": demo[sid].get("age"), "sex": demo[sid].get("sex"), **m})
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    new += 1
    print(f"done {sid} ({len(rows)} in cohort)")
    if a.limit and new >= a.limit:
        break

print(f"Finished: {new} added, {skipped} skipped, {len(rows)} total in {rel(out_path)}")
