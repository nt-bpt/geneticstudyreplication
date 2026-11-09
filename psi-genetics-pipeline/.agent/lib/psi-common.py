"""Shared helpers for the psi-genetics genotype-check skills.

Every skill script imports this module. It provides:
  * repo-relative paths (results/, logs/, panels/, config/)
  * config loading with defaults and path resolution
  * a Skill object that logs, runs commands and writes results/<skill>.json
Only the Python standard library is used.
"""
from __future__ import annotations

import datetime as _dt
import gzip
import io
import json
import os
import shutil
import subprocess
import sys
import traceback
import zipfile
from pathlib import Path

# Layout:  <root>/.agent/skills/<skill>/   scripts (not visible to the agent)
#          <root>/.agent/lib/psi-common.py
#          <root>/repo/                     the agent's workspace (config, input, results, logs, panels)
ROOT = Path(os.environ.get("PSI_ROOT", Path(__file__).resolve().parents[2])).resolve()
REPO = Path(os.environ.get("PSI_REPO", ROOT / "repo")).resolve()
RESULTS = REPO / "results"
LOGS = REPO / "logs"
PANELS = REPO / "panels"
CONFIG_PATH = REPO / "config" / "run-config.json"
SKILLS = ROOT / ".agent" / "skills"

OK, WARN, FAIL, SKIPPED = "OK", "WARN", "FAIL", "SKIPPED"
PASSING = {OK, WARN, SKIPPED}

DEFAULT_CONFIG = {
    "sample_label": "sample",
    "input": {"path": "", "path_r2": "", "type": "auto"},
    "build_override": "",
    "reference": {"GRCh37": "", "GRCh38": ""},
    "align_build": "GRCh38",
    "aligner": "auto",
    "build_aligner_index": False,
    "work_dir": "../psi-work",
    "threads": 4,
    "min_depth": 10,
    "min_mapq": 20,
    "min_baseq": 20,
    "network": True,
    "kg_phase3_chr7_vcf": "",
    "kg_phase3_panel": "",
}

PATH_KEYS = ("input.path", "input.path_r2", "reference.GRCh37", "reference.GRCh38",
             "work_dir", "kg_phase3_chr7_vcf", "kg_phase3_panel")

COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}

# chr7 and chr1 lengths identify the build.
BUILD_CONTIG_LENGTHS = {
    "GRCh37": {"1": 249250621, "7": 159138663},
    "GRCh38": {"1": 248956422, "7": 159345973},
}


def now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def resolve_path(value: str) -> str:
    """Resolve a config path. Relative paths are relative to the repo folder."""
    if not value:
        return ""
    p = Path(os.path.expanduser(value))
    if not p.is_absolute():
        p = REPO / p
    return str(p.resolve())


def write_default_config() -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2) + "\n")


def load_config() -> dict:
    """Load config/run-config.json, fill defaults, resolve paths.

    The resolved copy is returned; the file on disk is not changed.
    """
    raw = {}
    if CONFIG_PATH.exists():
        raw = json.loads(CONFIG_PATH.read_text())
    cfg = _merge(DEFAULT_CONFIG, raw)
    for key in PATH_KEYS:
        parts = key.split(".")
        holder = cfg
        for p in parts[:-1]:
            holder = holder[p]
        holder[parts[-1]] = resolve_path(holder.get(parts[-1], ""))
    cfg["threads"] = max(1, int(cfg.get("threads") or 1))
    return cfg


def read_result(name: str) -> dict | None:
    p = RESULTS / f"{name}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def open_text(path: str):
    """Open a plain, .gz or .zip text file for reading (first text member of a zip)."""
    if path.endswith(".zip"):
        zf = zipfile.ZipFile(path)
        members = [m for m in zf.namelist() if not m.endswith("/") and not m.startswith("__MACOSX")]
        if not members:
            raise ValueError(f"zip file has no members: {path}")
        members.sort(key=lambda m: (not m.lower().endswith((".txt", ".csv", ".tsv")), m))
        return io.TextIOWrapper(zf.open(members[0]), encoding="utf-8", errors="replace")
    with open(path, "rb") as fh:
        magic = fh.read(2)
    if magic == b"\x1f\x8b":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace")
    return open(path, "r", encoding="utf-8", errors="replace")


def strip_chr(chrom: str) -> str:
    c = chrom[3:] if chrom.lower().startswith("chr") else chrom
    return "MT" if c in ("M", "m") else c


class Skill:
    """Per-skill logging, command running and result writing."""

    def __init__(self, name: str):
        self.name = name
        RESULTS.mkdir(parents=True, exist_ok=True)
        LOGS.mkdir(parents=True, exist_ok=True)
        self.log_path = LOGS / f"{name}.log"
        self.result_path = RESULTS / f"{name}.json"
        self._log = open(self.log_path, "w", encoding="utf-8")
        self.metrics: dict = {}
        self.warnings: list[str] = []
        self.outputs: dict = {}
        self.started = now_iso()
        self.log(f"skill {name} started {self.started}")
        self.log(f"repo {REPO}")

    # ---- logging -------------------------------------------------------
    def log(self, msg: str) -> None:
        line = f"[{_dt.datetime.now().strftime('%H:%M:%S')}] {msg}"
        self._log.write(line + "\n")
        self._log.flush()
        print(line, flush=True)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)
        self.log(f"WARNING: {msg}")

    # ---- commands -----------------------------------------------------
    def run(self, cmd, check: bool = True, shell: bool = False, stdout_path: str | None = None,
            input_text: str | None = None) -> subprocess.CompletedProcess:
        shown = cmd if isinstance(cmd, str) else " ".join(str(c) for c in cmd)
        self.log(f"$ {shown}")
        stdout = open(stdout_path, "w") if stdout_path else subprocess.PIPE
        try:
            cp = subprocess.run(cmd, shell=shell, stdout=stdout, stderr=subprocess.PIPE, text=True, errors="replace",
                                input=input_text, executable="/bin/bash" if shell else None)
        finally:
            if stdout_path:
                stdout.close()
        if cp.stderr:
            tail = cp.stderr.strip().splitlines()[-15:]
            for t in tail:
                self.log(f"  stderr: {t}")
        if check and cp.returncode != 0:
            raise RuntimeError(f"command failed (exit {cp.returncode}): {shown}")
        return cp

    # ---- previous skills ------------------------------------------------
    def require(self, name: str) -> dict:
        res = read_result(name)
        if res is None:
            raise PrerequisiteError(f"{name} has not been run (results/{name}.json missing). Run it first.")
        if res.get("status") not in PASSING:
            raise PrerequisiteError(f"{name} status is {res.get('status')}. Fix and re-run {name} first.")
        return res

    # ---- finishing ------------------------------------------------------
    def finish(self, status: str, verdict: str) -> None:
        result = {
            "skill": self.name,
            "status": status,
            "verdict": verdict,
            "metrics": self.metrics,
            "warnings": self.warnings,
            "outputs": self.outputs,
            "started": self.started,
            "finished": now_iso(),
            "log": str(self.log_path.relative_to(REPO)),
        }
        self.result_path.write_text(json.dumps(result, indent=2) + "\n")
        self.log(f"STATUS {status}: {verdict}")
        self._log.close()
        print(json.dumps({"status": status, "verdict": verdict,
                          "result": str(self.result_path.relative_to(REPO))}))
        sys.exit(1 if status == FAIL else 0)


class PrerequisiteError(RuntimeError):
    pass


class SkillFail(RuntimeError):
    """Raise to end a skill with FAIL and a clear verdict."""


def main(name: str, fn) -> None:
    """Run fn(skill) -> (status, verdict); convert any exception into a FAIL result."""
    sk = Skill(name)
    try:
        status, verdict = fn(sk)
    except (PrerequisiteError, SkillFail) as e:
        status, verdict = FAIL, str(e)
    except Exception as e:  # noqa: BLE001 - always write a result
        sk.log(traceback.format_exc())
        status, verdict = FAIL, f"unexpected error: {e}"
    sk.finish(status, verdict)


def which(tool: str) -> str | None:
    return shutil.which(tool)


def write_tsv(path: Path, header: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\t".join(header) + "\n")
        for r in rows:
            f.write("\t".join("" if r.get(h) is None else str(r.get(h)) for h in header) + "\n")


def read_tsv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        header = f.readline().rstrip("\n").split("\t")
        out = []
        for line in f:
            if not line.strip():
                continue
            vals = line.rstrip("\n").split("\t")
            vals += [""] * (len(header) - len(vals))
            out.append(dict(zip(header, vals)))
    return out


def rel(path) -> str:
    """Show a path relative to the repo when it is inside it, else as ../<path> from the root."""
    p = Path(path).resolve()
    for base, prefix in ((REPO, ""), (ROOT, "../")):
        try:
            return prefix + str(p.relative_to(base))
        except ValueError:
            continue
    return str(path)
