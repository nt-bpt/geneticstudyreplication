"""Shared helpers for the ghost-ancestry pipeline skills.

Every skill script imports this module (a copy sits next to each script).
It uses only the Python standard library, so it runs on Python 3.8+.

Conventions
-----------
* Folder layout: the agent's working directory holds .agent/skills/ (the
  skills) and repo/ (everything else). ROOT is that repo/ folder: repo/config.env,
  results/, logs/, work/, data/ and tools/ all live under it.
* ADK runs each skill script inside a temporary copy of the skill folder that
  is deleted afterwards, so the script's own location says nothing about
  where repo/ is. repo/ is found from PIPELINE_ROOT if set, else as repo/
  inside the agent's working directory ($PWD) or one of its parents
  (see find_root below).
* Settings come from repo/config.env only.
* Each skill writes results/<skill>.json and logs/<skill>.log.
* status is one of OK, WARN, FAIL, SKIPPED (plus RUNNING for long skills
  that work in the background).
"""
from __future__ import annotations

import bisect
import gzip
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
import time
import traceback
import urllib.request
import zipfile
from pathlib import Path

# The agent framework activates .venv only for the skill's own Python process.
# Commands this pipeline starts through the shell (SINGER's convert_to_tskit,
# CrossMap, TRACE) would otherwise find the system python3 and miss packages.
# Put this Python's bin folder first on PATH for every child process.
_PY_BIN = str(Path(sys.executable).parent)  # not resolved: keep .venv/bin, not the system bin
if os.environ.get("PATH", "").split(os.pathsep)[:1] != [_PY_BIN]:
    os.environ["PATH"] = _PY_BIN + os.pathsep + os.environ.get("PATH", "")
if sys.prefix != sys.base_prefix:
    os.environ.setdefault("VIRTUAL_ENV", sys.prefix)


REPO_DIR = "repo"
SKILLS_DIR = Path(".agent") / "skills"


def find_root():
    """Return (repo folder, how it was found), or (None, reason)."""
    if os.environ.get("PIPELINE_ROOT"):
        p = Path(os.environ["PIPELINE_ROOT"]).expanduser().resolve()
        return (p, "PIPELINE_ROOT") if p.is_dir() else (None, f"PIPELINE_ROOT={p} is not a folder")
    bases = []
    if os.environ.get("PWD"):
        bases.append((Path(os.environ["PWD"]), "working directory ($PWD)"))
    bases.append((Path(os.getcwd()), "current directory"))
    # 1st choice: a folder holding both .agent/skills and repo (the agent's working dir)
    for base, how in bases:
        for d in [base, *base.parents]:
            if (d / REPO_DIR).is_dir() and (d / SKILLS_DIR).is_dir():
                return (d / REPO_DIR).resolve(), how
    # 2nd choice: a repo/ folder directly inside the working directory
    for base, how in bases:
        if (base / REPO_DIR).is_dir():
            return (base / REPO_DIR).resolve(), how
    return None, "no repo/ folder found"


_FOUND_ROOT, ROOT_SOURCE = find_root()
_BASE = Path(os.environ.get("PWD") or os.getcwd())
ROOT = _FOUND_ROOT or (_BASE / REPO_DIR)
RESULTS = ROOT / "results"
LOGS = ROOT / "logs"
DONE_STATUSES = ("OK", "WARN", "SKIPPED")

# --------------------------------------------------------------------------
# Defaults. Every key can be overridden in repo/config.env.
# --------------------------------------------------------------------------
DEFAULTS = {
    # input: set FASTQ_R1 + FASTQ_R2, OR INPUT_FILE (.cram / .bam)
    "FASTQ_R1": "", "FASTQ_R2": "", "INPUT_FILE": "", "INPUT_REFERENCE": "",
    "SAMPLE_NAME": "ME",
    # scope and resources
    "CHROMOSOMES": "22", "THREADS": "8", "MEMORY_GB": "16",
    "DATA_DIR": "data", "WORK_DIR": "work", "TOOLS_DIR": "tools",
    "MIN_FREE_GB": "100",
    # reference genome (GRCh38, chr-prefixed, same build as the 1000G panel)
    "REFERENCE_FASTA": "",
    "REFERENCE_URL": "http://ftp.1000genomes.ebi.ac.uk/vol1/ftp/technical/reference/"
                     "GRCh38_reference_genome/GRCh38_full_analysis_set_plus_decoy_hla.fa",
    "ALIGNER": "bwa",
    # variant calling
    "MIN_DP": "8", "MAX_DP_FACTOR": "2.5", "MIN_MEAN_DEPTH": "10",
    # 1000 Genomes phased panel and cohort
    "PANEL_URL_TEMPLATE": "http://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/"
                          "1000G_2504_high_coverage/working/20220422_3202_phased_SNV_INDEL_SV/"
                          "1kGP_high_coverage_Illumina.{chrom}.filtered.SNV_INDEL_SV_phased_panel.vcf.gz",
    "PANEL_SAMPLES_URL": "http://ftp.1000genomes.ebi.ac.uk/vol1/ftp/data_collections/"
                         "1000G_2504_high_coverage/20130606_g1k_3202_samples_ped_population.txt",
    "COHORT_POPS": "GBR CHB ITU YRI LWK",
    "GENETIC_MAP_URL": "https://bochet.gcc.biostat.washington.edu/beagle/genetic_maps/plink.GRCh38.map.zip",
    # phasing
    "JAVA": "java", "BEAGLE_JAR": "",
    "BEAGLE_URL": "https://faculty.washington.edu/browning/beagle/beagle.27Feb25.75f.jar",
    # ARG inference: relate (default) or singer
    "ARG_METHOD": "relate",
    "RELATE_DIR": "", "RELATE_MU": "1.25e-8", "RELATE_N": "30000", "RELATE_SEED": "1",
    "RELATE_MASK": "", "RELATE_POPSIZE": "1", "RELATE_POPSIZE_ITER": "5",
    # SINGER (ARG inference, ARG_METHOD=singer)
    "SINGER_DIR": "",
    "SINGER_NE": "1e4", "SINGER_MU": "1.2e-8", "SINGER_RATIO": "1",
    "SINGER_WINDOW_BP": "1000000", "SINGER_MIN_SITES": "100",
    "SINGER_N_SAMPLES": "100", "SINGER_THIN": "20", "SINGER_JOBS": "4",
    "SINGER_USE_SAMPLE": "last",
    "SINGER_CMD_TEMPLATE": "{singer_dir}/singer_master -Ne {ne} -m {mu} -ratio {ratio} "
                           "-vcf {vcf_prefix} -output {out_prefix} -start {start} -end {end} "
                           "-n {n_samples} -thin {thin}",
    "SINGER_CONVERT_TEMPLATE": "{singer_dir}/convert_to_tskit -input {out_prefix} "
                               "-output {out_prefix} -start 0 -end {last_sample} -step 1",
    # TRACE
    "TRACE_SOFTWARE_RECORD": "21541833", "TRACE_PIPELINE_RECORD": "20213447",
    "TRACE_DATA_RECORD": "19685110",
    "TRACE_CMD_TEMPLATE": "",
    "TRACE_OUTPUT_COLUMNS": "", "TRACE_STATE_COLUMN": "", "TRACE_ARCHAIC_VALUE": "archaic",
    "TRACE_HAP_IDS": "nodes", "TRACE_POS_OFFSET": "auto",
    "TRACE_T_GHOST": "15000", "TRACE_T_SUPER": "31500",
    "MIN_SEG_KB": "50", "MIN_SEG_CM": "0.05",
    "SUPER_MIN_SEG_KB": "10", "SUPER_MIN_SEG_CM": "0.01",
    # archaic genomes (hg19) for source labelling
    "ARCHAIC_GENOMES": "NEA_ALTAI NEA_VINDIJA NEA_CHAGYRSKAYA DEN_ALTAI",
    "ARCHAIC_URL_NEA_ALTAI": "http://cdna.eva.mpg.de/neandertal/Vindija/VCF/Altai/chr{n}_mq25_mapab100.vcf.gz",
    "ARCHAIC_URL_NEA_VINDIJA": "http://cdna.eva.mpg.de/neandertal/Vindija/VCF/Vindija33.19/chr{n}_mq25_mapab100.vcf.gz",
    "ARCHAIC_URL_NEA_CHAGYRSKAYA": "http://ftp.eva.mpg.de/neandertal/Chagyrskaya/VCF/chr{n}.noRB.vcf.gz",
    "ARCHAIC_URL_DEN_ALTAI": "http://cdna.eva.mpg.de/neandertal/Vindija/VCF/Denisova/chr{n}_mq25_mapab100.vcf.gz",
    "CHAIN_URL": "https://hgdownload.soe.ucsc.edu/goldenPath/hg38/liftOver/hg38ToHg19.over.chain.gz",
    "ANCESTRAL_URL": "https://ftp.ensembl.org/pub/release-112/fasta/ancestral_alleles/"
                     "homo_sapiens_ancestor_GRCh38.tar.gz",
    "ANCESTRAL_ALLOW_LOWCONF": "0",
    "LABEL_DELTA": "0.15", "MIN_DERIVED_SITES": "5", "SUPER_MAX_AFFINITY": "0.25",
    # annotation
    "GENCODE_URL": "https://ftp.ebi.ac.uk/pub/databases/gencode/Gencode_human/release_47/"
                   "gencode.v47.basic.annotation.gtf.gz",
}

# How to install the command-line tools (no conda needed).
INSTALL_TOOLS = ("on Debian/Ubuntu: sudo apt install samtools bcftools tabix bwa curl; "
                 "on Fedora: sudo dnf install samtools bcftools htslib-tools bwa curl; "
                 "on macOS: brew install samtools bcftools htslib bwa")
INSTALL_JAVA = ("on Debian/Ubuntu: sudo apt install default-jre; on Fedora: sudo dnf install "
                "java-21-openjdk; on macOS: brew install openjdk")
MIN_TOOL_VERSION = (1, 13)  # samtools / bcftools

# Genes named in the paper's main text, with where they were mentioned.
PAPER_GENES = {
    "CSMD1": "ghost ancestry high-frequency peak (main text)",
    "RBFOX1": "ghost ancestry high-frequency peak (main text)",
    "CSNK2A2IP": "ghost peak ~20% in chr3 Neanderthal desert (fig. S40)",
    "RNF39": "super-archaic tract >70% in MHC (Fig. 4B)",
    "PPP1R11": "super-archaic tract >70% in MHC (Fig. 4B)",
    "POLR1H": "super-archaic tract >70% in MHC (Fig. 4B)",
    "CYP24A1": "super-archaic tract, vitamin D degradation (fig. S54)",
}
for _g in ("BCAP29 NRCAM IMMP2L IFRD1 THAP5 FOXP2 TFEC TES KCND2 TSPAN12 ING3 "
           "FAM3C FEZF1 TAS2R16 IQUB NDUFA5 FSCN3 IMPDH1").split():
    PAPER_GENES.setdefault(_g, "chr7 archaic desert with 13.3% ghost peak (Fig. 3B)")

# Genes with a documented neurodevelopmental role in the wider literature
# (NOT a claim made by the paper itself).
NEURO_LITERATURE_GENES = {"FOXP2", "RBFOX1", "NRCAM", "IMMP2L", "KCND2", "FEZF1", "CSMD1"}


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
def find_config():
    c = ROOT / "config.env"  # ROOT is repo/, so this is repo/config.env only
    return c.resolve() if c.is_file() else None


def parse_env(path):
    out = {}
    for raw in Path(path).read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        if val[:1] in ("'", '"'):
            q = val[0]
            end = val.find(q, 1)
            val = val[1:end] if end > 0 else val[1:]
        else:
            val = re.sub(r"(^|\s+)#.*$", "", val).strip()
        out[key] = val
    return out


# Paths in config.env are relative to repo/. A value written relative to the
# working directory instead ("repo/work") would otherwise become repo/repo/work.
_REPO_PREFIXES = ("./repo/", "repo/")
_REPO_TOKEN = re.compile(r"(^|[\s'\"=])(?:\./)?repo/")


def strip_repo_prefix(value, key=None, record=None):
    v = value.replace("\\", "/")
    for pre in _REPO_PREFIXES:
        if v.startswith(pre):
            if record is not None and key:
                record[key] = value
            return v[len(pre):] or "."
    if v in ("repo", "./repo"):
        if record is not None and key:
            record[key] = value
        return "."
    return value


class Config:
    def __init__(self):
        self.file = find_config()
        self.repo_prefixed = {}  # settings written as repo/... (relative to the working dir)
        self.values = dict(DEFAULTS)
        if self.file:
            self.values.update(parse_env(self.file))

    def get(self, key, default=""):
        v = self.values.get(key, default)
        return default if v is None else str(v)

    def int(self, key):
        return int(float(self.get(key)))

    def float(self, key):
        return float(self.get(key))

    def list(self, key):
        return [x for x in re.split(r"[\s,]+", self.get(key)) if x]

    def path(self, key):
        v = self.get(key)
        if not v:
            return None
        p = Path(os.path.expandvars(v)).expanduser()
        if not p.is_absolute():
            p = Path(strip_repo_prefix(str(p), key, self.repo_prefixed))
        return (p if p.is_absolute() else ROOT / p).resolve()

    def template(self, key):
        """A command template with any "repo/..." path tokens made relative to repo/.
        Commands run from repo/, so relative paths in templates resolve there."""
        t = self.get(key)
        fixed = _REPO_TOKEN.sub(r"\1", t)
        if fixed != t:
            self.repo_prefixed[key] = t
        return fixed

    def chromosomes(self):
        out = []
        for part in self.list("CHROMOSOMES"):
            part = part.replace("chr", "")
            if "-" in part:
                a, b = part.split("-", 1)
                out += [str(i) for i in range(int(a), int(b) + 1)]
            else:
                out.append(part)
        seen, res = set(), []
        for c in out:
            name = "chr" + c
            if name not in seen:
                seen.add(name)
                res.append(name)
        return res

    def dir(self, key):
        p = self.path(key)
        p.mkdir(parents=True, exist_ok=True)
        return p


def chrom_number(chrom):
    return chrom[3:] if chrom.startswith("chr") else chrom


# --------------------------------------------------------------------------
# Step object: logging, commands, result JSON
# --------------------------------------------------------------------------
class StepError(Exception):
    pass


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str))
    tmp.replace(path)


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return None


def prev_result(name):
    return read_json(RESULTS / f"{name}.json")


class Step:
    def __init__(self, name, worker=False):
        self.name = name
        self.worker = worker
        RESULTS.mkdir(parents=True, exist_ok=True)
        LOGS.mkdir(parents=True, exist_ok=True)
        self.cfg = Config()
        self.log_path = LOGS / f"{name}.log"
        self.json_path = RESULTS / f"{name}.json"
        self.metrics, self.warnings, self.outputs, self.extra = {}, [], [], {}
        self.t0 = time.time()
        self._fh = open(self.log_path, "a", buffering=1)
        self.log(f"===== {name} start {time.strftime('%Y-%m-%d %H:%M:%S')} "
                 f"root={ROOT} config={self.cfg.file}")

    # logging -------------------------------------------------------------
    def log(self, msg, echo=False):
        line = f"[{time.strftime('%H:%M:%S')}] {msg}"
        self._fh.write(line + "\n")
        self._fh.flush()
        if echo and not self.worker:
            print(line, flush=True)

    def progress(self, msg):
        self.log("PROGRESS: " + msg)

    def warn(self, msg):
        if msg not in self.warnings:
            self.warnings.append(msg)
        self.log("WARNING: " + msg)

    def fail(self, msg):
        raise StepError(msg)

    def tail(self, n=8):
        try:
            lines = [l for l in self.log_path.read_text(errors="replace").splitlines() if l.strip()]
            return " | ".join(lines[-n:])
        except Exception:
            return ""

    # commands ------------------------------------------------------------
    @staticmethod
    def _args(cmd):
        if isinstance(cmd, (list, tuple)):
            args = [str(c) for c in cmd]
            return args, " ".join(shlex.quote(a) for a in args)
        return ["bash", "-o", "pipefail", "-c", cmd], cmd

    def run(self, cmd, stdout=None, cwd=None, check=True, log_path=None):
        """Run a command. stderr (and stdout unless redirected) go to the log."""
        args, shown = self._args(cmd)
        self.log("$ " + shown, echo=False)
        self._fh.flush()
        target_log = open(log_path, "a") if log_path else self._fh
        out_fh = open(stdout, "wb") if stdout else target_log
        try:
            p = subprocess.run(args, stdout=out_fh, stderr=target_log, cwd=cwd)
        finally:
            if stdout:
                out_fh.close()
            if log_path:
                target_log.close()
        if check and p.returncode != 0:
            where = f" (see {log_path})" if log_path else ""
            # quote the program's own output (its log file), not the pipeline log
            last = tail_file(log_path) if log_path else self.tail()
            raise StepError(f"command failed (exit {p.returncode}{exit_hint(p.returncode)}){where}: "
                            f"{shown[:300]} -- last log lines: {last or '(the program printed nothing)'}")
        return p.returncode

    def capture(self, cmd, check=True):
        args, shown = self._args(cmd)
        self.log("$ " + shown, echo=False)
        self._fh.flush()
        p = subprocess.run(args, stdout=subprocess.PIPE, stderr=self._fh, text=True,
                           errors="replace")
        if check and p.returncode != 0:
            raise StepError(f"command failed (exit {p.returncode}): {shown[:300]} "
                            f"-- last log lines: {self.tail()}")
        return p.stdout

    # result --------------------------------------------------------------
    def finish(self, status, verdict):
        data = {
            "skill": self.name, "status": status, "verdict": verdict,
            "metrics": self.metrics, "warnings": self.warnings,
            "outputs": [rel(o) for o in self.outputs],
            "log": rel(self.log_path),
            "elapsed_seconds": round(time.time() - self.t0, 1),
            "finished": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        data.update(self.extra)
        write_json(self.json_path, data)
        self.log(f"===== {self.name} {status}: {verdict}")
        if not self.worker:
            print(json.dumps(data, indent=1, default=str), flush=True)
        self._fh.close()
        return data


def is_python_script(path):
    try:
        with open(path, "rb") as f:
            first = f.readline(200)
        return first.startswith(b"#!") and b"python" in first
    except OSError:
        return False


def use_own_python(cmd):
    """If a command starts with a Python script (e.g. SINGER's convert_to_tskit),
    run it with this pipeline's Python. Its "#!/usr/bin/env python3" line could
    otherwise pick a different Python that lacks the needed packages (tskit)."""
    parts = shlex.split(cmd)
    if parts and is_python_script(parts[0]):
        return shlex.quote(sys.executable) + " " + cmd
    return cmd


def missing_modules(*names):
    """Modules that this pipeline's Python cannot import."""
    import importlib.util
    return [n for n in names if importlib.util.find_spec(n) is None]


ATTEMPT_MARK = "===== attempt started "


def ancestral_fasta(step, chrom):
    """Path to the Ensembl ancestral-allele FASTA for one chromosome (downloaded once)."""
    cfg = step.cfg
    n = chrom_number(chrom)
    url = cfg.get("ANCESTRAL_URL")
    adir = data(cfg, "ancestral", "x").parent
    fa = next(adir.rglob(f"*ancestor_{n}.fa"), None)
    if not fa:
        tarp = download(step, url, data(cfg, "ancestral", url.rsplit("/", 1)[-1]))
        extract(step, tarp, adir, members=[f"_ancestor_{n}.fa"])
        fa = next(adir.rglob(f"*ancestor_{n}.fa"), None)
        if not fa:
            step.fail(f"no ancestral FASTA for {chrom} inside {rel(tarp)}")
    return fa


def tail_file(path, n=8):
    """Last lines of a log, counting only the newest attempt."""
    try:
        lines = [l.strip() for l in Path(path).read_text(errors="replace").splitlines() if l.strip()]
        starts = [i for i, l in enumerate(lines) if l.startswith(ATTEMPT_MARK)]
        if starts:
            lines = lines[starts[-1] + 1:]
        return " | ".join(lines[-n:])
    except Exception:
        return ""


def exit_hint(code):
    """Plain meaning of common exit codes."""
    if code in (-9, 137):
        return ": killed, usually out of memory; lower SINGER_JOBS or THREADS"
    if code in (-11, 139):
        return ": crashed (segmentation fault), often bad or unexpected input"
    if code in (-6, 134):
        return ": aborted, often an internal check in the program failed"
    if code == 127:
        return ": program or a program it calls was not found"
    if code == 126:
        return ": file is not executable (check permissions, or wrong platform)"
    if code < 0:
        return f": stopped by signal {-code}"
    return ""


def rel(p):
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except Exception:
        return str(p)


# --------------------------------------------------------------------------
# Running a skill (foreground or background)
# --------------------------------------------------------------------------
def _execute(name, work, worker):
    step = Step(name, worker=worker)
    try:
        status, verdict = work(step)
    except StepError as e:
        status, verdict = "FAIL", str(e)
    except KeyboardInterrupt:
        status, verdict = "FAIL", "interrupted"
    except Exception as e:  # noqa: BLE001
        step.log(traceback.format_exc(), echo=False)
        status, verdict = "FAIL", f"unexpected error {type(e).__name__}: {e} (traceback in log)"
    if status == "WARN" and not step.warnings:
        status = "OK"
    if status == "OK" and step.warnings:
        status = "WARN"
    step.finish(status, verdict)
    if worker:
        try:
            (LOGS / f"{name}.pid").unlink()
        except FileNotFoundError:
            pass
    # Always exit 0: the status is in the JSON. A non-zero exit makes ADK treat
    # the call as a tool error and can hide the JSON from the agent.


def _pid_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:  # treat zombies as dead
        st = Path(f"/proc/{pid}/stat").read_text().split()
        if len(st) > 2 and st[2] == "Z":
            return False
    except Exception:
        pass
    return True


def _last_progress(name):
    try:
        lines = (LOGS / f"{name}.log").read_text(errors="replace").splitlines()
    except Exception:
        return "none yet"
    start = 0
    for i, l in enumerate(lines):
        if f"===== {name} start" in l:
            start = i
    for l in reversed(lines[start:]):
        if "PROGRESS:" in l:
            return l.split("PROGRESS:", 1)[1].strip()
    return "none yet"


def _controller(name, script):
    RESULTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)
    jpath, ppath = RESULTS / f"{name}.json", LOGS / f"{name}.pid"
    prev = read_json(jpath) or {}
    status = prev.get("status")
    pid = None
    if ppath.exists():
        try:
            pid = int(ppath.read_text().strip())
        except ValueError:
            pid = None

    def emit(data, code=0):
        write_json(jpath, data)
        print(json.dumps(data, indent=1, default=str), flush=True)
        sys.exit(0)

    if status in DONE_STATUSES:
        prev["note"] = (f"already finished. To force a fresh run delete results/{name}.json "
                        "and run this skill again.")
        print(json.dumps(prev, indent=1, default=str), flush=True)
        sys.exit(0)

    if pid and _pid_alive(pid):
        started = prev.get("started", time.time())
        hours = (time.time() - started) / 3600
        prev.update({"skill": name, "status": "RUNNING",
                     "verdict": f"still running in the background (pid {pid}, {hours:.1f} h so far). "
                                f"Last progress: {_last_progress(name)}"})
        emit(prev)

    if status == "RUNNING":
        prev.update({"status": "FAIL", "reported": True,
                     "verdict": "the background worker stopped without finishing (killed, machine "
                                "restarted, or out of memory). Check the log, then run this skill "
                                "again to resume; finished parts are kept."})
        try:
            ppath.unlink()
        except FileNotFoundError:
            pass
        emit(prev, 1)

    if status == "FAIL" and not prev.get("reported"):
        prev["reported"] = True
        emit(prev, 1)

    # start (or restart) a background worker
    data = {"skill": name, "status": "RUNNING", "started": time.time(),
            "verdict": "started in the background. This skill takes a long time; run it "
                       "again later to check progress. Do not start the next skill yet.",
            "metrics": {}, "warnings": [], "log": rel(LOGS / f"{name}.log")}
    write_json(jpath, data)
    # ADK deletes the folder this script runs from as soon as the call returns,
    # so the worker runs from a persistent copy inside the pipeline folder.
    runtime = ROOT / ".skill_runtime" / name
    shutil.rmtree(runtime, ignore_errors=True)
    shutil.copytree(Path(script).resolve().parent, runtime,
                    ignore=shutil.ignore_patterns("__pycache__"))
    worker_script = runtime / Path(script).name
    env = dict(os.environ, PIPELINE_ROOT=str(ROOT))
    with open(LOGS / f"{name}.log", "a") as errlog:
        p = subprocess.Popen([sys.executable, str(worker_script), "--worker"],
                             cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=errlog, start_new_session=True)
    ppath.write_text(str(p.pid))
    data["verdict"] = f"started in the background (pid {p.pid}). " + data["verdict"].split(". ", 1)[1]
    emit(data)


def _root_problem():
    if _FOUND_ROOT is not None:
        return None
    return (f"cannot find the repo folder ({ROOT_SOURCE}; looked for repo/ next to "
            f".agent/skills/ from {_BASE}). Ask the user to start the agent from the "
            "working directory that contains .agent/skills/ and repo/, or to set the "
            "PIPELINE_ROOT environment variable to the repo folder.")


def run_step(name, work, background=False):
    """Entry point used by every skill script."""
    script = sys._getframe(1).f_globals.get("__file__") or sys.argv[0]
    problem = _root_problem()
    if problem:
        print(json.dumps({"skill": name, "status": "FAIL", "verdict": problem,
                          "metrics": {"root_tried": str(ROOT), "root_source": ROOT_SOURCE},
                          "warnings": []}, indent=1), flush=True)
        sys.exit(0)
    worker = "--worker" in sys.argv
    if background and not worker and os.environ.get("PIPELINE_FOREGROUND") != "1":
        _controller(name, script)
    else:
        _execute(name, work, worker=worker)


# --------------------------------------------------------------------------
# Results of earlier skills
# --------------------------------------------------------------------------
def require(step, *names):
    out = {}
    for n in names:
        r = prev_result(n)
        if not r:
            step.fail(f"skill {n} has not been run yet. Run {n} first.")
        if r.get("status") not in DONE_STATUSES:
            step.fail(f"skill {n} has status {r.get('status')}. Finish {n} before this skill.")
        out[n] = r
    return out


def metric(name, key, default=None):
    r = prev_result(name) or {}
    return (r.get("metrics") or {}).get(key, default)


# --------------------------------------------------------------------------
# Files, downloads, tools
# --------------------------------------------------------------------------
def have(tool):
    return shutil.which(tool) is not None


def free_gb(path):
    p = Path(path)
    while not p.exists() and p != p.parent:
        p = p.parent
    return shutil.disk_usage(p).free / 1e9


def nonempty(path):
    p = Path(path)
    return p.exists() and p.stat().st_size > 0


def download(step, url, dest):
    dest = Path(dest)
    if nonempty(dest):
        step.log(f"already downloaded: {rel(dest)}", echo=False)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    step.log(f"downloading {url}")
    if have("curl"):
        step.run(["curl", "-fL", "--retry", "5", "--retry-delay", "15", "-C", "-",
                  "-sS", "-o", str(part), url])
    elif have("wget"):
        step.run(["wget", "-c", "-q", "-O", str(part), url])
    else:
        with urllib.request.urlopen(url) as r, open(part, "wb") as f:
            shutil.copyfileobj(r, f, 1 << 20)
    if not nonempty(part):
        step.fail(f"download produced an empty file: {url}")
    part.replace(dest)
    return dest


def extract(step, archive, dest_dir, members=None):
    archive, dest_dir = Path(archive), Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = archive.name.lower()
    if name.endswith(".zip"):
        with zipfile.ZipFile(archive) as z:
            for m in z.namelist():
                if members and not any(x in m for x in members):
                    continue
                target = (dest_dir / m).resolve()
                if not str(target).startswith(str(dest_dir.resolve())):
                    continue
                z.extract(m, dest_dir)
    elif name.endswith((".tar.gz", ".tgz", ".tar", ".tar.bz2")):
        with tarfile.open(archive) as t:
            safe = []
            for m in t.getmembers():
                if members and not any(x in m.name for x in members):
                    continue
                target = (dest_dir / m.name).resolve()
                if not str(target).startswith(str(dest_dir.resolve())) or m.issym() or m.islnk():
                    continue
                safe.append(m)
            t.extractall(dest_dir, members=safe)
    else:
        step.log(f"not an archive, left as is: {rel(archive)}", echo=False)
    return dest_dir


def open_text(path):
    path = str(path)
    if path.endswith(".gz") or path.endswith(".bgz"):
        return gzip.open(path, "rt", errors="replace")
    return open(path, "r", errors="replace")


def index_vcf(step, path):
    path = Path(path)
    if not (Path(str(path) + ".tbi").exists() or Path(str(path) + ".csi").exists()):
        step.run(["bcftools", "index", "-f", "-t", str(path)])


def vcf_count(step, path):
    out = step.capture(["bcftools", "index", "-n", str(path)], check=False).strip()
    try:
        return int(out)
    except ValueError:
        return int(step.capture(f"bcftools view -H {shlex.quote(str(path))} | wc -l").strip())


# --------------------------------------------------------------------------
# Standard locations shared between skills
# --------------------------------------------------------------------------
def work(cfg, *parts):
    p = cfg.dir("WORK_DIR").joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def data(cfg, *parts):
    p = cfg.dir("DATA_DIR").joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def tools(cfg, *parts):
    p = cfg.dir("TOOLS_DIR").joinpath(*parts)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def map_file(cfg, chrom):
    return work(cfg, "maps", f"{chrom}.map")


def cohort_vcf_gz(cfg, chrom):
    return work(cfg, "cohort", chrom, "cohort.vcf.gz")


def archaic_table(cfg, chrom):
    return work(cfg, "archaic", f"{chrom}.archaic.tsv")


# --------------------------------------------------------------------------
# Genetic map (PLINK format: chrom  id  cM  bp)
# --------------------------------------------------------------------------
class GeneticMap:
    def __init__(self, path):
        self.bp, self.cm = [], []
        with open_text(path) as f:
            for line in f:
                p = line.split()
                if len(p) < 4:
                    continue
                try:
                    self.bp.append(int(p[3]))
                    self.cm.append(float(p[2]))
                except ValueError:
                    continue
        if len(self.bp) < 2:
            raise StepError(f"genetic map {path} has fewer than two usable lines")

    def at(self, pos):
        bp, cm = self.bp, self.cm
        if pos <= bp[0]:
            return cm[0]
        if pos >= bp[-1]:
            return cm[-1]
        i = bisect.bisect_right(bp, pos)
        x0, x1, y0, y1 = bp[i - 1], bp[i], cm[i - 1], cm[i]
        return y0 if x1 == x0 else y0 + (y1 - y0) * (pos - x0) / (x1 - x0)

    def length(self, start, end):
        return max(0.0, self.at(end) - self.at(start))


# --------------------------------------------------------------------------
# Segment files (TRACE output, published tracts)
# --------------------------------------------------------------------------
_COLS = {
    "chrom": ("chrom", "chr", "chromosome", "contig", "seqname", "#chrom", "#chr"),
    "start": ("start", "begin", "left", "start_pos", "pos_start", "chromstart", "start_bp"),
    "end": ("end", "stop", "right", "end_pos", "pos_end", "chromend", "end_bp"),
    "hap": ("hap", "haplotype", "sample", "node", "sample_id", "focal", "hap_id", "individual"),
    "label": ("label", "ancestry", "source", "type", "state", "class", "origin"),
}


def _is_num(x):
    try:
        float(x)
        return True
    except ValueError:
        return False


def parse_segment_file(path, default_chrom=None, columns=None, state_col="", archaic_value="archaic"):
    """Return list of dicts {chrom,start,end,hap,label}. Raises StepError if unreadable."""
    rows = []
    with open_text(path) as f:
        lines = [l.rstrip("\n") for l in f if l.strip() and not l.startswith("##")]
    if not lines:
        return rows
    delim = "\t" if "\t" in lines[0] else ("," if "," in lines[0] else None)
    split = (lambda s: s.split(delim)) if delim else (lambda s: s.split())
    first = [c.strip() for c in split(lines[0])]
    idx = {}
    body = lines
    if columns:
        for i, c in enumerate(columns):
            if c and c != "-":
                idx[c] = i
        if not all(_is_num(x) for x in [first[idx["start"]]] if "start" in idx):
            body = lines[1:]
    elif not any(_is_num(x) for x in first[1:3]) or first[0].startswith("#"):
        low = [c.lower().lstrip("#") for c in first]
        for key, names in _COLS.items():
            for i, c in enumerate(low):
                if c in [n.lstrip("#") for n in names] and key not in idx:
                    idx[key] = i
        if state_col and state_col.lower() in low:
            idx["label"] = low.index(state_col.lower())
        body = lines[1:]
    else:
        idx = {"chrom": 0, "start": 1, "end": 2}
        if len(first) > 3:
            idx["hap"] = 3
    if "start" not in idx or "end" not in idx:
        raise StepError(f"cannot find start/end columns in {path}. First line: {lines[0][:200]!r}. "
                        "Set TRACE_OUTPUT_COLUMNS in repo/config.env, e.g. chrom,start,end,hap")
    for line in body:
        p = [c.strip() for c in split(line)]
        try:
            start, end = int(float(p[idx["start"]])), int(float(p[idx["end"]]))
        except (ValueError, IndexError):
            continue
        chrom = p[idx["chrom"]] if "chrom" in idx and idx["chrom"] < len(p) else default_chrom
        if chrom and not str(chrom).startswith("chr") and _is_num(chrom):
            chrom = "chr" + str(chrom)
        label = p[idx["label"]] if "label" in idx and idx["label"] < len(p) else ""
        if state_col and label and label.lower() != archaic_value.lower():
            continue
        rows.append({"chrom": chrom, "start": min(start, end), "end": max(start, end),
                     "hap": p[idx["hap"]] if "hap" in idx and idx["hap"] < len(p) else "NA",
                     "label": label})
    return rows


def merge_segments(segs, gap=1):
    """Merge overlapping/adjacent segments with the same chrom and hap."""
    out = []
    for s in sorted(segs, key=lambda x: (x["chrom"], str(x["hap"]), x["start"])):
        if out and out[-1]["chrom"] == s["chrom"] and out[-1]["hap"] == s["hap"] \
                and s["start"] <= out[-1]["end"] + gap:
            out[-1]["end"] = max(out[-1]["end"], s["end"])
        else:
            out.append(dict(s))
    return out


def write_tsv(path, rows, cols):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write("\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(r.get(c, "")) for c in cols) + "\n")
    return path


def read_tsv(path):
    with open_text(path) as f:
        header = f.readline().rstrip("\n").split("\t")
        return [dict(zip(header, l.rstrip("\n").split("\t"))) for l in f if l.strip()]


# --------------------------------------------------------------------------
# TRACE runner (used by skills 11 and 14)
# --------------------------------------------------------------------------
def read_windows(cfg):
    idx = work(cfg, "arg", "trees_index.tsv")
    if not idx.exists():
        raise StepError("work/arg/trees_index.tsv is missing. Run 10-build-arg first.")
    return [dict(r, start=int(r["start"]), end=int(r["end"])) for r in read_tsv(idx)]


def run_trace_windows(step, t, tag, windows):
    cfg = step.cfg
    tmpl = cfg.template("TRACE_CMD_TEMPLATE")
    if not tmpl:
        step.fail("TRACE_CMD_TEMPLATE is empty. Ask the user to set it in repo/config.env after "
                  "reading the TRACE README listed in results/09-fetch-trace.json.")
    nodes = metric("08-build-cohort", "user_hap_nodes") or []
    hap_file = work(cfg, "cohort", "user_hap_nodes.txt")
    trace_dir = metric("09-fetch-trace", "trace_software_dir", "")
    out_files = []
    for i, w in enumerate(windows, 1):
        out = work(cfg, "trace", tag, w["chrom"], f"w{w['start']}.out")
        if nonempty(out):
            out_files.append((w, out))
            continue
        cmd = tmpl.format(trees=w["trees"], chrom=w["chrom"], start=w["start"], end=w["end"],
                          haps=",".join(str(n) for n in nodes), hap_file=hap_file, t=t,
                          out=out, threads=cfg.get("THREADS"), trace_dir=trace_dir,
                          map=map_file(cfg, w["chrom"]))
        part_log = work(cfg, "trace", tag, w["chrom"], f"w{w['start']}.log")
        step.run(cmd, log_path=part_log)
        if not out.exists():
            step.fail(f"TRACE finished but did not write {rel(out)}. Check that "
                      "TRACE_CMD_TEMPLATE writes its result to {out}.")
        out_files.append((w, out))
        step.progress(f"TRACE t={t}: {i}/{len(windows)} windows done")
    return out_files


def collect_trace_segments(step, out_files):
    cfg = step.cfg
    cols = cfg.list("TRACE_OUTPUT_COLUMNS") or None
    nodes = [str(n) for n in (metric("08-build-cohort", "user_hap_nodes") or [])]
    mode = cfg.get("TRACE_HAP_IDS").lower()
    offset_mode = cfg.get("TRACE_POS_OFFSET").lower()
    segs, dropped, offset_used = [], 0, 0
    for w, path in out_files:
        rows = parse_segment_file(path, default_chrom=w["chrom"], columns=cols,
                                  state_col=cfg.get("TRACE_STATE_COLUMN"),
                                  archaic_value=cfg.get("TRACE_ARCHAIC_VALUE"))
        width = w["end"] - w["start"]
        add = 0
        if offset_mode == "add" or (offset_mode == "auto" and rows and w["start"] > 0
                                    and max(r["end"] for r in rows) <= width * 1.01):
            add = w["start"]
            offset_used += 1
        for r in rows:
            r["start"] += add
            r["end"] += add
            h = str(r["hap"])
            if mode == "nodes" and nodes and h != "NA":
                if h not in nodes:
                    dropped += 1
                    continue
                r["hap"] = nodes.index(h)
            elif mode == "index" and h in ("0", "1"):
                r["hap"] = int(h)
            segs.append(r)
    if offset_used:
        step.log(f"added window start offsets to {offset_used} window outputs (TRACE_POS_OFFSET)")
    if dropped:
        step.log(f"ignored {dropped} rows belonging to haplotypes other than the user's")
    return merge_segments(segs)


def filter_segments(cfg, segs, min_bp, min_cm):
    maps, kept = {}, []
    for s in segs:
        if s["chrom"] not in maps:
            maps[s["chrom"]] = GeneticMap(map_file(cfg, s["chrom"]))
        s["length_bp"] = s["end"] - s["start"]
        s["length_cM"] = round(maps[s["chrom"]].length(s["start"], s["end"]), 5)
        if s["length_bp"] > min_bp and s["length_cM"] > min_cm:
            kept.append(s)
    return kept


# --------------------------------------------------------------------------
# Allele affinity (used by skills 13 and 14)
# --------------------------------------------------------------------------
class ChromAlleles:
    """User haplotype alleles plus ancestral and archaic alleles for one chromosome."""

    def __init__(self, step, chrom):
        cfg = step.cfg
        name = cfg.get("SAMPLE_NAME")
        txt = step.capture(["bcftools", "query", "-s", name, "-f", "%POS\t%REF\t%ALT\t[%GT]\n",
                            str(cohort_vcf_gz(cfg, chrom))])
        self.pos, self.h = [], ([], [])
        for line in txt.splitlines():
            p = line.split("\t")
            if len(p) < 4 or "|" not in p[3]:
                continue
            a = p[3].split("|")
            alle = [p[1]] + p[2].split(",")
            try:
                b0, b1 = alle[int(a[0])], alle[int(a[1])]
            except (ValueError, IndexError):
                continue
            self.pos.append(int(p[0]))
            self.h[0].append(b0)
            self.h[1].append(b1)
        self.anc, self.arch = {}, {}
        tab = archaic_table(cfg, chrom)
        if not tab.exists():
            raise StepError(f"{rel(tab)} is missing. Run 12-fetch-archaic first.")
        with open(tab) as f:
            header = f.readline().rstrip("\n").split("\t")
            self.arch_names = header[4:]
            for line in f:
                p = line.rstrip("\n").split("\t")
                pos = int(p[0])
                self.anc[pos] = p[3]
                self.arch[pos] = p[4:]
        self.allow_low = cfg.get("ANCESTRAL_ALLOW_LOWCONF") == "1"

    def affinity(self, start, end, hap):
        hap = int(hap) if str(hap) in ("0", "1") else 0
        i0, i1 = bisect.bisect_left(self.pos, start), bisect.bisect_right(self.pos, end)
        names = self.arch_names
        den = [0] * len(names)
        sh = [0] * len(names)
        n_derived = 0
        for i in range(i0, i1):
            pos = self.pos[i]
            anc = self.anc.get(pos, ".")
            if anc == "." or (anc.islower() and not self.allow_low):
                continue
            b = self.h[hap][i]
            if b.upper() == anc.upper():
                continue
            n_derived += 1
            for j, val in enumerate(self.arch.get(pos, ["."] * len(names))):
                if val == ".":
                    continue
                den[j] += 1
                if b in val:
                    sh[j] += 1
        aff = {n: (sh[j] / den[j] if den[j] else None) for j, n in enumerate(names)}
        nea = [v for n, v in aff.items() if n.startswith("NEA") and v is not None]
        dee = [v for n, v in aff.items() if n.startswith("DEN") and v is not None]
        return {"n_derived": n_derived, "affinity": aff,
                "nea_affinity": max(nea) if nea else None,
                "den_affinity": max(dee) if dee else None}
