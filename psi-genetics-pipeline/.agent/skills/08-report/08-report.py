#!/usr/bin/env python3
"""SKILL 08 - write the user-facing report: results/psi-genetics-user-report.md"""
import json
import sys
from pathlib import Path

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "psicommon", Path(__file__).resolve().parents[2] / "lib" / "psi-common.py")
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)

NAME = "08-report"
SKILL_ORDER = ["00-check-env", "01-detect-input", "02-prepare-panels", "03-resolve-proxy",
               "04-align-fastq", "05-genotype-array", "06-genotype-sequence", "07-compare-studies"]


def pct(x):
    return f"{x * 100:.1f}%"


def run(sk):
    cfg = pc.load_config()
    det = sk.require("01-detect-input")
    cmp_ = sk.require("07-compare-studies")
    p1panel = json.loads((pc.PANELS / "p1-tnrc18.json").read_text())
    p2study = json.loads((pc.PANELS / "p2-study.json").read_text())
    m = det["metrics"]
    p1, p2 = cmp_["metrics"]["paper1"], cmp_["metrics"]["paper2"]
    p2rows = pc.read_tsv(pc.RESULTS / "07-p2-genotypes.tsv")
    L = []
    w = L.append

    w("# Psi-Genetics Study Comparison Report")
    w("")
    w(f"Sample: **{cfg['sample_label']}**  ")
    w(f"Input: {m['input_type']}" + (f" ({m.get('vendor')})" if m.get("vendor") else "")
      + f", genome build {m.get('build') or 'unknown'}  ")
    w(f"Generated: {pc.now_iso()}")
    w("")
    w("> **Read this first.** This report shows your genotype at DNA positions named in two small, "
      "unreplicated studies (23 and 102 participants). It does **not** measure, predict or confirm "
      "any psychic ability or experience. The variants are common in the general population, and "
      "results from studies this small often fail to replicate.")
    w("")

    # ---- Paper 1
    w("## Study 1: TNRC18 intronic variant (2021)")
    w("")
    w(f"*{p1panel['citation']}* doi:{p1panel['doi']}")
    w("")
    w(f"{p1panel['design']} The study reported one difference, at **rs117910193** "
      f"(chr7:{p1panel['target']['GRCh37']['pos']:,} GRCh37 / {p1panel['target']['GRCh38']['pos']:,} GRCh38, G>A): "
      "none of the 13 cases carried the A allele, while 7 of the 9 analysed controls were G/A.")
    w("")
    w("| | |")
    w("|---|---|")
    w(f"| Your genotype | **{p1['genotype'] or 'not available'}** |")
    w(f"| How it was obtained | {p1['method']}"
      + (f" (read depth {p1['depth']})" if p1['method'] == 'direct' and p1.get('depth') not in ('', None) else "")
      + (f": inferred from rs78262442 (EUR r² {float(p1.get('proxy_r2')):.3f}), not measured directly"
         if p1['method'] == 'proxy' else "") + " |")
    w(f"| Compared with the study | {p1['comparison']} |")
    w("")
    nfe = p1["population_expectation_nfe_hwe"]
    w("**Population context.** Using the gnomAD non-Finnish European allele frequency "
      f"({p1panel['population_af_alt_A']['gnomad_exomes_nfe']}) and Hardy–Weinberg proportions, about "
      f"{pct(nfe['GG'])} of Europeans are G/G, {pct(nfe['GA'])} G/A and {pct(nfe['AA'])} A/A. "
      "So most people share the genotype the study's cases had.")
    w("")
    w("**Why to be cautious about this study.** At a ~10% allele frequency you would expect about 2 of 9 "
      "controls to carry G/A; the study found 7. The unusual group is the controls, which points to "
      "chance or a technical artifact as much as to any signal. The site is 59 bp into an intron at the "
      "edge of exome capture, and no raw data were released.")
    w("")

    # ---- Paper 2
    w("## Study 2: 212 SNPs from a Random Forest analysis (2026)")
    w("")
    w(f"*{p2study['citation']}* doi:{p2study['doi']}")
    w("")
    w(f"{p2study['design']}")
    w("")
    w(f"Genotyped in your data: **{p2['n_called']} of {p2['n_sites']}** sites "
      f"({p2['n_top20_called']} of the top 20).")
    w("")
    w("**No score can be calculated.** The paper's \"effect size\" is an unsigned importance value. "
      "It says a SNP helped the model separate high from low scorers, not which allele went with which "
      "group. Your genotypes below can't be matched to either group.")
    w("")
    w("Top 20 sites (gene annotations from the paper's Table 3):")
    w("")
    w("| Rank | rsID | Gene | Importance | Your genotype | Status |")
    w("|---|---|---|---|---|---|")
    for r in p2rows:
        if int(r["rank"]) <= 20:
            w(f"| {r['rank']} | {r['rsid']} | {r['gene_reported']} | {r['effect_size_unsigned']} | "
              f"{r['genotype'] or '—'} | {r['status']} |")
    w("")
    w(f"All 212 sites are in `results/07-p2-genotypes.tsv`.")
    w("")

    # ---- QC
    w("## Data quality and processing")
    w("")
    for name in SKILL_ORDER:
        res = pc.read_result(name)
        if res:
            w(f"- **{name}**: {res['status']} — {res['verdict']}")
    warns = []
    for name in SKILL_ORDER:
        res = pc.read_result(name)
        if res:
            warns += [f"{name}: {x}" for x in res.get("warnings", [])]
    if warns:
        w("")
        w("Warnings:")
        for x in warns:
            w(f"- {x}")
    w("")
    w("## Status codes")
    w("")
    w("CALLED: genotype called. LOW_DEPTH: called on fewer reads than the minimum. NO_COVERAGE: no reads "
      "at the site. NOT_ON_CHIP: the array does not test this rsID. NO_CALL: tested but no result. "
      "NOT_IN_VCF: absent from a non-gVCF, so unknown. NO_COORDS: no coordinates for this build. "
      "REF_MISMATCH: the reference base disagrees with the panel (site skipped).")
    w("")

    out = pc.RESULTS / "psi-genetics-user-report.md"
    out.write_text("\n".join(L) + "\n")
    sk.outputs = {"report": pc.rel(out)}
    sk.metrics.update({"paper1_class": p1["class"], "paper2_called": p2["n_called"],
                       "n_warnings_included": len(warns)})
    return pc.OK, f"report written to {pc.rel(out)}"


if __name__ == "__main__":
    pc.main(NAME, run)
