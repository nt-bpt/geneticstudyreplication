"""Pipeline steps: ingest, segment, compare, report."""
from __future__ import annotations

import csv
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import nibabel as nib
import numpy as np

T1_PATTERN = re.compile(r"t1|mprage|mp-rage|spgr|bravo|tfe|fspgr|3d_?t1", re.I)


# ---------------------------------------------------------------- ingest
def ingest(input_path: str, out_dir: Path, t1_override: str | None = None) -> dict:
    """Convert DICOM to NIfTI if needed, pick the T1 series, report its geometry."""
    out_dir.mkdir(parents=True, exist_ok=True)
    src = Path(input_path)
    nifti_dir = out_dir / "nifti"

    is_nii = lambda p: p.name.endswith((".nii", ".nii.gz"))
    supplied_nifti = sorted(p for p in src.rglob("*") if is_nii(p)) if src.is_dir() else []

    if t1_override:
        t1 = Path(t1_override)
        if not t1.exists():
            raise RuntimeError(f"--t1 file not found: {t1}")
    elif src.is_file() and is_nii(src):
        t1 = src
    elif len(supplied_nifti) == 1:
        t1 = supplied_nifti[0]
    else:
        if supplied_nifti:
            series = supplied_nifti
        else:
            if not shutil.which("dcm2niix"):
                raise RuntimeError("dcm2niix not found; install it (apt-get install dcm2niix) to read DICOM")
            nifti_dir.mkdir(exist_ok=True)
            subprocess.run(["dcm2niix", "-z", "y", "-b", "y", "-f", "%s_%d", "-o", str(nifti_dir), str(src)],
                           check=True, capture_output=True)
            series = sorted(nifti_dir.glob("*.nii.gz"))
        if not series:
            raise RuntimeError(f"No DICOM or NIfTI images found under {src}")
        candidates = [s for s in series if T1_PATTERN.search(s.name)]
        if not candidates:
            raise RuntimeError("No series looks like a T1. Series found:\n  "
                               + "\n  ".join(s.name for s in series)
                               + "\nRe-run the ingest-mri skill with --t1 <file> to choose one.")
        # prefer the series with the smallest voxels (the 3D one)
        t1 = min(candidates, key=lambda p: float(np.prod(nib.load(p).header.get_zooms()[:3])))

    img = nib.load(t1)
    zooms = [round(float(z), 3) for z in img.header.get_zooms()[:3]]
    info = {
        "t1_path": str(t1),
        "shape": list(img.shape[:3]),
        "voxel_mm": zooms,
        "dwi_present": any(re.search(r"dwi|dti|diff", p.name, re.I)
                           for p in (list(nifti_dir.glob("*.nii.gz")) if nifti_dir.exists() else []) + supplied_nifti),
        "warnings": [],
    }
    if max(zooms) > 1.5:
        info["warnings"].append(
            f"Largest voxel dimension is {max(zooms)} mm (thick slices). SynthSeg can handle this, but "
            "small-structure and bridge-zone metrics will be noisier than from a 1 mm 3D scan.")
    return info


# ---------------------------------------------------------------- segment
def segment(t1_path: str, out_dir: Path, threads: int = 4) -> dict:
    """Run SynthSeg (FreeSurfer 7.3+). Returns paths to outputs."""
    exe = shutil.which("mri_synthseg")
    if not exe:
        raise RuntimeError("mri_synthseg not found. Install FreeSurfer 7.3+ (or the standalone SynthSeg "
                           "repo) and source its setup script.")
    seg = out_dir / "synthseg.nii.gz"
    res = out_dir / "t1_resampled.nii.gz"
    vols = out_dir / "synthseg_volumes.csv"
    qc = out_dir / "synthseg_qc.csv"
    subprocess.run([exe, "--i", t1_path, "--o", str(seg), "--resample", str(res),
                    "--vol", str(vols), "--qc", str(qc), "--robust",
                    "--threads", str(threads), "--cpu"], check=True)
    return {"seg": str(seg), "resampled": str(res), "volumes_csv": str(vols), "qc_csv": str(qc)}


def read_synthseg_csv(path: str) -> dict:
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    header, values = rows[0], rows[1]
    return {h.strip(): v.strip() for h, v in zip(header, values)}


def icv_from_volumes(vols: dict) -> float | None:
    for key, val in vols.items():
        if "intracranial" in key.lower():
            return float(val)
    return None


def qc_summary(qc: dict, threshold: float = 0.65) -> dict:
    """SynthSeg QC scores: ~1 good, below ~0.65 suspect (per SynthSeg docs)."""
    scores = {k: float(v) for k, v in qc.items() if k.lower() not in ("subject", "")}
    flagged = {k: v for k, v in scores.items() if v < threshold}
    return {"scores": scores, "flagged": flagged, "passed": not flagged}


# ---------------------------------------------------------------- compare
COMPARE_KEYS = [
    "left_caudate_icv_pct", "right_caudate_icv_pct",
    "left_putamen_icv_pct", "right_putamen_icv_pct",
    "left_bridge_mm3", "right_bridge_mm3",
    "left_bridge_gm_index", "right_bridge_gm_index",
    "caudate_asymmetry_pct", "putamen_asymmetry_pct", "bridge_asymmetry_pct",
]


def compare(subject: dict, reference_csv: str, age: float | None, sex: str | None,
            age_window: float = 10.0, min_n: int = 20) -> dict:
    """z-scores against a reference cohort processed with this same pipeline."""
    with open(reference_csv, newline="") as f:
        ref = list(csv.DictReader(f))

    def pick(window, use_sex):
        rows = ref
        if age is not None:
            rows = [r for r in rows if r.get("age") and abs(float(r["age"]) - age) <= window]
        if use_sex and sex:
            rows = [r for r in rows if (r.get("sex") or "").upper()[:1] == sex.upper()[:1]]
        return rows

    rows, window, use_sex = pick(age_window, True), age_window, True
    while len(rows) < min_n and window < 40:
        window += 5
        rows = pick(window, True)
    if len(rows) < min_n:
        use_sex = False
        rows = pick(window, False)

    out = {"reference_n": len(rows), "age_window_years": window if age is not None else None,
           "sex_matched": bool(use_sex and sex), "metrics": {}}
    for k in COMPARE_KEYS:
        x = subject.get(k)
        vals = np.array([float(r[k]) for r in rows if r.get(k) not in (None, "", "nan")], dtype=float)
        vals = vals[np.isfinite(vals)]
        if x is None or not np.isfinite(x) or len(vals) < 5:
            out["metrics"][k] = {"value": x, "z": None, "percentile": None, "ref_n": int(len(vals))}
            continue
        mu, sd = float(vals.mean()), float(vals.std(ddof=1))
        z = (x - mu) / sd if sd > 0 else None
        pct = 100.0 * float((vals < x).mean() + 0.5 * (vals == x).mean())
        out["metrics"][k] = {"value": x, "ref_mean": mu, "ref_sd": sd, "z": z,
                             "percentile": pct, "ref_n": int(len(vals))}
    return out


# ---------------------------------------------------------------- report
LIMITS = """\
## What this result can and cannot tell you

- **It cannot confirm or rule out an abduction or UAP encounter.** Nolan's caudate-putamen
  observation was reported in interviews, not published as a peer-reviewed method, and the
  encounter claims of the people scanned were not independently verified. Nolan himself has
  described the feature as possibly inherited and present before any experience, i.e. a trait
  rather than a mark left by an event.
- **There is no published threshold** for what counts as "increased" caudate-putamen density, so
  no z-score here maps onto Nolan's groups.
- **Outliers are expected by chance.** With ~11 metrics compared, at least one |z| > 2 happens in
  a large share of ordinary, healthy people.
- **Striatal size and signal vary for many ordinary reasons**: age, sex, head size, genetics,
  medications (notably antipsychotics), movement disorders, scanner and sequence differences.
- **A single scan has no "before".** Change over time needs two scans on comparable protocols.
- This is research software, not a diagnostic device. Anything that looks clinically odd should go
  to a radiologist or neurologist.
"""


def _fmt(v, nd=2):
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "–"
    return f"{v:.{nd}f}"


def write_report(out_dir: Path, ingest_info: dict, metrics: dict, qc: dict | None,
                 comparison: dict | None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = ["# Caudate–putamen measurement report", ""]
    lines += ["## Input", f"- T1 series: `{Path(ingest_info['t1_path']).name}`",
              f"- Voxel size (mm): {ingest_info['voxel_mm']}",
              f"- Diffusion (DWI/DTI) series present: {'yes' if ingest_info.get('dwi_present') else 'no'}"]
    for w in ingest_info.get("warnings", []):
        lines.append(f"- ⚠️ {w}")
    if qc is not None:
        lines.append(f"- Segmentation QC: {'passed' if qc['passed'] else 'FLAGGED — ' + ', '.join(qc['flagged'])}")
    lines.append("")

    lines += ["## Measurements", "", "| Metric | Left | Right |", "|---|---|---|"]
    for name, unit in (("caudate_mm3", "mm³"), ("caudate_icv_pct", "% ICV"),
                       ("putamen_mm3", "mm³"), ("putamen_icv_pct", "% ICV"),
                       ("bridge_mm3", "mm³"), ("bridge_gm_index", "0=WM-like, 1=striatum-like")):
        l, r = metrics.get(f"left_{name}"), metrics.get(f"right_{name}")
        nd = 0 if name.endswith("mm3") else 3
        lines.append(f"| {name.replace('_', ' ')} ({unit}) | {_fmt(l, nd)} | {_fmt(r, nd)} |")
    lines += ["", f"Asymmetry (L−R, % of mean): caudate {_fmt(metrics.get('caudate_asymmetry_pct'))}, "
              f"putamen {_fmt(metrics.get('putamen_asymmetry_pct'))}, bridge {_fmt(metrics.get('bridge_asymmetry_pct'))}",
              "", "*Bridge zone* = white matter within "
              f"{metrics['bridge_mm']:g} mm of both caudate and putamen (mostly the anterior limb of the "
              "internal capsule, where the grey 'cell bridges' between them run). The GM index asks how "
              "grey-matter-like that tissue looks on T1. It is this pipeline's stand-in for Nolan's "
              "description, not his method.", ""]

    if comparison:
        lines += ["## Comparison with reference cohort",
                  f"Reference n = {comparison['reference_n']}"
                  + (f", age ±{comparison['age_window_years']:g} y" if comparison.get("age_window_years") else "")
                  + (", sex-matched" if comparison["sex_matched"] else ", not sex-matched"), "",
                  "| Metric | Value | Ref mean ± SD | z | Percentile |", "|---|---|---|---|---|"]
        for k, m in comparison["metrics"].items():
            ref = f"{_fmt(m.get('ref_mean'), 3)} ± {_fmt(m.get('ref_sd'), 3)}" if m.get("ref_mean") is not None else "–"
            flag = " ◀" if m.get("z") is not None and abs(m["z"]) >= 2 else ""
            lines.append(f"| {k} | {_fmt(m['value'], 3)} | {ref} | {_fmt(m.get('z'))}{flag} | {_fmt(m.get('percentile'), 0)} |")
        lines += ["", "◀ marks |z| ≥ 2. See the limits below before reading anything into it.", ""]
    else:
        lines += ["## Comparison with reference cohort",
                  "Not run: no reference cohort. Raw numbers alone can't be called high or low; "
                  "build `repo/reference/reference.csv` with the build-reference skill.", ""]

    lines.append(LIMITS)
    path = out_dir / "report.md"
    path.write_text("\n".join(lines))
    (out_dir / "report.json").write_text(json.dumps(
        {"ingest": ingest_info, "metrics": metrics, "qc": qc, "comparison": comparison},
        indent=2, default=lambda o: None if isinstance(o, float) and not math.isfinite(o) else str(o)))
    return path
