#!/usr/bin/env python3
"""SKILL 09: download TRACE software, the authors' pipeline and published tracts from Zenodo."""
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "09-fetch-trace"


def zenodo_files(step, record):
    """Return (record_id, [(filename, url, size)]) for a Zenodo record or DOI number."""
    urls = [f"https://zenodo.org/api/records/{record}"]
    try:  # a concept DOI redirects to the latest version
        with urllib.request.urlopen(f"https://doi.org/10.5281/zenodo.{record}", timeout=60) as r:
            final = r.geturl().rstrip("/")
            rid = final.rsplit("/", 1)[-1]
            if rid.isdigit() and rid != record:
                urls.append(f"https://zenodo.org/api/records/{rid}")
    except Exception as e:  # noqa: BLE001
        step.log(f"doi.org lookup for {record} failed: {e}", echo=False)
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
    step.fail(f"could not list files for Zenodo record {record} ({last}). Ask the user to download "
              f"https://doi.org/10.5281/zenodo.{record} by hand into the folder named in this "
              "skill's instructions.")


def fetch(step, record, dest):
    marker = dest / ".complete"
    if marker.exists():
        return dest
    rid, files = zenodo_files(step, record)
    total = sum(s or 0 for _, _, s in files) / 1e9
    step.log(f"record {rid}: {len(files)} file(s), {total:.2f} GB")
    if total > pc.free_gb(dest) * 0.8:
        step.fail(f"Zenodo record {rid} needs {total:.1f} GB but only {pc.free_gb(dest):.1f} GB is free")
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
    soft = fetch(step, cfg.get("TRACE_SOFTWARE_RECORD"), pc.tools(cfg, "trace_software", "x").parent)
    pipe = fetch(step, cfg.get("TRACE_PIPELINE_RECORD"), pc.tools(cfg, "trace_pipeline", "x").parent)
    step.progress("downloading published archaic tracts (Trace_data)")
    dat = fetch(step, cfg.get("TRACE_DATA_RECORD"), pc.data(cfg, "trace_data", "x").parent)

    readmes = sorted(str(p) for d in (soft, pipe) for p in d.rglob("*")
                     if p.is_file() and p.name.lower().startswith("readme"))
    installers = sorted(str(p) for p in soft.rglob("*")
                        if p.name in ("setup.py", "pyproject.toml", "environment.yml",
                                      "requirements.txt", "Makefile", "CMakeLists.txt"))
    snakefiles = sorted(str(p) for p in pipe.rglob("*") if p.name in ("Snakefile", "config.yaml",
                                                                        "config.yml"))
    step.metrics.update({"trace_software_dir": str(soft), "trace_pipeline_dir": str(pipe),
                         "trace_data_dir": str(dat), "readme_files": readmes,
                         "install_files": installers, "pipeline_config_files": snakefiles})
    # the agent cannot open files, so hand it the start of the TRACE README
    main_readme = next((Path(r) for r in readmes if str(soft) in r), None) or \
        (Path(readmes[0]) if readmes else None)
    if main_readme:
        text = main_readme.read_text(errors="replace")
        step.extra["trace_readme_preview"] = text[:6000] + ("\n[... cut ...]" if len(text) > 6000 else "")
        step.extra["trace_readme_file"] = pc.rel(main_readme)
    if not cfg.get("TRACE_CMD_TEMPLATE"):
        step.warn("TRACE_CMD_TEMPLATE is still empty. Before skill 11, the user (or you, by "
                  "reading trace_readme_preview in this result) must install TRACE "
                  "and set TRACE_CMD_TEMPLATE in repo/config.env. Placeholders: {trees} {chrom} "
                  "{start} {end} {haps} {hap_file} {t} {out} {threads} {trace_dir} {map}.")
    return "OK", f"TRACE resources downloaded; {len(readmes)} README file(s) to read"


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
