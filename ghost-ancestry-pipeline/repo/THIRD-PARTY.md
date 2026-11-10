# Third-party programs, data and copyright

This pipeline is a set of scripts that *call* other people's programs and
*download* public data. It bundles none of them. That distinction is what
keeps publishing it straightforward, so keep it that way: do not commit any
program or dataset into this repository. The `.gitignore` at the top level
excludes `repo/tools/`, `repo/data/`, `repo/work/`, `repo/results/`,
`repo/logs/` and `repo/config.env` for that reason, and because those folders
hold personal genetic data.

This file records what the pipeline uses and the terms I was able to read on
2026-11-03. Licences change; check each one yourself before publishing, and
note that I am not a lawyer and this is not legal advice.

## Programs the pipeline runs

| Program | Used by | Terms as read |
|---|---|---|
| Relate | skill 10 (default) | Academic, non-commercial use only. University of Oxford. Redistribution is not permitted, and the terms require the notice below wherever results are used. Commercial enquiries: Oxford University Innovation, reference 15670 |
| SINGER | skill 10 (`ARG_METHOD=singer`) | MIT licence, Copyright (c) 2023 YunDeng98 |
| TRACE | skills 11 and 14 | MIT licence, Copyright (c) 2025 Arjun Biddanda, Yulin Zhang. <https://github.com/YulinZhang9806/trace> |
| Beagle | skill 7 | GNU GPL v3 (as packaged by third parties). Run as a separate program, so it imposes no licence on this pipeline's own code |
| samtools, bcftools, htslib | several | MIT/BSD-style |
| bwa | skill 3 | GPL v3 |
| CrossMap | skill 12 | GPL-style; check the current release |
| bedtools | optional, skill 11 with `TRACE_INCLUDE_REGIONS` | MIT licence |

### Required notice when using Relate

Relate's terms require that the following appears prominently wherever results
from it are used, and that it is cited in any publication describing the work:

> Copyright © 2018, University of Oxford

The terms also state that the user acquires no right, title or interest in the
output of the software. If that matters for what you intend to do with your
results, read the licence yourself and take advice.

Relate: Speidel et al., *Nature Genetics* 2019,
<https://myersgroup.github.io/relate/>

## Data the pipeline downloads at run time

None of this is stored in the repository; the skills fetch it into
`repo/data/`. Each source has its own terms — check them for any use beyond
your own research:

- 1000 Genomes Project phased panel and sample table
- Ensembl ancestral alleles (GRCh38)
- GRCh38 reference genome (1000 Genomes analysis set)
- Recombination maps distributed with Beagle
- High-coverage Neanderthal and Denisovan genomes (Max Planck Institute for
  Evolutionary Anthropology)
- GENCODE gene annotation
- UCSC liftOver chain file
- `Trace_data`: the archaic tracts published with the paper, from Zenodo

## The paper

The method follows Zhang, Biddanda, Johnson, O'Dushlaine and Moorjani,
"Recovering signatures of archaic hominin introgression using ancestral
recombination graphs", *Science* 2026, doi:10.1126/science.aef8874.

The paper is copyrighted by its publisher. **Do not commit the PDF or its
supplementary materials to this repository**; cite the DOI instead. Parameter
values, gene names and coordinates are facts and are used as such here; the
prose in this repository is its own.

Citing the paper, Relate or SINGER is not an endorsement by their authors, and
nothing in this repository comes from them.

## Your own data

Your genome is sensitive personal information, and publishing it also
discloses information about your relatives, who cannot consent for you. It
cannot be withdrawn once public. Before running `git add`, check
`git status --ignored` and confirm that nothing under `repo/work/`,
`repo/results/`, `repo/logs/` or `repo/config.env` is staged.
