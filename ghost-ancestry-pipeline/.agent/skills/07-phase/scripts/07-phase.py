#!/usr/bin/env python3
"""SKILL 07: phase the user's genotypes with Beagle, using the 1000G panel."""
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "07-phase"
q = shlex.quote


def beagle_jar(step):
    cfg = step.cfg
    if cfg.path("BEAGLE_JAR"):
        jar = cfg.path("BEAGLE_JAR")
        if not jar.is_file():
            step.fail(f"BEAGLE_JAR not found: {jar}")
        return jar
    url = cfg.get("BEAGLE_URL")
    try:
        return pc.download(step, url, pc.tools(cfg, "beagle", url.rsplit("/", 1)[-1]))
    except pc.StepError:
        step.fail("could not download Beagle. The jar name changes with each release: open "
                  "https://faculty.washington.edu/browning/beagle/beagle.html, copy the current "
                  "jar link into BEAGLE_URL in repo/config.env (or download it and set BEAGLE_JAR).")


def work(step):
    cfg = step.cfg
    pc.require(step, "05-fetch-panel", "06-call-variants")
    java = cfg.get("JAVA")
    if not pc.have(java):
        step.fail("java not found; install it " + pc.INSTALL_JAVA)
    jar = beagle_jar(step)
    mem = max(2, int(cfg.float("MEMORY_GB") * 0.8))
    name = cfg.get("SAMPLE_NAME")
    per = {}
    chroms = cfg.chromosomes()
    for i, chrom in enumerate(chroms, 1):
        gt = pc.work(cfg, "calls", f"{name}.{chrom}.vcf.gz")
        refp = pc.work(cfg, "panel", f"panel_snps.{chrom}.vcf.gz")
        prefix = pc.work(cfg, "phased", f"{name}.{chrom}")
        out = Path(str(prefix) + ".vcf.gz")
        if not (pc.nonempty(out) and Path(str(out) + ".tbi").exists()):
            step.progress(f"{chrom}: phasing with Beagle ({i}/{len(chroms)})")
            step.run(f"{q(java)} -Xmx{mem}g -jar {q(str(jar))} gt={q(str(gt))} ref={q(str(refp))} "
                     f"map={q(str(pc.map_file(cfg, chrom)))} out={q(str(prefix))} chrom={chrom} "
                     f"impute=false nthreads={cfg.get('THREADS')}")
            if not pc.nonempty(out):
                step.fail(f"Beagle did not write {pc.rel(out)}; see {pc.rel(str(prefix) + '.log')}")
            pc.index_vcf(step, out)
        total = pc.vcf_count(step, out)
        phased = int(step.capture(f"bcftools view -H -p {q(str(out))} | wc -l").strip())
        per[chrom] = {"sites": total, "phased_sites": phased}
        if total == 0:
            step.fail(f"{chrom}: Beagle output has no sites; rerun 06-call-variants and check it")
        if total and phased / total < 0.99:
            step.warn(f"{chrom}: only {phased / total:.1%} of sites are phased")
        step.outputs.append(out)
    step.metrics["per_chromosome"] = per
    return "OK", f"phased {sum(v['sites'] for v in per.values()):,} sites"


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
