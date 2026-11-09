#!/usr/bin/env python3
"""SKILL 15: list the genes inside the user's archaic segments, flag genes named
in the paper, and compare the user's ghost segments with the published tracts."""
import bisect
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "15-annotate-genes"


def load_genes(step, chroms):
    url = step.cfg.get("GENCODE_URL")
    gtf = pc.download(step, url, pc.data(step.cfg, "annotation", url.rsplit("/", 1)[-1]))
    genes = {c: [] for c in chroms}
    with pc.open_text(gtf) as f:
        for line in f:
            if line.startswith("#"):
                continue
            p = line.split("\t", 9)
            if len(p) < 9 or p[2] != "gene" or p[0] not in genes:
                continue
            name = re.search(r'gene_name "([^"]+)"', p[8])
            gtype = re.search(r'gene_type "([^"]+)"', p[8])
            genes[p[0]].append((int(p[3]) - 1, int(p[4]), name.group(1) if name else "?",
                                gtype.group(1) if gtype else "?"))
    for c in genes:
        genes[c].sort()
    return genes


def overlapping(genes, chrom, start, end):
    lst = genes.get(chrom, [])
    starts = [g[0] for g in lst]
    i = bisect.bisect_left(starts, end)
    return [g for g in lst[:i] if g[1] > start]


def published_ghost(step, chroms):
    """Union of published ghost tracts per chromosome, from the Trace_data download."""
    d = pc.metric("09-fetch-trace", "trace_data_dir")
    if not d or not Path(d).exists():
        return None, []
    tracts, used = {c: [] for c in chroms}, []
    for p in sorted(Path(d).rglob("*")):
        if not p.is_file() or "archives" in p.parts:
            continue
        if not re.search(r"\.(bed|tsv|txt|csv)(\.gz)?$", p.name, re.I):
            continue
        try:
            rows = pc.parse_segment_file(p)
        except Exception:  # noqa: BLE001
            continue
        hint_ghost = "ghost" in p.name.lower()
        n = 0
        for r in rows:
            lab = (r.get("label") or "").lower()
            if r["chrom"] in tracts and (hint_ghost or "ghost" in lab):
                tracts[r["chrom"]].append((r["start"], r["end"]))
                n += 1
        if n:
            used.append(f"{pc.rel(p)} ({n} ghost tracts)")
    for c in tracts:
        merged = []
        for s, e in sorted(tracts[c]):
            if merged and s <= merged[-1][1]:
                merged[-1][1] = max(merged[-1][1], e)
            else:
                merged.append([s, e])
        tracts[c] = merged
    return tracts, used


def overlap_bp(intervals, start, end):
    total = 0
    for s, e in intervals:
        if s >= end:
            break
        if e > start:
            total += min(e, end) - max(s, start)
    return total


def work(step):
    cfg = step.cfg
    pc.require(step, "13-label-segments")
    chroms = cfg.chromosomes()
    segs = pc.read_tsv(pc.work(cfg, "labels", "segments.labeled.tsv"))
    sup = pc.work(cfg, "labels", "super_archaic_candidates.tsv")
    if sup.exists():
        for r in pc.read_tsv(sup):
            segs.append(dict(r, label="SuperArchaicCandidate"))
    step.progress("loading GENCODE gene annotation")
    genes = load_genes(step, chroms)

    rows, paper_hits, neuro_hits = [], {}, {}
    for s in segs:
        start, end = int(s["start"]), int(s["end"])
        for gs, ge, name, gtype in overlapping(genes, s["chrom"], start, end):
            rows.append({"label": s["label"], "chrom": s["chrom"], "seg_start": start,
                         "seg_end": end, "hap": s["hap"], "gene": name, "gene_type": gtype,
                         "gene_start": gs, "gene_end": ge,
                         "named_in_paper": pc.PAPER_GENES.get(name, ""),
                         "neuro_role_in_literature": "yes" if name in pc.NEURO_LITERATURE_GENES else ""})
            if name in pc.PAPER_GENES:
                paper_hits.setdefault(name, set()).add(s["label"])
            if name in pc.NEURO_LITERATURE_GENES:
                neuro_hits.setdefault(name, set()).add(s["label"])
    cols = ["label", "chrom", "seg_start", "seg_end", "hap", "gene", "gene_type", "gene_start",
            "gene_end", "named_in_paper", "neuro_role_in_literature"]
    out = pc.write_tsv(pc.work(cfg, "annotation", "segment_genes.tsv"), rows, cols)
    step.outputs.append(out)

    # paper genes that fall on analysed chromosomes but are not in any segment
    absent = sorted(g for g in pc.PAPER_GENES if g not in paper_hits and any(
        x[2] == g for c in chroms for x in genes.get(c, [])))
    step.metrics.update({
        "gene_overlaps": len(rows),
        "genes_by_label": {lab: len({r["gene"] for r in rows if r["label"] == lab})
                           for lab in {r["label"] for r in rows}},
        "paper_genes_in_user_segments": {g: sorted(v) for g, v in paper_hits.items()},
        "paper_genes_on_analysed_chromosomes_not_hit": absent,
        "neuro_literature_genes_in_user_segments": {g: sorted(v) for g, v in neuro_hits.items()},
    })

    tracts, used = published_ghost(step, chroms)
    ghost = [s for s in segs if s["label"] == "Ghost"]
    if tracts is None:
        step.warn("Trace_data folder not found; skipped comparison with published tracts")
    elif not used:
        step.warn("could not find ghost tracts in the Trace_data files; inspect them by hand "
                  f"in {pc.metric('09-fetch-trace', 'trace_data_dir')}")
    else:
        gbp = sum(int(s["end"]) - int(s["start"]) for s in ghost)
        ov = sum(overlap_bp(tracts.get(s["chrom"], []), int(s["start"]), int(s["end"])) for s in ghost)
        step.metrics.update({"published_files_used": used, "user_ghost_bp": gbp,
                             "user_ghost_bp_in_published_tracts": ov,
                             "fraction_in_published": round(ov / gbp, 3) if gbp else None})
        step.warn("check that the Trace_data tracts are on GRCh38 before trusting the overlap "
                  "numbers")
    named = ", ".join(sorted(paper_hits)) or "none"
    return "OK", f"{len(rows)} gene overlaps; genes named in the paper found: {named}"


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
