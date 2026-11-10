#!/usr/bin/env python3
"""SKILL 11: run TRACE (t = 15,000 generations) on the user's two haplotypes and
keep archaic segments longer than 50 kb and 0.05 cM.

Drives TRACE's three commands: trace-extract, trace-infer, trace-summarize.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "11-run-trace"


def work(step):
    cfg = step.cfg
    res = pc.require(step, "08-build-cohort", "10-build-arg")
    t = cfg.int("TRACE_T_GHOST")
    min_bp = cfg.float("MIN_SEG_KB") * 1000
    min_cm = cfg.float("MIN_SEG_CM")
    segs, per_chrom = pc.run_trace(step, t, f"t{t}", min_bp, min_cm)

    cols = ["chrom", "start", "end", "hap", "length_bp", "length_cM", "mean_posterior"]
    out = pc.write_tsv(pc.work(cfg, "trace", f"t{t}", "segments.filtered.tsv"), segs, cols)

    analysed = res["10-build-arg"]["metrics"]["analysed_bp"]
    by_hap = {}
    for s in segs:
        by_hap[str(s["hap"])] = by_hap.get(str(s["hap"]), 0) + s["length_bp"]
    total = sum(by_hap.values())
    step.metrics.update({
        "t_generations": t, "segments_kept": len(segs), "segments_per_chromosome": per_chrom,
        "archaic_bp_by_hap": by_hap, "analysed_bp": analysed,
        "posterior_threshold": cfg.float("TRACE_POSTERIOR"),
        "min_segment_bp": int(min_bp), "min_segment_cM": min_cm,
        "archaic_fraction_per_genome": round(total / (analysed * 2), 5) if analysed else None,
    })
    step.outputs.append(out)
    if not cfg.get("TRACE_INCLUDE_REGIONS"):
        step.warn("no accessibility mask was used (TRACE_INCLUDE_REGIONS is empty). Segments "
                  "were clipped to the region holding variants, but poorly mappable regions "
                  "were kept. The paper used the 1000 Genomes strict mask; setting it needs "
                  "bedtools installed.")
    if len(cfg.chromosomes()) < 5:
        step.warn("TRACE trains its model on the chromosomes given to it; with only "
                  f"{len(cfg.chromosomes())} chromosome(s) there may be too little data for "
                  "stable estimates. Treat a pilot run as a check that the pipeline works, not "
                  "as a measurement.")
    frac_check = step.metrics["archaic_fraction_per_genome"] or 0
    if frac_check > 0.10:
        step.warn(f"TRACE called {frac_check:.1%} of the analysed sequence archaic. Published "
                  "estimates for real genomes are a few percent at most, so this is implausible: "
                  "likely causes are a time cutoff (TRACE_T_GHOST) that does not match the "
                  "lineage being looked for, poorly fitted genealogies, or a genetic map that "
                  "does not match the genome build. Report this to the user rather than treating "
                  "the number as a result.")
    if not segs:
        step.warn("TRACE found no archaic segments passing the filters. On a small pilot that "
                  "can be normal; check work/trace/t%d/trace.log for how the model fitted." % t)
    frac = step.metrics["archaic_fraction_per_genome"] or 0
    return "OK", (f"{len(segs)} archaic segments kept (all sources), "
                  f"{frac:.2%} of the analysed genome; labelled by source in skill 13")


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
