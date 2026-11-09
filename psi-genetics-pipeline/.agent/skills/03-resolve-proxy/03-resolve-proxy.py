#!/usr/bin/env python3
"""SKILL 03 - work out which rs78262442 allele travels with each rs117910193 allele.

Uses phased 1000 Genomes phase 3 (GRCh37) EUR haplotypes. Needed only when the
input is a consumer array that has the proxy but not rs117910193 itself.
Writes panels/p1-proxy-pairing.json.
"""
import json
import os
import sys
from collections import Counter
from pathlib import Path

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "psicommon", Path(__file__).resolve().parents[2] / "lib" / "psi-common.py")
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)

NAME = "03-resolve-proxy"
KG_BASE = "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502"
KG_VCF = f"{KG_BASE}/ALL.chr7.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz"
KG_PANEL = f"{KG_BASE}/integrated_call_samples_v3.20130502.ALL.panel"
MIN_CONCORDANCE = 0.95


def eur_samples(sk, cfg, work):
    panel = cfg.get("kg_phase3_panel") or ""
    if not panel:
        panel = str(work / "1000G-phase3.panel")
        if not os.path.exists(panel):
            if not cfg.get("network", True):
                raise RuntimeError("network disabled and kg_phase3_panel not set")
            sk.run(["curl", "-fsSL", "--retry", "3", "-o", panel, KG_PANEL])
    eur = []
    with open(panel) as f:
        for line in f:
            c = line.rstrip("\n").split("\t")
            if len(c) >= 3 and c[2] == "EUR":
                eur.append(c[0])
    if not eur:
        raise pc.SkillFail(f"no EUR samples found in {panel}")
    return eur


def run(sk):
    cfg = pc.load_config()
    det = sk.require("01-detect-input")
    itype = det["metrics"]["input_type"]
    out_path = pc.PANELS / "p1-proxy-pairing.json"
    if out_path.exists():
        prev = json.loads(out_path.read_text())
        sk.metrics.update(prev)
        sk.outputs = {"pairing": pc.rel(out_path)}
        return pc.OK, f"proxy pairing already resolved: {prev.get('summary')}"
    if itype != "array":
        return pc.SKIPPED, f"{itype} input genotypes rs117910193 directly; proxy not needed"
    has_target = has_proxy = False
    with pc.open_text(det["metrics"]["input_path"]) as fh:
        for line in fh:
            rid = line.split("\t", 1)[0].split(",", 1)[0].strip().strip('"')
            has_target = has_target or rid == "rs117910193"
            has_proxy = has_proxy or rid == "rs78262442"
    sk.metrics.update({"array_has_target": has_target, "array_has_proxy": has_proxy})
    if has_target:
        return pc.SKIPPED, "array file contains rs117910193 itself; proxy not needed"
    if not has_proxy:
        return pc.SKIPPED, "array file has neither rs117910193 nor the proxy rs78262442; nothing to resolve"

    p1 = json.loads((pc.PANELS / "p1-tnrc18.json").read_text())
    t, p = p1["target"], p1["proxy"]
    tpos, ppos = t["GRCh37"]["pos"], p["GRCh37"]["pos"]
    work = Path(cfg["work_dir"])
    work.mkdir(parents=True, exist_ok=True)
    try:
        samples = eur_samples(sk, cfg, work)
    except Exception as e:  # noqa: BLE001 - optional step
        sk.warn(f"1000 Genomes sample panel unavailable ({e}); the proxy cannot be used")
        return pc.WARN, "proxy pairing unresolved (no 1000 Genomes sample panel)"
    sfile = work / "eur-samples.txt"
    sfile.write_text("\n".join(samples) + "\n")

    vcf = cfg.get("kg_phase3_chr7_vcf") or KG_VCF
    if vcf == KG_VCF and not cfg.get("network", True):
        sk.warn("network disabled and kg_phase3_chr7_vcf not set; the proxy cannot be used")
        return pc.WARN, "proxy pairing unresolved (no 1000 Genomes VCF)"
    if vcf == KG_VCF:
        # fetch the remote index under a dash-only local name instead of letting bcftools
        # save it with the upstream (underscored) file name
        local_tbi = work / "1000G-phase3-chr7.vcf.gz.tbi"
        if not local_tbi.exists():
            cp_tbi = sk.run(["curl", "-fsSL", "--retry", "3", "-o", str(local_tbi), KG_VCF + ".tbi"], check=False)
            if cp_tbi.returncode != 0:
                local_tbi.unlink(missing_ok=True)
                sk.warn("could not download the 1000 Genomes chr7 index; the proxy cannot be used")
                return pc.WARN, "proxy pairing unresolved (1000 Genomes not reachable)"
        vcf = f"{KG_VCF}##idx##{local_tbi}"
    lo, hi = min(tpos, ppos), max(tpos, ppos)
    region = f"7:{lo}-{hi}"
    cmd = (f"cd {json.dumps(str(work))} && bcftools view -r {region} -S {json.dumps(str(sfile))} "
           f"--force-samples {json.dumps(vcf)} -Ou | bcftools query "
           f"-i 'POS={tpos} || POS={ppos}' -f '%POS\\t%ID\\t%REF\\t%ALT[\\t%GT]\\n'")
    cp = sk.run(cmd, shell=True, check=False)
    if cp.returncode != 0 or not cp.stdout.strip():
        sk.warn("could not read 1000 Genomes haplotypes; the proxy cannot be used. "
                "Array files without rs117910193 will report Paper 1 as NOT_AVAILABLE")
        return pc.WARN, "proxy pairing unresolved (1000 Genomes not reachable)"

    recs = {}
    for line in cp.stdout.strip().splitlines():
        c = line.split("\t")
        pos, rid, ref, alt, gts = int(c[0]), c[1], c[2], c[3], c[4:]
        if "," in alt:
            sk.warn(f"{rid} is multi-allelic in 1000 Genomes ({ref}>{alt}); only the first ALT is used")
        wanted = t["rsid"] if pos == tpos else p["rsid"]
        if pos in recs and recs[pos]["id"] == wanted and rid != wanted:
            continue  # keep the record whose ID matches the rsID (split multi-allelics)
        recs[pos] = {"id": rid, "alleles": [ref] + alt.split(","), "gts": gts}
    if tpos not in recs or ppos not in recs:
        sk.warn(f"1000 Genomes lacks {'target' if tpos not in recs else 'proxy'} site")
        return pc.WARN, "proxy pairing unresolved (site missing in 1000 Genomes)"
    tr, pr = recs[tpos], recs[ppos]
    if tr["alleles"][0] != t["GRCh37"]["ref"] or pr["alleles"][0] != p["GRCh37"]["ref"]:
        raise pc.SkillFail("1000 Genomes reference alleles do not match the panel; check the VCF build")

    pairs = Counter()
    for gt_t, gt_p in zip(tr["gts"], pr["gts"]):
        if "|" not in gt_t or "|" not in gt_p:
            continue
        for ht, hp in zip(gt_t.split("|"), gt_p.split("|")):
            if ht == "." or hp == ".":
                continue
            pairs[(tr["alleles"][int(ht)], pr["alleles"][int(hp)])] += 1
    n = sum(pairs.values())
    if n == 0:
        return pc.WARN, "proxy pairing unresolved (no phased haplotypes)"

    tref, talt = tr["alleles"][0], tr["alleles"][1]
    pref, palt = pr["alleles"][0], pr["alleles"][1]
    # proxy allele that travels with each target allele
    def best(target_allele):
        sub = {pa: c for (ta, pa), c in pairs.items() if ta == target_allele}
        tot = sum(sub.values())
        if not tot:
            return None, 0.0, 0
        pa = max(sub, key=sub.get)
        return pa, sub[pa] / tot, tot
    pa_for_alt, conc_alt, n_alt = best(talt)
    pa_for_ref, conc_ref, n_ref = best(tref)

    # r2 from haplotype counts
    x11 = pairs.get((talt, palt), 0) / n
    p_t = sum(c for (ta, _), c in pairs.items() if ta == talt) / n
    p_p = sum(c for (_, pa), c in pairs.items() if pa == palt) / n
    d = x11 - p_t * p_p
    denom = p_t * (1 - p_t) * p_p * (1 - p_p)
    r2 = (d * d / denom) if denom else 0.0

    result = {
        "status": "RESOLVED",
        "target": t["rsid"], "proxy": p["rsid"],
        "proxy_allele_with_target_" + talt: pa_for_alt,
        "proxy_allele_with_target_" + tref: pa_for_ref,
        "map_proxy_to_target": {pa_for_alt: talt, pa_for_ref: tref} if pa_for_alt != pa_for_ref else {},
        "concordance_target_alt": round(conc_alt, 4), "n_target_alt_haplotypes": n_alt,
        "concordance_target_ref": round(conc_ref, 4), "n_target_ref_haplotypes": n_ref,
        "r2_eur_computed": round(r2, 4), "n_haplotypes": n,
        "haplotype_counts": {f"{a}-{b}": c for (a, b), c in sorted(pairs.items())},
        "source": "1000 Genomes phase 3 (GRCh37), EUR" if vcf.startswith(KG_VCF) else vcf,
    }
    result["summary"] = (f"{p['rsid']} {pa_for_alt} tags {t['rsid']} {talt} "
                         f"({conc_alt:.1%} of {n_alt} haplotypes); computed r2 {r2:.3f}")
    sk.metrics.update(result)
    if pa_for_alt == pa_for_ref:
        result["status"] = "UNUSABLE"
        sk.warn("the same proxy allele travels with both target alleles; the proxy cannot be used")
        out_path.write_text(json.dumps(result, indent=2) + "\n")
        return pc.WARN, "proxy is not informative"
    if conc_alt < MIN_CONCORDANCE or conc_ref < MIN_CONCORDANCE:
        result["status"] = "LOW_CONCORDANCE"
        sk.warn(f"proxy concordance below {MIN_CONCORDANCE:.0%}; inferred genotypes will be flagged")
    out_path.write_text(json.dumps(result, indent=2) + "\n")
    sk.outputs = {"pairing": pc.rel(out_path)}
    return (pc.WARN if sk.warnings else pc.OK), result["summary"]


if __name__ == "__main__":
    pc.main(NAME, run)
