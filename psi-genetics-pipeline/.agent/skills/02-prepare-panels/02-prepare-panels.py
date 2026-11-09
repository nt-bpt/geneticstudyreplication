#!/usr/bin/env python3
"""SKILL 02 - build the study site panels and resolve P2 rsIDs to GRCh37/GRCh38 coordinates.

Coordinates come from (in priority order):
  1. panels/p2-coords-manual.tsv  (rsid, build, chrom, pos, ref, alt) - optional, user supplied
  2. panels/cache/p2-coords-<build>.json  - written by earlier runs
  3. Ensembl REST batch lookup (rest.ensembl.org / grch37.rest.ensembl.org)
"""
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "psicommon", Path(__file__).resolve().parents[2] / "lib" / "psi-common.py")
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)

NAME = "02-prepare-panels"
RES = Path(__file__).resolve().parent / "resources"
ENSEMBL = {"GRCh38": "https://rest.ensembl.org", "GRCh37": "https://grch37.rest.ensembl.org"}
PRIMARY = {str(i) for i in range(1, 23)} | {"X", "Y", "MT"}
BATCH = 200


def ensembl_batch(sk, build, ids):
    url = f"{ENSEMBL[build]}/variation/homo_sapiens"
    out = {}
    for i in range(0, len(ids), BATCH):
        chunk = ids[i:i + BATCH]
        body = json.dumps({"ids": chunk}).encode()
        for attempt in range(4):
            req = urllib.request.Request(url, data=body, method="POST", headers={
                "Content-Type": "application/json", "Accept": "application/json"})
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    out.update(json.loads(r.read().decode()))
                break
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < 3:
                    wait = int(e.headers.get("Retry-After", 2 ** attempt * 3))
                    sk.log(f"Ensembl {build} HTTP {e.code}; retrying in {wait}s")
                    time.sleep(wait)
                    continue
                raise
            except urllib.error.URLError:
                if attempt < 3:
                    time.sleep(2 ** attempt * 3)
                    continue
                raise
        sk.log(f"Ensembl {build}: {min(i + BATCH, len(ids))}/{len(ids)} looked up")
    return out


def parse_ensembl(sk, build, data):
    """Return {rsid: {chrom,pos,ref,alt,current_name,source}} for unambiguous primary SNV mappings."""
    coords = {}
    for key, rec in data.items():
        maps = [m for m in rec.get("mappings", [])
                if str(m.get("seq_region_name")) in PRIMARY and m.get("assembly_name") == build]
        if len(maps) != 1:
            sk.warn(f"{key}: {len(maps)} primary {build} mappings; coordinates left empty")
            continue
        m = maps[0]
        alleles = (m.get("allele_string") or "").split("/")
        if m.get("start") != m.get("end") or any(len(a) != 1 or a not in "ACGT" for a in alleles):
            sk.warn(f"{key}: not a simple SNV in {build} ({m.get('allele_string')}); left empty")
            continue
        if m.get("strand") == -1:
            alleles = [pc.COMPLEMENT[a] for a in alleles]
        coords[key] = {"chrom": str(m["seq_region_name"]), "pos": int(m["start"]),
                       "ref": alleles[0], "alt": ",".join(alleles[1:]),
                       "current_name": rec.get("name", key), "source": f"ensembl_{build}"}
        if rec.get("name") and rec["name"] != key:
            sk.warn(f"{key} is now {rec['name']} in Ensembl (merged rsID)")
    return coords


def load_manual():
    p = pc.PANELS / "p2-coords-manual.tsv"
    out = {"GRCh37": {}, "GRCh38": {}}
    if not p.exists():
        return out, False
    for r in pc.read_tsv(p):
        b = r.get("build", "")
        if b in out and r.get("rsid"):
            out[b][r["rsid"]] = {"chrom": pc.strip_chr(r["chrom"]), "pos": int(r["pos"]),
                                 "ref": r["ref"].upper(), "alt": r["alt"].upper(),
                                 "current_name": r["rsid"], "source": "manual"}
    return out, True


def run(sk):
    cfg = pc.load_config()
    det = sk.require("01-detect-input")
    itype = det["metrics"]["input_type"]
    pc.PANELS.mkdir(parents=True, exist_ok=True)
    cache_dir = pc.PANELS / "cache"
    cache_dir.mkdir(exist_ok=True)

    # ---- P1 ---------------------------------------------------------
    p1 = json.loads((RES / "p1-tnrc18.json").read_text())
    pairing = pc.PANELS / "p1-proxy-pairing.json"
    if pairing.exists():
        p1["proxy"]["allele_pairing"] = json.loads(pairing.read_text())
    (pc.PANELS / "p1-tnrc18.json").write_text(json.dumps(p1, indent=2) + "\n")
    shutil.copy(RES / "p2-study.json", pc.PANELS / "p2-study.json")

    # ---- P2 ---------------------------------------------------------
    snps = pc.read_tsv(RES / "p2-212-snps.tsv")
    ids = [s["rsid"] for s in snps]
    if len(ids) != 212 or len(set(ids)) != 212:
        raise pc.SkillFail(f"bundled P2 list has {len(ids)} rows / {len(set(ids))} unique; expected 212")

    manual, have_manual = load_manual()
    coords = {}
    for build in ("GRCh37", "GRCh38"):
        cache_file = cache_dir / f"p2-coords-{build}.json"
        cached = json.loads(cache_file.read_text()) if cache_file.exists() else {}
        missing = [i for i in ids if i not in cached and i not in manual[build]]
        if missing and cfg.get("network", True):
            try:
                data = ensembl_batch(sk, build, missing)
                new = parse_ensembl(sk, build, data)
                cached.update(new)
                cache_file.write_text(json.dumps(cached, indent=1, sort_keys=True) + "\n")
                not_found = [i for i in missing if i not in data]
                if not_found:
                    sk.warn(f"Ensembl {build} did not return {len(not_found)} rsIDs: {', '.join(not_found[:10])}")
            except Exception as e:  # noqa: BLE001 - network is optional
                sk.warn(f"Ensembl {build} lookup failed ({e}); {len(missing)} P2 sites lack {build} coordinates")
        elif missing:
            sk.warn(f"network disabled; {len(missing)} P2 sites lack {build} coordinates")
        merged = dict(cached)
        merged.update(manual[build])
        coords[build] = merged

    rows = []
    for s in snps:
        r = dict(s)
        for build, tag in (("GRCh37", "37"), ("GRCh38", "38")):
            c = coords[build].get(s["rsid"])
            r[f"chrom{tag}"] = c["chrom"] if c else ""
            r[f"pos{tag}"] = c["pos"] if c else ""
            r[f"ref{tag}"] = c["ref"] if c else ""
            r[f"alt{tag}"] = c["alt"] if c else ""
            r[f"src{tag}"] = c["source"] if c else ""
        rows.append(r)
    header = ["rank", "rsid", "gene_reported", "effect_size", "fdr_q", "source_table",
              "chrom37", "pos37", "ref37", "alt37", "src37", "chrom38", "pos38", "ref38", "alt38", "src38"]
    pc.write_tsv(pc.PANELS / "p2-212-snps.tsv", header, rows)

    n37 = sum(1 for r in rows if r["pos37"] != "")
    n38 = sum(1 for r in rows if r["pos38"] != "")
    build = det["metrics"].get("build", "")
    n_build = n37 if build == "GRCh37" else n38 if build == "GRCh38" else 0
    sk.metrics.update({"p1_sites": 2, "p2_snps": len(rows), "p2_with_GRCh37": n37,
                       "p2_with_GRCh38": n38, "input_build": build,
                       "manual_coords_file": have_manual,
                       "proxy_pairing_known": pairing.exists()})
    sk.outputs = {"p1_panel": "panels/p1-tnrc18.json", "p2_panel": "panels/p2-212-snps.tsv",
                  "p2_study": "panels/p2-study.json"}

    if itype == "array":
        if n37 < 212:
            sk.warn(f"only {n37}/212 P2 sites have GRCh37 alleles; array strand checks will be skipped for the rest")
        status = pc.WARN if sk.warnings else pc.OK
        return status, f"P1 panel ready; P2 212 rsIDs ready for array lookup ({n37} with GRCh37 alleles)"
    if n_build == 0:
        sk.warn(f"no P2 sites have {build} coordinates; only Paper 1 can be genotyped from this {itype}. "
                "Re-run with network on, or supply panels/p2-coords-manual.tsv")
        return pc.WARN, f"P1 panel ready; P2 has no {build} coordinates (P2 will be skipped)"
    if n_build < 212:
        sk.warn(f"{212 - n_build} P2 sites lack {build} coordinates and will be reported as NO_COORDS")
    status = pc.WARN if sk.warnings else pc.OK
    return status, f"P1 panel ready; P2 {n_build}/212 sites have {build} coordinates"


if __name__ == "__main__":
    pc.main(NAME, run)
