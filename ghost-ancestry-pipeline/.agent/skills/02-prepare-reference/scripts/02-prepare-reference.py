#!/usr/bin/env python3
"""SKILL 02: get and index the GRCh38 reference genome."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "02-prepare-reference"
GRCH38_LEN = {"chr1": 248956422, "chr7": 159345973, "chr22": 50818468}


def writable_copy(step, fasta):
    """Return a FASTA path whose folder we can write index files into."""
    if os.access(fasta.parent, os.W_OK):
        return fasta
    link = pc.data(step.cfg, "reference", fasta.name)
    if not link.exists():
        link.symlink_to(fasta)
    return link


def work(step):
    cfg = step.cfg
    res = pc.require(step, "01-inspect-input")
    mode = res["01-inspect-input"]["metrics"]["mode"]

    if mode == "alignment_grch38" and cfg.path("INPUT_REFERENCE"):
        # a GRCh38 CRAM must be decoded with its own FASTA, so use it for everything
        fasta = cfg.path("INPUT_REFERENCE")
        source = "INPUT_REFERENCE (the GRCh38 FASTA the CRAM was made with)"
    elif cfg.path("REFERENCE_FASTA"):
        fasta = cfg.path("REFERENCE_FASTA")
        if not fasta.is_file():
            step.fail(f"REFERENCE_FASTA not found: {fasta}")
        source = "REFERENCE_FASTA"
    else:
        url = cfg.get("REFERENCE_URL")
        step.progress("downloading GRCh38 reference (about 3 GB)")
        fasta = pc.download(step, url, pc.data(cfg, "reference", url.rsplit("/", 1)[-1]))
        source = url
    fasta = writable_copy(step, fasta)
    if str(fasta).endswith(".gz"):
        step.warn("reference is gzip-compressed; it must be bgzip-compressed for samtools. "
                  "If faidx fails, decompress it with gunzip and point REFERENCE_FASTA at it.")

    if not Path(str(fasta) + ".fai").exists():
        step.progress("indexing reference with samtools faidx")
        step.run(["samtools", "faidx", str(fasta)])
    lengths = {}
    for line in open(str(fasta) + ".fai"):
        p = line.split("\t")
        lengths[p[0]] = int(p[1])
    for chrom in cfg.chromosomes():
        if chrom not in lengths:
            step.fail(f"{chrom} is not in the reference; the reference must use chr-prefixed "
                      "GRCh38 names (chr1, chr2, ...)")
        if chrom in GRCH38_LEN and lengths[chrom] != GRCH38_LEN[chrom]:
            step.fail(f"{chrom} length {lengths[chrom]} is not GRCh38 ({GRCH38_LEN[chrom]})")

    if mode in ("fastq", "realign"):
        aligner = cfg.get("ALIGNER")
        if aligner == "bwa-mem2":
            done = Path(str(fasta) + ".bwt.2bit.64").exists()
            cmd = ["bwa-mem2", "index", str(fasta)]
        else:
            done = Path(str(fasta) + ".bwt").exists() and Path(str(fasta) + ".sa").exists()
            cmd = ["bwa", "index", str(fasta)]
        if not done:
            step.progress(f"building {aligner} index (about 1 hour, 5 GB RAM for bwa)")
            step.run(cmd)
        step.metrics["aligner_index"] = "ready"

    step.metrics.update({"reference": str(fasta), "source": source,
                         "n_contigs": len(lengths)})
    step.outputs.append(fasta)
    return "OK", f"GRCh38 reference ready: {pc.rel(fasta)}"


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
