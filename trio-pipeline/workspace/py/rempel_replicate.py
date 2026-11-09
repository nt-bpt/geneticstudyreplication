#!/usr/bin/env python3
"""Re-run the preprint's method AS PUBLISHED in github.com/maxrempel/xg1-2024 (read from the notebooks), not my own definition.

  NPASearch45v14 : a record is an NPA if the child's two alleles are not both among the parents' four alleles; any record type
                   (SNV, indel, SV, multiallelic); no FILTER test; records with a missing allele are skipped.
  WinRank46v04   : windows of 60,000 bp (60 'SNPs' x an assumed 1,000 bp each), step 20,000 bp, starting at the trio's first NPA;
                   a window is kept if it holds >= 5 NPA records.
  Classification : max kept-window count <10 normal, 10-19 'possible hybrid', >=20 'definite hybrid' (paper's Table 1).
  WindowCollapse : windows whose centres are within 50 kb of the FIRST window centre of the current region are merged; the
                   notebook SUMS their NPA counts (windows overlap, so the sum double counts).
usage: rempel_replicate.py --vcf V --contig C --start S --end E --trios T --outdir D [--focus-start A --focus-end B]"""
import argparse, os, sys
import numpy as np
from cyvcf2 import VCF

ap = argparse.ArgumentParser()
ap.add_argument("--vcf", required=True); ap.add_argument("--contig", required=True)
ap.add_argument("--start", type=int, default=1); ap.add_argument("--end", type=int, default=0)
ap.add_argument("--trios", required=True); ap.add_argument("--outdir", required=True)
ap.add_argument("--window-bp", type=int, default=60000); ap.add_argument("--step-bp", type=int, default=20000)
ap.add_argument("--min-npas", type=int, default=5); ap.add_argument("--collapse-gap", type=int, default=50000)
ap.add_argument("--focus-start", type=int, default=0); ap.add_argument("--focus-end", type=int, default=0)
ap.add_argument("--progress", type=int, default=50000)
a = ap.parse_args()
os.makedirs(a.outdir, exist_ok=True)

vcf = VCF(a.vcf); idx = {s: i for i, s in enumerate(vcf.samples)}
trios = [l.rstrip("\n").split("\t") for l in open(a.trios)][1:]
trios = [t for t in trios if all(x in idx for x in t)]
T = len(trios)
if not T: sys.exit("no trio has all three members in the VCF")
ci = np.array([idx[t[0]] for t in trios]); fi = np.array([idx[t[1]] for t in trios]); mi = np.array([idx[t[2]] for t in trios])
region = f"{a.contig}:{a.start}-{a.end}" if a.end else (a.contig if a.start <= 1 else f"{a.contig}:{a.start}-")
print(f"replicating the published method on {region} with {T} trios", flush=True)

pos = [[] for _ in range(T)]; n_rec = 0; n_types = {"snv": 0, "indel": 0, "other": 0}
for v in vcf(region):
    n_rec += 1
    if n_rec % a.progress == 0: print(f"  {n_rec} records, now at {v.POS}", flush=True)
    G = v.genotype.array()
    if G.shape[1] < 2: continue
    A = G[:, :2].astype(np.int16); c, f, m = A[ci], A[fi], A[mi]
    ok = (c.min(1) >= 0) & (f.min(1) >= 0) & (m.min(1) >= 0)
    pool = np.stack([f[:, 0], f[:, 1], m[:, 0], m[:, 1]], axis=1)
    viol = ok & ~((pool == c[:, [0]]).any(1) & (pool == c[:, [1]]).any(1))
    for t in np.nonzero(viol)[0]: pos[t].append(v.POS)
    if viol.any(): n_types["snv" if v.is_snp else "indel" if v.is_indel else "other"] += 1

W, S, MINN = a.window_bp, a.step_bp, a.min_npas
fam_rows, win_rows, region_rows = [], [], []
for t in range(T):
    child = trios[t][0]; P = np.array(sorted(pos[t]), dtype=np.int64); tot = len(P)
    best = 0; wins = []
    if tot >= MINN and P[-1] > P[0]:
        starts = np.arange(P[0], P[-1] + 1, S)
        cnt = np.searchsorted(P, starts + W, side="left") - np.searchsorted(P, starts, side="left")
        for s0, k in zip(starts, cnt):
            if k >= MINN: wins.append((int(s0), int(s0 + W), int(k)))
        best = int(cnt.max()) if len(cnt) else 0
    cls = "definite" if best >= 20 else "possible" if best >= 10 else "normal"
    fam_rows.append((child, tot, best, cls, len(wins)))
    for s0, e0, k in wins: win_rows.append((child, s0, e0, k))
    # collapse as WindowCollapse50v02 does (gap measured from the region's FIRST window centre)
    regs = []
    for s0, e0, k in sorted(wins, key=lambda x: (x[0] + x[1]) // 2):
        cen = (s0 + e0) // 2
        if regs and cen - regs[-1]["cen"] <= a.collapse_gap:
            r = regs[-1]; r["end"] = max(r["end"], e0); r["start"] = min(r["start"], s0); r["sum"] += k; r["max"] = max(r["max"], k); r["n"] += 1
        else: regs.append(dict(cen=cen, start=s0, end=e0, sum=k, max=k, n=1))
    for r in regs:
        uniq = int(np.searchsorted(P, r["end"], side="left") - np.searchsorted(P, r["start"], side="left"))
        region_rows.append((child, r["start"], r["end"], r["n"], r["max"], r["sum"], uniq))

with open(f"{a.outdir}/rempel_families.tsv", "w") as fh:
    fh.write("child\ttotal_npa_records\tmax_window\tclass\tkept_windows\n")
    for r in sorted(fam_rows, key=lambda r: -r[2]): fh.write("\t".join(map(str, r)) + "\n")
with open(f"{a.outdir}/rempel_regions.tsv", "w") as fh:
    fh.write("child\tstart\tend\twindows\tmax_window_npas\tsum_of_window_counts\tunique_npa_records_in_region\n")
    for r in sorted(region_rows, key=lambda r: -r[4]): fh.write("\t".join(map(str, r)) + "\n")
with open(f"{a.outdir}/rempel_windows.tsv", "w") as fh:
    fh.write("child\tstart\tend\tnpas\n")
    for r in win_rows: fh.write("\t".join(map(str, r)) + "\n")

nn = sum(r[3] == "normal" for r in fam_rows); npos = sum(r[3] == "possible" for r in fam_rows); nde = sum(r[3] == "definite" for r in fam_rows)
print(f"records read {n_rec}; records that were NPA in >=1 trio: SNV {n_types['snv']}, indel {n_types['indel']}, other {n_types['other']}")
print(f"classification (paper's cut-offs on max 60 kb window): normal {nn}, possible hybrid (10-19) {npos}, definite hybrid (>=20) {nde}   [paper: 570 / 7 / 4 of 581]")
print("top families:")
for r in sorted(fam_rows, key=lambda r: -r[2])[:12]: print(f"  {r[0]:<10} max window {r[2]:>4}  total NPA records {r[1]:>6}  {r[3]}")
print("collapsed regions (top 8):")
for r in sorted(region_rows, key=lambda r: -r[4])[:8]:
    print(f"  {r[0]:<10} {r[1]}-{r[2]}  windows {r[3]}  max {r[4]}  summed {r[5]}  unique records in region {r[6]}")
if a.focus_end:
    print(f"regions overlapping {a.focus_start}-{a.focus_end}:")
    for r in sorted(region_rows, key=lambda r: -r[4]):
        if r[1] <= a.focus_end and r[2] >= a.focus_start: print(f"  {r[0]:<10} max {r[4]}  summed {r[5]}  unique {r[6]}")
print(f"METRIC trios={T}"); print(f"METRIC normal={nn}"); print(f"METRIC possible={npos}"); print(f"METRIC definite={nde}")
print(f"VERDICT published method on these data: {nn} normal / {npos} possible / {nde} definite of {T} trios (paper: 570/7/4 of 581)")
