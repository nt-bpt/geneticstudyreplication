"""Project path conventions. Every file the pipeline reads or writes lives under repo/.

repo/input/<subject>/        the subject's scan: a DICOM folder tree or NIfTI file(s)
repo/work/<subject>/         intermediate files (NIfTI conversion, segmentation, JSON state)
repo/results/<subject>/      final report.md and report.json
repo/reference/              reference cohort: ixi/T1/*.nii.gz, ixi_demographics.csv, reference.csv
repo/work/reference/         intermediate files for the reference cohort
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]   # repo/lib/striatum/paths.py -> project root
REPO = ROOT / "repo"
INPUT = REPO / "input"
WORK = REPO / "work"
RESULTS = REPO / "results"
REFERENCE = REPO / "reference"
REFERENCE_CSV = REFERENCE / "reference.csv"
REFERENCE_T1_DIR = REFERENCE / "ixi" / "T1"
REFERENCE_DEMOGRAPHICS = REFERENCE / "ixi_demographics.csv"


def rel(p) -> str:
    """Path relative to the project root, for messages and JSON state."""
    p = Path(p).resolve()
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def abs_path(p) -> Path:
    p = Path(p)
    return p if p.is_absolute() else ROOT / p


def subject_dirs(subject: str) -> dict:
    d = {"input": INPUT / subject, "work": WORK / subject, "results": RESULTS / subject}
    d["work"].mkdir(parents=True, exist_ok=True)
    return d


def save_state(subject: str, name: str, data: dict) -> Path:
    path = subject_dirs(subject)["work"] / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, default=_json_default))
    return path


def load_state(subject: str, name: str, needed_by: str) -> dict:
    path = WORK / subject / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"{rel(path)} not found. Run the skill that produces it before {needed_by}.")
    return json.loads(path.read_text())


def _json_default(o):
    try:
        f = float(o)
        return f if f == f and abs(f) != float("inf") else None
    except (TypeError, ValueError):
        return str(o)
