#!/usr/bin/env python3
"""SKILL 01 - identify the input type, genome build, chromosome naming and indexes."""
import os
import re
import sys
from pathlib import Path

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "psicommon", Path(__file__).resolve().parents[2] / "lib" / "psi-common.py")
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)

NAME = "01-detect-input"
FASTQ_RE = re.compile(r"\.(fastq|fq)(\.gz)?$", re.I)
VCF_RE = re.compile(r"\.(vcf|vcf\.gz|vcf\.bgz|bcf)$", re.I)


def sniff_type(path):
    low = path.lower()
    if low.endswith(".cram"):
        return "cram"
    if low.endswith(".bam"):
        return "bam"
    if VCF_RE.search(low):
        return "vcf"
    if FASTQ_RE.search(low):
        return "fastq"
    with pc.open_text(path) as fh:
        head = [next(fh, "") for _ in range(40)]
    text = "".join(head)
    if text.startswith("##fileformat=VCF"):
        return "vcf"
    if head and head[0].startswith("@") and len(head) > 2 and head[2].startswith("+"):
        return "fastq"
    if re.search(r"^\"?rs\d+", text, re.M) or re.search(r"rsid", text, re.I):
        return "array"
    return "unknown"


def build_from_lengths(lengths):
    """lengths: {chrom_without_chr: length}. Return (build, evidence)."""
    for build, ref in pc.BUILD_CONTIG_LENGTHS.items():
        hits = [c for c, ln in ref.items() if lengths.get(c) == ln]
        if hits:
            return build, f"contig length match on chr{','.join(hits)}"
    return "", "no contig length matched GRCh37 or GRCh38"


def fai_lengths(fasta):
    fai = fasta + ".fai"
    if not os.path.exists(fai):
        return None
    out = {}
    with open(fai) as f:
        for line in f:
            c = line.split("\t")
            out[c[0]] = int(c[1])
    return out


def find_index(path, kind):
    cands = {"cram": [path + ".crai", re.sub(r"\.cram$", ".crai", path)],
             "bam": [path + ".bai", re.sub(r"\.bam$", ".bai", path), path + ".csi"],
             "vcf": [path + ".tbi", path + ".csi"]}[kind]
    for c in cands:
        if c != path and os.path.exists(c):
            return c
    return ""


def detect_array(sk, path):
    vendor, build_hdr, fmt = "unknown", "", "unknown"
    n_rows = 0
    with pc.open_text(path) as fh:
        header_lines = []
        for line in fh:
            if line.startswith("#"):
                header_lines.append(line)
                continue
            s = line.strip()
            if not s:
                continue
            if s.lower().startswith(("rsid", '"rsid"')):
                fmt = "csv" if "," in s else "tsv"
                continue
            n_rows += 1
            if fmt == "unknown":
                fmt = "csv" if s.count(",") >= 3 else "tsv"
            if n_rows >= 2000:
                break
    hdr = "".join(header_lines)
    if "23andme" in hdr.lower():
        vendor = "23andMe"
    elif "ancestrydna" in hdr.lower() or "ancestry" in hdr.lower():
        vendor = "AncestryDNA"
    elif "myheritage" in hdr.lower():
        vendor = "MyHeritage"
    elif fmt == "csv":
        vendor = "generic_csv"
    m = re.search(r"(?:build|grch)\s*(3[678])", hdr, re.I)
    if m:
        build_hdr = {"36": "NCBI36", "37": "GRCh37", "38": "GRCh38"}[m.group(1)]
    sk.metrics.update({"vendor": vendor, "file_format": fmt, "header_build": build_hdr,
                       "rows_sampled": n_rows})
    if n_rows == 0:
        raise pc.SkillFail("array file has no genotype rows")
    if not build_hdr:
        sk.warn("array header does not state a build; 23andMe and AncestryDNA files are normally GRCh37")
    elif build_hdr == "NCBI36":
        sk.warn("array file is NCBI36 (very old 23andMe); positions will not be used, rsIDs still work")
    return build_hdr or "GRCh37"


def detect_alignment(sk, path, kind, cfg):
    cp = sk.run(["samtools", "view", "-H", path])
    lengths, names, samples = {}, [], set()
    for line in cp.stdout.splitlines():
        if line.startswith("@SQ"):
            f = dict(x.split(":", 1) for x in line.split("\t")[1:] if ":" in x)
            names.append(f["SN"])
            lengths[pc.strip_chr(f["SN"])] = int(f["LN"])
        elif line.startswith("@RG"):
            m = re.search(r"\tSM:([^\t]+)", line)
            if m:
                samples.add(m.group(1))
    if not names:
        raise pc.SkillFail("alignment header has no @SQ lines")
    prefix = "chr" if any(n.lower().startswith("chr") for n in names[:30]) else ""
    build, why = build_from_lengths(lengths)
    sk.metrics.update({"n_contigs": len(names), "read_groups_samples": sorted(samples)})
    if len(samples) > 1:
        sk.warn(f"alignment has {len(samples)} samples in read groups; all reads are pooled as one sample")
    idx = find_index(path, kind)
    if not idx:
        sk.warn(f"no index found next to the {kind.upper()}; 06-genotype-sequence will create one in work_dir")
    return build, why, prefix, idx, lengths


def detect_vcf(sk, path):
    cp = sk.run(["bcftools", "view", "-h", path])
    lengths, names = {}, []
    is_gvcf = False
    for line in cp.stdout.splitlines():
        if line.startswith("##contig"):
            m_id = re.search(r"ID=([^,>]+)", line)
            m_len = re.search(r"length=(\d+)", line)
            if m_id:
                names.append(m_id.group(1))
                if m_len:
                    lengths[pc.strip_chr(m_id.group(1))] = int(m_len.group(1))
        if "NON_REF" in line or "GVCFBlock" in line or 'ID=END,' in line:
            is_gvcf = True
        if line.startswith("##reference="):
            sk.metrics["vcf_reference_line"] = line.split("=", 1)[1][:200]
    samples = sk.run(["bcftools", "query", "-l", path]).stdout.split()
    if not samples:
        raise pc.SkillFail("VCF has no sample columns")
    if len(samples) > 1:
        sk.warn(f"VCF has {len(samples)} samples; the first ({samples[0]}) is used")
    prefix = "chr" if any(n.lower().startswith("chr") for n in names[:30]) else ""
    build, why = build_from_lengths(lengths)
    if not build and "vcf_reference_line" in sk.metrics:
        ref = sk.metrics["vcf_reference_line"].lower()
        if any(k in ref for k in ("grch38", "hg38", "hs38")):
            build, why = "GRCh38", "##reference line"
        elif any(k in ref for k in ("grch37", "hg19", "hs37", "b37")):
            build, why = "GRCh37", "##reference line"
    if not is_gvcf:
        sk.warn("VCF is not a gVCF: sites absent from the file cannot be called homozygous-reference "
                "and will be reported as NOT_IN_VCF")
    sk.metrics.update({"vcf_sample": samples[0], "is_gvcf": is_gvcf})
    idx = find_index(path, "vcf")
    if not idx:
        sk.warn("VCF has no .tbi/.csi index; 06-genotype-sequence will create one in work_dir")
    return build, why, prefix, idx


def pick_reference(sk, cfg, build, prefix, lengths=None):
    ref = cfg["reference"].get(build, "") if build else ""
    if not ref:
        return ""
    if not os.path.exists(ref):
        raise pc.SkillFail(f"reference.{build} points to a missing file: {ref}")
    fl = fai_lengths(ref)
    if fl is None:
        sk.warn(f"reference {pc.rel(ref)} has no .fai index; 06 will try 'samtools faidx'")
        return ref
    fl_norm = {pc.strip_chr(k): v for k, v in fl.items()}
    ref_prefix = "chr" if any(k.lower().startswith("chr") for k in list(fl)[:30]) else ""
    if prefix is not None and ref_prefix != prefix:
        raise pc.SkillFail(f"reference uses '{ref_prefix or 'no'}' chr prefix but the input uses "
                           f"'{prefix or 'no'}' prefix; use a matching reference FASTA")
    if lengths and lengths.get("7") and fl_norm.get("7") and lengths["7"] != fl_norm["7"]:
        raise pc.SkillFail(f"chr7 length differs between input ({lengths['7']}) and reference "
                           f"({fl_norm['7']}); the reference is the wrong build or assembly")
    return ref


def run(sk):
    cfg = pc.load_config()
    path = cfg["input"]["path"]
    if not path or not os.path.exists(path):
        raise pc.SkillFail(f"input.path not set or not found: {path or '(empty)'}")
    itype = (cfg["input"].get("type") or "auto").lower()
    if itype == "auto":
        itype = sniff_type(path)
    if itype not in ("array", "vcf", "bam", "cram", "fastq"):
        raise pc.SkillFail(f"could not identify input type for {pc.rel(path)}; set input.type in the config")
    sk.metrics["input_type"] = itype
    sk.metrics["input_path"] = path
    override = cfg.get("build_override") or ""
    build, why, prefix, idx, ref, r2 = "", "", "", "", "", ""

    if itype == "array":
        build = detect_array(sk, path)
        why = "array header" if sk.metrics.get("header_build") else "default for consumer arrays"
    elif itype in ("bam", "cram"):
        build, why, prefix, idx, lengths = detect_alignment(sk, path, itype, cfg)
        if override:
            build, why = override, "build_override in config"
        if not build:
            raise pc.SkillFail(f"could not tell the build from the {itype.upper()} header ({why}); "
                               "set build_override to GRCh37 or GRCh38")
        ref = pick_reference(sk, cfg, build, prefix, lengths)
        if itype == "cram" and not ref:
            raise pc.SkillFail(f"CRAM input needs reference.{build} set to the FASTA it was compressed against")
        if itype == "bam" and not ref:
            sk.warn(f"reference.{build} not set; BAM genotyping will FAIL in 06 without it")
    elif itype == "vcf":
        build, why, prefix, idx = detect_vcf(sk, path)
        if override:
            build, why = override, "build_override in config"
        if not build:
            raise pc.SkillFail("could not tell the VCF build (no contig lengths or ##reference); set build_override")
    elif itype == "fastq":
        r2 = cfg["input"].get("path_r2") or ""
        if not r2:
            cand = re.sub(r"_R1(\b|_)", r"_R2\1", path)
            cand = cand if cand != path else re.sub(r"_1\.(f(ast)?q)", r"_2.\1", path)
            if cand != path and os.path.exists(cand):
                r2 = cand
        if r2 and not os.path.exists(r2):
            raise pc.SkillFail(f"input.path_r2 not found: {r2}")
        if not r2:
            sk.warn("no R2 file found; FASTQ will be aligned as single-end")
        build = override or cfg["align_build"]
        why = "build_override" if override else "align_build in config"
        ref = cfg["reference"].get(build, "")
        if not ref or not os.path.exists(ref):
            raise pc.SkillFail(f"FASTQ input needs reference.{build}")
        fl = fai_lengths(ref) or {}
        prefix = "chr" if any(k.lower().startswith("chr") for k in list(fl)[:30]) else ""

    if override and itype == "array":
        build, why = override, "build_override in config"
    sk.metrics.update({"build": build, "build_evidence": why, "chrom_prefix": prefix,
                       "index": idx, "reference": ref, "path_r2": r2})
    status = pc.WARN if sk.warnings else pc.OK
    return status, f"{itype} input, {build} ({why})"


if __name__ == "__main__":
    pc.main(NAME, run)
