#!/usr/bin/env python3
"""SKILL 05: download the phased 1000 Genomes panel, pick the study cohort,
and prepare SNP site lists and genetic maps."""
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "05-fetch-panel"
q = shlex.quote


def pick_cohort(step, ped):
    cfg = step.cfg
    pops = set(cfg.list("COHORT_POPS"))
    lines = [l.rstrip("\n").split() for l in open(ped) if l.strip()]
    header = [h.lower() for h in lines[0]]

    def col(*names):
        for n in names:
            if n in header:
                return header.index(n)
        step.fail(f"column {names[0]} not found in {pc.rel(ped)} header: {lines[0]}")

    i_s, i_p = col("sampleid", "sample"), col("population", "pop")
    i_f, i_m = col("fatherid", "father"), col("motherid", "mother")
    chosen, counts, children = [], {}, 0
    for p in lines[1:]:
        if len(p) <= max(i_s, i_p, i_f, i_m):
            continue
        if p[i_f] != "0" or p[i_m] != "0":
            children += 1          # drop children of trios: keep unrelated samples only
            continue
        if p[i_p] in pops:
            chosen.append(p[i_s])
            counts[p[i_p]] = counts.get(p[i_p], 0) + 1
    missing = pops - set(counts)
    if missing:
        step.fail(f"no samples found for population(s) {sorted(missing)}; check COHORT_POPS")
    out = pc.work(cfg, "panel", "cohort_samples.txt")
    out.write_text("\n".join(chosen) + "\n")
    step.metrics.update({"cohort_size": len(chosen), "cohort_by_population": counts,
                         "children_excluded": children})
    if abs(len(chosen) - 503) > 25:
        step.warn(f"cohort has {len(chosen)} samples; the paper analysed 503")
    return out


def prepare_maps(step, chroms):
    cfg = step.cfg
    url = cfg.get("GENETIC_MAP_URL")
    zpath = pc.download(step, url, pc.data(cfg, "maps", url.rsplit("/", 1)[-1]))
    mdir = pc.extract(step, zpath, pc.data(cfg, "maps", "extracted"))
    for chrom in chroms:
        dest = pc.map_file(cfg, chrom)
        if pc.nonempty(dest):
            continue
        n = pc.chrom_number(chrom)
        cands = [p for p in mdir.rglob("*.map")
                 if f".chr{n}." in p.name or p.name.endswith(f"chr{n}.map") or f"_chr{n}." in p.name]
        if not cands:
            step.fail(f"no genetic map file for {chrom} inside {pc.rel(zpath)}")
        with open(cands[0]) as f, open(dest, "w") as o:
            for line in f:
                p = line.split()
                if len(p) >= 4:
                    o.write("\t".join([chrom, p[1], p[2], p[3]]) + "\n")


def work(step):
    cfg = step.cfg
    pc.require(step, "00-check-env")
    chroms = cfg.chromosomes()
    ped = pc.download(step, cfg.get("PANEL_SAMPLES_URL"), pc.data(cfg, "panel", "samples_ped.txt"))
    pick_cohort(step, ped)
    step.progress("downloading genetic maps")
    prepare_maps(step, chroms)

    sites_total = {}
    for i, chrom in enumerate(chroms, 1):
        snps = pc.work(cfg, "panel", f"panel_snps.{chrom}.vcf.gz")
        sites = pc.work(cfg, "panel", f"sites.{chrom}.tsv.gz")
        if not (pc.nonempty(snps) and pc.nonempty(str(sites) + ".tbi")):
            url = cfg.get("PANEL_URL_TEMPLATE").format(chrom=chrom, n=pc.chrom_number(chrom))
            raw = pc.data(cfg, "panel", url.rsplit("/", 1)[-1])
            step.progress(f"{chrom}: downloading 1000 Genomes phased panel ({i}/{len(chroms)})")
            pc.download(step, url, raw)
            try:
                pc.download(step, url + ".tbi", Path(str(raw) + ".tbi"))
            except pc.StepError:
                pc.index_vcf(step, raw)
            step.progress(f"{chrom}: keeping biallelic SNPs")
            t = cfg.get("THREADS")
            part = Path(str(snps) + ".part.vcf.gz")
            step.run(f"bcftools view --threads {t} -m2 -M2 -v snps -c 1:minor -Oz "
                     f"-o {q(str(part))} {q(str(raw))}")
            part.replace(snps)
            pc.index_vcf(step, snps)
            step.run(f"bcftools query -f '%CHROM\\t%POS\\t%REF,%ALT\\n' {q(str(snps))} "
                     f"| bgzip -c > {q(str(sites))}")
            step.run(["tabix", "-f", "-s1", "-b2", "-e2", str(sites)])
        sites_total[chrom] = pc.vcf_count(step, snps)
        step.log(f"{chrom}: {sites_total[chrom]:,} biallelic SNP sites")
    step.metrics["panel_snp_sites"] = sites_total
    return "OK", (f"panel ready for {len(chroms)} chromosome(s); cohort of "
                  f"{step.metrics['cohort_size']} unrelated samples from {cfg.get('COHORT_POPS')}")


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
