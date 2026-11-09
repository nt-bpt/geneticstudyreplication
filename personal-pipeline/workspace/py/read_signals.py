#!/usr/bin/env python3
"""Read-level signals in the primary hotspot and extended window, each compared with a control region.

usage: read_signals.py REGION.bam PRIMARY_REGION EXTENDED_REGION CONTROL_REGION
Prints tables, then METRIC key=value lines and a VERDICT line (parsed by the skill wrapper).

Two kinds of evidence:
  * region-wide rates (soft-clipped, split, discordant, low-MAPQ reads)  -> catch broad problems
  * LOCAL evidence (500 bp depth windows; clusters of reads clipped at the same position) -> catch a small
    event such as a few-kb deletion, which region-wide averages dilute away.
Rates use primary alignments only (secondary, supplementary and unmapped records are skipped).
"""
import math, os, re, statistics, subprocess, sys
from collections import Counter

bam, reg_primary, reg_ext, reg_ctrl = sys.argv[1:5]
env = os.environ.get
MINMAPQ = int(env("MIN_MAPQ", "20"))
RATIO = float(env("RATIO_FLAG", "2.0"))
FLOOR = {"softclip": float(env("SOFTCLIP_FLOOR_PCT", "2")), "split": float(env("SPLIT_FLOOR_PCT", "0.5")),
         "discordant": float(env("DISCORDANT_FLOOR_PCT", "1"))}
MIN_READS = int(env("MIN_FLAG_READS", "10"))
WIN = int(env("DEPTH_WINDOW", "500"))
DEPTH_LO, DEPTH_HI = float(env("DEPTH_LOW_RATIO", "0.65")), float(env("DEPTH_HIGH_RATIO", "1.5"))
MIN_RUN = int(env("DEPTH_MIN_WINDOWS", "2"))
BP_MIN = int(env("BREAKPOINT_MIN_READS", "6"))
BP_FRAC = float(env("BREAKPOINT_DEPTH_FRAC", "0.15"))
CLIP_MIN = 10
op_re = re.compile(r"(\d+)([MIDNSHP=X])")


def parse(region):
    name, rng = region.rsplit(":", 1); s, e = (int(x) for x in rng.split("-")); return name, s, e


def scan(region):
    p = subprocess.Popen(["samtools", "view", bam, region], stdout=subprocess.PIPE, text=True)
    c = dict(n=0, dup=0, lowmapq=0, softclip=0, split=0, discordant=0)
    bp = Counter()
    for line in p.stdout:
        f = line.split("\t", 11)
        flag = int(f[1])
        if flag & 0x904:               # unmapped (0x4), secondary (0x100), supplementary (0x800)
            continue
        c["n"] += 1
        if flag & 0x400: c["dup"] += 1
        if int(f[4]) < MINMAPQ: c["lowmapq"] += 1
        ops = op_re.findall(f[5])
        lc = int(ops[0][0]) if ops and ops[0][1] == "S" else 0
        rcl = int(ops[-1][0]) if ops and ops[-1][1] == "S" else 0
        if lc + rcl >= CLIP_MIN: c["softclip"] += 1
        pos = int(f[3])
        if lc >= CLIP_MIN: bp[pos] += 1                                   # breakpoint = first aligned base
        if rcl >= CLIP_MIN: bp[pos + sum(int(n) for n, o in ops if o in "MDN=X")] += 1   # base after the last aligned one
        if "\tSA:Z:" in line: c["split"] += 1
        if (flag & 1) and not (flag & 2) and not (flag & 8): c["discordant"] += 1
    p.wait()
    return c, bp


def breakpoint_clusters(bp, min_support):
    out, cur = [], None
    for pos in sorted(bp):
        if cur and pos - cur[1] <= 3: cur[1] = pos; cur[2] += bp[pos]
        else:
            if cur and cur[2] >= min_support: out.append(tuple(cur))
            cur = [pos, pos, bp[pos]]
    if cur and cur[2] >= min_support: out.append(tuple(cur))
    return sorted(out, key=lambda x: -x[2])


def depth_profile(region):
    name, s, e = parse(region)
    nwin = (e - s) // WIN + 1
    sums, cnt = [0] * nwin, [0] * nwin
    p = subprocess.Popen(["samtools", "depth", "-a", "-r", region, bam], stdout=subprocess.PIPE, text=True)
    for line in p.stdout:
        _, pos, d = line.split("\t"); i = (int(pos) - s) // WIN
        if 0 <= i < nwin: sums[i] += int(d); cnt[i] += 1
    p.wait()
    return [(s + i * WIN, sums[i] / cnt[i]) for i in range(nwin) if cnt[i] >= WIN // 2]


def depth_runs(profile, base):
    """Runs of >= MIN_RUN consecutive windows all below DEPTH_LO x or all above DEPTH_HI x the control median."""
    runs, cur = [], None
    def close():
        if cur and len(cur["r"]) >= MIN_RUN: runs.append((cur["start"], cur["end"], statistics.mean(cur["r"])))
    for st, m in profile:
        r = m / base if base else 1.0
        d = -1 if r < DEPTH_LO else (1 if r > DEPTH_HI else 0)
        if d != 0 and cur and cur["d"] == d and st == cur["end"]:
            cur["end"] = st + WIN; cur["r"].append(r)
        else:
            close(); cur = {"d": d, "start": st, "end": st + WIN, "r": [r]} if d != 0 else None
    close()
    return runs


def mean_depth(profile): return statistics.mean(m for _, m in profile) if profile else 0.0
def pct(a, n): return 100.0 * a / n if n else 0.0


regs = {"primary": reg_primary, "extended": reg_ext, "control": reg_ctrl}
data, prof, bps = {}, {}, {}
for label, reg in regs.items():
    d, bp = scan(reg); prof[label] = depth_profile(reg); d["depth"] = mean_depth(prof[label]); d["region"] = reg
    d["len_kb"] = (parse(reg)[2] - parse(reg)[1] + 1) / 1000.0
    for k in ("dup", "lowmapq", "softclip", "split", "discordant"): d[k + "_pct"] = pct(d[k], d["n"])
    data[label] = d; bps[label] = bp

print(f"{'metric':<26}{'primary':>12}{'extended':>12}{'control':>12}")
for k, lab in (("n", "reads"), ("depth", "mean depth (x)"), ("dup_pct", "duplicate %"), ("lowmapq_pct", f"MAPQ<{MINMAPQ} %"),
               ("softclip_pct", f"soft-clipped >={CLIP_MIN}bp %"), ("split_pct", "split reads (SA) %"), ("discordant_pct", "discordant pairs %")):
    print(f"{lab:<26}" + "".join((f"{data[r][k]:>12.2f}" if k != "n" else f"{data[r][k]:>12d}") for r in regs))

ctrl = data["control"]
ctrl_median = statistics.median([m for _, m in prof["control"]]) if prof["control"] else 0.0
ctrl_runs = depth_runs(prof["control"], ctrl_median)
flags = {"primary": [], "extended": []}
detail = {}
for region in ("primary", "extended"):
    d = data[region]
    for k in ("softclip", "split", "discordant"):
        if d[k + "_pct"] > FLOOR[k] and d[k + "_pct"] > RATIO * ctrl[k + "_pct"] and d[k] >= MIN_READS:
            flags[region].append(k)
    # local depth shift: expected number of runs from the control's own rate, scaled to this region's length
    runs = depth_runs(prof[region], ctrl_median)
    exp_runs = len(ctrl_runs) / ctrl["len_kb"] * d["len_kb"]
    detail[region + "_depth_runs"] = runs
    if runs and len(runs) > RATIO * exp_runs and (region == "primary" or len(runs) >= 3):
        flags[region].append("depth_shift")
    # breakpoint clusters (reads clipped at the same position), threshold scaled to depth
    thr = max(BP_MIN, math.ceil(BP_FRAC * d["depth"]))
    cl = breakpoint_clusters(bps[region], thr)
    cl_ctrl = breakpoint_clusters(bps["control"], max(BP_MIN, math.ceil(BP_FRAC * ctrl["depth"])))
    exp_cl = len(cl_ctrl) / ctrl["len_kb"] * d["len_kb"]
    detail[region + "_clusters"] = cl; detail[region + "_cluster_threshold"] = thr
    if cl and len(cl) > RATIO * exp_cl:
        flags[region].append("breakpoint_cluster")

watch = []
for region in ("primary", "extended"):
    d = data[region]
    if d["lowmapq_pct"] > 20 and d["lowmapq_pct"] > RATIO * ctrl["lowmapq_pct"]: watch.append(f"{region}:low_mapq")
    if ctrl["depth"] > 0 and not (DEPTH_LO + 0.1 < d["depth"] / ctrl["depth"] < DEPTH_HI): watch.append(f"{region}:mean_depth_ratio_{d['depth']/ctrl['depth']:.2f}")

print(f"\ncontrol baseline: median {WIN} bp-window depth {ctrl_median:.1f}x; {len(ctrl_runs)} depth-shift run(s) in {ctrl['len_kb']:.0f} kb")
for region in ("primary", "extended"):
    for st, en, r in detail[region + "_depth_runs"][:8]:
        print(f"  {region}: depth shift {st}-{en}  ({r:.2f}x of control median)")
    for a, b, sup in detail[region + "_clusters"][:6]:
        print(f"  {region}: {sup} reads clipped at {a}{'' if a == b else '-' + str(b)} (threshold {detail[region + '_cluster_threshold']})")

for region in ("primary", "extended", "control"):
    for k in ("n", "depth", "softclip_pct", "split_pct", "discordant_pct", "lowmapq_pct", "dup_pct"):
        v = data[region][k]
        print(f"METRIC {region}_{k}={v:.3f}" if isinstance(v, float) else f"METRIC {region}_{k}={v}")
print(f"METRIC flags_primary={len(flags['primary'])}")
print(f"METRIC flags_extended={len(flags['extended'])}")
print(f"METRIC flagged_primary={'+'.join(flags['primary']) or 'none'}")
print(f"METRIC flagged_extended={'+'.join(flags['extended']) or 'none'}")
print(f"METRIC watch={'+'.join(watch) or 'none'}")
print("VERDICT primary flags: %s | extended flags: %s | watch: %s" % (
    ",".join(flags["primary"]) or "none", ",".join(flags["extended"]) or "none", ",".join(watch) or "none"))
