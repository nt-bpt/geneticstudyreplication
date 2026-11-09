#!/usr/bin/env python3
"""Build trios.tsv (child, father, mother) from the 1000G pedigree file and the VCF's sample list.
usage: prepare_trios.py PEDIGREE VCF_SAMPLES.txt OUT.tsv
The pedigree column layout is detected from its header when there is one; otherwise standard PED order
(family, sample, father, mother) is assumed. The first rows are printed so you can check the choice."""
import re, sys
ped, samples_file, out = sys.argv[1:4]
samples = {l.strip() for l in open(samples_file) if l.strip()}
rows = [re.split(r"[\t ]+", l.strip()) for l in open(ped) if l.strip() and not l.startswith("##")]
first = [c.strip("#").lower() for c in rows[0]]
has_header = any(re.search(r"father|paternal|mother|maternal|dad|mom", c) for c in first)
if has_header:
    def col(pats, exclude=()):
        for i, c in enumerate(first):
            if any(re.search(p, c) for p in pats) and not any(re.search(x, c) for x in exclude): return i
        return None
    ci, fi, mi = col([r"^sample", r"individual", r"^iid"], exclude=["fam"]), col([r"father", r"paternal", r"dad"]), col([r"mother", r"maternal", r"mom"])
    if None in (ci, fi, mi): sys.exit(f"cannot find sample/father/mother columns in header: {rows[0]}")
    data = rows[1:]; how = f"header found: sample={rows[0][ci]}, father={rows[0][fi]}, mother={rows[0][mi]}"
else:
    ci, fi, mi = 1, 2, 3; data = rows; how = "no header: assuming PED order family, sample, father, mother"
print(how); print("first rows:"); [print("   ", r) for r in rows[:3]]
MISSING = {"0", ".", "", "na", "-9", "none"}
trios, seen, n_with_parents = [], set(), 0
for r in data:
    if len(r) <= max(ci, fi, mi): continue
    c, f, m = r[ci], r[fi], r[mi]
    if f.lower() in MISSING or m.lower() in MISSING: continue
    n_with_parents += 1
    if c in samples and f in samples and m in samples and c not in seen:
        trios.append((c, f, m)); seen.add(c)
print(f"pedigree rows: {len(data)}; with both parents listed: {n_with_parents}; complete trios present in the VCF: {len(trios)}")
if not trios: sys.exit("no usable trios — check the pedigree layout printed above")
with open(out, "w") as fh:
    fh.write("child\tfather\tmother\n")
    for t in trios: fh.write("\t".join(t) + "\n")
print(f"METRIC trios={len(trios)}")
print(f"METRIC pedigree_rows={len(data)}")
print(f"VERDICT {len(trios)} complete trios")
