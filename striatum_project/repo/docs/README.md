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

1. Download the IXI T1 archive and `IXI.xls` from https://brain-development.org/ixi-dataset/.
2. Extract the T1 images into `repo/reference/ixi/T1/`.
3. From `IXI.xls`, make `repo/reference/ixi_demographics.csv` with columns `subject,age,sex`.
   `subject` is the image file name without `.nii.gz` (e.g. `IXI002-Guys-0828-T1`); IXI codes sex
   as 1 = male, 2 = female — write `M`/`F`. Rows without an age can be dropped.
4. Ask the agent to run the build-reference skill (several hours on CPU; resumable).

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
