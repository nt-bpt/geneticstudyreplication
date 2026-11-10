#!/usr/bin/env python3
"""SKILL 10: build ancestral recombination graphs (ARGs) for the cohort.

ARG_METHOD=relate (default): Relate, one run per chromosome
  VCF -> haps/sample -> polarise with the ancestral genome (PrepareInputFiles)
  -> RelateParallel -> optional population-size recalibration
  (EstimatePopulationSize) -> tskit .trees for TRACE.
ARG_METHOD=singer: SINGER, window by window (the paper's choice).

Resumable: each finished stage leaves a marker file, so running the skill
again continues where it stopped.
"""
import bisect
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline_common as pc  # noqa: E402

NAME = "10-build-arg"


def windows_for(cfg, chrom, first, last):
    size = cfg.int("SINGER_WINDOW_BP")
    pos = [int(x) for x in pc.work(cfg, "cohort", chrom, "positions.txt").read_text().split()]
    start = (first // size) * size
    out = []
    while start <= last:
        end = start + size
        n = bisect.bisect_left(pos, end) - bisect.bisect_left(pos, start)
        out.append({"chrom": chrom, "start": start, "end": end, "n_sites": n})
        start = end
    return out


def pick_trees(wdir, which):
    files = []
    for p in wdir.glob("*.trees"):
        m = re.search(r"(\d+)\.trees$", p.name)
        files.append((int(m.group(1)) if m else -1, p))
    if not files:
        return None
    files.sort()
    if which == "first":
        return files[0][1]
    if which.isdigit():
        for k, p in files:
            if k == int(which):
                return p
    return files[-1][1]


def run_window(step, w, singer_dir):
    cfg = step.cfg
    wdir = pc.work(cfg, "arg", w["chrom"], f"w{w['start']}", "x").parent
    done = wdir / "DONE"
    if done.exists():
        return w, None
    vcf_prefix = str(pc.work(cfg, "cohort", w["chrom"], "cohort"))
    out_prefix = str(wdir / "singer")
    vals = dict(singer_dir=singer_dir, ne=cfg.get("SINGER_NE"), mu=cfg.get("SINGER_MU"),
                ratio=cfg.get("SINGER_RATIO"), vcf_prefix=vcf_prefix, out_prefix=out_prefix,
                start=w["start"], end=w["end"], n_samples=cfg.get("SINGER_N_SAMPLES"),
                thin=cfg.get("SINGER_THIN"), last_sample=cfg.int("SINGER_N_SAMPLES") - 1,
                chrom=w["chrom"])
    log = wdir / "singer.log"
    with open(log, "a") as f:  # earlier attempts stay above this line
        f.write(f"{pc.ATTEMPT_MARK}{time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
    try:
        # run from repo/ (like every other command) so relative paths in the
        # templates resolve against repo/; all outputs use absolute paths
        sampled = wdir / "SAMPLED"  # SINGER finished; a rerun only repeats the conversion
        if not sampled.exists():
            step.run(pc.use_own_python(cfg.template("SINGER_CMD_TEMPLATE").format(**vals)),
                     log_path=log, cwd=str(pc.ROOT))
            sampled.write_text("ok\n")
        step.run(pc.use_own_python(cfg.template("SINGER_CONVERT_TEMPLATE").format(**vals)),
                 log_path=log, cwd=str(pc.ROOT))
    except pc.StepError as e:
        return w, f"{e} (window log: {pc.rel(log)})"
    if not pick_trees(wdir, "last"):
        return w, f"no .trees file written in {pc.rel(wdir)} (window log: {pc.rel(log)})"
    done.write_text("ok\n")
    return w, None


# ---------------------------------------------------------------------------
# Relate
# ---------------------------------------------------------------------------
def relate_tools(step):
    d = step.cfg.path("RELATE_DIR")
    if not d:
        step.fail("RELATE_DIR is empty. Ask the user to download Relate "
                  "(https://myersgroup.github.io/relate/) and set RELATE_DIR in repo/config.env "
                  "to the folder that holds bin/ and scripts/.")
    t = {"relate": d / "bin" / "Relate", "formats": d / "bin" / "RelateFileFormats",
         "prepare": d / "scripts" / "PrepareInputFiles" / "PrepareInputFiles.sh",
         "parallel": d / "scripts" / "RelateParallel" / "RelateParallel.sh",
         "popsize": d / "scripts" / "EstimatePopulationSize" / "EstimatePopulationSize.sh"}
    for key in ("relate", "formats", "prepare"):
        if not t[key].exists():
            step.fail(f"Relate file {t[key]} not found. RELATE_DIR must be the unpacked Relate "
                      "folder that contains bin/ and scripts/.")
        if not os.access(t[key], os.X_OK):
            step.fail(f"{t[key]} is not executable. Ask the user to run: chmod +x {t[key]}")
    return t


def write_relate_map(cfg, chrom, dest):
    """PLINK map (chrom id cM bp) -> Relate map (pos COMBINED_rate Genetic_Map)."""
    bp, cm = [], []
    for line in open(pc.map_file(cfg, chrom)):
        p = line.split()
        if len(p) >= 4:
            bp.append(int(p[3]))
            cm.append(float(p[2]))
    with open(dest, "w") as f:
        f.write("pos COMBINED_rate Genetic_Map\n")
        for i in range(len(bp)):
            nxt = i + 1 < len(bp) and bp[i + 1] > bp[i]
            rate = (cm[i + 1] - cm[i]) / (bp[i + 1] - bp[i]) * 1e6 if nxt else 0.0
            f.write(f"{bp[i]} {max(rate, 0.0):.8f} {cm[i]:.8f}\n")


def write_poplabels(cfg, sample_gz, dest):
    """Population labels in .sample order; the user's genome gets its own label."""
    import gzip
    ped = pc.data(cfg, "panel", "samples_ped.txt")
    pops = {}
    lines = [l.split() for l in open(ped) if l.strip()]
    head = [h.lower() for h in lines[0]]
    i_s = head.index("sampleid") if "sampleid" in head else 1
    i_p = head.index("population") if "population" in head else 5
    for p in lines[1:]:
        if len(p) > max(i_s, i_p):
            pops[p[i_s]] = p[i_p]
    with gzip.open(sample_gz, "rt") as f, open(dest, "w") as o:
        o.write("sample population group sex\n")
        for r in [l.split() for l in f][2:]:
            pop = pops.get(r[0], "USER")
            o.write(f"{r[0]} {pop} {pop} NA\n")


def relate_chrom(step, t, chrom, n_sites):
    cfg = step.cfg
    d = pc.work(cfg, "arg", chrom, "relate", "x").parent
    log = d / "relate.log"
    trees = d / f"{chrom}.trees"
    if (d / "DONE").exists() and trees.exists():
        return trees, None
    with open(log, "a") as f:
        f.write(f"{pc.ATTEMPT_MARK}{time.strftime('%Y-%m-%d %H:%M:%S')} =====\n")
    run = lambda cmd: step.run(cmd, log_path=log, cwd=str(d))  # noqa: E731  Relate writes to cwd
    warn = None

    # 1. VCF -> haps/sample, polarised with the ancestral genome
    if not (d / "PREPARED").exists():
        step.progress(f"{chrom}: preparing Relate input (polarising with the ancestral genome)")
        cohort = pc.work(cfg, "cohort", chrom, "cohort")  # cohort.vcf from skill 08
        run([t["formats"], "--mode", "ConvertFromVcf", "--haps", "in.haps", "--sample",
             "in.sample", "-i", cohort])
        anc = pc.ancestral_fasta(step, chrom)
        cmd = [t["prepare"], "--haps", "in.haps", "--sample", "in.sample", "--ancestor", anc,
               "-o", "prep"]
        mask = cfg.path("RELATE_MASK")
        if mask:
            mask = Path(str(mask).replace("{chrom}", chrom).replace("{n}", pc.chrom_number(chrom)))
            if not mask.exists():
                step.fail(f"RELATE_MASK file {mask} not found")
            cmd += ["--mask", mask]
        run(cmd)
        for f in ("in.haps", "in.sample"):
            (d / f).unlink(missing_ok=True)
        (d / "PREPARED").write_text("ok\n")
    kept = sum(1 for _ in pc.open_text(d / "prep.haps.gz"))
    if n_sites and kept / n_sites < 0.5:
        warn = (f"{chrom}: only {kept:,} of {n_sites:,} sites kept after polarising; check that "
                "the ancestral genome matches GRCh38")
    write_relate_map(cfg, chrom, d / "relate.map")

    # 2. build the genealogies
    base = chrom
    if not (d / "BUILT").exists():
        step.progress(f"{chrom}: building genealogies with Relate ({kept:,} sites)")
        args = ["--haps", "prep.haps.gz", "--sample", "prep.sample.gz", "--map", "relate.map",
                "-m", cfg.get("RELATE_MU"), "-N", cfg.get("RELATE_N"), "-o", base,
                "--seed", cfg.get("RELATE_SEED")]
        if (d / "prep.dist.gz").exists():
            args += ["--dist", "prep.dist.gz"]
        threads = cfg.int("THREADS")
        if (d / base).is_dir():  # Relate's temp folder from an interrupted run makes it refuse
            import shutil
            shutil.rmtree(d / base)
        if threads > 1 and t["parallel"].exists():
            mem = max(1, int(cfg.float("MEMORY_GB") * 0.5))
            run([t["parallel"], *args, "--threads", threads, "--memory", mem])
        else:
            run([t["relate"], "--mode", "All", *args])
        if not ((d / f"{base}.anc").exists() and (d / f"{base}.mut").exists()):
            step.fail(f"{chrom}: Relate finished without writing {base}.anc/.mut (log: {pc.rel(log)})")
        (d / "BUILT").write_text("ok\n")

    # 3. optional: recalibrate branch lengths with the estimated population sizes
    final = base
    if cfg.get("RELATE_POPSIZE") == "1" and t["popsize"].exists():
        if not (d / "CALIBRATED").exists():
            step.progress(f"{chrom}: re-estimating population sizes and branch lengths")
            write_poplabels(cfg, d / "prep.sample.gz", d / "relate.poplabels")
            try:
                run([t["popsize"], "-i", base, "-o", f"{base}_popsize", "--poplabels",
                     "relate.poplabels", "-m", cfg.get("RELATE_MU"), "--years_per_gen", "28",
                     "--threshold", "0", "--num_iter", cfg.get("RELATE_POPSIZE_ITER"),
                     "--threads", cfg.get("THREADS"), "--seed", cfg.get("RELATE_SEED"),
                     "--noplot", "1"])
                for ext in ("anc", "mut"):
                    step.run(["gunzip", "-c", d / f"{base}_popsize.{ext}.gz"],
                             stdout=d / f"{base}_cal.{ext}")
                (d / "CALIBRATED").write_text("ok\n")
            except pc.StepError as e:
                warn = (f"{chrom}: population-size recalibration failed, so trees use a constant "
                        f"population size (RELATE_N). Error: {str(e)[:300]}")
        if (d / "CALIBRATED").exists():
            final = f"{base}_cal"

    # 4. convert to tskit for TRACE
    step.progress(f"{chrom}: converting to tskit tree sequence")
    run([t["formats"], "--mode", "ConvertToTreeSequence", "-i", final, "-o", chrom])
    if not trees.exists():
        step.fail(f"{chrom}: conversion did not write {pc.rel(trees)} (log: {pc.rel(log)})")
    (d / "DONE").write_text(final + "\n")
    return trees, warn


def work_relate(step, per):
    cfg = step.cfg
    t = relate_tools(step)
    rows, analysed = [], 0
    for chrom in cfg.chromosomes():
        info = per.get(chrom)
        if not info:
            step.fail(f"{chrom} is missing from 08-build-cohort results; rerun 08-build-cohort")
        trees, warn = relate_chrom(step, t, chrom, info.get("sites", 0))
        if warn:
            step.warn(warn)
        # one row per chromosome; start=0 so TRACE positions are used as they are
        rows.append({"chrom": chrom, "start": 0, "end": info["last_pos"] + 1,
                     "n_sites": info.get("sites", 0), "trees": str(trees)})
        analysed += info["last_pos"] - info["first_pos"]
        step.progress(f"{chrom}: genealogies ready")
    idx = pc.write_tsv(pc.work(cfg, "arg", "trees_index.tsv"), rows,
                       ["chrom", "start", "end", "n_sites", "trees"])
    step.metrics.update({"arg_method": "relate", "analysed_bp": analysed,
                         "popsize_recalibrated": cfg.get("RELATE_POPSIZE") == "1"})
    step.outputs.append(idx)
    step.warn("genealogies were built with Relate. In the paper's simulations TRACE found under "
              "10% of true archaic segments with Relate versus about 50% with SINGER, so expect "
              "far fewer segments; precision stays high (about 90%).")
    return "OK", f"Relate genealogies built for {len(rows)} chromosome(s) ({analysed / 1e6:.1f} Mb)"


# ---------------------------------------------------------------------------
def work(step):
    cfg = step.cfg
    res = pc.require(step, "08-build-cohort")
    for k, v in cfg.repo_prefixed.items():
        step.warn(f"{k} in repo/config.env starts with repo/ ({v!r}); paths are relative to "
                  "repo/, so the leading repo/ was ignored. Remove it from config.env.")
    method = cfg.get("ARG_METHOD").lower()
    per = res["08-build-cohort"]["metrics"]["per_chromosome"]
    if method == "relate":
        return work_relate(step, per)
    if method != "singer":
        step.fail(f"ARG_METHOD must be relate or singer, got {method!r}; ask the user to fix "
                  "repo/config.env")
    return work_singer(step, per)


def work_singer(step, per):
    cfg = step.cfg
    singer_dir = cfg.path("SINGER_DIR")
    prog = cfg.template("SINGER_CMD_TEMPLATE").split()[0] if cfg.get("SINGER_CMD_TEMPLATE") else ""
    if prog and "{" not in prog:
        p = Path(os.path.expanduser(prog))
        p = p if p.is_absolute() else pc.ROOT / p
        if "/" in prog and not p.exists():
            step.fail(f"SINGER_CMD_TEMPLATE starts with {prog}, which does not exist (looked for "
                      f"{p}). Relative paths are relative to repo/; using {{singer_dir}} in the "
                      "template avoids this.")
    # SINGER's repository keeps stale loose copies of `singer` and
    # `convert_to_tskit` at the top of releases/, next to the proper versioned
    # release folders. The stale converter builds the tree sequence without
    # sorting mutations or computing mutation parents, so tskit rejects it with
    # TSK_ERR_MUTATION_PARENT_AFTER_CHILD ("Parent mutation ID must be <
    # current ID"). Catch that here rather than after sampling every window.
    conv = singer_dir / "convert_to_tskit" if singer_dir else None
    if conv and conv.exists():
        try:
            src = conv.read_text(errors="replace")
        except OSError:
            src = ""
        if src and "compute_mutation_parents" not in src:
            step.fail(
                f"{conv} is an outdated copy of convert_to_tskit: it does not call "
                "compute_mutation_parents(), so tskit rejects its output with "
                "'Parent mutation ID must be < current ID' "
                "(TSK_ERR_MUTATION_PARENT_AFTER_CHILD). Do not patch it. SINGER ships a "
                "working converter inside each versioned release folder, while "
                "releases/ itself holds stale loose copies. Ask the user to point "
                "SINGER_DIR at a versioned release folder instead, for example "
                "SINGER_DIR=tools/SINGER/releases/singer-0.1.9-beta-linux-x86_64, then run "
                "this skill again; windows already sampled are kept and only the "
                "conversion is repeated.")
    missing = pc.missing_modules("tskit")
    if missing:
        step.fail(f"Python package {', '.join(missing)} is not installed for the Python that runs "
                  f"the pipeline ({sys.executable}); SINGER's convert_to_tskit needs it. Ask the "
                  f"user to run: {sys.executable} -m pip install {' '.join(missing)}")
    if not singer_dir or not (singer_dir / "singer_master").exists():
        step.fail("SINGER not found. Install it (https://github.com/popgenmethods/SINGER) and set "
                  "SINGER_DIR in repo/config.env to the folder that holds singer_master.")
    min_sites = cfg.int("SINGER_MIN_SITES")
    all_w, skipped = [], []
    for chrom in cfg.chromosomes():
        info = per.get(chrom)
        if not info:
            step.fail(f"{chrom} is missing from 08-build-cohort results; rerun 08-build-cohort")
        for w in windows_for(cfg, chrom, info["first_pos"], info["last_pos"]):
            (all_w if w["n_sites"] >= min_sites else skipped).append(w)
    step.metrics.update({"arg_method": "singer", "windows_total": len(all_w),
                         "windows_too_few_sites": len(skipped)})
    step.log(f"{len(all_w)} windows to build, {len(skipped)} skipped (< {min_sites} sites)")

    errors, finished, ok, stopped = [], 0, 0, False
    jobs = max(1, cfg.int("SINGER_JOBS"))
    give_up = max(4, 2 * jobs)  # all of the first N windows failed -> the setup is wrong
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(run_window, step, w, str(singer_dir)) for w in all_w]
        for f in as_completed(futs):
            if f.cancelled():
                continue
            w, err = f.result()
            finished += 1
            if err:
                errors.append(f"{w['chrom']}:{w['start']}-{w['end']}: {err}")
            else:
                ok += 1
            step.progress(f"{finished}/{len(all_w)} SINGER windows processed, {len(errors)} failed")
            if ok == 0 and len(errors) >= give_up and not stopped:
                stopped = True
                for other in futs:
                    other.cancel()
    if errors:
        step.metrics.update({"failed_windows": len(errors), "succeeded_windows": ok})
        what = (f"the first {len(errors)} windows all failed, so the rest were not started"
                if stopped else f"{len(errors)} window(s) failed")
        step.fail(f"{what}. First failure: {errors[0]}. Fix the cause and run this skill "
                  "again; finished windows are kept.")

    rows, analysed = [], 0
    for w in all_w:
        wdir = pc.work(cfg, "arg", w["chrom"], f"w{w['start']}", "x").parent
        trees = pick_trees(wdir, cfg.get("SINGER_USE_SAMPLE"))
        rows.append(dict(w, trees=str(trees)))
        analysed += w["end"] - w["start"]
    idx = pc.write_tsv(pc.work(cfg, "arg", "trees_index.tsv"), rows,
                       ["chrom", "start", "end", "n_sites", "trees"])
    step.metrics["analysed_bp"] = analysed
    step.outputs.append(idx)
    if skipped:
        step.warn(f"{len(skipped)} windows had too few sites and were left out of the ARG "
                  "(gaps such as centromeres are normal)")
    return "OK", f"ARGs built for {len(rows)} windows ({analysed / 1e6:.1f} Mb)"


if __name__ == "__main__":
    pc.run_step(NAME, work, background=True)
