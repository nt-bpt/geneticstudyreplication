#!/usr/bin/env python3
"""SKILL 12: build a per-site table of ancestral and archaic (Neanderthal,
Denisovan) alleles at the cohort's SNP positions.

The archaic genomes are on hg19, so cohort positions are lifted GRCh38 -> hg19
with CrossMap, looked up, and stored again by GRCh38 position.
"""
import re
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "12-fetch-archaic"
q = shlex.quote
COMP = str.maketrans("ACGTacgt", "TGCAtgca")


def crossmap(step):
    for c in ("CrossMap", "CrossMap.py"):
        if pc.have(c):
            return c
    step.fail("CrossMap not found: pip install -r requirements.txt (or pip install CrossMap)")


def ancestral_seq(step, chrom):
    fa = pc.ancestral_fasta(step, chrom)
    with open(fa) as f:
        return "".join(l.strip() for l in f if not l.startswith(">"))


def archaic_vcf(step, name, chrom):
    cfg = step.cfg
    tmpl = cfg.get(f"ARCHAIC_URL_{name}")
    if not tmpl:
        step.fail(f"ARCHAIC_URL_{name} is not set in repo/config.env")
    url = tmpl.format(n=pc.chrom_number(chrom), chrom=chrom)
    dest = pc.data(cfg, "archaic", name, url.rsplit("/", 1)[-1])
    pc.download(step, url, dest)
    if not (Path(str(dest) + ".tbi").exists() or Path(str(dest) + ".csi").exists()):
        try:
            pc.download(step, url + ".tbi", Path(str(dest) + ".tbi"))
        except pc.StepError:
            step.run(["tabix", "-f", "-p", "vcf", str(dest)])
    return dest


def bases(ref, alt, gt):
    alle = [ref] + ([a for a in alt.split(",")] if alt not in (".", "") else [])
    out = set()
    for g in re.split(r"[/|]", gt):
        if g in (".", ""):
            continue
        try:
            a = alle[int(g)]
        except (ValueError, IndexError):
            return None
        if len(a) != 1 or a in ("*", "<"):
            return None
        out.add(a.upper())
    return "".join(sorted(out)) if out else None


def work(step):
    cfg = step.cfg
    pc.require(step, "08-build-cohort")
    cm = crossmap(step)
    chain_url = cfg.get("CHAIN_URL")
    chain = pc.download(step, chain_url, pc.data(cfg, "liftover", chain_url.rsplit("/", 1)[-1]))
    names = cfg.list("ARCHAIC_GENOMES")
    if not any(n.startswith("NEA") for n in names) or not any(n.startswith("DEN") for n in names):
        step.fail("ARCHAIC_GENOMES needs at least one NEA_* and one DEN_* genome")
    per = {}
    chroms = cfg.chromosomes()
    for ci, chrom in enumerate(chroms, 1):
        out = pc.archaic_table(cfg, chrom)
        if pc.nonempty(out):
            per[chrom] = "already built"
            continue
        n = pc.chrom_number(chrom)
        step.progress(f"{chrom}: lifting cohort sites to hg19 ({ci}/{len(chroms)})")
        bed38 = pc.work(cfg, "archaic", f"{chrom}.sites.hg38.bed")
        bed19 = pc.work(cfg, "archaic", f"{chrom}.sites.hg19.bed")
        step.run(f"bcftools query -f '%CHROM\\t%POS0\\t%POS\\t%POS|%REF|%ALT\\n' "
                 f"{q(str(pc.cohort_vcf_gz(cfg, chrom)))}", stdout=bed38)
        step.run([cm, "bed", str(chain), str(bed38), str(bed19)])
        lifted = {}
        for line in open(bed19):
            p = line.split("\t")
            if len(p) < 4 or p[0].replace("chr", "") != n:
                continue
            pos38, ref, alt = p[3].strip().split("|")
            lifted[int(p[2])] = (int(pos38), ref, alt)
        step.log(f"{chrom}: {len(lifted):,} sites lifted to hg19")

        anc = ancestral_seq(step, chrom)
        table = {pos38: [ref, alt, anc[pos38 - 1] if pos38 <= len(anc) else ".", []]
                 for (pos38, ref, alt) in lifted.values()}
        for name in names:
            step.progress(f"{chrom}: reading {name} genotypes")
            vcf = archaic_vcf(step, name, chrom)
            contigs = step.capture(["tabix", "-l", str(vcf)]).split()
            contig = next((c for c in contigs if c.replace("chr", "") == n), None)
            if not contig:
                step.fail(f"{name} VCF has no contig for chromosome {n}")
            regions = pc.work(cfg, "archaic", f"{chrom}.{name}.regions.tsv")
            with open(regions, "w") as f:
                for p19 in sorted(lifted):
                    f.write(f"{contig}\t{p19}\n")
            txt = step.capture(f"bcftools query -T {q(str(regions))} "
                               f"-f '%POS\\t%REF\\t%ALT\\t[%GT]\\n' {q(str(vcf))}")
            got = {}
            for line in txt.splitlines():
                p = line.split("\t")
                if len(p) < 4:
                    continue
                p19 = int(p[0])
                if p19 not in lifted:
                    continue
                pos38, ref38, _ = lifted[p19]
                b = bases(p[1].upper(), p[2].upper(), p[3])
                aref = p[1].upper()
                if b is None:
                    continue
                if aref == ref38.upper():
                    got[pos38] = b
                elif aref.translate(COMP) == ref38.upper():
                    got[pos38] = "".join(sorted(b.translate(COMP)))
            for pos38, row in table.items():
                row[3].append(got.get(pos38, "."))
            step.log(f"{chrom}: {name} has genotypes at {len(got):,} sites")
            regions.unlink(missing_ok=True)
        tmp = Path(str(out) + ".part")
        with open(tmp, "w") as f:
            f.write("\t".join(["pos", "ref", "alt", "anc"] + names) + "\n")
            for pos38 in sorted(table):
                ref, alt, a, vals = table[pos38]
                f.write("\t".join([str(pos38), ref, alt, a] + vals) + "\n")
        tmp.replace(out)
        per[chrom] = {"sites": len(table)}
        step.outputs.append(out)
    step.metrics["per_chromosome"] = per
    return "OK", f"archaic allele tables ready for {len(per)} chromosome(s)"


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
