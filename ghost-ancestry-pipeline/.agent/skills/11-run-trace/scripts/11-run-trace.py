#!/usr/bin/env python3
"""SKILL 11: run TRACE (t = 15,000 generations) on the user's two haplotypes and
keep archaic segments longer than 50 kb and 0.05 cM."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "11-run-trace"


def work(step):
    cfg = step.cfg
    res = pc.require(step, "08-build-cohort", "09-fetch-trace", "10-build-arg")
    t = cfg.int("TRACE_T_GHOST")
    windows = pc.read_windows(cfg)
    outs = pc.run_trace_windows(step, t, f"t{t}", windows)
    segs = pc.collect_trace_segments(step, outs)
    raw = pc.write_tsv(pc.work(cfg, "trace", f"t{t}", "segments.raw.tsv"), segs,
                       ["chrom", "start", "end", "hap"])
    kept = pc.filter_segments(cfg, segs, cfg.float("MIN_SEG_KB") * 1000, cfg.float("MIN_SEG_CM"))
    cols = ["chrom", "start", "end", "hap", "length_bp", "length_cM"]
    out = pc.write_tsv(pc.work(cfg, "trace", f"t{t}", "segments.filtered.tsv"), kept, cols)

    analysed = res["10-build-arg"]["metrics"]["analysed_bp"]
    by_hap = {}
    for s in kept:
        by_hap[str(s["hap"])] = by_hap.get(str(s["hap"]), 0) + s["length_bp"]
    total = sum(by_hap.values())
    n_haps = 2 if all(h in ("0", "1") for h in by_hap) or not by_hap else max(2, len(by_hap))
    step.metrics.update({
        "t_generations": t, "segments_raw": len(segs), "segments_kept": len(kept),
        "archaic_bp_by_hap": by_hap, "analysed_bp": analysed,
        "archaic_fraction_per_genome": round(total / (analysed * n_haps), 5) if analysed else None,
    })
    step.outputs += [raw, out]
    if "NA" in by_hap:
        step.warn("TRACE output had no haplotype column; both haplotypes were pooled")
    if not kept:
        step.warn("no archaic segments passed the length filters; check TRACE output format "
                  f"in {pc.rel(raw)} and the TRACE_* settings")
    frac = step.metrics["archaic_fraction_per_genome"] or 0
    return "OK", (f"{len(kept)} archaic segments kept (all sources), "
                  f"{frac:.2%} of the analysed genome; labelled by source in skill 13")


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
