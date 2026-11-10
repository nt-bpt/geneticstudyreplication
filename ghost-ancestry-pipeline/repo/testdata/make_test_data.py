#!/usr/bin/env python3
"""Build a small, self-contained test dataset for the ghost-ancestry pipeline.

The point is a positive control: a simulated cohort with a *known* archaic
introgression event, so a run that completes can be checked against the truth
instead of only "it did not crash". Everything the skills would normally
download is produced locally, so the whole pipeline runs on real tools
(bwa, samtools, bcftools, Beagle, Relate, TRACE) in minutes rather than days.

Usage (from the repo folder, in the pipeline's own environment):

    python testdata/make_test_data.py --out testdata/fixture

Then point the pipeline at the generated config:

    cp testdata/fixture/config.env.test config.env

What is simulated (msprime), on a 3 Mb stretch placed on chr22:

    ancestral
      |-- GHOST            split 25,000 generations ago, never sampled
      |-- NEA              split 20,000 generations ago, 1 genome sampled
      |     '-- DEN        split 15,000 generations ago, 1 genome sampled
      '-- MODERN           31 genomes sampled (30 panel + 1 "user")

    pulses into MODERN:  GHOST 3,000 gens ago, NEA 2,000, DEN 1,500

Outputs in --out:

    ref.fa                 chr22 of true GRCh38 length, sequence only in the region
    user_R1.fq.gz, _R2.fq.gz   simulated reads for the user genome
    panel.vcf.gz           the 30-genome phased panel (stands in for 1000 Genomes)
    ped.txt                sample/population table, including two trio children
    maps.zip               PLINK-format genetic map
    nea*.vcf.gz, den.vcf.gz    archaic genomes, on hg19 coordinates like the real ones
    anc.tar.gz             ancestral alleles
    chain.gz               hg38 -> hg19 liftover chain for the region
    genes.gtf.gz           a few genes, named so skill 15 reports hits
    truth.tsv              THE TRUE introgressed segments in the user's haplotypes
    config.env.test        ready-to-use settings pointing at all of the above
"""
from __future__ import annotations

import argparse
import gzip
import random
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

CHR = "chr22"
CHR_LEN = 50818468          # GRCh38 chr22; skill 01 identifies the build from this
REGION_START = 20_000_000   # where the simulated stretch sits on chr22
HG19_OFFSET = -1_000_000    # pretend liftover shift, as in the real chain
GEN_TIME = 28
POPS = ["GBR", "CHB", "ITU", "YRI", "LWK"]   # COHORT_POPS in config.env


def simulate(length, n_panel, seed, pulse_scale):
    import msprime
    d = msprime.Demography()
    for name in ("MODERN", "NEA", "DEN", "GHOST", "ANC", "NEA_DEN", "MOD_NEA"):
        d.add_population(name=name, initial_size=10_000)
    d.add_population_split(time=15_000, derived=["NEA", "DEN"], ancestral="NEA_DEN")
    d.add_population_split(time=20_000, derived=["MODERN", "NEA_DEN"], ancestral="MOD_NEA")
    d.add_population_split(time=25_000, derived=["MOD_NEA", "GHOST"], ancestral="ANC")
    # Pulses of archaic ancestry into the modern population. The proportions are
    # deliberately larger than real human values (~2% Neanderthal) and the pulses
    # recent enough to leave long tracts, so that a few Mb carry a signal well
    # above the pipeline's 50 kb / 0.05 cM filters. This is a positive control,
    # not a model of human history; --pulse-scale turns the signal down.
    d.add_mass_migration(time=1_200, source="MODERN", dest="DEN",
                         proportion=0.05 * pulse_scale)
    d.add_mass_migration(time=1_500, source="MODERN", dest="NEA",
                         proportion=0.10 * pulse_scale)
    d.add_mass_migration(time=2_500, source="MODERN", dest="GHOST",
                         proportion=0.10 * pulse_scale)
    d.sort_events()
    ts = msprime.sim_ancestry(
        samples=[msprime.SampleSet(n_panel + 1, population="MODERN"),
                 msprime.SampleSet(1, population="NEA"),
                 msprime.SampleSet(1, population="DEN")],
        demography=d, sequence_length=length, recombination_rate=1e-8,
        record_migrations=True, random_seed=seed)
    ts = msprime.sim_mutations(ts, rate=1.25e-8, random_seed=seed, model="binary")
    return ts, d


def truth_segments(ts, d, user_nodes):
    """True archaic segments in the user's haplotypes, from the migration records."""
    import bisect
    archaic = {d[n].id for n in ("NEA", "DEN", "GHOST", "NEA_DEN")}
    migs = sorted((m.left, m.right, m.node) for m in ts.migrations()
                  if m.dest in archaic)
    lefts = [m[0] for m in migs]
    pieces = {i: [] for i in range(len(user_nodes))}
    for tree in ts.trees():
        tl, tr = tree.interval.left, tree.interval.right
        # migrations whose interval can overlap this tree
        hi = bisect.bisect_left(lefts, tr)
        for left, right, node in migs[:hi]:
            if right <= tl:
                continue
            lo, up = max(left, tl), min(right, tr)
            if up <= lo:
                continue
            for hap_index, sample in enumerate(user_nodes):
                u = sample
                while u != -1:
                    if u == node:
                        pieces[hap_index].append((lo, up))
                        break
                    u = tree.parent(u)
    out = []
    for hap_index, raw in pieces.items():
        raw.sort()
        merged = []
        for lo, up in raw:
            if merged and lo <= merged[-1][1] + 1:
                merged[-1][1] = max(merged[-1][1], up)
            else:
                merged.append([lo, up])
        for lo, up in merged:
            out.append((hap_index, int(lo) + REGION_START, int(up) + REGION_START))
    out.sort(key=lambda r: (r[0], r[1]))
    return out


def genotypes(ts, length, seed):
    """Per variant: position on chr22, REF, ALT and the haplotype alleles."""
    rng = random.Random(seed)
    bases = "ACGT"
    rows = []
    seen = set()
    for v in ts.variants():
        pos = int(v.site.position) + REGION_START
        if pos in seen or not (REGION_START < pos < REGION_START + length - 1):
            continue
        seen.add(pos)
        ref = rng.choice(bases)
        alt = rng.choice([b for b in bases if b != ref])
        rows.append((pos, ref, alt, v.genotypes))
    return rows


def write_reference(path, rows, length, seed):
    """chr22 at its true length: real sequence in the region, N elsewhere."""
    rng = random.Random(seed + 1)
    region = [rng.choice("ACGT") for _ in range(length)]
    for pos, ref, _alt, _g in rows:          # REF must match the reference base
        region[pos - REGION_START - 1] = ref
    seq = "N" * REGION_START + "".join(region) + "N" * (CHR_LEN - REGION_START - length)
    with open(path, "w") as f:
        f.write(f">{CHR}\n")
        for i in range(0, len(seq), 60):
            f.write(seq[i:i + 60] + "\n")
    return region


def write_vcf(path, rows, names, hap_slice, chrom=CHR, offset=0, phased=True,
              diploid=True, contig_len=CHR_LEN):
    sep = "|" if phased else "/"
    with open(path, "w") as f:
        f.write("##fileformat=VCFv4.2\n")
        f.write(f"##contig=<ID={chrom},length={contig_len}>\n")
        f.write('##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">\n')
        f.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t" +
                "\t".join(names) + "\n")
        for pos, ref, alt, g in rows:
            calls = []
            for k in range(*hap_slice):
                if diploid:
                    calls.append(f"{g[2 * k]}{sep}{g[2 * k + 1]}")
                else:
                    calls.append(f"{g[2 * k]}{sep}{g[2 * k + 1]}")
            if all(c in ("0|0", "0/0") for c in calls):
                continue                      # keep only sites that vary here
            f.write(f"{chrom}\t{pos + offset}\t.\t{ref}\t{alt}\t.\tPASS\t.\tGT\t"
                    + "\t".join(calls) + "\n")


def bgzip_index(path, csi=False):
    subprocess.run(["bgzip", "-f", str(path)], check=True)
    subprocess.run(["tabix", "-f", "-p", "vcf", str(path) + ".gz"], check=True)


def write_reads(out1, out2, region, rows, user_hap_a, user_hap_b, depth, seed):
    """Paired reads from the user's two haplotypes, enough for confident calls."""
    rng = random.Random(seed + 2)
    comp = str.maketrans("ACGT", "TGCA")
    haps = []
    for hap in (user_hap_a, user_hap_b):
        s = list(region)
        for (pos, ref, alt, g) in rows:
            if g[hap]:
                s[pos - REGION_START - 1] = alt
        haps.append("".join(s))
    read_len, frag = 100, 350
    n_pairs = int(len(region) * depth / (2 * read_len))
    with gzip.open(out1, "wt") as f1, gzip.open(out2, "wt") as f2:
        for i in range(n_pairs):
            h = haps[i % 2]
            st = rng.randint(0, len(h) - frag - 1)
            a = h[st:st + read_len]
            b = h[st + frag - read_len:st + frag].translate(comp)[::-1]
            q = "I" * read_len
            f1.write(f"@sim{i}/1\n{a}\n+\n{q}\n")
            f2.write(f"@sim{i}/2\n{b}\n+\n{q}\n")
    return n_pairs


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="testdata/fixture", help="output folder")
    ap.add_argument("--region-mb", type=float, default=5.0, help="simulated length in Mb")
    ap.add_argument("--pulse-scale", type=float, default=1.0,
                    help="scale the archaic pulse proportions (1.0 gives a strong, "
                         "easily detectable signal; 0.2 is closer to real human values)")
    ap.add_argument("--depth", type=float, default=15.0, help="read depth for the user genome")
    ap.add_argument("--panel", type=int, default=30, help="panel genomes (6 per population)")
    ap.add_argument("--seed", type=int, default=20261109)
    a = ap.parse_args()

    try:
        import msprime  # noqa: F401
    except ImportError:
        sys.exit("msprime is needed to build the test data. Install it in this environment:\n"
                 f"  {sys.executable} -m pip install msprime")
    for tool in ("bgzip", "tabix"):
        if subprocess.run(["which", tool], capture_output=True).returncode != 0:
            sys.exit(f"{tool} not found; install samtools/htslib first")

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    length = int(a.region_mb * 1e6)
    n_panel = a.panel

    print(f"simulating {a.region_mb} Mb, {n_panel} panel genomes + 1 user + 2 archaic ...")
    ts, dem = simulate(length, n_panel, a.seed, a.pulse_scale)
    rows = genotypes(ts, length, a.seed)
    print(f"  {ts.num_trees:,} trees, {len(rows):,} usable variants")

    # haplotype order: panel 0..n-1, user n, NEA n+1, DEN n+2 (2 haplotypes each)
    user_i, nea_i, den_i = n_panel, n_panel + 1, n_panel + 2
    user_nodes = [2 * user_i, 2 * user_i + 1]

    truth = truth_segments(ts, dem, user_nodes)
    with open(out / "truth.tsv", "w") as f:
        f.write("hap\tstart\tend\tlength_bp\n")
        for hap, lo, hi in truth:
            f.write(f"{hap}\t{lo}\t{hi}\t{hi - lo}\n")
    tot = sum(hi - lo for _, lo, hi in truth)
    big = [r for r in truth if r[2] - r[1] >= 50_000]
    print(f"  truth: {len(truth)} archaic segments in the user genome, "
          f"{tot / 1e3:.0f} kb total ({tot / (2 * length):.2%} per haplotype); "
          f"{len(big)} are >= 50 kb, which is what the pipeline's filters keep")
    if len(big) < 3:
        print("  NOTE: few segments clear the 50 kb filter. Use a larger --region-mb "
              "or a higher --pulse-scale for a stronger positive control.")

    print("writing reference ...")
    region = write_reference(out / "ref.fa", rows, length, a.seed)

    print("writing panel and sample table ...")
    panel_names = [f"HG{i:05d}" for i in range(n_panel)]
    write_vcf(out / "panel.vcf", rows, panel_names, (0, n_panel))
    bgzip_index(out / "panel.vcf")
    with open(out / "ped.txt", "w") as f:
        f.write("FamilyID SampleID FatherID MotherID Sex Population Superpopulation\n")
        for k, name in enumerate(panel_names):
            f.write(f"F{k} {name} 0 0 1 {POPS[k % len(POPS)]} X\n")
        for k in range(2):      # trio children: skill 05 must exclude these
            f.write(f"C{k} NA9999{k} {panel_names[0]} {panel_names[1]} 1 {POPS[0]} X\n")

    # The user's genotypes with the TRUE phase. Phasing quality decides whether a
    # long archaic tract survives as one haplotype, so if a run recovers little,
    # swapping this in for skill 07's output separates a phasing problem from an
    # ARG or TRACE problem. See testdata/README.md.
    write_vcf(out / "user_truth_phased.vcf", rows, ["TESTUSER"], (user_i, user_i + 1))
    bgzip_index(out / "user_truth_phased.vcf")

    print("writing archaic genomes (hg19 coordinates) ...")
    for name, idx in (("nea_altai", nea_i), ("nea_vindija", nea_i),
                      ("nea_chagyrskaya", nea_i), ("den_altai", den_i)):
        write_vcf(out / f"{name}.vcf", rows, [name], (idx, idx + 1),
                  chrom="22", offset=HG19_OFFSET, phased=False, contig_len=51304566)
        bgzip_index(out / f"{name}.vcf")

    print("writing ancestral alleles, maps, chain and genes ...")
    anc_dir = out / "anc_build" / "homo_sapiens_ancestor_GRCh38"
    anc_dir.mkdir(parents=True, exist_ok=True)
    seq = "N" * REGION_START + "".join(region) + "N" * (CHR_LEN - REGION_START - length)
    with open(anc_dir / "homo_sapiens_ancestor_22.fa", "w") as f:
        f.write(">ANCESTOR_for_chromosome:GRCh38:22\n")
        for i in range(0, len(seq), 60):
            f.write(seq[i:i + 60] + "\n")
    with tarfile.open(out / "anc.tar.gz", "w:gz") as t:
        t.add(anc_dir, arcname="homo_sapiens_ancestor_GRCh38")

    with zipfile.ZipFile(out / "maps.zip", "w", zipfile.ZIP_DEFLATED) as z:
        lines = "".join(f"22\t.\t{bp / 1e6:.6f}\t{bp}\n"
                        for bp in range(16_000_000, 50_000_001, 5_000))
        z.writestr("plink.chr22.GRCh38.map", lines)

    with gzip.open(out / "chain.gz", "wt") as f:
        f.write(f"chain 1000 {CHR} {CHR_LEN} + {REGION_START - 1_000_000} "
                f"{REGION_START + length + 1_000_000} 22 51304566 + "
                f"{REGION_START - 1_000_000 + HG19_OFFSET} "
                f"{REGION_START + length + 1_000_000 + HG19_OFFSET} 1\n"
                f"{length + 2_000_000}\n\n")

    # genes placed inside the region, named so skill 15 reports paper genes
    mid = REGION_START + length // 2
    with gzip.open(out / "genes.gtf.gz", "wt") as f:
        for name, start, gtype in (("FOXP2", mid, "protein_coding"),
                                   ("RBFOX1", mid + 150_000, "protein_coding"),
                                   ("CYP24A1", mid - 200_000, "protein_coding"),
                                   ("TESTGENE1", REGION_START + 50_000, "lncRNA")):
            f.write(f"{CHR}\tsim\tgene\t{start}\t{start + 40_000}\t.\t+\t.\t"
                    f'gene_id "{name}"; gene_type "{gtype}"; gene_name "{name}";\n')

    print("writing reads ...")
    n_pairs = write_reads(out / "user_R1.fq.gz", out / "user_R2.fq.gz", region, rows,
                          user_nodes[0], user_nodes[1], a.depth, a.seed)
    print(f"  {n_pairs:,} read pairs at about {a.depth}x")

    fx = out.resolve()
    (out / "config.env.test").write_text(f"""\
# Generated by testdata/make_test_data.py. Copy to repo/config.env to run the
# pipeline on the test data, then compare skill 11's segments with truth.tsv.
FASTQ_R1={fx}/user_R1.fq.gz
FASTQ_R2={fx}/user_R2.fq.gz
SAMPLE_NAME=TESTUSER
CHROMOSOMES=22
THREADS=4
MEMORY_GB=8
MIN_FREE_GB=5
MIN_MEAN_DEPTH=5
REFERENCE_FASTA={fx}/ref.fa

# everything the skills would download, served from the fixture
PANEL_URL_TEMPLATE=file://{fx}/panel.vcf.gz
PANEL_SAMPLES_URL=file://{fx}/ped.txt
GENETIC_MAP_URL=file://{fx}/maps.zip
ANCESTRAL_URL=file://{fx}/anc.tar.gz
CHAIN_URL=file://{fx}/chain.gz
GENCODE_URL=file://{fx}/genes.gtf.gz
ARCHAIC_URL_NEA_ALTAI=file://{fx}/nea_altai.vcf.gz
ARCHAIC_URL_NEA_VINDIJA=file://{fx}/nea_vindija.vcf.gz
ARCHAIC_URL_NEA_CHAGYRSKAYA=file://{fx}/nea_chagyrskaya.vcf.gz
ARCHAIC_URL_DEN_ALTAI=file://{fx}/den_altai.vcf.gz

# fill these in for your own installs
RELATE_DIR=
BEAGLE_JAR=
ARG_METHOD=relate
RELATE_POPSIZE=1
""")
    print(f"\ndone. Test data in {fx}")
    print("next:  cp", out / "config.env.test", "config.env   "
          "# then set RELATE_DIR and BEAGLE_JAR")


if __name__ == "__main__":
    main()
