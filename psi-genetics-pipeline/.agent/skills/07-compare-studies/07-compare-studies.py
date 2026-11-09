#!/usr/bin/env python3
"""SKILL 07 - set the sample's genotypes beside what each study reported.

Paper 1: one directional site (plus an optional LD proxy for arrays).
Paper 2: lookup only - genotypes at the 212 sites, no score (the paper gives no allele direction).
Outputs: results/07-compare-studies.json (metrics), results/07-p2-genotypes.tsv
"""
import json
import sys
from pathlib import Path

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "psicommon", Path(__file__).resolve().parents[2] / "lib" / "psi-common.py")
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)

NAME = "07-compare-studies"
USABLE = ("CALLED", "LOW_DEPTH")


def load_genotypes(itype):
    name = "05-genotypes-array.tsv" if itype == "array" else "06-genotypes-sequence.tsv"
    path = pc.RESULTS / name
    if not path.exists():
        raise pc.PrerequisiteError(f"results/{name} missing; run {'05-genotype-array' if itype == 'array' else '06-genotype-sequence'}")
    return pc.read_tsv(path), name


def hwe(af):
    q = af
    p = 1 - q
    return {"GG": round(p * p, 4), "GA": round(2 * p * q, 4), "AA": round(q * q, 4)}


def classify_p1(genotype):
    alleles = sorted(genotype.split("/"))
    key = "".join(alleles)
    if key == "GG":
        return ("GG", "Same genotype as all 13 'psychic' cases in the study (reference/wild-type). "
                      "It is also the most common genotype in the general population.")
    if key == "AG":
        return ("GA", "Same genotype as 7 of the 9 analysed controls in the study.")
    if key == "AA":
        return ("AA", "Homozygous for the alternate allele; this genotype was not reported in the study.")
    if "T" in alleles:
        return (genotype, "Carries the rare T allele, which the study did not discuss.")
    if len(alleles) == 1:
        return (genotype, "Haploid call; unexpected on chromosome 7.")
    return (genotype, "Genotype not interpretable against the study.")


def run(sk):
    det = sk.require("01-detect-input")
    itype = det["metrics"]["input_type"]
    if itype == "array":
        sk.require("05-genotype-array")
    else:
        sk.require("06-genotype-sequence")
    rows, source = load_genotypes(itype)
    p1_panel = json.loads((pc.PANELS / "p1-tnrc18.json").read_text())
    pairing_path = pc.PANELS / "p1-proxy-pairing.json"
    pairing = json.loads(pairing_path.read_text()) if pairing_path.exists() else None

    # ---------------- Paper 1 ----------------
    tgt = next(r for r in rows if r["study"] == "P1")
    prx = next((r for r in rows if r["study"] == "P1_proxy"), None)
    p1 = {"rsid": "rs117910193", "source_table": source, "direct_status": tgt["status"],
          "direct_genotype": tgt.get("genotype", ""), "depth": tgt.get("depth", ""),
          "proxy_status": prx["status"] if prx else "", "proxy_genotype": prx.get("genotype", "") if prx else ""}
    method, gt = "", ""
    if tgt["status"] in USABLE and tgt.get("genotype"):
        method, gt = "direct", tgt["genotype"]
        if tgt["status"] == "LOW_DEPTH":
            sk.warn(f"Paper 1 genotype rests on low read depth ({tgt.get('depth')}); treat it as uncertain")
    elif prx and prx["status"] in USABLE and prx.get("genotype"):
        if pairing and pairing.get("status") in ("RESOLVED", "LOW_CONCORDANCE") and pairing.get("map_proxy_to_target"):
            mp = pairing["map_proxy_to_target"]
            inferred = [mp.get(a) for a in prx["genotype"].split("/")]
            if None in inferred:
                sk.warn(f"proxy genotype {prx['genotype']} has an allele not seen in 1000 Genomes haplotypes")
            else:
                method, gt = "proxy", "/".join(inferred)
                p1["proxy_r2"] = p1_panel["proxy"]["r2_eur"]
                p1["proxy_concordance"] = pairing.get("concordance_target_alt")
                if pairing["status"] == "LOW_CONCORDANCE":
                    sk.warn("proxy concordance is below 95%; the inferred Paper 1 genotype is uncertain")
        else:
            sk.warn("proxy rs78262442 is genotyped but its allele pairing is unresolved (03-resolve-proxy); "
                    "Paper 1 genotype not inferred")
    if method:
        cls, text = classify_p1(gt)
        p1.update({"method": method, "genotype": gt, "class": cls, "comparison": text,
                   "matches_case_pattern": cls == "GG", "matches_control_majority": cls == "GA"})
    else:
        p1.update({"method": "none", "genotype": "", "class": "NOT_AVAILABLE",
                   "comparison": "This file does not contain a usable call at rs117910193 or its proxy."})
    if method == "direct" and prx and prx["status"] in USABLE and pairing and pairing.get("map_proxy_to_target"):
        mp = pairing["map_proxy_to_target"]
        implied = sorted(mp.get(a, "?") for a in prx["genotype"].split("/"))
        p1["proxy_consistent"] = implied == sorted(gt.split("/"))
        if not p1["proxy_consistent"]:
            sk.warn("direct genotype and proxy-implied genotype disagree (possible error, or a rare haplotype)")
    afs = p1_panel["population_af_alt_A"]
    p1["population_expectation_nfe_hwe"] = hwe(afs["gnomad_exomes_nfe"])
    p1["population_expectation_global_hwe"] = hwe(afs["gnomad_exomes_global"])
    p1["study_pattern"] = p1_panel["target"]["reported_pattern"]

    # ---------------- Paper 2 ----------------
    p2rows = [r for r in rows if r["study"] == "P2"]
    out_rows = []
    for r in p2rows:
        out_rows.append({"rank": r["rank"], "rsid": r["rsid"], "gene_reported": r.get("gene", ""),
                         "genotype": r.get("genotype", ""), "status": r["status"],
                         "depth": r.get("depth", ""), "note": r.get("note", "") or r.get("strand_check", "")})
    effect = {x["rsid"]: x["effect_size"] for x in pc.read_tsv(pc.PANELS / "p2-212-snps.tsv")}
    for o in out_rows:
        o["effect_size_unsigned"] = effect.get(o["rsid"], "")
    out_rows.sort(key=lambda o: int(o["rank"]))
    p2_out = pc.RESULTS / "07-p2-genotypes.tsv"
    pc.write_tsv(p2_out, ["rank", "rsid", "gene_reported", "effect_size_unsigned", "genotype", "status",
                          "depth", "note"], out_rows)
    called = [o for o in out_rows if o["status"] in USABLE]
    top20 = [o for o in out_rows if int(o["rank"]) <= 20]
    status_counts = {}
    for o in out_rows:
        status_counts[o["status"]] = status_counts.get(o["status"], 0) + 1
    p2 = {"n_sites": len(out_rows), "n_called": len(called),
          "n_top20_called": sum(1 for o in top20 if o["status"] in USABLE),
          "status_counts": status_counts,
          "top_hit": next((o for o in out_rows if o["rsid"] == "rs10410488"), {}),
          "scoring": "NOT_POSSIBLE - the paper reports no allele direction, encoding or model"}

    sk.metrics.update({"input_type": itype, "build": det["metrics"].get("build"), "paper1": p1, "paper2": p2})
    sk.outputs = {"p2_genotypes": pc.rel(p2_out)}
    status = pc.WARN if (sk.warnings or p1["class"] == "NOT_AVAILABLE") else pc.OK
    if p1["class"] == "NOT_AVAILABLE":
        sk.warn("Paper 1 could not be checked for this sample")
    return status, (f"Paper 1: {p1['class']} ({p1['method']}); "
                    f"Paper 2: {len(called)}/{len(out_rows)} sites genotyped, lookup only")


if __name__ == "__main__":
    pc.main(NAME, run)
