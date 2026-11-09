#!/usr/bin/env python3
"""SKILL 01: identify the input (FASTQ pair or CRAM/BAM) and its genome build."""
import gzip
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "01-inspect-input"
# (GRCh38 length, GRCh37 length) for a few chromosomes, used to identify the build
KNOWN = {"1": (248956422, 249250621), "7": (159345973, 159138663),
         "22": (50818468, 51304566), "X": (156040895, 155270560)}


def first_reads(path, n=4000):
    opener = gzip.open if str(path).endswith(".gz") else open
    names, lengths = [], []
    with opener(path, "rt", errors="replace") as f:
        for i, line in enumerate(f):
            if i >= n * 4:
                break
            k = i % 4
            if k == 0:
                if not line.startswith("@"):
                    raise pc.StepError(f"{path} does not look like FASTQ (line {i + 1} lacks '@')")
                names.append(line[1:].split()[0].rsplit("/", 1)[0])
            elif k == 1:
                lengths.append(len(line.strip()))
            elif k == 2 and not line.startswith("+"):
                raise pc.StepError(f"{path} does not look like FASTQ (line {i + 1} lacks '+')")
    return names, lengths


def work(step):
    cfg = step.cfg
    pc.require(step, "00-check-env")
    r1, r2, inp = cfg.path("FASTQ_R1"), cfg.path("FASTQ_R2"), cfg.path("INPUT_FILE")

    if r1 and r2:
        n1, l1 = first_reads(r1)
        n2, l2 = first_reads(r2)
        if not n1 or not n2:
            step.fail("a FASTQ file is empty")
        same = sum(a == b for a, b in zip(n1, n2)) / min(len(n1), len(n2))
        step.metrics.update({"mode": "fastq", "read_length": max(l1 + l2),
                             "read_names_paired_fraction": round(same, 3),
                             "fastq_gb": round((r1.stat().st_size + r2.stat().st_size) / 1e9, 1)})
        if same < 0.95:
            step.fail("FASTQ_R1 and FASTQ_R2 read names do not match in order; they may not be "
                      "a matching pair. Ask the user to check the files.")
        if max(l1) > 1000:
            step.warn("reads longer than 1 kb: this looks like long-read data; bwa is meant for "
                      "short reads. Results may be poor.")
        return "OK", (f"paired FASTQ input, read length {step.metrics['read_length']}; "
                      "reads will be aligned to GRCh38 in skill 03")

    # CRAM / BAM ----------------------------------------------------------
    header = step.capture(["samtools", "view", "-H", str(inp)] +
                          (["-T", str(cfg.path("INPUT_REFERENCE"))] if cfg.path("INPUT_REFERENCE") else []))
    sq, samples, platforms = {}, set(), set()
    for line in header.splitlines():
        f = dict(x.split(":", 1) for x in line.split("\t")[1:] if ":" in x)
        if line.startswith("@SQ"):
            sq[f.get("SN")] = int(f.get("LN", 0))
        elif line.startswith("@RG"):
            samples.add(f.get("SM", "?"))
            platforms.add(f.get("PL", "?"))
    if not sq:
        step.fail("no @SQ lines in the header; the alignment file looks damaged")
    votes = {}
    for n, (l38, l37) in KNOWN.items():
        ln = sq.get("chr" + n) or sq.get(n)
        if ln == l38:
            votes["GRCh38"] = votes.get("GRCh38", 0) + 1
        elif ln == l37:
            votes["GRCh37"] = votes.get("GRCh37", 0) + 1
    build = max(votes, key=votes.get) if len(votes) == 1 else "unknown"
    prefixed = any(k.startswith("chr") for k in sq)
    step.metrics.update({"build": build, "chr_prefix": prefixed, "n_contigs": len(sq),
                         "read_group_samples": sorted(samples), "platforms": sorted(platforms),
                         "input_gb": round(inp.stat().st_size / 1e9, 1)})

    # quick decode test (CRAM needs the right reference)
    cmd = ["samtools", "view", str(inp)]
    if cfg.path("INPUT_REFERENCE"):
        cmd += ["-T", str(cfg.path("INPUT_REFERENCE"))]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    first = p.stdout.readline()
    p.kill()
    err = p.stderr.read()[:300] if not first else ""
    if not first:
        step.fail("could not read any alignments. For a CRAM, INPUT_REFERENCE must be the exact "
                  f"FASTA it was made with. samtools said: {err.strip()}")
    rlen = len(first.split("\t")[9]) if len(first.split("\t")) > 9 else 0
    step.metrics["read_length"] = rlen

    if build == "GRCh38" and prefixed:
        mode = "alignment_grch38"
        verdict = "GRCh38 alignment with chr-prefixed contigs; it will be used directly"
    elif build in ("GRCh38", "GRCh37"):
        mode = "realign"
        verdict = (f"{build} alignment ({'chr' if prefixed else 'no chr'} prefix); reads will be "
                   "extracted and realigned to GRCh38 in skill 03 (several hours)")
        if not pc.have(cfg.get("ALIGNER")):
            step.fail(f"realignment needed but {cfg.get('ALIGNER')} is not installed: "
                      "install it " + pc.INSTALL_TOOLS)
    else:
        step.fail(f"could not identify the genome build from the contig lengths "
                  f"(matches: {votes or 'none'}). Ask the user which reference the file was "
                  "aligned to.")
    step.metrics["mode"] = mode
    if rlen > 1000:
        step.warn("reads longer than 1 kb: long-read data; calling settings assume short reads")
    return "OK", verdict


if __name__ == "__main__":
    pc.run_step(NAME, work)
