#!/usr/bin/env python3
"""Join PASS calls in the gnomAD-covered span against gnomAD allele frequencies (keyed on pos/ref/alt).

usage: gnomad_join.py CALLS.vcf.gz GNOMAD_SUBSET.vcf.gz SPAN_START SPAN_END PRIMARY_START PRIMARY_END
                      AF_FIELD AC_FIELD AN_FIELD NHOM_FIELD OUT.tsv
Chromosome names are ignored on purpose: both inputs hold only chr3, and the two files may spell it differently.
"""
import subprocess, sys

calls, gvcf, span_s, span_e, prim_s, prim_e, f_af, f_ac, f_an, f_nh, out_tsv = sys.argv[1:12]
span_s, span_e, prim_s, prim_e = map(int, (span_s, span_e, prim_s, prim_e))
RARE = 0.01


def fnum(x):
    try: return float(x)
    except ValueError: return None


# ---- gnomAD records (alleles may be comma-separated) ----
fields = ["%POS", "%REF", "%ALT", "%FILTER"] + [f"%INFO/{f}" if f else "." for f in (f_af, f_ac, f_an, f_nh)]
fmt = "\t".join(x for x in fields if x != ".") + "\n"
have = [f for f in (f_af, f_ac, f_an, f_nh) if f]
gn = {}
txt = subprocess.run(["bcftools", "query", "-f", fmt, gvcf], capture_output=True, text=True).stdout
for line in txt.splitlines():
    p = line.split("\t"); pos, ref, alts, flt = int(p[0]), p[1], p[2].split(","), p[3]
    vals = dict(zip(have, p[4:]))
    afs = (vals.get(f_af) or ".").split(","); acs = (vals.get(f_ac) or ".").split(",")
    an = vals.get(f_an, "."); nh = (vals.get(f_nh) or ".").split(",")
    for i, alt in enumerate(alts):
        af = fnum(afs[i]) if i < len(afs) else None
        ac = acs[i] if i < len(acs) else "."
        if af is None and fnum(ac) is not None and fnum(an):
            af = fnum(ac) / fnum(an)
        gn[(pos, ref, alt)] = dict(af=af, ac=ac, an=an, nhom=nh[i] if i < len(nh) else ".", filter=flt)

# ---- our PASS calls ----
txt = subprocess.run(["bcftools", "query", "-f", "%POS\t%REF\t%ALT\t%FILTER\t[%GT]\t[%DP]\n", calls],
                     capture_output=True, text=True).stdout
rows, counts = [], dict(absent=0, rare=0, common=0, unknown=0)
prim = dict(absent=0, rare=0, common=0, unknown=0)
for line in txt.splitlines():
    pos, ref, alt, flt, gt, dp = line.split("\t")
    pos = int(pos)
    if flt not in ("PASS", ".") or not (span_s <= pos <= span_e): continue
    g = gn.get((pos, ref, alt))
    if g is None: cls, af = "absent", 0.0
    elif g["af"] is None: cls, af = "unknown", None
    else: cls, af = ("absent" if g["af"] == 0 else "rare" if g["af"] < RARE else "common"), g["af"]
    in_p = prim_s <= pos <= prim_e
    counts[cls] += 1
    if in_p: prim[cls] += 1
    rows.append((pos, ref, alt, gt, dp, "" if af is None else f"{af:.6g}", cls,
                 g["ac"] if g else ".", g["nhom"] if g else ".", g["filter"] if g else ".", "YES" if in_p else ""))

with open(out_tsv, "w") as fh:
    fh.write("pos\tref\talt\tgt\tdp\tgnomad_af\tclass\tgnomad_ac\tgnomad_nhomalt\tgnomad_filter\tin_primary\n")
    for r in rows: fh.write("\t".join(map(str, r)) + "\n")

print(f"gnomAD records loaded: {len(gn)}   your PASS calls in span: {len(rows)}")
print(f"{'pos':<11}{'ref>alt':<14}{'gt':<6}{'dp':<5}{'gnomAD AF':<12}{'class':<8}in primary")
for r in rows:
    if r[6] in ("absent", "rare", "unknown") or r[10]:
        print(f"{r[0]:<11}{(r[1]+'>'+r[2])[:13]:<14}{r[3]:<6}{r[4]:<5}{(r[5] or '-'):<12}{r[6]:<8}{r[10]}")
for k, v in counts.items(): print(f"METRIC span_{k}={v}")
for k, v in prim.items(): print(f"METRIC primary_{k}={v}")
print(f"METRIC gnomad_records={len(gn)}")
print(f"METRIC primary_rare_or_absent={prim['absent'] + prim['rare']}")
print(f"VERDICT primary hotspot: {prim['absent']} absent + {prim['rare']} rare + {prim['common']} common variants (gnomAD AF<1% = rare)")
