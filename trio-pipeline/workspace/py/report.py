#!/usr/bin/env python3
"""usage: report.py WORK_DIR CHROM FOCUS_START FOCUS_END"""
import csv, json, os, sys
W, chrom, fs, fe = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
R = lambda n: (json.load(open(f"{W}/results/{n}.json")) if os.path.exists(f"{W}/results/{n}.json") else None)
def tsv(p): return list(csv.DictReader(open(p), delimiter="\t")) if os.path.exists(p) else []
out = []; P = out.append
P("=" * 72); P("TRIO ANALYSIS — nonparental-allele (NPA) clusters, 1000 Genomes 30x phased panel"); P("=" * 72)
P("Independent re-implementation of the signal described in an unreviewed preprint (Rempel 2025).")
P("It does NOT use the author's code; the definition below is mine and may differ from his.\n")
P("STEPS")
for n in ["00_check_env", "01_download", "02_build_trios", "03_npa_scan", "04_context_checks", "05_compare_rempel", "06_baseline", "07_rempel_method"]:
    r = R(n); P(f"  {n:<20}{(r or {}).get('status', 'NOT RUN'):<9}{(r or {}).get('verdict', '')}")
    for w in (r or {}).get("warnings", []): P(f"      warning: {w}")
d = f"{W}/npa/chr{chrom}"
trios, regs, ctx = tsv(f"{d}/npa_per_trio.tsv"), tsv(f"{d}/npa_regions.tsv"), tsv(f"{d}/npa_region_context.tsv")
P("\nRESULT 1 — do hot NPA regions exist?")
if not trios: P("  no scan output — cannot report"); open(f"{W}/results/FINAL_REPORT.txt", "w").write("\n".join(out)); print("\n".join(out)); sys.exit(0)
withreg = [t for t in trios if int(t["n_regions"] or 0) > 0]
P(f"  trios scanned: {len(trios)}; trios with >=1 hot region: {len(withreg)}; regions: {len(regs)}")
hb = [t for t in trios if t["high_background"] == "YES"]
P(f"  high-background trios (NPA rate >= several x cohort median — suspect sample/pedigree problem): {len(hb)}")
P("\nRESULT 2 — the claimed window chr%s:%d-%d" % (chrom, fs, fe))
atfocus = [r for r in regs if int(r["start"]) <= fe and int(r["end"]) >= fs]
P(f"  hot regions overlapping it: {len(atfocus)} in {len({r['child'] for r in atfocus})} trios")
for r in atfocus[:15]:
    c = next((x for x in ctx if x["child"] == r["child"] and x["start"] == r["start"]), None)
    P(f"    {r['child']}  {r['start']}-{r['end']}  {r['n_events']} NPAs  log10p={r['log10p_adj']}  tags: {c['tags'] if c else '(not in top N)'}")
P("\nRESULT 3 — what the explanatory checks say (top regions)")
if ctx:
    cnt = lambda t: sum(t in c["tags"] for c in ctx)
    P(f"  regions checked {len(ctx)}: segdup overlap {cnt('segdup_overlap')}, SV in same trio {cnt('sv_in_trio')}, SV nearby {cnt('sv_nearby')}, "
      f"recurrent across trios {cnt('recurrent_x')}, common alleles {cnt('common_alleles')}, rare alleles {cnt('rare_alleles')}, high-background trio {cnt('high_background_trio')}")
    none = [c for c in ctx if c["tags"] == "none" or c["tags"] == "overlaps_focus"]
    P(f"  regions with NO mundane tag: {len(none)}  <- these are the ones worth manual inspection (reads/IGV)")
else: P("  not run")
b = tsv(f"{W}/results/06_baseline.tsv")
P("\nRESULT 4 — baseline")
if len(b) > 1:
    P("  chrom  trios_with_region  regions  informative_records  regions per 1000 records")
    for r in b:
        try: rate = 1000 * int(r["regions"]) / int(r["informative_records"])
        except Exception: rate = float("nan")
        P(f"  {r['chrom']:<6} {r['trios_with_region']:<18} {r['regions']:<8} {r['informative_records']:<20} {rate:.2f}")
else: P("  not run — without it, 'hot' only means hot relative to each trio's own background, not relative to other chromosomes")
r5 = R("05_compare_rempel"); P("\nRESULT 5 — families from the preprint vs other trios")
P("  " + ((r5 or {}).get("verdict") or "not run"))
P("\nRESULT 6 — the preprint's own published method, run on the same VCF (fixed 60 kb windows, any record type)")
rp = f"{W}/results/07_rempel_method.txt"
if os.path.exists(rp):
    keep = False
    for ln in open(rp).read().splitlines():
        if ln.startswith(("classification", "top families", "collapsed regions", "regions overlapping")): keep = True
        if ln.startswith(("METRIC", "VERDICT")): continue
        if keep: P("  " + ln)
else: P("  not run")
P("\nREADING THE RESULT")
P("  * A hot region means: many child alleles absent from both listed parents within ~60 informative SNVs, more than that trio's own background predicts.")
P("  * Tags are possible mundane explanations. A region carrying none of them is unexplained by THESE checks only; it is not evidence of any cause.")
P("  * Mendelian errors are rarer in the phased panel than in raw calls (phasing can use the pedigree). Hot regions that exist in raw genotypes but not here would be hidden by this choice.")
P("\nNOT VERIFIED")
P("  * The focus coordinates and the preprint's exact signal definition. * Family IDs (none bundled). * Cell-line (EBV) artifacts need read-level data (see personal pipeline).")
txt = "\n".join(out); open(f"{W}/results/FINAL_REPORT.txt", "w").write(txt + "\n"); print(txt)
print("METRIC trios=%d" % len(trios)); print("METRIC trios_with_region=%d" % len(withreg)); print("METRIC regions_at_focus=%d" % len(atfocus))
print("VERDICT report written")
