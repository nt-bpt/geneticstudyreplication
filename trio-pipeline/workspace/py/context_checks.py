#!/usr/bin/env python3
"""Describe each hot NPA region with context checks. Descriptive tags only — none of them proves a cause.

usage: context_checks.py OUTDIR VCF CONTIG TRIOS_TSV SEGDUP_GZ|- SEGDUP_CHROM TOP_N PAD FOCUS_START FOCUS_END COMMON_AF
Tags: segdup_overlap (>=50% of the padded region lies in a UCSC segmental duplication),
      sv_in_trio (an SV-type record in the padded region is carried by the child), sv_nearby (SV present, child not a carrier),
      recurrent_xN (N other examined regions overlap this one), common_alleles (median cohort AF >= COMMON_AF),
      rare_alleles (>=80% of NPA alleles seen in <0.1% of the cohort), high_background_trio, overlaps_focus.
"""
import csv, gzip, os, sys
from cyvcf2 import VCF

outdir, vcf_path, contig, trios_tsv, segdup, seg_chrom, top_n, pad, f_s, f_e, common_af = sys.argv[1:12]
top_n, pad, f_s, f_e, common_af = int(top_n), int(pad), int(f_s), int(f_e), float(common_af)
regs = list(csv.DictReader(open(os.path.join(outdir, "npa_regions.tsv")), delimiter="\t"))
trio_rows = {r["child"]: r for r in csv.DictReader(open(os.path.join(outdir, "npa_per_trio.tsv")), delimiter="\t")}
for r in regs:
    for k in ("start", "end", "n_events", "best_window"): r[k] = int(r[k])
    for k in ("log10p_adj", "median_cohort_af", "frac_af_lt_0.001"): r[k] = float(r[k])

seg = []
if segdup != "-" and os.path.exists(segdup):
    op = gzip.open if segdup.endswith(".gz") else open
    with op(segdup, "rt") as fh:
        for line in fh:
            p = line.split("\t")
            if len(p) > 3 and p[1] == seg_chrom: seg.append((int(p[2]), int(p[3])))
    seg.sort()
print(f"segmental duplications loaded for {seg_chrom}: {len(seg)}" + ("" if seg else "  (no file: segdup tag unavailable)"))


def seg_fraction(s, e):
    tot = 0
    for a, b in seg:
        if b < s: continue
        if a > e: break
        tot += min(b, e) - max(a, s)
    return tot / max(e - s, 1)


vcf = VCF(vcf_path); idx = {s: i for i, s in enumerate(vcf.samples)}
trio_ids = {}
for line in list(open(trios_tsv))[1:]:
    c, f, m = line.rstrip("\n").split("\t")
    if c in idx and f in idx and m in idx: trio_ids[c] = (idx[c], idx[f], idx[m])


def sv_scan(s, e, child):
    ci, fi, mi = trio_ids[child]
    found = []
    if e - s > 5_000_000: return None
    for v in vcf(f"{contig}:{max(s - pad, 1)}-{e + pad}"):
        sym = any(str(x).startswith("<") for x in v.ALT)
        big = len(v.REF) >= 50 or any(len(str(x)) >= 50 for x in v.ALT)
        if not (sym or big or v.INFO.get("SVTYPE")): continue
        g = v.genotype.array()
        carr = [bool((g[i, :2] > 0).any()) for i in (ci, fi, mi)]
        found.append((v.POS, str(v.INFO.get("SVTYPE") or (v.ALT[0] if v.ALT else "?")), carr))
    return found


regs = sorted(regs, key=lambda r: r["log10p_adj"])[:top_n]
rows = []
for r in regs:
    tags = []
    sf = seg_fraction(r["start"] - pad, r["end"] + pad) if seg else None
    if sf is not None and sf >= 0.5: tags.append("segdup_overlap")
    svs = sv_scan(r["start"], r["end"], r["child"]) if r["child"] in trio_ids else None
    sv_txt = "skipped" if svs is None else f"{len(svs)}"
    if svs:
        tags.append("sv_in_trio" if any(x[2][0] for x in svs) else "sv_nearby")
    others = {q["child"] for q in regs if q["child"] != r["child"] and q["start"] <= r["end"] + pad and q["end"] >= r["start"] - pad}
    if others: tags.append(f"recurrent_x{len(others)}")
    if r["median_cohort_af"] >= common_af: tags.append("common_alleles")
    if r["frac_af_lt_0.001"] >= 0.8: tags.append("rare_alleles")
    if trio_rows.get(r["child"], {}).get("high_background") == "YES": tags.append("high_background_trio")
    if r["start"] <= f_e and r["end"] >= f_s: tags.append("overlaps_focus")
    rows.append(dict(r, segdup_frac="" if sf is None else f"{sf:.2f}", sv_records=sv_txt, tags=",".join(tags) or "none"))

cols = ["child", "start", "end", "n_events", "best_window", "log10p_adj", "median_cohort_af", "frac_af_lt_0.001", "segdup_frac", "sv_records", "tags"]
with open(os.path.join(outdir, "npa_region_context.tsv"), "w") as fh:
    fh.write("\t".join(cols) + "\n")
    for r in rows: fh.write("\t".join(f"{r[c]:.5g}" if isinstance(r[c], float) else str(r[c]) for c in cols) + "\n")
print(f"{'child':<10}{'start':>11}{'end':>11}{'NPAs':>6}{'log10p':>8}{'medAF':>8}  tags")
for r in rows[:25]:
    print(f"{r['child']:<10}{r['start']:>11}{r['end']:>11}{r['n_events']:>6}{r['log10p_adj']:>8.1f}{r['median_cohort_af']:>8.3f}  {r['tags']}")
def n(tag): return sum(1 for r in rows if tag in r["tags"])
print(f"METRIC regions_checked={len(rows)}")
for tag in ("segdup_overlap", "sv_in_trio", "sv_nearby", "common_alleles", "rare_alleles", "high_background_trio", "overlaps_focus"):
    print(f"METRIC n_{tag}={n(tag)}")
print(f"METRIC n_recurrent={sum(1 for r in rows if 'recurrent_x' in r['tags'])}")
print(f"METRIC n_no_tag={sum(1 for r in rows if r['tags'] == 'none')}")
print(f"VERDICT {len(rows)} regions described; {sum(1 for r in rows if r['tags'] == 'none')} carry none of the explanatory tags")
