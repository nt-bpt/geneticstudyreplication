#!/usr/bin/env python3
"""SKILL 09: check that TRACE is installed, and download the archaic tracts
published with the paper (used by skill 15 for comparison)."""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "09-fetch-trace"
PIP = "'git+https://github.com/YulinZhang9806/trace.git'"


def zenodo_files(step, record):
    """Return (record_id, [(filename, url, size)]) for a Zenodo record."""
    urls = [f"https://zenodo.org/api/records/{record}"]
    try:  # a concept DOI redirects to the latest version
        with urllib.request.urlopen(f"https://doi.org/10.5281/zenodo.{record}", timeout=60) as r:
            rid = r.geturl().rstrip("/").rsplit("/", 1)[-1]
            if rid.isdigit() and rid != record:
                urls.append(f"https://zenodo.org/api/records/{rid}")
    except Exception as e:  # noqa: BLE001
        step.log(f"doi.org lookup for {record} failed: {e}")
    last = None
    for u in urls:
        try:
            with urllib.request.urlopen(u, timeout=60) as r:
                meta = json.load(r)
            files = []
            for f in meta.get("files", []):
                name = f.get("key") or f.get("filename")
                link = (f.get("links") or {}).get("self") or (f.get("links") or {}).get("download")
                if name and link:
                    files.append((name, link, f.get("size", 0)))
            if files:
                return str(meta.get("id", record)), files
        except Exception as e:  # noqa: BLE001
            last = e
    raise pc.StepError(f"could not list files for Zenodo record {record} ({last})")


def fetch(step, record, dest):
    marker = dest / ".complete"
    if marker.exists():
        return dest
    rid, files = zenodo_files(step, record)
    total = sum(s or 0 for _, _, s in files) / 1e9
    step.log(f"record {rid}: {len(files)} file(s), {total:.2f} GB")
    if total > pc.free_gb(dest) * 0.8:
        raise pc.StepError(f"Zenodo record {rid} needs {total:.1f} GB but only "
                           f"{pc.free_gb(dest):.1f} GB is free")
    for name, url, _ in files:
        f = pc.download(step, url, dest / "archives" / name)
        if name.lower().endswith((".zip", ".tar.gz", ".tgz", ".tar")):
            pc.extract(step, f, dest)
        else:
            target = dest / name
            if not target.exists():
                target.symlink_to(f)
    marker.write_text(rid + "\n")
    return dest


def work(step):
    cfg = step.cfg
    pc.require(step, "00-check-env")

    # 1. TRACE itself is a Python package (MIT licence) providing three commands
    found, missing = {}, []
    for name in ("trace-extract", "trace-infer", "trace-summarize"):
        p = Path(sys.executable).parent / name
        if p.exists():
            found[name] = str(p)
        elif pc.have(name):
            found[name] = name
        else:
            missing.append(name)
    step.metrics.update({"trace_commands": found, "python": sys.executable})
    if missing:
        step.fail(f"TRACE is not installed in this environment: {' '.join(missing)} not found. "
                  f"Ask the user to run: {sys.executable} -m pip install {PIP}")

    # 2. published archaic tracts, for the comparison in skill 15
    dat = pc.data(cfg, "trace_data", "x").parent
    step.metrics["trace_data_dir"] = str(dat)
    try:
        step.progress("downloading the published archaic tracts (Trace_data)")
        fetch(step, cfg.get("TRACE_DATA_RECORD"), dat)
        step.metrics["trace_data_downloaded"] = True
    except pc.StepError as e:
        step.metrics["trace_data_downloaded"] = False
        step.warn("could not download the published tracts from Zenodo "
                  f"(10.5281/zenodo.{cfg.get('TRACE_DATA_RECORD')}): {str(e)[:200]}. The run can "
                  "continue; skill 15 will simply skip the comparison with the published tracts. "
                  f"To add it later, the user can download that record by hand into {pc.rel(dat)}.")
    return "OK", f"TRACE installed ({len(found)} commands found)"


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
