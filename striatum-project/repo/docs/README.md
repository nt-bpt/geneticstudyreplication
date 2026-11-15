# Caudate–putamen MRI pipeline — setup guide

Measures the caudate, putamen and the tissue "bridge" between them on a T1 brain MRI and compares
the numbers with a healthy reference cohort. An AI agent runs it through the skills in
`.agent/skills/`, following `AGENTS.md`. All paths below are relative to the project root.

## 1. Build and start the container

```bash
docker build -t striatum -f repo/docker/Dockerfile repo/docker
docker run --rm -it \
  -v "$PWD":/project -w /project \
  -v /path/to/freesurfer_license.txt:/license.txt:ro -e FS_LICENSE=/license.txt \
  --memory 32g striatum
```

The FreeSurfer licence is free: https://surfer.nmr.mgh.harvard.edu/registration.html. The image
is large (~25 GB) because FreeSurfer is.

Without Docker: install the packages in `repo/docker/apt-packages.txt`, the FreeSurfer 8.2 .deb,
and `pip install -r repo/requirements.txt`, then `source $FREESURFER_HOME/SetUpFreeSurfer.sh`.

Check with: `python3 .agent/skills/check-environment/scripts/check_env.py`

## 2. Reference cohort (once)

Two open cohorts are scripted: **IXI** (healthy adults, London, 1.5T/3T, CC BY-SA 3.0) and **DLBS**
(Dallas Lifespan Brain Study, Philips 3T, OpenNeuro ds004856, CC0). Only subjects in your age/sex
band are kept. Example for a 47-year-old man (age ±15):

```bash
python3 .agent/skills/fetch-reference/scripts/fetch_reference.py --age-min 32 --age-max 62 --sex M
python3 .agent/skills/build-reference/scripts/build_reference.py --threads 8
python3 .agent/skills/build-reference/scripts/build_reference.py --threads 8 \
    --t1-dir repo/reference/dlbs/T1 --demographics repo/reference/dlbs_demographics.csv
```

The fetch downloads ~4.5 GB for IXI (deleted after extraction) and ~1 GB for DLBS. The two build
runs take a few hours on CPU and resume if interrupted.

Optional: OASIS-1 (non-demented adults, 1.5T) is distributed through NITRC/XNAT after
registration, so it isn't scripted. To add it, put its T1s in `repo/reference/oasis1/T1/`, make
`repo/reference/oasis1_demographics.csv` (`subject,age,sex,cohort`, keeping only CDR 0) and run
build-reference with those paths.

## 3. Your scan

1. Ask the scan provider for the DICOM files of the brain series, and whether a 3D T1-weighted
   series (MPRAGE / SPGR / BRAVO) and any diffusion series were acquired.
2. Put the DICOM folder (or NIfTI files) in `repo/input/<name>/`, e.g. `repo/input/me/`.
3. Ask the agent to run the pipeline for `<name>`, giving your age at the scan and sex.
4. The report is written to `repo/results/<name>/report.md`.

## What the result can and cannot tell you

Every report ends with this section. In short: you get real measurements of these structures, but
no measurement can confirm or rule out an encounter, because the original observation has no
published method, threshold or verified cohort to compare against.
