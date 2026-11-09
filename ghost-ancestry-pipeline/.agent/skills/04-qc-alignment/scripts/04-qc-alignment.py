#!/usr/bin/env python3
"""SKILL 04: check depth of coverage and basic quality of the alignment."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "04-qc-alignment"


def coverage(step, aln, ref, region):
    out = step.capture(["samtools", "coverage", "--reference", str(ref), "-r", region, str(aln)])
    for line in out.splitlines():
        if line.startswith("#") or not line.strip():
            continue
        p = line.split("\t")
        return {"reads": int(p[3]), "covered_fraction": float(p[5]) / 100,
                "mean_depth": float(p[6]), "mean_mapq": float(p[8])}
    step.fail(f"samtools coverage returned nothing for {region}")


def work(step):
    cfg = step.cfg
    res = pc.require(step, "02-prepare-reference", "03-align-reads")
    ref = Path(res["02-prepare-reference"]["metrics"]["reference"])
    aln = Path(res["03-align-reads"]["metrics"]["alignment"])

    per = {}
    for chrom in cfg.chromosomes():
        per[chrom] = coverage(step, aln, ref, chrom)
        step.log(f"{chrom}: mean depth {per[chrom]['mean_depth']:.1f}x, "
                 f"{per[chrom]['covered_fraction']:.1%} covered")
    for v in per.values():  # depth over covered bases only (ignores N gaps / centromeres)
        v["depth_covered"] = v["mean_depth"] / v["covered_fraction"] if v["covered_fraction"] else 0
    mean = sum(v["depth_covered"] for v in per.values()) / len(per)
    step.metrics.update({"mean_depth": round(mean, 2), "per_chromosome": per})

    try:
        cx = coverage(step, aln, ref, "chrX")
        x = cx["mean_depth"] / cx["covered_fraction"] if cx["covered_fraction"] else 0
        ratio = x / mean if mean else 0
        step.metrics["chrX_to_autosome_depth"] = round(ratio, 2)
        step.metrics["inferred_sex"] = "XX" if ratio > 0.8 else ("XY" if ratio > 0.3 else "unclear")
    except pc.StepError:
        pass

    low_cov = [c for c, v in per.items() if v["covered_fraction"] < 0.85]
    if low_cov:
        step.warn(f"less than 85% of {', '.join(low_cov)} is covered; expect missing genotypes")
    if mean < cfg.float("MIN_MEAN_DEPTH") / 2:
        step.fail(f"mean depth {mean:.1f}x is too low for reliable genotypes "
                  f"(need about {cfg.get('MIN_MEAN_DEPTH')}x or more)")
    if mean < cfg.float("MIN_MEAN_DEPTH"):
        step.warn(f"mean depth {mean:.1f}x is below MIN_MEAN_DEPTH={cfg.get('MIN_MEAN_DEPTH')}x; "
                  "heterozygous sites will be missed more often")
    return "OK", f"mean depth {mean:.1f}x over {len(per)} chromosome(s)"


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
