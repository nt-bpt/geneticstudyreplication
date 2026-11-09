#!/usr/bin/env python3
"""Allele balance at heterozygous SNV/indel calls: primary hotspot and extended window vs control.

usage: allele_balance.py CALLS.vcf.gz PRIMARY_REGION EXTENDED_REGION CONTROL_REGION
A het site is 'skewed' when the exact two-sided binomial p-value for its ref/alt read split (expected 0.5)
is below AB_P_THRESHOLD. Counting skewed sites by p-value (not a fixed 0.35-0.65 band) keeps low-depth
sites from being flagged just because of sampling noise.
"""
import math, os, subprocess, sys

vcf, reg_primary, reg_ext, reg_ctrl = sys.argv[1:5]
MIN_DEPTH = int(os.environ.get("AB_MIN_DEPTH", "10"))
P_THR = float(os.environ.get("AB_P_THRESHOLD", "0.001"))
RATIO = float(os.environ.get("RATIO_FLAG", "2.0"))


def binom_two_sided(k, n, p=0.5):
    logp, logq = math.log(p), math.log(1 - p)
    def lpmf(i): return math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1) + i * logp + (n - i) * logq
    ref = lpmf(k)
    return min(1.0, sum(math.exp(lpmf(i)) for i in range(n + 1) if lpmf(i) <= ref + 1e-9))


def het_sites(region):
    cmd = ["bcftools", "query", "-r", region, "-f", "%POS\t%FILTER\t[%GT]\t[%AD]\n", vcf]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    sites = []
    for line in out.splitlines():
        pos, flt, gt, ad = line.split("\t")
        if flt not in ("PASS", "."): continue
        if gt.replace("|", "/") not in ("0/1", "1/0"): continue
        parts = ad.split(",")
        if len(parts) != 2 or "." in parts: continue
        r, a = int(parts[0]), int(parts[1])
        if r + a < MIN_DEPTH: continue
        sites.append((int(pos), r, a, binom_two_sided(a, r + a)))
    return sites


res = {}
for label, reg in (("primary", reg_primary), ("extended", reg_ext), ("control", reg_ctrl)):
    s = het_sites(reg)
    skew = [x for x in s if x[3] < P_THR]
    fr = sorted(x[2] / (x[1] + x[2]) for x in s)
    res[label] = dict(n_het=len(s), n_skew=len(skew), skew_pct=100.0 * len(skew) / len(s) if s else 0.0,
                      median_alt_frac=fr[len(fr) // 2] if fr else float("nan"), skewed=skew)

print(f"{'':<10}{'het sites':>10}{'skewed':>8}{'skewed %':>10}{'median alt frac':>17}")
for label in ("primary", "extended", "control"):
    r = res[label]; print(f"{label:<10}{r['n_het']:>10}{r['n_skew']:>8}{r['skew_pct']:>10.1f}{r['median_alt_frac']:>17.3f}")
for s in res["primary"]["skewed"][:15]:
    print(f"  skewed site in primary: pos={s[0]} ref_reads={s[1]} alt_reads={s[2]} p={s[3]:.2e}")

verdict_by = {}
for region in ("primary", "extended"):
    r, c = res[region], res["control"]
    if r["n_het"] < 10:
        verdict_by[region] = "LOW_POWER"            # too few het sites to say anything
    elif r["n_skew"] >= 3 and r["skew_pct"] > RATIO * c["skew_pct"]:
        verdict_by[region] = "FLAG"
    else:
        verdict_by[region] = "NORMAL"
for region in ("primary", "extended", "control"):
    for k in ("n_het", "n_skew"): print(f"METRIC {region}_{k}={res[region][k]}")
    print(f"METRIC {region}_skew_pct={res[region]['skew_pct']:.2f}")
print(f"METRIC flag_primary={1 if verdict_by['primary']=='FLAG' else 0}")
print(f"METRIC flag_extended={1 if verdict_by['extended']=='FLAG' else 0}")
print(f"METRIC primary_call={verdict_by['primary']}")
print(f"METRIC extended_call={verdict_by['extended']}")
print(f"VERDICT primary: {verdict_by['primary']} | extended: {verdict_by['extended']}"
      + ("  (primary has <10 het sites: low statistical power)" if verdict_by["primary"] == "LOW_POWER" else ""))
