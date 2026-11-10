#!/usr/bin/env python3
"""SKILL 14: look for super-archaic pieces inside the user's Denisovan segments
(TRACE with t = 31,500 generations, pieces >= 10 kb and >= 0.01 cM)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "14-super-archaic"


def work(step):
    cfg = step.cfg
    pc.require(step, "13-label-segments")
    labelled = pc.read_tsv(pc.work(cfg, "labels", "segments.labeled.tsv"))
    den = [dict(r, start=int(r["start"]), end=int(r["end"])) for r in labelled
           if r["label"] == "Denisovan"]
    step.metrics["denisovan_segments"] = len(den)
    if not den:
        return "SKIPPED", ("no Denisovan segments in this genome, so there is nothing to screen. "
                           "Super-archaic ancestry is only expected inside Denisovan tracts, "
                           "which are common mainly in Oceanian and some Asian genomes.")
    t = cfg.int("TRACE_T_SUPER")
    # TRACE runs genome-wide at the deeper time cutoff; the result is then
    # intersected with the Denisovan segments found in skill 13.
    deep, _ = pc.run_trace(step, t, f"t{t}", cfg.float("SUPER_MIN_SEG_KB") * 1000,
                           cfg.float("SUPER_MIN_SEG_CM"))
    step.metrics["deep_segments_genome_wide"] = len(deep)

    pieces = []
    for s in deep:
        for d in den:
            if d["chrom"] != s["chrom"] or str(d["hap"]) != str(s["hap"]):
                continue
            a, b = max(s["start"], d["start"]), min(s["end"], d["end"])
            if b > a:
                pieces.append({"chrom": s["chrom"], "start": a, "end": b, "hap": s["hap"],
                               "parent_start": d["start"], "parent_end": d["end"]})
    pieces = pc.filter_segments(cfg, pieces, cfg.float("SUPER_MIN_SEG_KB") * 1000 - 1,
                                cfg.float("SUPER_MIN_SEG_CM") - 1e-9)  # recompute cM for the overlap
    max_aff = cfg.float("SUPER_MAX_AFFINITY")
    alleles = {}
    for p in pieces:
        if p["chrom"] not in alleles:
            alleles[p["chrom"]] = pc.ChromAlleles(step, p["chrom"])
        a = alleles[p["chrom"]].affinity(p["start"], p["end"], p["hap"])
        p["n_derived"] = a["n_derived"]
        p["nea_affinity"] = None if a["nea_affinity"] is None else round(a["nea_affinity"], 3)
        p["den_affinity"] = None if a["den_affinity"] is None else round(a["den_affinity"], 3)
        low = (a["nea_affinity"] is not None and a["den_affinity"] is not None
               and a["nea_affinity"] < max_aff and a["den_affinity"] < max_aff)
        p["low_affinity_to_both"] = "yes" if low else "no"
    cols = ["chrom", "start", "end", "hap", "length_bp", "length_cM", "parent_start",
            "parent_end", "n_derived", "nea_affinity", "den_affinity", "low_affinity_to_both"]
    out = pc.write_tsv(pc.work(cfg, "labels", "super_archaic_candidates.tsv"), pieces, cols)
    strong = [p for p in pieces if p["low_affinity_to_both"] == "yes"]
    den_bp = sum(d["end"] - d["start"] for d in den)
    step.metrics.update({"candidates": len(pieces), "candidates_low_affinity": len(strong),
                         "candidate_bp": sum(p["length_bp"] for p in pieces),
                         "denisovan_bp": den_bp,
                         "fraction_of_denisovan": round(sum(p["length_bp"] for p in pieces) / den_bp, 4)
                         if den_bp else None})
    step.outputs.append(out)
    step.warn("the paper also uses coalescence-time and ILS-length features (supplementary "
              "S8.4-S8.5) to call super-archaic pieces; these candidates use only TRACE plus "
              "low archaic affinity and should be treated as unconfirmed")
    return "OK", (f"{len(pieces)} candidate super-archaic piece(s) inside Denisovan segments, "
                  f"{len(strong)} with low affinity to both archaic genomes")


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
