#!/usr/bin/env python3
"""Check that everything the pipeline needs is installed. Exit code 0 = ready, 1 = something missing."""
import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "repo" / "lib"))

checks = []


def check(name, ok, fix=""):
    checks.append(ok)
    print(f"[{'OK ' if ok else 'MISSING'}] {name}" + ("" if ok else f"\n          fix: {fix}"))


check("python >= 3.9", sys.version_info >= (3, 9), "use Python 3.9 or newer")
for mod, apt in (("numpy", "python3-numpy"), ("scipy", "python3-scipy"), ("nibabel", "python3-nibabel")):
    try:
        importlib.import_module(mod)
        check(f"python module {mod}", True)
    except ImportError:
        check(f"python module {mod}", False, f"apt-get install {apt}  (or pip install -r repo/requirements.txt)")

check("dcm2niix on PATH", bool(shutil.which("dcm2niix")), "apt-get install dcm2niix")
fs_home = os.environ.get("FREESURFER_HOME")
check("FREESURFER_HOME set", bool(fs_home), "source $FREESURFER_HOME/SetUpFreeSurfer.sh (see repo/docs/README.md)")
check("mri_synthseg on PATH", bool(shutil.which("mri_synthseg")),
      "install FreeSurfer 8.x (see repo/docker/Dockerfile) and source its setup script")

lic = os.environ.get("FS_LICENSE") or (fs_home and str(Path(fs_home) / "license.txt"))
check("FreeSurfer license file present", bool(lic and Path(lic).exists()),
      "get a free licence at https://surfer.nmr.mgh.harvard.edu/registration.html and set FS_LICENSE to its path")

try:
    mem_gb = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024 ** 3
    print(f"[INFO] RAM: {mem_gb:.0f} GB" + ("  (FreeSurfer 8 recommends 32 GB+ for its Python tools; "
                                           "SynthSeg may fail with less)" if mem_gb < 32 else ""))
except (ValueError, OSError):
    pass

if shutil.which("mri_synthseg"):
    r = subprocess.run(["mri_synthseg", "--help"], capture_output=True, text=True)
    check("mri_synthseg runs", r.returncode == 0, "inspect: mri_synthseg --help\n" + r.stderr[-500:])

ref = ROOT / "repo" / "reference" / "reference.csv"
print(f"[INFO] reference cohort: {'present' if ref.exists() else 'not built yet (build-reference skill)'}")

sys.exit(0 if all(checks) else 1)
