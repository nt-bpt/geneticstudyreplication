#!/usr/bin/env python3
"""Assemble results/*.json into one plain-text report. usage: report.py WORKSPACE_DIR"""
import json, os, sys, glob
W = sys.argv[1]
R = {}
for f in sorted(glob.glob(os.path.join(W, "results", "*.json"))):
    if os.path.basename(f).startswith("FINAL"): continue
    d = json.load(open(f)); R[d["skill"]] = d
state = {}
for line in open(os.path.join(W, "state.env")):
    if "=" in line: k, _, v = line.strip().partition("="); state[k] = v.strip('"')
m = lambda s, k, default=0: R.get(s, {}).get("metrics", {}).get(k, default)

L = []
add = L.append
add("=" * 78); add(" PERSONAL HOTSPOT CHECK — REPORT"); add("=" * 78)
add(f" input: {state.get('INPUT_KIND','?')}   chr3 is named '{state.get('CHR3_NAME','?')}' ({state.get('CHR3_STYLE','?')}), assembly {state.get('ASSEMBLY','GRCh38 (by reference)')}")
add("")
add(" SKILL STATUS")
for s, d in R.items():
    add(f"   {d['status']:<8}{s:<24}{d['verdict'][:70]}")
    for w in d["warnings"]: add(f"            ! {w[:100]}")
missing = [s for s in ("04_extract_region", "06_call_variants", "07_read_signals", "08_allele_balance", "09_gnomad_frequency") if s not in R]
failed = [s for s, d in R.items() if d["status"] == "FAIL"]

fl_read = m("07_read_signals", "flags_primary")
fl_ab = m("08_allele_balance", "flag_primary")
rare = m("09_gnomad_frequency", "primary_rare_or_absent")
add("")
add(" COVERAGE")
add(f"   mean depth  primary {m('04_extract_region','depth_primary')}x | extended {m('04_extract_region','depth_extended')}x | control {m('04_extract_region','depth_control')}x")
add(" VARIANTS (PASS / all)")
add(f"   primary hotspot {m('06_call_variants','pass_primary')}/{m('06_call_variants','variants_primary')} | extended {m('06_call_variants','pass_extended')}/{m('06_call_variants','variants_extended')} | control {m('06_call_variants','pass_control')}/{m('06_call_variants','variants_control')}")
add(" SIGNALS IN THE PRIMARY HOTSPOT")
add(f"   read-level flags: {fl_read} ({m('07_read_signals','flagged_primary','n/a')})   [extended window: {m('07_read_signals','flags_extended')} ({m('07_read_signals','flagged_extended','n/a')})]")
add(f"   allele balance:   {m('08_allele_balance','primary_call','n/a')}   [extended window: {m('08_allele_balance','extended_call','n/a')}]")
add(f"   rare/absent in gnomAD: {rare}")
add(f"   watch items: {m('07_read_signals','watch','n/a')}")
add("")
add(" OVERALL")
if failed or missing:
    add(f"   INCOMPLETE — failed: {failed or 'none'}; not run: {missing or 'none'}")
else:
    signals = fl_read + fl_ab
    if signals >= 2 and rare > 0:
        v = "SEVERAL SIGNALS PLUS RARE VARIANT(S): multiple read-level/allele-balance flags and rare/absent variants in the primary hotspot. Inspect in IGV."
    elif signals >= 2:
        v = "SEVERAL SIGNALS, NO RARE VARIANTS: read-level flags without rare variants (repetitive sequence or alignment artefact is the usual explanation)."
    elif signals == 1:
        v = "ONE SIGNAL: inconclusive."
    elif rare > 0:
        v = "RARE VARIANT(S), NORMAL READ SIGNAL: see results/09_gnomad_annotated.tsv. Absent from gnomAD does not mean harmful: every genome carries some private variants."
    else:
        v = "NOTHING UNUSUAL DETECTED by these tests at this locus."
    add("   " + v)
add("")
add(" HOW TO READ THIS")
add("   * This asks only whether YOUR genome looks unusual at these coordinates. Without parental DNA nothing here can")
add("     test inheritance, so it can neither support nor refute any claim about how a variant arose.")
if state.get("ALIGN_BIAS"):
    add("   * Alignment was chr3-only: reads from similar regions elsewhere may be piled onto chr3. Treat depth, read-level and")
    add("     variant results as unreliable; re-align to the full genome for a trustworthy answer.")
if m("04_extract_region", "depth_control") and float(m("04_extract_region", "depth_control")) > 120:
    add("   * Control-region depth is far above whole-genome norms (~30x): see the warning in skill 04.")
if m("08_allele_balance", "primary_call", "") == "LOW_POWER":
    add("   * The hotspot holds few heterozygous sites, so allele balance there has little statistical power.")
add("   * Hotspot window: the paper gives only 'chr3:75.5 Mb'; the window used here was set from the trio scan's own regions.")
add("   * Thresholds (config.env) are conventions, not validated cut-offs.")
add("=" * 78)
txt = "\n".join(L)
print(txt)
open(os.path.join(W, "results", "FINAL_REPORT.txt"), "w").write(txt + "\n")
