#!/usr/bin/env python3
"""SKILL 03: align FASTQ reads to GRCh38 (or realign a non-GRCh38 CRAM/BAM).

A GRCh38 CRAM/BAM is used as it is; this skill then only makes sure it is
indexed and reports SKIPPED.
"""
import os
import shlex
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "03-align-reads"
q = shlex.quote


def ensure_index(step, aln, ref):
    for ext in (".crai", ".bai", ".csi"):
        if Path(str(aln) + ext).exists():
            return aln
    if aln.name.endswith(".cram") and Path(str(aln)[:-5] + ".crai").exists():
        return aln
    if aln.name.endswith(".bam") and Path(str(aln)[:-4] + ".bai").exists():
        return aln
    if not os.access(aln.parent, os.W_OK):
        link = pc.work(step.cfg, "align", aln.name)
        if not link.exists():
            link.symlink_to(aln)
        aln = link
    step.progress("indexing alignment file")
    step.run(["samtools", "index", "-@", step.cfg.get("THREADS"), str(aln)])
    return aln


def align(step, r1, r2, ref, out):
    cfg = step.cfg
    t = cfg.int("THREADS")
    sample = cfg.get("SAMPLE_NAME")
    mem_per = max(256, int(cfg.float("MEMORY_GB") * 1024 * 0.6 / max(1, t)))
    tmp = pc.work(cfg, "align", "tmp", "sort")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    rg = f"@RG\\tID:{sample}\\tSM:{sample}\\tPL:ILLUMINA\\tLB:{sample}"
    aligner = "bwa-mem2 mem" if cfg.get("ALIGNER") == "bwa-mem2" else "bwa mem"
    part = Path(str(out) + ".part.cram")
    cmd = (f"{aligner} -t {t} -K 100000000 -Y -R {q(rg)} {q(str(ref))} {q(str(r1))} {q(str(r2))}"
           f" | samtools fixmate -@ 2 -m -u - -"
           f" | samtools sort -@ {t} -m {mem_per}M -T {q(str(tmp))} -u -"
           f" | samtools markdup -@ {t} --reference {q(str(ref))} -O CRAM - {q(str(part))}")
    step.progress("aligning reads (this is the slowest part of this skill; ~1 h per 10x of "
                  "coverage with 8 threads)")
    step.run(cmd)
    part.replace(out)
    step.run(["samtools", "index", "-@", str(t), str(out)])
    shutil.rmtree(tmp.parent, ignore_errors=True)


def work(step):
    cfg = step.cfg
    res = pc.require(step, "01-inspect-input", "02-prepare-reference")
    mode = res["01-inspect-input"]["metrics"]["mode"]
    ref = Path(res["02-prepare-reference"]["metrics"]["reference"])
    sample = cfg.get("SAMPLE_NAME")
    out = pc.work(cfg, "align", f"{sample}.GRCh38.cram")

    if mode == "alignment_grch38":
        aln = ensure_index(step, cfg.path("INPUT_FILE"), ref)
        step.metrics.update({"alignment": str(aln), "aligned_here": False})
        return "SKIPPED", "input is already a GRCh38 alignment; using it directly"

    if pc.nonempty(out) and Path(str(out) + ".crai").exists():
        step.metrics.update({"alignment": str(out), "aligned_here": True})
        return "OK", f"alignment already present: {pc.rel(out)}"

    need = 3 * ((cfg.path("FASTQ_R1").stat().st_size + cfg.path("FASTQ_R2").stat().st_size) / 1e9
                if mode == "fastq" else cfg.path("INPUT_FILE").stat().st_size / 1e9 * 4)
    free = pc.free_gb(out.parent)
    if free < need:
        step.fail(f"only {free:.0f} GB free in {out.parent}, about {need:.0f} GB needed for "
                  "alignment temp files. Free space or point WORK_DIR at a larger disk.")

    if mode == "fastq":
        align(step, cfg.path("FASTQ_R1"), cfg.path("FASTQ_R2"), ref, out)
    else:  # realign
        inp = cfg.path("INPUT_FILE")
        fq1, fq2 = pc.work(cfg, "align", "reads_R1.fq.gz"), pc.work(cfg, "align", "reads_R2.fq.gz")
        if not (pc.nonempty(fq1) and pc.nonempty(fq2)):
            step.progress("extracting read pairs from the existing alignment")
            refopt = f"--reference {q(str(cfg.path('INPUT_REFERENCE')))}" if cfg.path("INPUT_REFERENCE") else ""
            prefix = pc.work(cfg, "align", "collate_tmp")
            t = cfg.get("THREADS")
            step.run(f"samtools collate -@ {t} -O -u {refopt} {q(str(inp))} {q(str(prefix))}"
                     f" | samtools fastq -@ {t} -F 0x900 -1 {q(str(fq1))}.part -2 {q(str(fq2))}.part"
                     f" -0 /dev/null -s /dev/null -n -")
            Path(str(fq1) + ".part").replace(fq1)
            Path(str(fq2) + ".part").replace(fq2)
        align(step, fq1, fq2, ref, out)
        fq1.unlink(missing_ok=True)
        fq2.unlink(missing_ok=True)

    step.metrics.update({"alignment": str(out), "aligned_here": True,
                         "cram_gb": round(out.stat().st_size / 1e9, 1)})
    step.outputs.append(out)
    return "OK", f"reads aligned to GRCh38: {pc.rel(out)}"


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
