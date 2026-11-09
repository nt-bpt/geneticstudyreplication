#!/usr/bin/env python3
"""SKILL 04 - align FASTQ reads to the reference (bwa-mem2 or bwa), mark duplicates, index.

Output: <work_dir>/<label>.<build>.bam (+ .bai). Skipped for non-FASTQ input.
A finished alignment is reused when its input signature matches.
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

NAME = "04-align-fastq"


def index_present(aligner, ref):
    if aligner == "bwa-mem2":
        return os.path.exists(ref + ".bwt.2bit.64")
    return os.path.exists(ref + ".bwt")


def run(sk):
    cfg = pc.load_config()
    det = sk.require("01-detect-input")
    m = det["metrics"]
    if m["input_type"] != "fastq":
        return pc.SKIPPED, f"{m['input_type']} input does not need alignment"

    build, ref = m["build"], m["reference"]
    r1, r2 = m["input_path"], m.get("path_r2") or ""
    want = cfg.get("aligner", "auto")
    aligner = next((a for a in (["bwa-mem2", "bwa"] if want == "auto" else [want]) if pc.which(a)), None)
    if not aligner:
        raise pc.SkillFail("no aligner found (bwa-mem2 or bwa); install one and re-run 00-check-env")
    threads = cfg["threads"]
    work = Path(cfg["work_dir"])
    work.mkdir(parents=True, exist_ok=True)
    label = "".join(ch if ch.isalnum() or ch in "-." else "-" for ch in cfg["sample_label"]) or "sample"
    bam = work / f"{label}.{build}.bam"
    sig = {"r1": r1, "r2": r2, "ref": ref, "aligner": aligner,
           "r1_size": os.path.getsize(r1), "r2_size": os.path.getsize(r2) if r2 else 0}
    done = work / f"{label}.{build}.bam.done.json"
    sk.metrics.update({"aligner": aligner, "build": build, "paired": bool(r2), "threads": threads})

    if bam.exists() and done.exists() and json.loads(done.read_text()) == sig and os.path.exists(str(bam) + ".bai"):
        sk.outputs = {"bam": str(bam)}
        sk.metrics["reused"] = True
        return pc.OK, f"reusing existing alignment {pc.rel(bam)}"

    if not os.path.exists(ref + ".fai"):
        sk.run(["samtools", "faidx", ref])
    if not index_present(aligner, ref):
        if not cfg.get("build_aligner_index"):
            raise pc.SkillFail(f"{aligner} index for {pc.rel(ref)} is missing. Either set "
                               f"build_aligner_index to true (takes about 1 hour; bwa-mem2 needs ~64 GB RAM) "
                               f"or run '{aligner} index {ref}' yourself, then re-run this skill")
        sk.log(f"building {aligner} index (slow)")
        sk.run([aligner, "index", ref])

    rg = f"@RG\\tID:{label}\\tSM:{label}\\tPL:ILLUMINA\\tLB:{label}"
    tmp = work / f"{label}.{build}.tmp"
    reads = shlex.quote(r1) + (" " + shlex.quote(r2) if r2 else "")
    fixmate = f"samtools fixmate -m -@ {threads} - - | " if r2 else ""
    markdup = f" | samtools markdup -@ {threads} - {shlex.quote(str(bam))}" if r2 else ""
    sort_out = "-o - " if r2 else f"-o {shlex.quote(str(bam))} "
    cmd = (f"set -o pipefail; {aligner} mem -t {threads} -R '{rg}' {shlex.quote(ref)} {reads} | "
           f"{fixmate}samtools sort -@ {threads} -m 1G -T {shlex.quote(str(tmp))} {sort_out}-"
           f"{markdup}")
    if not r2:
        sk.warn("single-end reads: duplicates are not marked")
    sk.log("aligning; a 30x genome takes several hours")
    if done.exists():
        done.unlink()
    sk.run(cmd, shell=True)
    sk.run(["samtools", "index", "-@", str(threads), str(bam)])
    fs = sk.run(["samtools", "flagstat", "-@", str(threads), str(bam)]).stdout
    for line in fs.splitlines():
        if " mapped (" in line and "primary" not in line:
            sk.metrics["mapped"] = line.strip()
        if " in total " in line:
            sk.metrics["total_reads"] = line.split()[0]
        if "duplicates" in line and "primary" not in line:
            sk.metrics["duplicates"] = line.split()[0]
    done.write_text(json.dumps(sig) + "\n")
    sk.outputs = {"bam": str(bam)}
    return (pc.WARN if sk.warnings else pc.OK), f"aligned to {build}: {pc.rel(bam)}"


if __name__ == "__main__":
    pc.main(NAME, run)
