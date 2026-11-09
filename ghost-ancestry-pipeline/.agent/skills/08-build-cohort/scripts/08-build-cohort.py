#!/usr/bin/env python3
"""SKILL 08: join the user's phased genome to the 1000 Genomes study cohort."""
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "08-build-cohort"
q = shlex.quote


def work(step):
    cfg = step.cfg
    pc.require(step, "05-fetch-panel", "07-phase")
    name = cfg.get("SAMPLE_NAME")
    t = cfg.get("THREADS")
    samples_file = pc.work(cfg, "panel", "cohort_samples.txt")
    cohort_ids = set(samples_file.read_text().split())
    if name in cohort_ids:
        step.fail(f"SAMPLE_NAME {name} clashes with a 1000 Genomes sample ID; choose another name")

    per, nodes, n_samples = {}, None, None
    for chrom in cfg.chromosomes():
        final = pc.cohort_vcf_gz(cfg, chrom)
        plain = final.with_name("cohort.vcf")
        if not (pc.nonempty(final) and pc.nonempty(plain)):
            panel = pc.work(cfg, "panel", f"panel_snps.{chrom}.vcf.gz")
            user = pc.work(cfg, "phased", f"{name}.{chrom}.vcf.gz")
            only = final.with_name("cohort_only.vcf.gz")
            step.progress(f"{chrom}: building cohort VCF")
            step.run(f"bcftools view --threads {t} -S {q(str(samples_file))} --force-samples -Ou "
                     f"{q(str(panel))} | bcftools view -c 1:minor -Oz -o {q(str(only))}")
            pc.index_vcf(step, only)
            part = Path(str(final) + ".part.vcf.gz")
            step.run(f"bcftools merge --threads {t} -m none -Ou {q(str(only))} {q(str(user))}"
                     f" | bcftools view -i 'N_MISSING=0' -m2 -M2 -v snps -c 1:minor"
                     f" -Oz -o {q(str(part))}")
            part.replace(final)
            pc.index_vcf(step, final)
            step.run(["bcftools", "view", "-Ov", "-o", str(plain), str(final)])
            only.unlink(missing_ok=True)
            for ext in (".tbi", ".csi"):
                Path(str(only) + ext).unlink(missing_ok=True)

        ids = step.capture(["bcftools", "query", "-l", str(final)]).split()
        if ids[-1] != name:
            step.fail(f"expected {name} as the last sample in {pc.rel(final)}, found {ids[-1]}")
        n_samples = len(ids)
        nodes = [2 * (n_samples - 1), 2 * (n_samples - 1) + 1]
        sites = pc.vcf_count(step, final)
        unphased = sites - int(step.capture(f"bcftools view -H -p {q(str(final))} | wc -l").strip())
        if unphased:
            step.fail(f"{chrom}: {unphased} sites are not fully phased; rerun 07-phase")
        ends = step.capture(f"bcftools query -f '%POS\\n' {q(str(final))} | sed -n '1p;$p'").split()
        user_sites = pc.vcf_count(step, pc.work(cfg, "phased", f"{name}.{chrom}.vcf.gz"))
        positions = final.with_name("positions.txt")
        if not pc.nonempty(positions):
            step.run(["bcftools", "query", "-f", "%POS\n", str(final)], stdout=positions)
        per[chrom] = {"sites": sites, "first_pos": int(ends[0]), "last_pos": int(ends[-1]),
                      "user_sites": user_sites}
        if user_sites and sites / user_sites < 0.5:
            step.warn(f"{chrom}: only {sites / user_sites:.0%} of the user's sites survived the "
                      "merge; check that REF/ALT alleles match the panel")
        step.log(f"{chrom}: {sites:,} sites, {n_samples} samples")
        step.outputs.append(final)

    pc.work(cfg, "cohort", "user_hap_nodes.txt").write_text("\n".join(map(str, nodes)) + "\n")
    step.metrics.update({"per_chromosome": per, "n_samples": n_samples,
                         "user_sample_index": n_samples - 1, "user_hap_nodes": nodes})
    step.warn("user haplotype node IDs assume SINGER numbers sample nodes in VCF haplotype "
              f"order (user = nodes {nodes}). Check this against the SINGER/TRACE docs.")
    return "OK", f"cohort of {n_samples} genomes (1000G + user) ready on {len(per)} chromosome(s)"


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
