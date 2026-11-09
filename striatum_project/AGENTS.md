# AGENTS.md — caudate–putamen MRI measurement

You run a measurement pipeline on one person's brain MRI and compare it with a healthy reference
cohort. Produce accurate numbers and an honest interpretation.

## Project layout

```
AGENTS.md                      this file (the only file in the project root)
.agent/skills/<skill>/         one folder per pipeline step: SKILL.md + scripts/
repo/input/<subject>/          the subject's scan (DICOM folder tree or NIfTI)
repo/work/<subject>/           intermediate files and JSON state passed between skills
repo/results/<subject>/        report.md and report.json
repo/reference/                IXI data (ixi/T1/, ixi_demographics.csv) and reference.csv
repo/lib/striatum/             shared Python code used by the skill scripts
repo/docs/README.md            human setup guide
repo/docker/                   Dockerfile and package list
repo/requirements.txt          Python packages for non-Docker installs
```

All data, outputs and documentation live under `repo/`. Run every command from the project root.

## Rules for using skills

1. **Every step is done by executing a skill's script with your command-execution tool** (shell /
   terminal / Bash tool), exactly as shown in that skill's SKILL.md. Read the SKILL.md before the
   first time you use a skill.
2. **Never do a step's work directly**: don't re-implement a script's logic, compute volumes or
   statistics yourself, estimate anything from looking at images, or substitute another tool or a
   vision-language model. If a script can't run, report why and stop.
3. **Don't edit the scripts or `repo/lib/`** unless the user explicitly asks you to change the
   code.
4. Pass state between steps only through the files the skills write in `repo/work/<subject>/`.

## Skills, in order

| Skill | Purpose |
|---|---|
| `check-environment` | Confirm FreeSurfer/SynthSeg, dcm2niix, Python libs, license. Run first. |
| `build-reference` | One-time: build `repo/reference/reference.csv` from IXI scans. |
| `ingest-mri` | DICOM → NIfTI, choose the T1, flag thick slices. |
| `segment-synthseg` | SynthSeg segmentation, intracranial volume, QC. |
| `measure-striatum` | Caudate/putamen volumes, asymmetry, bridge zone. |
| `compare-reference` | Age/sex-matched z-scores and percentiles. |
| `write-report` | `repo/results/<subject>/report.md`. |
| `run-full-pipeline` | Runs ingest → report in one command. |

## Typical session

1. Run **check-environment**. If anything is missing, tell the user and stop.
2. If `repo/reference/reference.csv` doesn't exist, run **build-reference** (or tell the user the
   IXI data is needed; see `repo/docs/README.md`).
3. Confirm the scan is in `repo/input/<subject>/` and get the subject's age at scan and sex.
4. Run **run-full-pipeline**, or the individual skills in order if you need to intervene (e.g.
   choosing the T1 series).
5. Visual sanity check, if the user has a viewer (freeview, fsleyes): ask them to open
   `repo/work/<subject>/t1_resampled.nii.gz` with `repo/work/<subject>/synthseg.nii.gz` overlaid
   and confirm the caudate and putamen labels sit on those structures.
6. Summarise per the write-report skill.

## Background you must keep straight

- Garry Nolan (Stanford) has said in interviews that some people reporting UAP encounters showed
  denser tissue/connectivity between the head of the caudate and the putamen. The encounters were
  not verified, no method or threshold has been published for it, and Nolan has suggested the
  feature may be inherited and stable — a trait, not a mark left by an event. He has said genetic
  findings in families, but has not published them.
- This pipeline **measures**; it does not **validate** anything about an encounter. Never state or
  imply that a result confirms, supports, or rules out an abduction or UAP encounter.
- With ~11 metrics compared, one |z| ≥ 2 is common by chance. Say so whenever you mention one.
- If something looks medically abnormal (large asymmetry, very small structures, QC flags
  suggesting a lesion), recommend the user show the scan to a radiologist or neurologist. Don't
  diagnose.

## Optional: diffusion

Nolan described the feature as fiber density. If ingest-mri reports `dwi_present: true`, a
tractography analysis (MRtrix3: caudate-seeded streamlines reaching the putamen, normalised by
seed volume) would be closer to that idea. No skill implements it yet; tell the user it would need
to be added rather than approximating it. Most elective MRIs have no diffusion series.
