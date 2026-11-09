#!/usr/bin/env python3
"""SKILL 00: check programs, repo/config.env settings and free disk space."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "00-check-env"


def work(step):
    cfg = step.cfg
    problems = []
    if not cfg.file:
        step.fail("repo/config.env not found. Ask the user to create it "
                  "(copy repo/config.env.example to repo/config.env).")
    step.metrics["config"] = str(cfg.file)

    # input mode ----------------------------------------------------------
    r1, r2, inp = cfg.path("FASTQ_R1"), cfg.path("FASTQ_R2"), cfg.path("INPUT_FILE")
    if (r1 or r2) and inp:
        problems.append("both FASTQ_R1/FASTQ_R2 and INPUT_FILE are set; set only one input type")
    if not (r1 or r2 or inp):
        problems.append("no input set: fill FASTQ_R1 and FASTQ_R2, or INPUT_FILE, in repo/config.env")
    mode = "fastq" if (r1 or r2) else "alignment"
    step.metrics["input_type"] = mode
    if mode == "fastq":
        for k, p in (("FASTQ_R1", r1), ("FASTQ_R2", r2)):
            if not p:
                problems.append(f"{k} is empty")
            elif not p.is_file():
                problems.append(f"{k} file not found: {p}")
    elif inp:
        if not inp.is_file():
            problems.append(f"INPUT_FILE not found: {inp}")
        elif inp.suffix.lower() not in (".cram", ".bam"):
            problems.append(f"INPUT_FILE must be .cram or .bam, got {inp.name}")
        if inp and inp.suffix.lower() == ".cram":
            ref = cfg.path("INPUT_REFERENCE")
            if not ref:
                problems.append("INPUT_REFERENCE is empty; a CRAM can only be read with the FASTA "
                                "it was made with")
            elif not ref.is_file():
                problems.append(f"INPUT_REFERENCE not found: {ref}")

    name = cfg.get("SAMPLE_NAME")
    if not name or any(c.isspace() for c in name):
        problems.append("SAMPLE_NAME must be a single word without spaces")

    try:
        chroms = cfg.chromosomes()
        if not chroms:
            raise ValueError
        step.metrics["chromosomes"] = chroms
        if len(chroms) > 1:
            step.warn(f"{len(chroms)} chromosomes selected. A pilot run on chromosome 22 alone is "
                      "strongly recommended first; ARG building takes days per large chromosome.")
    except ValueError:
        problems.append("CHROMOSOMES could not be read; use e.g. 22, or 20,21,22, or 1-22")

    for key in ("THREADS", "MEMORY_GB", "MIN_DP", "SINGER_WINDOW_BP", "SINGER_JOBS",
                "TRACE_T_GHOST", "TRACE_T_SUPER"):
        try:
            cfg.float(key)
        except ValueError:
            problems.append(f"{key} must be a number, got {cfg.get(key)!r}")

    # programs -----------------------------------------------------------
    core = ["samtools", "bcftools", "bgzip", "tabix"]
    missing = [t for t in core if not pc.have(t)]
    if not (pc.have("curl") or pc.have("wget")):
        missing.append("curl")
    if mode == "fastq":
        aligner = cfg.get("ALIGNER")
        if not pc.have(aligner):
            missing.append(aligner)
    elif not pc.have(cfg.get("ALIGNER")):
        step.warn(f"{cfg.get('ALIGNER')} not installed. It is only needed if the CRAM/BAM turns "
                  "out not to be GRCh38 and must be realigned (skill 01 will tell).")
    if missing:
        problems.append("missing programs: " + " ".join(missing) + ". Install them " +
                        pc.INSTALL_TOOLS)
    for tool in ("samtools", "bcftools"):
        if pc.have(tool):
            v = step.capture([tool, "--version"], check=False).splitlines()
            step.metrics[f"{tool}_version"] = v[0] if v else "unknown"
            m = re.search(r"(\d+)\.(\d+)", v[0] if v else "")
            if m and (int(m.group(1)), int(m.group(2))) < pc.MIN_TOOL_VERSION:
                problems.append(f"{tool} {m.group(0)} is too old; version "
                                f"{pc.MIN_TOOL_VERSION[0]}.{pc.MIN_TOOL_VERSION[1]} or newer is "
                                "needed (older Linux releases ship old versions; use a newer "
                                "release, Homebrew, or build from www.htslib.org)")

    later = []
    if not pc.have(cfg.get("JAVA")):
        later.append("java (skill 07; install it " + pc.INSTALL_JAVA + ")")
    method = cfg.get("ARG_METHOD").lower()
    step.metrics["arg_method"] = method
    if method not in ("relate", "singer"):
        problems.append(f"ARG_METHOD must be relate or singer, got {method!r}")
    elif method == "relate":
        rd = cfg.path("RELATE_DIR")
        if not rd or not (rd / "bin" / "Relate").exists():
            later.append("Relate (skill 10; download from https://myersgroup.github.io/relate/ "
                         "and set RELATE_DIR in repo/config.env to the folder holding bin/ and "
                         "scripts/)")
    else:
        singer = cfg.path("SINGER_DIR")
        if not singer or not (singer / "singer_master").exists():
            later.append("SINGER (skill 10; set SINGER_DIR to the folder holding singer_master)")
    if not (pc.have("CrossMap") or pc.have("CrossMap.py")):
        later.append("CrossMap (skill 12; pip install -r requirements.txt)")
    if not pc.have("unzip") and not pc.have("python3"):
        later.append("unzip")
    py_missing = pc.missing_modules("tskit", "numpy")
    if py_missing:
        later.append(f"Python packages {' '.join(py_missing)} (skill 10; run: {sys.executable} "
                     f"-m pip install {' '.join(py_missing)})")
    step.metrics["python"] = sys.executable
    if later:
        step.warn("not yet installed, needed by later skills: " + "; ".join(later))
    step.metrics["later_tools_missing"] = later

    for key in ("DATA_DIR", "WORK_DIR", "TOOLS_DIR"):
        p = cfg.path(key)
        try:
            p.relative_to(pc.ROOT)
        except ValueError:
            problems.append(f"{key}={p} is outside the repo folder {pc.ROOT}; all pipeline "
                            "files must be under repo/. Use a relative path such as "
                            f"{key.split('_')[0].lower()}")
    step.metrics["repo"] = str(pc.ROOT)
    for k in ("SINGER_CMD_TEMPLATE", "SINGER_CONVERT_TEMPLATE", "TRACE_CMD_TEMPLATE"):
        cfg.template(k)
    for k in ("FASTQ_R1", "FASTQ_R2", "INPUT_FILE", "INPUT_REFERENCE", "REFERENCE_FASTA",
              "SINGER_DIR", "RELATE_DIR", "RELATE_MASK", "BEAGLE_JAR"):
        cfg.path(k)
    for k, v in sorted(cfg.repo_prefixed.items()):
        step.warn(f"{k} in repo/config.env starts with repo/ ({v!r}). Paths in config.env are "
                  "relative to repo/, so the leading repo/ is ignored; remove it to avoid "
                  "confusion.")
    stray = pc.ROOT / "repo"
    if stray.is_dir():
        step.warn(f"found a folder {stray}: earlier runs wrote files to repo/repo/ because of "
                  "a repo/ prefix in config.env. Those files are no longer used; ask the user "
                  "to delete that folder (or move its contents up one level if later skills "
                  "report missing files).")

    # disk and memory ----------------------------------------------------
    need = cfg.float("MIN_FREE_GB")
    for key in ("WORK_DIR", "DATA_DIR"):
        p = cfg.path(key)
        gb = round(pc.free_gb(p), 1)
        step.metrics[f"free_gb_{key.lower()}"] = gb
        if gb < need * 0.3:
            problems.append(f"only {gb} GB free for {key} ({p}); need about {need:.0f} GB")
        elif gb < need:
            step.warn(f"{gb} GB free for {key} is below MIN_FREE_GB={need:.0f}")
    try:
        mem_kb = int([l for l in open("/proc/meminfo") if l.startswith("MemTotal")][0].split()[1])
        mem_gb = round(mem_kb / 1e6, 1)
        step.metrics["ram_gb"] = mem_gb
        if mem_gb < cfg.float("MEMORY_GB"):
            step.warn(f"machine has {mem_gb} GB RAM but MEMORY_GB={cfg.get('MEMORY_GB')}; "
                      "lower MEMORY_GB in repo/config.env")
    except Exception:
        pass
    if not cfg.get("TRACE_CMD_TEMPLATE"):
        step.warn("TRACE_CMD_TEMPLATE is empty. It must be filled in before skill 11 "
                  "(skill 09 downloads the TRACE README that explains the command).")

    if problems:
        step.fail("; ".join(problems))
    return "OK", f"environment ready for {mode} input on {', '.join(step.metrics['chromosomes'])}"


if __name__ == "__main__":
    pc.run_step(NAME, work)
