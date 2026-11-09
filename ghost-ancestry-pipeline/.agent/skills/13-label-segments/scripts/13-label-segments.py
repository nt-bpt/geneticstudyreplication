#!/usr/bin/env python3
"""SKILL 13: label each archaic segment as Neanderthal, Denisovan or Ghost from
how many of its derived alleles are shared with the sequenced archaic genomes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "13-label-segments"


def label(a, delta, min_sites):
    n, d = a["nea_affinity"], a["den_affinity"]
    if a["n_derived"] < min_sites or n is None or d is None:
        return "Unclassified"
    if n - d > delta:
        return "Neanderthal"
    if d - n > delta:
        return "Denisovan"
    return "Ghost"


def work(step):
    cfg = step.cfg
    res = pc.require(step, "10-build-arg", "11-run-trace", "12-fetch-archaic")
    t = cfg.int("TRACE_T_GHOST")
    segs = pc.read_tsv(pc.work(cfg, "trace", f"t{t}", "segments.filtered.tsv"))
    delta, min_sites = cfg.float("LABEL_DELTA"), cfg.int("MIN_DERIVED_SITES")
    alleles, rows = {}, []
    for s in segs:
        chrom = s["chrom"]
        if chrom not in alleles:
            step.progress(f"loading alleles for {chrom}")
            alleles[chrom] = pc.ChromAlleles(step, chrom)
        a = alleles[chrom].affinity(int(s["start"]), int(s["end"]), s["hap"])
        row = dict(s, n_derived=a["n_derived"],
                   nea_affinity=None if a["nea_affinity"] is None else round(a["nea_affinity"], 3),
                   den_affinity=None if a["den_affinity"] is None else round(a["den_affinity"], 3),
                   label=label(a, delta, min_sites))
        for k, v in a["affinity"].items():
            row[f"aff_{k}"] = None if v is None else round(v, 3)
        rows.append(row)
    names = alleles[next(iter(alleles))].arch_names if alleles else cfg.list("ARCHAIC_GENOMES")
    cols = ["chrom", "start", "end", "hap", "length_bp", "length_cM", "label", "n_derived",
            "nea_affinity", "den_affinity"] + [f"aff_{n}" for n in names]
    out = pc.write_tsv(pc.work(cfg, "labels", "segments.labeled.tsv"), rows, cols)

    analysed = res["10-build-arg"]["metrics"]["analysed_bp"]
    summary = {}
    for r in rows:
        s = summary.setdefault(r["label"], {"segments": 0, "bp": 0})
        s["segments"] += 1
        s["bp"] += int(r["length_bp"])
    for s in summary.values():
        s["fraction_per_genome"] = round(s["bp"] / (2 * analysed), 5) if analysed else None
    step.metrics.update({"by_label": summary, "label_delta": delta,
                         "min_derived_sites": min_sites, "analysed_bp": analysed})
    step.outputs.append(out)
    step.warn("source labels use a simple rule (Neanderthal vs Denisovan affinity difference "
              f"> {delta}); the paper's exact rule is in supplementary section S4.2. "
              "Adjust LABEL_DELTA after reading it if needed.")
    if len(cfg.chromosomes()) < 5:
        step.warn("proportions from a few chromosomes are noisy; do not compare them with the "
                  "paper's genome-wide 0.5-1.1% ghost estimate")
    parts = ", ".join(f"{k} {v['fraction_per_genome']:.2%}" for k, v in sorted(summary.items())
                      if v["fraction_per_genome"] is not None)
    return "OK", f"{len(rows)} segments labelled: {parts or 'none'}"


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
