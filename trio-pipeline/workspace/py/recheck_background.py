#!/usr/bin/env python3
"""Recompute the high-background flag WITHOUT rescanning, excluding events inside hot regions.
usage: recheck_background.py NPA_DIR [FACTOR=5]
Reads npa_per_trio.tsv + npa_regions.tsv from an earlier run (made before bg_rate existed)."""
import csv, sys
d = sys.argv[1]; f = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
trios = list(csv.DictReader(open(f"{d}/npa_per_trio.tsv"), delimiter="\t"))
inreg = {}
for r in csv.DictReader(open(f"{d}/npa_regions.tsv"), delimiter="\t"): inreg[r["child"]] = inreg.get(r["child"], 0) + int(r["n_events"])
for t in trios:
    t["old"] = float(t["rate"]); t["new"] = max(int(t["npa"]) - inreg.get(t["child"], 0), 0) / max(int(t["informative"]), 1)
med_old = sorted(t["old"] for t in trios)[len(trios) // 2]; med_new = sorted(t["new"] for t in trios)[len(trios) // 2]
print(f"cohort median rate: with clusters {med_old:.2e}; outside clusters {med_new:.2e}")
print(f"{'child':<10}{'rate_all':>12}{'rate_outside':>14}  old_flag  new_flag  region_events")
for t in sorted(trios, key=lambda t: -t["old"]):
    o = med_old > 0 and t["old"] >= f * med_old; n = med_new > 0 and t["new"] >= f * med_new
    if o or n or t["child"] in inreg:
        print(f"{t['child']:<10}{t['old']:>12.2e}{t['new']:>14.2e}  {'YES' if o else '-':<9} {'YES' if n else '-':<9} {inreg.get(t['child'], 0)}")
print(f"high-background trios: old rule {sum(med_old > 0 and t["old"] >= f*med_old for t in trios)}, corrected {sum(med_new > 0 and t["new"] >= f*med_new for t in trios)}")
