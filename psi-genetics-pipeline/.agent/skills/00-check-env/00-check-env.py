#!/usr/bin/env python3
"""SKILL 00 - check tools, Python version, config and free disk space."""
import os
import re
import shutil
import sys
from pathlib import Path

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "psicommon", Path(__file__).resolve().parents[2] / "lib" / "psi-common.py")
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)

NAME = "00-check-env"
CORE_TOOLS = ["bcftools", "samtools", "tabix", "bgzip", "curl"]
GB = 1024 ** 3


def tool_version(sk, tool):
    flag = "--version"
    try:
        cp = sk.run([tool, flag], check=False)
    except FileNotFoundError:
        return None
    text = (cp.stdout or "") + (cp.stderr or "")
    m = re.search(r"(\d+\.\d+(?:\.\d+)?)", text)
    return m.group(1) if m else "unknown"


def guess_input_type(cfg):
    t = (cfg["input"].get("type") or "auto").lower()
    if t != "auto":
        return t
    p = cfg["input"]["path"].lower()
    if p.endswith(".cram"):
        return "cram"
    if p.endswith(".bam"):
        return "bam"
    if re.search(r"\.(vcf|vcf\.gz|bcf|g\.vcf\.gz)$", p):
        return "vcf"
    if re.search(r"\.(fastq|fq)(\.gz)?$", p):
        return "fastq"
    return "array" if p else "unknown"


def free_bytes(path):
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    return shutil.disk_usage(p).free


def run(sk):
    if not pc.CONFIG_PATH.exists():
        pc.write_default_config()
        raise pc.SkillFail("config/run-config.json did not exist; a default was written. "
                           "Set input.path (and reference paths for CRAM/BAM/FASTQ), then re-run.")
    cfg = pc.load_config()
    fails = []

    py = sys.version_info
    sk.metrics["python"] = f"{py.major}.{py.minor}.{py.micro}"
    if py < (3, 8):
        fails.append("python3 >= 3.8 required")

    versions = {}
    for t in CORE_TOOLS:
        if pc.which(t):
            versions[t] = tool_version(sk, t)
        else:
            versions[t] = None
            fails.append(f"missing tool: {t}")
    bcf = versions.get("bcftools")
    if bcf and bcf != "unknown":
        major, minor = (int(x) for x in bcf.split(".")[:2])
        if (major, minor) < (1, 10):
            fails.append(f"bcftools {bcf} is too old; need >= 1.10")

    itype = guess_input_type(cfg)
    sk.metrics["input_type_guess"] = itype
    aligner = None
    if itype == "fastq":
        want = cfg.get("aligner", "auto")
        for cand in (["bwa-mem2", "bwa"] if want == "auto" else [want]):
            if pc.which(cand):
                aligner = cand
                break
        if not aligner:
            fails.append("FASTQ input needs bwa-mem2 or bwa on PATH")
    else:
        for cand in ("bwa-mem2", "bwa"):
            if pc.which(cand):
                aligner = cand
                break
    versions["aligner"] = aligner
    sk.metrics["tools"] = versions

    # input presence
    inp = cfg["input"]["path"]
    if not inp:
        fails.append("input.path is empty in config/run-config.json")
    elif not os.path.exists(inp):
        fails.append(f"input file not found: {inp}")
    sk.metrics["input_path"] = pc.rel(inp) if inp else ""

    # disk space
    in_size = 0
    for p in (cfg["input"]["path"], cfg["input"]["path_r2"]):
        if p and os.path.exists(p):
            in_size += os.path.getsize(p)
    need = {"array": 0.2 * GB, "vcf": 1 * GB, "bam": 2 * GB, "cram": 2 * GB,
            "fastq": in_size * 1.5 + 10 * GB}.get(itype, 1 * GB)
    work = cfg["work_dir"]
    free_work = free_bytes(work)
    free_repo = free_bytes(pc.REPO)
    sk.metrics["disk"] = {
        "work_dir": pc.rel(work),
        "free_work_gb": round(free_work / GB, 1),
        "free_repo_gb": round(free_repo / GB, 1),
        "input_size_gb": round(in_size / GB, 2),
        "estimated_need_gb": round(need / GB, 1),
    }
    if free_work < need:
        fails.append(f"not enough free space in work_dir: {free_work / GB:.1f} GB free, "
                     f"about {need / GB:.1f} GB needed")
    elif free_work < need * 1.5:
        sk.warn(f"work_dir free space is tight ({free_work / GB:.1f} GB free, ~{need / GB:.1f} GB needed)")
    if free_repo < 0.2 * GB:
        fails.append("less than 0.2 GB free in the repo/ workspace")

    # references (only needed for sequence inputs)
    refs = {}
    for b in ("GRCh37", "GRCh38"):
        r = cfg["reference"][b]
        refs[b] = {"path": pc.rel(r) if r else "", "exists": bool(r) and os.path.exists(r),
                   "fai": bool(r) and os.path.exists(r + ".fai")}
    sk.metrics["references"] = refs
    if itype in ("cram", "bam", "fastq"):
        if not any(v["exists"] for v in refs.values()):
            msg = "no reference FASTA configured (reference.GRCh37 / reference.GRCh38)"
            if itype in ("cram", "fastq"):
                fails.append(msg + f"; {itype.upper()} input needs one")
            else:
                sk.warn(msg + "; BAM genotyping needs one to check reference bases")
    if itype == "fastq" and not refs.get(cfg["align_build"], {}).get("exists"):
        fails.append(f"align_build is {cfg['align_build']} but reference.{cfg['align_build']} is not set or missing")

    if not cfg.get("network", True):
        sk.warn("network is disabled in config; P2 coordinates and proxy phasing must come from caches or local files")

    if fails:
        for f in fails:
            sk.log(f"FAIL: {f}")
        sk.metrics["problems"] = fails
        return pc.FAIL, "; ".join(fails)
    return (pc.WARN if sk.warnings else pc.OK,
            f"environment ready for {itype} input ({free_work / GB:.0f} GB free in work_dir)")


if __name__ == "__main__":
    pc.main(NAME, run)
