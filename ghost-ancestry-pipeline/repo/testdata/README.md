# Test data: a fast end-to-end check before committing a real genome

A full run takes days, so an error in the last stage is expensive to discover.
This fixture runs the whole pipeline on a simulated 5 Mb region in minutes,
using the real tools (bwa, samtools, bcftools, Beagle, Relate, TRACE), and
gives you a known answer to compare against.

## Build it

From the repo folder, in the same environment that runs the pipeline:

```
pip install msprime                      # only needed to build the test data
python testdata/make_test_data.py --out testdata/fixture
```

That writes about 120 MB into `testdata/fixture`, including everything the
skills would otherwise download, so no network access is needed.

## Run the pipeline on it

```
cp testdata/fixture/config.env.test config.env
# then set RELATE_DIR and BEAGLE_JAR in config.env to your own installs
```

Run skills 00 to 16 as usual, then:

```
python testdata/check_result.py --fixture testdata/fixture
```

The checker prints every stage's status, the key numbers, and how much of the
planted signal the run recovered. It exits non-zero if a stage is missing or
failed, so you can use it as a smoke test.

## What is simulated

msprime, with a known archaic introgression history:

```
ancestral
  |-- GHOST          split 25,000 generations ago, never sampled
  |-- NEA            split 20,000 generations ago, one genome sampled
  |     '-- DEN      split 15,000 generations ago, one genome sampled
  '-- MODERN         31 genomes sampled (30 panel + 1 "user")

pulses into MODERN:  GHOST 2,500 generations ago, NEA 1,500, DEN 1,200
```

`truth.tsv` lists the true archaic segments in the user's two haplotypes. The
pulse proportions are deliberately larger than real human values (about 10%
rather than 2%) and recent enough to leave long tracts, so that a few Mb carry
a signal above the pipeline's 50 kb and 0.05 cM filters. `--pulse-scale 0.2`
brings them closer to real values, at the cost of a much weaker signal. The
archaic genomes are written on hg19 coordinates with a matching liftover chain,
like the real Neanderthal and Denisovan files, so skill 12 exercises its
liftover. A few genes are placed in the region and named FOXP2, RBFOX1 and
CYP24A1 so that skill 15 can report hits.

## What this does and does not prove

**It proves the plumbing.** Every tool runs, every file format matches, the
genome build is identified, coordinates line up across liftover, genes
annotate, the report renders. That is the class of error that otherwise costs
you days, and it is most of what has gone wrong in practice: a stale script, a
wrong path, an unset option, mismatched coordinates.

**It also gives a real precision check.** In my run, TRACE reported one segment
and that segment fell entirely inside a true archaic tract.

**It does not prove good recall, and a low number here is expected.** My run
recovered 1 of the 16 true segments longer than 50 kb, about 5% of the
introgressed sequence. That is in line with the paper's own simulations, where
TRACE recovered under 10% of true segments from Relate genealogies against
about 50% from SINGER. On 5 Mb with 31 genomes there is also little data for
TRACE's model to train on. So read the result as "what it found was real",
not as "it found what is there".

Two settings visibly change recall on this fixture, which is a good reason to
try them here rather than on a real genome:

- `RELATE_POPSIZE`: with recalibration on I recovered nothing; with it off I
  recovered one true segment. Which is better on real data at full scale is not
  something this fixture can settle.
- `ARG_METHOD=singer` should do better on recall, if you have SINGER working.

## Isolating a phasing problem

Phasing decides whether a long archaic tract survives as one haplotype, so poor
phasing alone can flatten the signal. The fixture therefore also writes
`user_truth_phased.vcf.gz`, the user's genotypes with the true phase. If a run
recovers very little, comparing against that file tells you whether phase is
the cause before you blame the ARG or TRACE stage.

## A bug this already caught

Writing the fixture immediately exposed an off-by-one in its own reference
sequence: VCF positions are 1-based while the sequence array is 0-based, so
`bcftools` rejected the run with "The reference alleles are not compatible".
That is the kind of failure this is meant to surface in minutes.
