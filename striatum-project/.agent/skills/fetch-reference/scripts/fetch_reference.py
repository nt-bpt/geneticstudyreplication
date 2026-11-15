#!/usr/bin/env python3
"""Download reference-cohort T1 scans into repo/reference/, keeping only the matched age/sex band.

Cohorts
  ixi   IXI (CC BY-SA 3.0). Downloads IXI-T1.tar (~4.5 GB) and IXI.xls, extracts only matching
        subjects into repo/reference/ixi/T1/, writes repo/reference/ixi_demographics.csv.
  dlbs  Dallas Lifespan Brain Study, OpenNeuro ds004856 (CC0). Downloads participants.tsv, then
        only the wave-1 MPRAGE T1 of matching subjects into repo/reference/dlbs/T1/, writes
        repo/reference/dlbs_demographics.csv.

Safe to re-run: files already present are skipped.
"""
import argparse
import csv
import hashlib
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
REF = ROOT / "repo" / "reference"
DL = REF / "downloads"

IXI_BASE = "http://biomedic.doc.ic.ac.uk/brain-development/downloads/IXI"
IXI_TAR_MD5 = "34901a0593b41dd19c1a1f746eac2d58"
DLBS_BASE = "https://s3.amazonaws.com/openneuro.org/ds004856"


def rel(p):
    return str(Path(p).resolve().relative_to(ROOT))


def download(url, dest: Path, retries=3):
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".part")
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                done, last = 0, 0.0
                while chunk := r.read(1 << 20):
                    f.write(chunk)
                    done += len(chunk)
                    if total > 50 << 20 and time.time() - last > 10:
                        print(f"  {dest.name}: {done / total:5.1%} of {total / 1e9:.1f} GB", flush=True)
                        last = time.time()
            tmp.rename(dest)
            return dest
        except Exception as e:  # network hiccups: retry
            print(f"  download failed ({e}); attempt {attempt}/{retries}: {url}", flush=True)
            time.sleep(5 * attempt)
    sys.exit(f"Could not download {url}")


def md5(path: Path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 24):
            h.update(chunk)
    return h.hexdigest()


def in_band(age, sex, a):
    return age is not None and a.age_min <= age <= a.age_max and (a.sex == "any" or sex == a.sex)


def write_demographics(path: Path, rows):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["subject", "age", "sex", "cohort"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {rel(path)} ({len(rows)} subjects)")


# ------------------------------------------------------------------ IXI
def fetch_ixi(a):
    try:
        import xlrd
    except ImportError:
        sys.exit("Reading IXI.xls needs xlrd: apt-get install python3-xlrd (or pip install xlrd)")

    xls = download(f"{a.ixi_base}/IXI.xls", DL / "IXI.xls")
    sheet = xlrd.open_workbook(str(xls)).sheet_by_index(0)
    raw_head = [str(c).strip() for c in sheet.row_values(0)]
    head = [h.upper().replace(" ", "_") for h in raw_head]

    def find(key):
        # exact match first, then a header that starts with the key, e.g. "SEX_ID (1=m, 2=f)"
        for i, h in enumerate(head):
            if h == key:
                return i
        for i, h in enumerate(head):
            if h.startswith(key):
                return i
        sys.exit(f"IXI.xls has no '{key}' column. Columns found: {raw_head}\n"
                 f"If the file isn't a spreadsheet, delete {rel(xls)} and re-run.")

    col = {k: find(k) for k in ("IXI_ID", "SEX_ID", "AGE")}
    print(f"IXI: using columns {[raw_head[c] for c in col.values()]}")
    demo = {}
    for i in range(1, sheet.nrows):
        r = sheet.row_values(i)
        try:
            sid, sex_id = int(r[col["IXI_ID"]]), int(r[col["SEX_ID"]])
            age = float(r[col["AGE"]])
        except (TypeError, ValueError):
            continue  # rows without an age are unusable
        demo[sid] = (round(age, 1), {1: "M", 2: "F"}.get(sex_id))
    wanted = {sid for sid, (age, sex) in demo.items() if in_band(age, sex, a)}
    print(f"IXI: {len(demo)} subjects with age; {len(wanted)} in band")

    tar_path = download(f"{a.ixi_base}/IXI-T1.tar", DL / "IXI-T1.tar")
    if not a.skip_md5:
        print("IXI: checking archive MD5 ...", flush=True)
        if md5(tar_path) != IXI_TAR_MD5:
            sys.exit(f"{rel(tar_path)} MD5 mismatch; delete it and re-run")

    out = REF / "ixi" / "T1"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    with tarfile.open(tar_path) as tar:
        for m in tar:
            name = Path(m.name).name
            if not m.isfile() or not name.startswith("IXI") or not name.endswith(".nii.gz"):
                continue
            try:
                sid = int(name[3:6])
            except ValueError:
                continue
            if sid not in wanted:
                continue
            dest = out / name
            if not dest.exists():
                with tar.extractfile(m) as src, open(dest, "wb") as f:
                    f.write(src.read())
            age, sex = demo[sid]
            rows.append({"subject": name[:-7], "age": age, "sex": sex, "cohort": "IXI"})
    write_demographics(REF / "ixi_demographics.csv", rows)
    if not a.keep_archive:
        tar_path.unlink()
        print(f"Deleted {rel(tar_path)} (use --keep-archive to keep it)")


# ------------------------------------------------------------------ DLBS
def fetch_dlbs(a):
    tsv = download(f"{a.dlbs_base}/participants.tsv", DL / "dlbs_participants.tsv")
    with open(tsv, newline="") as f:
        parts = list(csv.DictReader(f, delimiter="\t"))
    sel = []
    for p in parts:
        try:
            age = float(p["AgeMRI_W1"])
        except (KeyError, ValueError):
            continue
        sex = {"m": "M", "f": "F"}.get(p.get("Sex", "").strip().lower())
        if in_band(age, sex, a):
            sel.append((p["participant_id"], age, sex))
    print(f"DLBS: {len(parts)} participants; {len(sel)} in band with a wave-1 MRI")

    out = REF / "dlbs" / "T1"
    rows = []
    for n, (pid, age, sex) in enumerate(sel, 1):
        src = f"{a.dlbs_base}/{pid}/ses-wave1/anat/{pid}_ses-wave1_acq-MPRAGE_run-1_T1w.nii.gz"
        subject = f"DLBS-{pid}"
        download(src, out / f"{subject}.nii.gz")
        rows.append({"subject": subject, "age": age, "sex": sex, "cohort": "DLBS"})
        print(f"  [{n}/{len(sel)}] {subject}", flush=True)
    write_demographics(REF / "dlbs_demographics.csv", rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cohorts", nargs="+", choices=["ixi", "dlbs"], default=["ixi", "dlbs"])
    ap.add_argument("--age-min", type=float, required=True)
    ap.add_argument("--age-max", type=float, required=True)
    ap.add_argument("--sex", choices=["M", "F", "any"], required=True)
    ap.add_argument("--keep-archive", action="store_true", help="keep the 4.5 GB IXI tar after extracting")
    ap.add_argument("--skip-md5", action="store_true")
    ap.add_argument("--ixi-base", default=IXI_BASE, help=argparse.SUPPRESS)
    ap.add_argument("--dlbs-base", default=DLBS_BASE, help=argparse.SUPPRESS)
    a = ap.parse_args()
    REF.mkdir(parents=True, exist_ok=True)
    if "ixi" in a.cohorts:
        fetch_ixi(a)
    if "dlbs" in a.cohorts:
        fetch_dlbs(a)
    print("\nNext: build-reference skill, once per cohort, into the same repo/reference/reference.csv")


if __name__ == "__main__":
    main()
