#!/usr/bin/env python3
"""Compare a pipeline run on the test data against the simulated truth.

    python testdata/check_result.py --fixture testdata/fixture

Reads truth.tsv from the fixture and the pipeline's own outputs under repo/,
and prints what the run recovered. Exits 0 if the run looks structurally sound
(every stage produced its output), 1 if a stage is missing or empty, so it can
be used as a smoke test in a script.

Recovering the planted segments is reported separately from the structural
check, because recall depends on the ARG method and the region size: see
testdata/README.md before reading anything into a low number.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def read_tsv(path):
    rows = []
    with open(path) as f:
        head = f.readline().rstrip("\n").split("\t")
        for line in f:
            if line.strip():
                rows.append(dict(zip(head, line.rstrip("\n").split("\t"))))
    return rows


def overlap(a, b):
    return max(0, min(a[1], b[1]) - max(a[0], b[0]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixture", default="testdata/fixture")
    ap.add_argument("--repo", default=".", help="the repo folder holding results/ and work/")
    a = ap.parse_args()
    fx, repo = Path(a.fixture), Path(a.repo)
    truth_file = fx / "truth.tsv"
    if not truth_file.exists():
        sys.exit(f"{truth_file} not found; generate the test data first")

    problems = []

    # ---- structural check: did every stage produce something? --------------
    print("== stages")
    expect = ["00-check-env", "01-inspect-input", "02-prepare-reference", "03-align-reads",
              "04-qc-alignment", "05-fetch-panel", "06-call-variants", "07-phase",
              "08-build-cohort", "09-fetch-trace", "10-build-arg", "11-run-trace",
              "12-fetch-archaic", "13-label-segments", "14-super-archaic",
              "15-annotate-genes", "16-report"]
    versions = set()
    for name in expect:
        f = repo / "results" / f"{name}.json"
        if not f.exists():
            print(f"  {name}: not run")
            problems.append(f"{name} did not run")
            continue
        d = json.loads(f.read_text())
        st = d.get("status")
        versions.add(d.get("pipeline_version"))
        print(f"  {name}: {st} - {str(d.get('verdict'))[:88]}")
        if st not in ("OK", "WARN", "SKIPPED"):
            problems.append(f"{name} ended as {st}")
    if len(versions - {None}) > 1:
        problems.append(f"results come from several pipeline versions: {sorted(versions)}")

    # ---- numbers worth eyeballing -----------------------------------------
    def metrics(name):
        f = repo / "results" / f"{name}.json"
        return (json.loads(f.read_text()).get("metrics") or {}) if f.exists() else {}

    print("\n== key numbers")
    depth = metrics("04-qc-alignment").get("mean_depth")
    called = metrics("06-call-variants").get("per_chromosome", {})
    cohort = metrics("08-build-cohort").get("n_samples")
    arg = metrics("10-build-arg")
    seg = metrics("11-run-trace")
    print(f"  mean depth: {depth}")
    for c, v in called.items():
        print(f"  {c}: {v.get('called_sites')} of {v.get('panel_sites')} panel sites genotyped")
    print(f"  cohort size: {cohort} genomes (expect panel + 1)")
    print(f"  ARG method: {arg.get('arg_method')}, analysed {arg.get('analysed_bp', 0) / 1e6:.1f} Mb")
    print(f"  TRACE segments kept: {seg.get('segments_kept')} "
          f"({(seg.get('archaic_fraction_per_genome') or 0):.2%} per genome)")
    labels = metrics("13-label-segments").get("by_label") or {}
    if labels:
        print("  labels: " + ", ".join(f"{k} {v['segments']}" for k, v in sorted(labels.items())))
    genes = metrics("15-annotate-genes").get("paper_genes_in_user_segments") or {}
    print(f"  genes named in the paper that were hit: {', '.join(sorted(genes)) or 'none'}")

    # ---- recovery of the planted segments ---------------------------------
    truth = [(int(r["hap"]), int(r["start"]), int(r["end"])) for r in read_tsv(truth_file)]
    big = [t for t in truth if t[2] - t[1] >= 50_000]
    found_file = None
    for cand in sorted((repo / "work" / "trace").glob("t*/segments.filtered.tsv")):
        found_file = cand
    print(f"\n== planted signal ({len(truth)} true segments, {len(big)} of them >= 50 kb)")
    if not found_file:
        print("  no TRACE segment file found, so nothing to compare")
    else:
        found = [(int(r["hap"]), int(r["start"]), int(r["end"])) for r in read_tsv(found_file)]
        hit = 0
        rec_bp = 0
        for hap, lo, hi in big:
            ov = sum(overlap((lo, hi), (f_lo, f_hi))
                     for f_hap, f_lo, f_hi in found if f_hap == hap)
            rec_bp += ov
            if ov >= 0.5 * (hi - lo):
                hit += 1
        true_bp = sum(hi - lo for _, lo, hi in big)
        found_bp = sum(hi - lo for _, lo, hi in found)
        in_truth = sum(min(sum(overlap((lo, hi), (t_lo, t_hi))
                               for t_hap, t_lo, t_hi in truth if t_hap == hap), hi - lo)
                       for hap, lo, hi in found)
        print(f"  TRACE reported {len(found)} segments, {found_bp / 1e3:.0f} kb")
        print(f"  recovered {hit} of {len(big)} true segments at >=50% of their length")
        print(f"  base-level recall: {rec_bp / true_bp:.1%}" if true_bp else "")
        print(f"  of what TRACE reported, {in_truth / found_bp:.1%} overlaps a true segment"
              if found_bp else "  TRACE reported nothing")
        print("  (low recall does not by itself mean the pipeline is broken; see "
              "testdata/README.md)")

    print("\n== verdict")
    if problems:
        print("  PROBLEMS:")
        for p in problems:
            print("   -", p)
        return 1
    print("  every stage ran and produced output; the pipeline is wired up correctly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
