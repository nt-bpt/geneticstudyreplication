#!/usr/bin/env python3
"""Scan trios for clusters of nonparental alleles (NPAs). A reimplementation of the idea described for Rempel (2025);
it is NOT his code and need not reproduce his numbers exactly.

Definitions
  site         : SNV record that passes filters (FILTER is PASS or '.'); indels only with --include-indels
  informative  : for one trio, all three genotypes called AND at least one of the three carries a non-reference allele
  NPA          : informative site where a child allele is present in neither parent
  window       : WINDOW consecutive informative sites of that trio
  hot window   : a window containing >= MIN_WINDOW_NPA NPAs;  overlapping hot windows merge into a region
  p-value      : Poisson tail of the best window's NPA count against the trio's OWN background NPA rate (the rate outside
                 its regions), Bonferroni-corrected for the number of windows in that trio. A screening aid, not a proof:
                 NPAs are not independent (linkage, CNV, mapping artefacts), which makes p-values optimistic.
"""
import argparse, math, os, sys
import numpy as np
from cyvcf2 import VCF

ap = argparse.ArgumentParser()
ap.add_argument("--vcf", required=True); ap.add_argument("--contig", required=True)
ap.add_argument("--start", type=int, default=1); ap.add_argument("--end", type=int, default=0)
ap.add_argument("--trios", required=True); ap.add_argument("--outdir", required=True)
ap.add_argument("--window", type=int, default=60); ap.add_argument("--min-window-npa", type=int, default=8)
ap.add_argument("--include-indels", action="store_true"); ap.add_argument("--high-bg-factor", type=float, default=5.0)
ap.add_argument("--progress", type=int, default=20000)
a = ap.parse_args()
os.makedirs(a.outdir, exist_ok=True)

vcf = VCF(a.vcf)
idx = {s: i for i, s in enumerate(vcf.samples)}
trios = [l.rstrip("\n").split("\t") for l in open(a.trios)][1:]
trios = [t for t in trios if all(x in idx for x in t)]
T = len(trios)
if T == 0: sys.exit("no trio has all three members in the VCF")
ci = np.array([idx[t[0]] for t in trios]); fi = np.array([idx[t[1]] for t in trios]); mi = np.array([idx[t[2]] for t in trios])

if a.end: region = f"{a.contig}:{a.start}-{a.end}"
else:     region = a.contig if a.start <= 1 else f"{a.contig}:{a.start}-"
print(f"scanning {region} with {T} trios, window={a.window} informative sites, hot window >= {a.min_window_npa} NPAs", flush=True)

cum = np.zeros(T, dtype=np.int64)          # informative sites seen so far, per trio
inf_total = np.zeros(T, dtype=np.int64)
npa_total = np.zeros(T, dtype=np.int64)
ev = [[] for _ in range(T)]                # per trio: (cum_index, pos, ref, allele_base, child_gt, father_gt, mother_gt, cohort_af)
n_rec = n_used = 0

for v in vcf(region):
    n_rec += 1
    if n_rec % a.progress == 0: print(f"  {n_rec} records, now at {v.POS}", flush=True)
    if v.FILTER is not None: continue
    if not (v.is_snp or (a.include_indels and v.is_indel)): continue
    G = v.genotype.array()
    if G.shape[1] < 2: continue
    A = G[:, :2].astype(np.int16)
    c, f, m = A[ci], A[fi], A[mi]
    called = (c.min(1) >= 0) & (f.min(1) >= 0) & (m.min(1) >= 0)
    anyalt = np.maximum(np.maximum(c.max(1), f.max(1)), m.max(1)) > 0
    inf = called & anyalt
    if not inf.any(): continue
    n_used += 1
    pool = np.stack([f[:, 0], f[:, 1], m[:, 0], m[:, 1]], axis=1)
    npa0 = inf & ~(pool == c[:, [0]]).any(1)
    npa1 = inf & ~(pool == c[:, [1]]).any(1)
    npa = npa0 | npa1
    cum += inf; inf_total += inf; npa_total += npa
    if npa.any():
        alleles = [v.REF] + list(v.ALT)
        an = int((A >= 0).sum())
        for t in np.nonzero(npa)[0]:
            al = int(c[t, 0]) if npa0[t] else int(c[t, 1])
            af = float((A == al).sum()) / an if an else float("nan")
            ev[t].append((int(cum[t]), v.POS, v.REF, alleles[al] if al < len(alleles) else "?",
                          f"{c[t,0]}/{c[t,1]}", f"{f[t,0]}/{f[t,1]}", f"{m[t,0]}/{m[t,1]}", af))
print(f"done: {n_rec} records read, {n_used} informative for at least one trio", flush=True)


def log10_poisson_sf(k, lam):
    """log10 P(X >= k), X ~ Poisson(lam)."""
    if k <= 0: return 0.0
    lam = max(lam, 1e-9)
    logs = [-lam + i * math.log(lam) - math.lgamma(i + 1) for i in range(k, k + 400)]
    mx = max(logs)
    return (mx + math.log(sum(math.exp(x - mx) for x in logs))) / math.log(10)


W, MINW = a.window, a.min_window_npa
regions, per_trio = [], []
for t in range(T):
    E = len(ev[t]); child, father, mother = trios[t]
    row = dict(child=child, father=father, mother=mother, informative=int(inf_total[t]), npa=int(npa_total[t]),
               rate=float(npa_total[t]) / max(int(inf_total[t]), 1), bg_rate=float(npa_total[t]) / max(int(inf_total[t]), 1), n_regions=0, best_window=0,
               best_start="", best_end="", best_events=0, best_log10p="", )
    if E:
        cums = np.array([e[0] for e in ev[t]], dtype=np.int64)
        count = np.searchsorted(cums, cums + W, side="left") - np.arange(E)    # NPAs in the window starting at event i
        hot = np.nonzero(count >= MINW)[0]
        merged = []
        for i in hot:
            s, e = int(cums[i]), int(cums[i]) + W
            if merged and s <= merged[-1][1]: merged[-1][1] = max(merged[-1][1], e)
            else: merged.append([s, e])
        in_regions = 0; reg_windows = 0; trio_regions = []
        for s, e in merged:
            mask = (cums >= s) & (cums < e)
            evs = [ev[t][j] for j in np.nonzero(mask)[0]]
            in_regions += len(evs); reg_windows += (e - s)
            trio_regions.append((s, e, evs, int(count[mask].max())))
        bg = max((npa_total[t] - in_regions) / max(inf_total[t] - reg_windows, 1), 1e-7)
        nwin = max(inf_total[t] / W, 1.0)
        row['bg_rate'] = bg      # NPA rate OUTSIDE the hot regions: used for the high-background flag so a cluster cannot flag its own trio
        for s, e, evs, best in trio_regions:
            lp = min(0.0, log10_poisson_sf(best, bg * W) + math.log10(nwin))
            afs = sorted(x[7] for x in evs if x[7] == x[7])
            regions.append(dict(child=child, father=father, mother=mother, start=evs[0][1], end=evs[-1][1],
                                span_bp=evs[-1][1] - evs[0][1] + 1, n_events=len(evs), best_window=best, log10p_adj=lp,
                                median_cohort_af=afs[len(afs) // 2] if afs else float("nan"),
                                frac_af_lt_0001=sum(x < 0.001 for x in afs) / max(len(afs), 1),
                                frac_af_ge_01=sum(x >= 0.01 for x in afs) / max(len(afs), 1), events=evs))
        if trio_regions:
            best_r = min((r for r in regions if r["child"] == child), key=lambda r: r["log10p_adj"])
            row.update(n_regions=len(trio_regions), best_window=best_r["best_window"], best_start=best_r["start"],
                       best_end=best_r["end"], best_events=best_r["n_events"], best_log10p=f"{best_r['log10p_adj']:.2f}")
        else:
            row["best_window"] = int(count.max())
    per_trio.append(row)

rates = sorted(r["bg_rate"] for r in per_trio)
median_rate = rates[len(rates) // 2]
for r in per_trio:
    r["high_background"] = "YES" if median_rate > 0 and r["bg_rate"] >= a.high_bg_factor * median_rate else ""

with open(os.path.join(a.outdir, "npa_per_trio.tsv"), "w") as fh:
    cols = ["child", "father", "mother", "informative", "npa", "rate", "bg_rate", "n_regions", "best_window", "best_start", "best_end",
            "best_events", "best_log10p", "high_background"]
    fh.write("\t".join(cols) + "\n")
    for r in sorted(per_trio, key=lambda r: (r["best_log10p"] == "", float(r["best_log10p"] or 0))):
        fh.write("\t".join(f"{r[c]:.6g}" if isinstance(r[c], float) else str(r[c]) for c in cols) + "\n")
regions.sort(key=lambda r: r["log10p_adj"])
with open(os.path.join(a.outdir, "npa_regions.tsv"), "w") as fh:
    fh.write("child\tfather\tmother\tstart\tend\tspan_bp\tn_events\tbest_window\tlog10p_adj\tmedian_cohort_af\tfrac_af_lt_0.001\tfrac_af_ge_0.01\n")
    for r in regions:
        fh.write(f"{r['child']}\t{r['father']}\t{r['mother']}\t{r['start']}\t{r['end']}\t{r['span_bp']}\t{r['n_events']}\t{r['best_window']}\t"
                 f"{r['log10p_adj']:.2f}\t{r['median_cohort_af']:.5f}\t{r['frac_af_lt_0001']:.3f}\t{r['frac_af_ge_01']:.3f}\n")
with open(os.path.join(a.outdir, "npa_region_events.tsv"), "w") as fh:
    fh.write("child\tpos\tref\tnonparental_allele\tchild_gt\tfather_gt\tmother_gt\tcohort_af\n")
    for r in regions:
        for e in r["events"]: fh.write(f"{r['child']}\t{e[1]}\t{e[2]}\t{e[3]}\t{e[4]}\t{e[5]}\t{e[6]}\t{e[7]:.5f}\n")

nreg_trios = len({r["child"] for r in regions})
print(f"cohort median NPA rate per informative site: {median_rate:.2e}")
print(f"trios with >=1 hot region: {nreg_trios} of {T}; regions: {len(regions)}; high-background trios: {sum(1 for r in per_trio if r['high_background'])}")
for r in regions[:10]:
    print(f"  {r['child']}  {r['start']}-{r['end']}  {r['n_events']} NPAs (best window {r['best_window']})  log10p_adj={r['log10p_adj']:.1f}")
print(f"METRIC trios={T}"); print(f"METRIC records_read={n_rec}"); print(f"METRIC informative_records={n_used}")
print(f"METRIC trios_with_region={nreg_trios}"); print(f"METRIC regions={len(regions)}")
print(f"METRIC median_npa_rate={median_rate:.3e}")
print(f"METRIC high_background_trios={sum(1 for r in per_trio if r['high_background'])}")
print(f"VERDICT {nreg_trios} of {T} trios have >=1 hot NPA region ({len(regions)} regions)")
