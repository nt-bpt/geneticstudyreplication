#!/usr/bin/env python3
"""SKILL 05 - read a consumer array raw file (23andMe, AncestryDNA, MyHeritage/FTDNA CSV)
and extract genotypes at every panel rsID. Skipped for sequence input.

Output: results/05-genotypes-array.tsv
"""
import csv
import json
import sys
from pathlib import Path

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "psicommon", Path(__file__).resolve().parents[2] / "lib" / "psi-common.py")
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)

NAME = "05-genotype-array"
NO_CALL = {"--", "00", "0", "", "NC", "N", "NN", "??", "-"}
HEADER = ["study", "rank", "rsid", "gene", "chrom", "pos", "genotype", "raw_genotype",
          "status", "strand_check", "expected_alleles", "note"]


def panel_sites():
    p1 = json.loads((pc.PANELS / "p1-tnrc18.json").read_text())
    sites = []
    for role in ("target", "proxy"):
        s = p1[role]
        sites.append({"study": "P1" if role == "target" else "P1_proxy", "rank": "", "rsid": s["rsid"],
                      "gene": s.get("gene", "TNRC18"),
                      "alleles": [s["GRCh37"]["ref"]] + s["GRCh37"]["alt"],
                      "pos37": s["GRCh37"]["pos"]})
    for r in pc.read_tsv(pc.PANELS / "p2-212-snps.tsv"):
        alleles = [r["ref37"]] + r["alt37"].split(",") if r["ref37"] else []
        sites.append({"study": "P2", "rank": r["rank"], "rsid": r["rsid"], "gene": r["gene_reported"],
                      "alleles": alleles, "pos37": int(r["pos37"]) if r["pos37"] else None})
    return sites


def parse_line(line, fmt):
    if fmt == "csv":
        row = next(csv.reader([line]))
    else:
        row = line.rstrip("\n").split("\t")
        if len(row) == 1:
            row = line.split()
    row = [c.strip().strip('"') for c in row]
    if len(row) < 4:
        return None
    rsid, chrom, pos = row[0], row[1], row[2]
    gt = row[3] + row[4] if len(row) >= 5 and len(row[3]) <= 1 and len(row[4]) <= 1 else row[3]
    return rsid, chrom, pos, gt.upper()


def strand_check(gt_alleles, expected):
    """Return (alleles_to_use, check) for observed alleles vs expected plus-strand alleles."""
    if not expected:
        return gt_alleles, "UNCHECKED"
    exp = set(expected)
    if set(gt_alleles) <= exp:
        return gt_alleles, "OK"
    comp = [pc.COMPLEMENT.get(a, a) for a in gt_alleles]
    palin = exp in ({"A", "T"}, {"C", "G"})
    if set(comp) <= exp and not palin:
        return comp, "COMPLEMENTED"
    return gt_alleles, "ALLELE_MISMATCH"


def run(sk):
    det = sk.require("01-detect-input")
    sk.require("02-prepare-panels")
    m = det["metrics"]
    if m["input_type"] != "array":
        return pc.SKIPPED, f"{m['input_type']} input is genotyped by 06-genotype-sequence"
    fmt = m.get("file_format", "tsv")
    sites = panel_sites()
    wanted = {s["rsid"]: s for s in sites}
    found = {}
    n_lines = 0
    with pc.open_text(m["input_path"]) as fh:
        for line in fh:
            if line.startswith("#") or not line.strip() or line.lower().lstrip('"').startswith("rsid"):
                continue
            n_lines += 1
            rid = line.split("\t", 1)[0].split(",", 1)[0].strip().strip('"')
            if rid in wanted:
                parsed = parse_line(line, fmt)
                if parsed:
                    found[rid] = parsed
    sk.metrics["rows_read"] = n_lines
    if n_lines < 1000:
        sk.warn(f"only {n_lines} genotype rows read; is this a complete raw-data file?")

    rows, pos_checks = [], {"GRCh37": 0, "other": 0}
    for s in sites:
        r = {"study": s["study"], "rank": s["rank"], "rsid": s["rsid"], "gene": s["gene"],
             "expected_alleles": "/".join(s["alleles"])}
        if s["rsid"] not in found:
            r.update({"status": "NOT_ON_CHIP", "genotype": "", "strand_check": ""})
            rows.append(r)
            continue
        _, chrom, pos, gt = found[s["rsid"]]
        r.update({"chrom": pc.strip_chr(chrom), "pos": pos, "raw_genotype": gt})
        if s["pos37"] and pos.isdigit():
            pos_checks["GRCh37" if int(pos) == s["pos37"] else "other"] += 1
        if gt in NO_CALL or any(a not in "ACGT" for a in gt):
            note = "indel/no-call code" if gt not in NO_CALL else ""
            r.update({"status": "NO_CALL", "genotype": "", "strand_check": "", "note": note})
            rows.append(r)
            continue
        alleles = list(gt)
        if len(alleles) == 1:
            r["note"] = "haploid call (X/Y/MT in males)"
        use, check = strand_check(alleles, s["alleles"])
        r.update({"status": "CALLED", "genotype": "/".join(sorted(use, key=lambda a: (
            s["alleles"].index(a) if a in s["alleles"] else 9, a))), "strand_check": check})
        rows.append(r)

    out = pc.RESULTS / "05-genotypes-array.tsv"
    pc.write_tsv(out, HEADER, rows)
    sk.outputs = {"genotypes": pc.rel(out)}

    def count(study, status):
        return sum(1 for r in rows if r["study"] == study and r["status"] == status)
    p1 = next(r for r in rows if r["study"] == "P1")
    prox = next(r for r in rows if r["study"] == "P1_proxy")
    mism = [r["rsid"] for r in rows if r.get("strand_check") == "ALLELE_MISMATCH"]
    comp = [r["rsid"] for r in rows if r.get("strand_check") == "COMPLEMENTED"]
    sk.metrics.update({
        "p1_target_status": p1["status"], "p1_target_genotype": p1.get("genotype", ""),
        "p1_proxy_status": prox["status"], "p1_proxy_genotype": prox.get("genotype", ""),
        "p2_called": count("P2", "CALLED"), "p2_no_call": count("P2", "NO_CALL"),
        "p2_not_on_chip": count("P2", "NOT_ON_CHIP"),
        "allele_mismatches": mism, "complemented": comp,
        "positions_matching_GRCh37": pos_checks["GRCh37"], "positions_other": pos_checks["other"],
    })
    if mism:
        sk.warn(f"{len(mism)} sites have alleles that do not match the panel even after complementing: "
                + ", ".join(mism[:10]))
    if comp:
        sk.warn(f"{len(comp)} sites were reported on the minus strand and were complemented")
    if pos_checks["other"] > pos_checks["GRCh37"] and pos_checks["other"] > 5:
        sk.warn("most panel positions in the file do not match GRCh37; the file may use another build "
                "(rsID matching is unaffected)")
    if p1["status"] != "CALLED" and prox["status"] != "CALLED":
        sk.warn("neither rs117910193 nor its proxy rs78262442 is called in this file; "
                "Paper 1 cannot be checked from this array")
    called = count("P2", "CALLED")
    if called == 0:
        raise pc.SkillFail("none of the 212 Paper 2 rsIDs were found; this does not look like a supported raw file")
    status = pc.WARN if sk.warnings else pc.OK
    return status, (f"P1 target {p1['status']}{' ' + p1['genotype'] if p1.get('genotype') else ''}, "
                    f"proxy {prox['status']}; P2 {called}/212 called")


if __name__ == "__main__":
    pc.main(NAME, run)
