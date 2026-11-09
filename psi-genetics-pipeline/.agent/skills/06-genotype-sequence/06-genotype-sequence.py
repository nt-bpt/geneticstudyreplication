#!/usr/bin/env python3
"""SKILL 06 - force-genotype every panel site from a BAM/CRAM (or read them from a VCF/gVCF).

BAM/CRAM: bcftools mpileup (region-indexed) + bcftools call -m -C alleles, so homozygous-reference
sites are called explicitly with their read depth. VCF: sites are looked up; absence is only treated
as homozygous-reference inside a gVCF reference block.

Output: results/06-genotypes-sequence.tsv
"""
import json
import os
import shlex
import sys
from pathlib import Path

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "psicommon", Path(__file__).resolve().parents[2] / "lib" / "psi-common.py")
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)

NAME = "06-genotype-sequence"
HEADER = ["study", "rank", "rsid", "gene", "chrom", "pos", "ref", "alt", "genotype", "status",
          "depth", "allele_depths", "gq", "method", "note"]


def build_sites(build):
    tag = "37" if build == "GRCh37" else "38"
    p1 = json.loads((pc.PANELS / "p1-tnrc18.json").read_text())
    sites = []
    for role, study in (("target", "P1"), ("proxy", "P1_proxy")):
        s = p1[role]
        c = s[build]
        sites.append({"study": study, "rank": "", "rsid": s["rsid"], "gene": s.get("gene", "TNRC18"),
                      "chrom": c["chrom"], "pos": c["pos"], "ref": c["ref"], "alt": ",".join(c["alt"])})
    for r in pc.read_tsv(pc.PANELS / "p2-212-snps.tsv"):
        site = {"study": "P2", "rank": r["rank"], "rsid": r["rsid"], "gene": r["gene_reported"],
                "chrom": r[f"chrom{tag}"], "pos": int(r[f"pos{tag}"]) if r[f"pos{tag}"] else None,
                "ref": r[f"ref{tag}"], "alt": r[f"alt{tag}"]}
        sites.append(site)
    return sites


def gt_to_bases(gt, alleles):
    sep = "|" if "|" in gt else "/"
    out = []
    for g in gt.split(sep):
        if g == ".":
            return None
        i = int(g)
        out.append(alleles[i] if i < len(alleles) else "?")
    return "/".join(out)


def check_reference_bases(sk, ref, sites, prefix, work):
    """Compare panel REF with the FASTA base; return the number of mismatches."""
    regions = work / "panel-regions.txt"
    usable = [s for s in sites if s["pos"]]
    regions.write_text("".join(f"{prefix}{s['chrom']}:{s['pos']}-{s['pos']}\n" for s in usable))
    cp = sk.run(["samtools", "faidx", ref, "-r", str(regions)], check=False)
    if cp.returncode != 0:
        raise pc.SkillFail("samtools faidx could not read the panel positions from the reference "
                           "(wrong chromosome names or build?)")
    bases, cur = {}, None
    for line in cp.stdout.splitlines():
        if line.startswith(">"):
            cur = line[1:].strip()
        elif cur:
            bases[cur] = line.strip().upper()
    mism = 0
    for s in usable:
        b = bases.get(f"{prefix}{s['chrom']}:{s['pos']}-{s['pos']}", "")
        if b != s["ref"]:
            s["ref_mismatch"] = b or "?"
            mism += 1
    return mism, len(usable)


def ensure_index(sk, path, kind, idx, work, threads):
    if idx:
        return path if idx in (path + ".crai", path + ".bai", path + ".tbi", path + ".csi") \
            else f"{path}##idx##{idx}"
    ext = {"cram": ".crai", "bam": ".bai", "vcf": ".tbi"}[kind]
    out = work / (Path(path).name + ext)
    if not out.exists():
        sk.log(f"creating index {pc.rel(out)} (one pass over the file)")
        if kind == "vcf":
            sk.run(["bcftools", "index", "-t", "-o", str(out), path])
        else:
            sk.run(["samtools", "index", "-@", str(threads), "-o", str(out), path])
    return f"{path}##idx##{out}"


def genotype_alignment(sk, cfg, aln, kind, ref, prefix, sites, work):
    pos_file = work / "panel.pos.tsv"
    allele_file = work / "panel.alleles.tsv"
    usable = [s for s in sites if s["pos"] and "ref_mismatch" not in s]
    usable.sort(key=lambda s: (s["chrom"], s["pos"]))
    pos_file.write_text("".join(f"{prefix}{s['chrom']}\t{s['pos']}\n" for s in usable))
    allele_file.write_text("".join(f"{prefix}{s['chrom']}\t{s['pos']}\t{s['ref']},{s['alt']}\n"
                                   for s in usable))
    sk.run(["bgzip", "-f", str(allele_file)])
    sk.run(["tabix", "-f", "-s1", "-b2", "-e2", f"{allele_file}.gz"])
    out_vcf = work / "panel-calls.vcf.gz"
    cmd = (f"set -o pipefail; bcftools mpileup -f {shlex.quote(ref)} -R {shlex.quote(str(pos_file))} "
           f"-q {cfg['min_mapq']} -Q {cfg['min_baseq']} --max-depth 2000 -a FORMAT/AD,FORMAT/DP "
           f"-Ou {shlex.quote(aln)} | bcftools call -m -a FORMAT/GQ -C alleles -T {shlex.quote(str(allele_file))}.gz "
           f"-Oz -o {shlex.quote(str(out_vcf))}")
    sk.run(cmd, shell=True)
    q = sk.run(["bcftools", "query", "-f", "%CHROM\t%POS\t%REF\t%ALT[\t%GT\t%DP\t%AD\t%GQ]\n",
                str(out_vcf)]).stdout
    calls = {}
    for line in q.splitlines():
        c = line.split("\t")
        calls[(pc.strip_chr(c[0]), int(c[1]))] = c
    min_dp = cfg["min_depth"]
    for s in sites:
        s["method"] = "bcftools mpileup+call -C alleles"
        if not s["pos"]:
            s.update(status="NO_COORDS", note="no coordinates for this build")
            continue
        if "ref_mismatch" in s:
            s.update(status="REF_MISMATCH", note=f"reference base is {s['ref_mismatch']}, panel REF {s['ref']}")
            continue
        c = calls.get((s["chrom"], s["pos"]))
        if not c:
            s.update(status="NO_COVERAGE", depth=0)
            continue
        alleles = [c[2]] + c[3].split(",")
        gt = gt_to_bases(c[4], alleles)
        dp = int(c[5]) if c[5] not in (".", "") else 0
        s.update(depth=dp, allele_depths=c[6], gq=c[7])
        if gt is None:
            s.update(status="NO_COVERAGE")
        else:
            s.update(genotype=gt, status="CALLED" if dp >= min_dp else "LOW_DEPTH")
            if dp < min_dp:
                s["note"] = f"depth {dp} < min_depth {min_dp}"


def genotype_vcf(sk, cfg, vcf, sample, is_gvcf, prefix, sites, work):
    pos_file = work / "panel.pos.tsv"
    usable = [s for s in sites if s["pos"]]
    pos_file.write_text("".join(f"{prefix}{s['chrom']}\t{s['pos']}\n" for s in usable))
    hdr = sk.run(["bcftools", "view", "-h", vcf]).stdout
    def tag(kind, name):  # bcftools query fails on undefined tags, so substitute "."
        return f"%{'INFO/' if kind == 'INFO' else ''}{name}" if f"##{kind}=<ID={name}," in hdr else "."
    fmt = (f"%CHROM\t%POS\t%REF\t%ALT\t{tag('INFO', 'END')}[\t%GT\t{tag('FORMAT', 'DP')}"
           f"\t{tag('FORMAT', 'AD')}\t{tag('FORMAT', 'GQ')}]\n")
    q = sk.run(["bcftools", "query", "-s", sample, "-R", str(pos_file), "-f", fmt, vcf]).stdout
    recs = {}
    for line in q.splitlines():
        c = line.split("\t")
        recs.setdefault(pc.strip_chr(c[0]), []).append(c)
    min_dp = cfg["min_depth"]
    for s in sites:
        s["method"] = "gVCF lookup" if is_gvcf else "VCF lookup"
        if not s["pos"]:
            s.update(status="NO_COORDS", note="no coordinates for this build")
            continue
        hits = []
        for c in recs.get(s["chrom"], []):
            start = int(c[1])
            end = int(c[4]) if c[4] not in (".", "") else start + len(c[2]) - 1
            if start <= s["pos"] <= end:
                hits.append(c)
        exact = [c for c in hits if int(c[1]) == s["pos"]]
        if not hits:
            s.update(status="NO_COVERAGE" if is_gvcf else "NOT_IN_VCF",
                     note="" if is_gvcf else "absent from VCF: could be homozygous reference or not called")
            continue
        c = exact[0] if exact else hits[0]
        alts = [a for a in c[3].split(",") if a not in ("<NON_REF>", "<*>", "*", ".")]
        gt_field, dp_field = c[5], c[6]
        dp = int(dp_field) if dp_field not in (".", "") else None
        s.update(depth=dp if dp is not None else "", allele_depths=c[7], gq=c[8])
        gts = gt_field.replace("|", "/").split("/")
        if "." in gts:
            s.update(status="NO_CALL")
            continue
        if all(g == "0" for g in gts):
            if exact and c[2] != s["ref"]:
                s.update(status="REF_MISMATCH", note=f"VCF REF {c[2]} vs panel REF {s['ref']}")
                continue
            s.update(genotype="/".join([s["ref"]] * len(gts)), status="CALLED",
                     note="reference block" if not exact or not alts else "")
        elif exact and len(c[2]) == 1:
            if c[2] != s["ref"]:
                s.update(status="REF_MISMATCH", note=f"VCF REF {c[2]} vs panel REF {s['ref']}")
                continue
            alleles = [c[2]] + c[3].split(",")
            s.update(genotype=gt_to_bases(gt_field, alleles), status="CALLED")
        else:
            s.update(status="OVERLAPPING_VARIANT", note=f"site lies inside a {c[2]}>{c[3]} variant at {c[1]}")
            continue
        if dp is not None and dp < min_dp and s["status"] == "CALLED":
            s.update(status="LOW_DEPTH", note=(s.get("note", "") + f" depth {dp} < {min_dp}").strip())


def run(sk):
    cfg = pc.load_config()
    det = sk.require("01-detect-input")
    sk.require("02-prepare-panels")
    m = det["metrics"]
    itype = m["input_type"]
    if itype == "array":
        return pc.SKIPPED, "array input is genotyped by 05-genotype-array"
    work = Path(cfg["work_dir"]) / "genotyping"
    work.mkdir(parents=True, exist_ok=True)
    build, ref, prefix = m["build"], m.get("reference", ""), m.get("chrom_prefix", "")
    path, idx = m["input_path"], m.get("index", "")
    kind = itype
    if itype == "fastq":
        aln = sk.require("04-align-fastq")
        path, idx, kind = aln["outputs"]["bam"], aln["outputs"]["bam"] + ".bai", "bam"
        hdr = sk.run(["samtools", "view", "-H", path]).stdout
        prefix = "chr" if "\tSN:chr" in hdr else ""

    sites = build_sites(build)
    sk.metrics.update({"build": build, "input_type": itype, "chrom_prefix": prefix})

    if kind in ("bam", "cram"):
        if not ref:
            raise pc.SkillFail(f"reference.{build} is required to genotype a {kind.upper()}")
        if not os.path.exists(ref + ".fai"):
            sk.run(["samtools", "faidx", ref])
        mism, n = check_reference_bases(sk, ref, sites, prefix, work)
        sk.metrics["reference_base_mismatches"] = mism
        if n and mism / n > 0.2:
            raise pc.SkillFail(f"{mism}/{n} panel REF alleles disagree with the reference FASTA; "
                               f"the input is probably not {build}. Set build_override or fix the reference")
        if mism:
            sk.warn(f"{mism} panel sites disagree with the reference base and were skipped")
        aln_path = ensure_index(sk, path, kind, idx, work, cfg["threads"])
        genotype_alignment(sk, cfg, aln_path, kind, ref, prefix, sites, work)
    elif kind == "vcf":
        vcf_path = ensure_index(sk, path, "vcf", idx, work, cfg["threads"])
        genotype_vcf(sk, cfg, vcf_path, m["vcf_sample"], m.get("is_gvcf", False), prefix, sites, work)
    else:
        raise pc.SkillFail(f"unsupported input type {itype}")

    out = pc.RESULTS / "06-genotypes-sequence.tsv"
    pc.write_tsv(out, HEADER, sites)
    sk.outputs = {"genotypes": pc.rel(out)}

    def cnt(study, *st):
        return sum(1 for s in sites if s["study"] == study and s.get("status") in st)
    p1 = next(s for s in sites if s["study"] == "P1")
    p2_with_coords = sum(1 for s in sites if s["study"] == "P2" and s["pos"])
    sk.metrics.update({
        "p1_status": p1.get("status"), "p1_genotype": p1.get("genotype", ""), "p1_depth": p1.get("depth", ""),
        "p2_with_coords": p2_with_coords, "p2_called": cnt("P2", "CALLED"),
        "p2_low_depth": cnt("P2", "LOW_DEPTH"),
        "p2_no_coverage": cnt("P2", "NO_COVERAGE", "NOT_IN_VCF", "NO_CALL"),
        "p2_no_coords": cnt("P2", "NO_COORDS"),
    })
    if p1.get("status") not in ("CALLED",):
        sk.warn(f"Paper 1 site rs117910193 status is {p1.get('status')}"
                + (f" (depth {p1.get('depth')})" if p1.get("depth") not in (None, "") else ""))
    if p2_with_coords and cnt("P2", "CALLED") < 0.5 * p2_with_coords:
        sk.warn("fewer than half of the Paper 2 sites were called; check coverage (exome data misses most of them)")
    status = pc.WARN if sk.warnings else pc.OK
    return status, (f"P1 {p1.get('status')} {p1.get('genotype', '')} (depth {p1.get('depth', 0)}); "
                    f"P2 {cnt('P2', 'CALLED')}/{p2_with_coords} called")


if __name__ == "__main__":
    pc.main(NAME, run)
