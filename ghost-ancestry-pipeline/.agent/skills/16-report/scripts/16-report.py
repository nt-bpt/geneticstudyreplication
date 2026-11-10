#!/usr/bin/env python3
"""SKILL 16: write results/report.md from the results of all earlier skills."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "16-report"
SKILLS = ["00-check-env", "01-inspect-input", "02-prepare-reference", "03-align-reads",
          "04-qc-alignment", "05-fetch-panel", "06-call-variants", "07-phase",
          "08-build-cohort", "09-fetch-trace", "10-build-arg", "11-run-trace",
          "12-fetch-archaic", "13-label-segments", "14-super-archaic", "15-annotate-genes"]


def pct(x):
    return "n/a" if x is None else f"{x:.2%}"


def work(step):
    cfg = step.cfg
    res = {s: pc.prev_result(s) for s in SKILLS}
    if not res["13-label-segments"]:
        step.fail("13-label-segments has not run; the report needs at least skills 00-13")
    m = lambda s: (res.get(s) or {}).get("metrics") or {}  # noqa: E731
    L = ["# Personal archaic ancestry report", ""]
    L.append(f"Sample: **{cfg.get('SAMPLE_NAME')}**  ·  chromosomes: {', '.join(cfg.chromosomes())}"
             f"  ·  mean depth: {m('04-qc-alignment').get('mean_depth', 'n/a')}x  ·  "
             f"analysed: {m('13-label-segments').get('analysed_bp', 0) / 1e6:.1f} Mb")
    arg = (m("10-build-arg").get("arg_method") or "singer").lower()
    arg_name = "Relate" if arg == "relate" else "SINGER"
    L += ["", f"Method: TRACE on {arg_name} ARGs built jointly with "
          f"{m('08-build-cohort').get('n_samples', '?') - 1 if m('08-build-cohort').get('n_samples') else '?'} "
          f"1000 Genomes samples ({cfg.get('COHORT_POPS')}), following Zhang et al., Science "
          "2026 (doi:10.1126/science.aef8874).", ""]

    L += ["## Archaic ancestry by source", "", "| Source | Segments | Total length | Share of genome |",
          "|---|---|---|---|"]
    for lab, v in sorted((m("13-label-segments").get("by_label") or {}).items()):
        L.append(f"| {lab} | {v['segments']} | {v['bp'] / 1e3:,.0f} kb | {pct(v['fraction_per_genome'])} |")
    sa = res.get("14-super-archaic") or {}
    L += ["", f"Super-archaic screen: {sa.get('status', 'not run')} — {sa.get('verdict', '')}", ""]

    a = m("15-annotate-genes")
    L += ["## Genes", ""]
    hits = a.get("paper_genes_in_user_segments") or {}
    if hits:
        L += ["Genes named in the paper that lie inside your segments:", "",
              "| Gene | Your segment label(s) | Where the paper mentions it |", "|---|---|---|"]
        for g, labs in sorted(hits.items()):
            L.append(f"| {g} | {', '.join(labs)} | {pc.PAPER_GENES.get(g, '')} |")
    else:
        L.append("None of the genes named in the paper lie inside your segments.")
    nh = a.get("neuro_literature_genes_in_user_segments") or {}
    if nh:
        L += ["", "Of these, genes with a documented neurodevelopmental role in the wider "
              "literature (not a finding of the paper): " +
              ", ".join(f"{g} ({', '.join(v)})" for g, v in sorted(nh.items())) + "."]
    L += ["", f"Full gene list: `work/annotation/segment_genes.tsv` "
          f"({a.get('gene_overlaps', 0)} overlaps).", ""]
    if a.get("fraction_in_published") is not None:
        L += [f"{pct(a['fraction_in_published'])} of your ghost-labelled sequence overlaps ghost "
              "tracts published with the paper.", ""]

    L += ["## How far to trust this", "",
          (f"- With {arg_name} genealogies, TRACE found "
           + ("under 10% of true archaic segments in the paper's simulations (about 50% with "
              "SINGER), so totals here are strong underestimates."
              if arg == "relate" else
              "roughly 30-50% of true archaic segments in the paper's simulations, so totals "
              "here are underestimates.")),
          "- Source labels use a simplified rule (see 13-label-segments warnings).",
          "- A single genome added to the cohort gives noisy per-person numbers; results from a "
          "few chromosomes are not genome-wide estimates.",
          "- A segment inside a gene says nothing about whether it changes how that gene works. "
          "This is research output, not a medical result.", ""]

    if arg == "relate":
        # Relate's licence requires this notice wherever its results are used
        L += ["## Software notice", "",
              "Genealogies were built with Relate (Speidel et al. 2019). Relate's licence "
              "requires the following notice wherever results from it are used:", "",
              "> Copyright (c) 2018, University of Oxford", "",
              "Relate is licensed for academic, non-commercial use. See repo/THIRD-PARTY.md.", ""]

    L += ["## Skill status", "", "| Skill | Status | Verdict |", "|---|---|---|"]
    warns = []
    for s in SKILLS:
        r = res.get(s)
        if not r:
            L.append(f"| {s} | not run | |")
            continue
        L.append(f"| {s} | {r.get('status')} | {str(r.get('verdict', '')).replace('|', '/')} |")
        warns += [f"{s}: {w}" for w in r.get("warnings", [])]
    if warns:
        L += ["", "## Warnings", ""] + [f"- {w}" for w in warns]
    out = pc.RESULTS / "report.md"
    out.write_text("\n".join(L) + "\n")
    step.extra["report"] = out.read_text()
    step.outputs.append(out)
    step.metrics["warnings_collected"] = len(warns)
    return "OK", f"report written to {pc.rel(out)}"


if __name__ == "__main__":
    pc.run_step(NAME, work)
