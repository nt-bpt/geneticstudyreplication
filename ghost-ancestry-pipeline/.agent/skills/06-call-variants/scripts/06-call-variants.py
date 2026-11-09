#!/usr/bin/env python3
"""SKILL 06: genotype the user's genome at every 1000 Genomes SNP site."""
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "06-call-variants"
q = shlex.quote


def sample_stats(step, vcf):
    out = step.capture(["bcftools", "stats", "-s", "-", str(vcf)])
    for line in out.splitlines():
        p = line.split("\t")
        if p[0] == "PSC" and len(p) > 6:
            return {"hom_ref": int(p[3]), "hom_alt": int(p[4]), "het": int(p[5])}
    return {}


def work(step):
    cfg = step.cfg
    res = pc.require(step, "02-prepare-reference", "03-align-reads", "04-qc-alignment",
                     "05-fetch-panel")
    ref = res["02-prepare-reference"]["metrics"]["reference"]
    aln = res["03-align-reads"]["metrics"]["alignment"]
    mean = res["04-qc-alignment"]["metrics"]["mean_depth"]
    min_dp = cfg.int("MIN_DP")
    max_dp = max(min_dp + 1, int(mean * cfg.float("MAX_DP_FACTOR")))
    name = cfg.get("SAMPLE_NAME")
    t = cfg.get("THREADS")
    namefile = pc.work(cfg, "calls", "sample_name.txt")
    namefile.write_text(name + "\n")
    step.metrics.update({"min_dp": min_dp, "max_dp": max_dp})

    per = {}
    chroms = cfg.chromosomes()
    for i, chrom in enumerate(chroms, 1):
        out = pc.work(cfg, "calls", f"{name}.{chrom}.vcf.gz")
        if not (pc.nonempty(out) and Path(str(out) + ".tbi").exists()):
            sites = pc.work(cfg, "panel", f"sites.{chrom}.tsv.gz")
            tmp = Path(str(out) + ".tmp.vcf.gz")
            step.progress(f"{chrom}: genotyping panel sites ({i}/{len(chroms)})")
            step.run(
                f"bcftools mpileup --threads {t} -f {q(ref)} -r {chrom} -T {q(str(sites))} "
                f"-a FORMAT/AD,FORMAT/DP -q 20 -Q 20 -Ou {q(aln)}"
                f" | bcftools call --threads {t} -m -C alleles -T {q(str(sites))} "
                f"--ploidy GRCh38 -Ou"
                f" | bcftools filter -S . -e 'FMT/DP<{min_dp} || FMT/DP>{max_dp}' -Ou"
                f" | bcftools view -e 'GT=\"mis\"' -Oz -o {q(str(tmp))}")
            step.run(["bcftools", "reheader", "-s", str(namefile), "-o", str(out), str(tmp)])
            tmp.unlink(missing_ok=True)
            pc.index_vcf(step, out)
        st = sample_stats(step, out)
        panel = (res["05-fetch-panel"]["metrics"].get("panel_snp_sites") or {}).get(chrom, 0)
        called = sum(st.values()) if st else pc.vcf_count(step, out)
        st.update({"called_sites": called, "panel_sites": panel,
                   "called_fraction": round(called / panel, 3) if panel else None})
        per[chrom] = st
        if panel and called / panel < 0.1:
            step.fail(f"{chrom}: only {called:,} of {panel:,} panel sites were genotyped. Check that "
                      "the alignment and reference match, and the depth limits in this skill's "
                      "metrics (min_dp, max_dp).")
        if panel and called / panel < 0.7:
            step.warn(f"{chrom}: only {called / panel:.0%} of panel sites got a confident genotype")
        if st.get("het") and st.get("hom_alt"):
            ratio = st["het"] / st["hom_alt"]
            st["het_hom_ratio"] = round(ratio, 2)
            if not 0.9 < ratio < 2.6:
                step.warn(f"{chrom}: het/hom-alt ratio {ratio:.2f} is unusual (expect 1.3-2.2); "
                          "possible contamination or wrong sample")
        step.log(f"{chrom}: {called:,} sites genotyped")
        step.outputs.append(out)
    step.metrics["per_chromosome"] = per
    return "OK", f"genotyped {sum(v['called_sites'] for v in per.values()):,} panel sites"


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
