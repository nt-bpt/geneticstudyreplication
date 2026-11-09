#!/usr/bin/env python3
"""Compare trios whose members are listed in a family file with all other trios.
usage: compare_rempel.py NPA_DIR FAMILY_FILE FOCUS_START FOCUS_END"""
import csv, math, sys
d, famfile, fs, fe = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
ids = {l.split()[0] for l in open(famfile) if l.strip() and not l.lstrip().startswith("#")}
trios = list(csv.DictReader(open(f"{d}/npa_per_trio.tsv"), delimiter="\t"))
regs = list(csv.DictReader(open(f"{d}/npa_regions.tsv"), delimiter="\t"))
def listed(t): return bool({t["child"], t["father"], t["mother"]} & ids)
L = [t for t in trios if listed(t)]; O = [t for t in trios if not listed(t)]
found = {x for t in L for x in (t["child"], t["father"], t["mother"])} & ids
print(f"listed IDs: {len(ids)}; matched to a trio in the VCF: {len(found)}; missing: {sorted(ids - found)[:10]}")
if not L: sys.exit("none of the listed IDs is in a trio — nothing to compare")
has = lambda t: int(t["n_regions"] or 0) > 0
fociset = {r["child"] for r in regs if int(r["start"]) <= fe and int(r["end"]) >= fs}
def rate(g): return sum(has(t) for t in g) / max(len(g), 1)
a, b = sum(has(t) for t in L), sum(has(t) for t in O)
print(f"listed trios with a hot region: {a}/{len(L)} ({rate(L):.0%});  other trios: {b}/{len(O)} ({rate(O):.0%})")
print(f"listed trios with a hot region overlapping the focus window: {sum(t['child'] in fociset for t in L)}/{len(L)};  other: {sum(t['child'] in fociset for t in O)}/{len(O)}")
p = None
try:
    from scipy.stats import fisher_exact
    p = fisher_exact([[a, len(L) - a], [b, len(O) - b]])[1]; print(f"Fisher exact p (listed vs other, any hot region): {p:.3g}")
except Exception: print("scipy missing — no significance test")
print(f"METRIC listed_trios={len(L)}"); print(f"METRIC listed_with_region={a}")
print(f"METRIC other_trios={len(O)}"); print(f"METRIC other_with_region={b}")
print(f"METRIC listed_at_focus={sum(t['child'] in fociset for t in L)}")
if p is not None: print(f"METRIC fisher_p={p:.3g}")
print(f"VERDICT listed {rate(L):.0%} vs other {rate(O):.0%} of trios have a hot region")
