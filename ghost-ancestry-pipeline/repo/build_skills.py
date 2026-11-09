#!/usr/bin/env python3
"""Generate every SKILL.md (ADK format) and copy pipeline_common.py into each skill's scripts/ folder.
Run from the project folder: python3 build_skills.py"""
import re
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent          # repo/
LIB = HERE / "lib" / "pipeline_common.py"
SKILLS = None  # defined below
SKILLS_ROOT = HERE.parent / ".agent" / "skills"  # <working dir>/.agent/skills

ASK = "ask the user to set it in repo/config.env"

SKILLS = [
    dict(name="00-check-env",
         desc="verify tools, configuration and disk space before any slow step",
         what="Check that the required programs, the input settings in repo/config.env and the free disk space are all in order.",
         time="This skill finishes in seconds.",
         outputs=["results/00-check-env.json"],
         fixes=["missing tools: tell the user to install them with the system package manager, e.g. `sudo apt install samtools bcftools tabix bwa curl` (Debian/Ubuntu) or `brew install samtools bcftools htslib bwa` (macOS). The exact command is in the verdict.",
                f"no input set, or both FASTQ and INPUT_FILE set: {ASK}. Use FASTQ_R1 + FASTQ_R2 for FASTQ files, or INPUT_FILE (+ INPUT_REFERENCE for a CRAM).",
                f"repo/config.env not found: ask the user to create it by copying repo/config.env.example.",
                "low disk space: ask the user to free space or point WORK_DIR and DATA_DIR at a larger disk."],
         notes=["Installing system programs needs the user's permission (sudo). Do not run install commands yourself; give the user the command from the verdict.",
                "A WARN listing tools needed by later skills (java, SINGER, CrossMap) is normal at this point; mention it in the report."]),
    dict(name="01-inspect-input",
         desc="identify the input files (FASTQ pair or CRAM/BAM) and the genome build",
         what="Work out whether the input is a FASTQ pair or a CRAM/BAM, and for an alignment which genome build it uses.",
         time="This skill finishes in seconds to a minute.",
         outputs=["results/01-inspect-input.json (`metrics.mode` is fastq, alignment_grch38 or realign)"],
         fixes=[f"read names do not match: the two FASTQ files may not be a pair; {ASK.replace('set it in repo/config.env', 'check FASTQ_R1 and FASTQ_R2 in repo/config.env')}.",
                f"could not read alignments from a CRAM: INPUT_REFERENCE must be the exact FASTA the CRAM was made with; {ASK}.",
                "unknown genome build: ask the user which reference the file was aligned to."]),
    dict(name="02-prepare-reference", bg=True,
         desc="download and index the GRCh38 reference genome",
         what="Get the GRCh38 reference genome and build the indexes needed for alignment and variant calling.",
         time="Downloading takes 10-60 minutes; building the bwa index adds about 1 hour (only for FASTQ input or realignment).",
         outputs=["results/02-prepare-reference.json (`metrics.reference` is the FASTA used by later skills)"],
         fixes=["download failed: run the skill again (downloads resume). If it keeps failing, ask the user to download REFERENCE_URL by hand and set REFERENCE_FASTA in repo/config.env.",
                "chromosome missing or wrong length: the reference is not chr-prefixed GRCh38; ask the user to clear REFERENCE_FASTA so the default GRCh38 is downloaded.",
                "bwa index failed: usually too little memory (needs about 5 GB) or disk."]),
    dict(name="03-align-reads", bg=True,
         desc="align FASTQ reads to GRCh38, or realign a non-GRCh38 CRAM/BAM",
         what="Align the reads to GRCh38 and produce a sorted, duplicate-marked CRAM. A GRCh38 CRAM/BAM is used as it is and the skill reports SKIPPED.",
         time="Alignment takes many hours (roughly 1 hour per 10x of coverage with 8 threads). SKIPPED inputs finish in minutes.",
         outputs=["results/03-align-reads.json (`metrics.alignment` is the CRAM/BAM used by later skills)",
                  "work/align/<SAMPLE_NAME>.GRCh38.cram (when aligned here)"],
         fixes=["not enough disk space: ask the user to free space or move WORK_DIR to a larger disk.",
                "bwa or samtools killed: lower THREADS or MEMORY_GB in repo/config.env and run again.",
                "command failed: the verdict ends with the last log lines; report them to the user."]),
    dict(name="04-qc-alignment", bg=True,
         desc="check depth of coverage and alignment quality",
         what="Measure depth of coverage on the chosen chromosomes and check that it is enough for reliable genotypes.",
         time="This skill finishes in a few minutes.",
         outputs=["results/04-qc-alignment.json (`metrics.mean_depth`, `metrics.inferred_sex`)"],
         fixes=["depth too low: the genome cannot be genotyped reliably; tell the user and stop. Lowering MIN_MEAN_DEPTH in repo/config.env only hides the problem."]),
    dict(name="05-fetch-panel", bg=True,
         desc="download the phased 1000 Genomes panel, pick the study cohort, prepare genetic maps",
         what="Download the phased 1000 Genomes panel for the chosen chromosomes, select the 503-sample study cohort (GBR, CHB, ITU, YRI, LWK) and prepare genetic maps.",
         time="About 10-30 minutes per chromosome, mostly download time.",
         outputs=["results/05-fetch-panel.json (`metrics.cohort_size` should be close to 503)",
                  "work/panel/ (SNP panel, site lists, cohort_samples.txt)", "work/maps/ (genetic maps)"],
         fixes=["download failed: run the skill again; downloads resume.",
                "a URL no longer works: ask the user to check PANEL_URL_TEMPLATE, PANEL_SAMPLES_URL or GENETIC_MAP_URL in repo/config.env."]),
    dict(name="06-call-variants", bg=True,
         desc="genotype the user's genome at every 1000 Genomes SNP site",
         what="Genotype the user's alignment at every SNP position in the 1000 Genomes panel, keeping only confident calls.",
         time="About 15-60 minutes per chromosome.",
         outputs=["results/06-call-variants.json (`metrics.per_chromosome` has call rates and het/hom ratios)",
                  "work/calls/<SAMPLE_NAME>.<chrom>.vcf.gz"],
         fixes=["CRAM decoding error: the reference in results/02-prepare-reference.json is not the one the CRAM was made with; ask the user to set INPUT_REFERENCE correctly, then rerun 02 and this skill.",
                "low call rate or unusual het/hom ratio (WARN): mention it in the report; it can mean low coverage or a sample problem."]),
    dict(name="07-phase", bg=True,
         desc="phase the user's genotypes into two haplotypes with Beagle",
         what="Split the user's genotypes into two haplotypes (phasing) with Beagle, using the 1000 Genomes panel as reference.",
         time="About 10-60 minutes per chromosome.",
         outputs=["results/07-phase.json", "work/phased/<SAMPLE_NAME>.<chrom>.vcf.gz"],
         fixes=["java not found: tell the user to install Java, e.g. `sudo apt install default-jre` (Debian/Ubuntu) or `brew install openjdk` (macOS).",
                f"Beagle download failed: the jar name changes with each release; {ASK.replace('set it', 'set BEAGLE_URL or BEAGLE_JAR')}.",
                "Beagle out of memory: lower THREADS or raise MEMORY_GB in repo/config.env, then run again."]),
    dict(name="08-build-cohort", bg=True,
         desc="join the user's phased genome to the 1000 Genomes study cohort",
         what="Combine the 503 cohort genomes and the user's phased genome into one VCF per chromosome, ready for ARG building.",
         time="About 5-20 minutes per chromosome.",
         outputs=["results/08-build-cohort.json (`metrics.user_hap_nodes` are the user's haplotype IDs)",
                  "work/cohort/<chrom>/cohort.vcf and cohort.vcf.gz"],
         fixes=[f"SAMPLE_NAME clashes with a 1000 Genomes ID: {ASK.replace('set it', 'change SAMPLE_NAME')}, then rerun from 06-call-variants.",
                "sites not phased: rerun 07-phase, then this skill."],
         notes=["This skill always gives one WARN about haplotype node numbering; that is expected. Mention it in the report."]),
    dict(name="09-fetch-trace", bg=True,
         desc="download TRACE software, the authors' pipeline and published tracts from Zenodo",
         what="Download the TRACE software, the authors' analysis pipeline and the published archaic tracts from Zenodo.",
         time="A few minutes to an hour, depending on download size.",
         outputs=["results/09-fetch-trace.json (`trace_readme_preview` holds the start of the TRACE README)",
                  "tools/trace_software/, tools/trace_pipeline/, data/trace_data/"],
         fixes=["Zenodo listing failed: ask the user to download the three Zenodo records by hand into tools/trace_software, tools/trace_pipeline and data/trace_data, then run again.",
                "not enough disk space for Trace_data: ask the user to free space."],
         notes=["If TRACE_CMD_TEMPLATE is empty this skill gives a WARN. Tell the user they must install TRACE and set TRACE_CMD_TEMPLATE in repo/config.env before skill 11. The start of the TRACE README is in `trace_readme_preview` in the tool result; you may use it to suggest a template, but the user sets it."]),
    dict(name="10-build-arg", bg=True,
         desc="build the cohort's genealogies (ARGs) with Relate, or SINGER if ARG_METHOD=singer",
         what="Build ancestral recombination graphs (ARGs) for the cohort, one chromosome at a time with Relate (default), and convert them to the tree files TRACE reads.",
         time="With Relate: roughly 1-4 hours per large chromosome on 8 threads, plus population-size recalibration. With ARG_METHOD=singer: days per large chromosome. Finished stages are kept, so running it again after a stop continues where it left off.",
         outputs=["results/10-build-arg.json (`metrics.arg_method`, `metrics.analysed_bp`)", "work/arg/trees_index.tsv",
                  "work/arg/<chrom>/relate/<chrom>.trees and relate.log (Relate)",
                  "work/arg/<chrom>/w<start>/ (SINGER, one folder per window)"],
         fixes=[f"RELATE_DIR is empty or Relate file not found: ask the user to download Relate from https://myersgroup.github.io/relate/, unpack it, and set RELATE_DIR in repo/config.env to the folder holding bin/ and scripts/.",
                "a Relate file is not executable: give the user the chmod command from the verdict.",
                "a Relate command failed: the verdict ends with the last lines of relate.log; report them to the user.",
                "few sites kept after polarising (WARN): the ancestral genome may not match GRCh38; mention it in the report.",
                "worker stopped (FAIL after RUNNING): the machine may have run out of memory; lower THREADS or MEMORY_GB in repo/config.env and run again.",
                f"with ARG_METHOD=singer, SINGER not found: install SINGER and {ASK.replace('set it', 'set SINGER_DIR')}."],
         notes=["With Relate this skill always gives one WARN that TRACE finds far fewer segments with Relate than with SINGER (under 10% versus about 50% in the paper's simulations). That is expected; mention it in the report.",
                "A WARN that population-size recalibration failed means the trees use a constant population size; the run can continue."]),
    dict(name="11-run-trace", bg=True,
         desc="run TRACE at t=15,000 generations to find archaic segments in the user's haplotypes",
         what="Run TRACE (t = 15,000 generations) on the user's two haplotypes and keep archaic segments longer than 50 kb and 0.05 cM.",
         time="Several hours, depending on TRACE speed and the number of windows.",
         outputs=["results/11-run-trace.json", "work/trace/t15000/segments.filtered.tsv"],
         fixes=[f"TRACE_CMD_TEMPLATE is empty: {ASK.replace('set it', 'set TRACE_CMD_TEMPLATE')} (see 09-fetch-trace).",
                "cannot find start/end columns: TRACE output has an unexpected layout. Show the user the first lines of one file in work/trace/t15000/, and ask them to set TRACE_OUTPUT_COLUMNS (and TRACE_STATE_COLUMN if needed) in repo/config.env.",
                "TRACE did not write the output file: the template must write to `{out}`; tell the user."]),
    dict(name="12-fetch-archaic", bg=True,
         desc="build tables of ancestral, Neanderthal and Denisovan alleles at the cohort sites",
         what="Download the Neanderthal and Denisovan genomes and ancestral alleles, and record their alleles at every cohort SNP site.",
         time="About 30-90 minutes per chromosome, mostly downloads.",
         outputs=["results/12-fetch-archaic.json", "work/archaic/<chrom>.archaic.tsv"],
         fixes=["CrossMap not found: tell the user to run `pip install -r requirements.txt`.",
                f"an archaic genome URL failed: {ASK.replace('set it', 'check the ARCHAIC_URL_* entries')}.",
                "no ancestral FASTA: ask the user to check ANCESTRAL_URL in repo/config.env."]),
    dict(name="13-label-segments", bg=True,
         desc="label archaic segments as Neanderthal, Denisovan or Ghost",
         what="Label each archaic segment as Neanderthal, Denisovan or Ghost from how many of its derived alleles it shares with the sequenced archaic genomes.",
         time="This skill finishes in a few minutes.",
         outputs=["results/13-label-segments.json (`metrics.by_label` has segment counts and genome shares)",
                  "work/labels/segments.labeled.tsv"],
         fixes=["archaic table missing: run 12-fetch-archaic first.",
                "no segments: 11-run-trace kept nothing; report that and stop."],
         notes=["This skill always gives a WARN that the labelling rule is simplified; mention it in the report."]),
    dict(name="14-super-archaic", bg=True,
         desc="screen the user's Denisovan segments for super-archaic pieces",
         what="Run TRACE again with t = 31,500 generations inside the user's Denisovan segments to find candidate super-archaic pieces.",
         time="Minutes to hours. Reports SKIPPED at once when the genome has no Denisovan segments, which is common outside Oceania and Asia.",
         outputs=["results/14-super-archaic.json", "work/labels/super_archaic_candidates.tsv"],
         fixes=["TRACE errors: same fixes as 11-run-trace."]),
    dict(name="15-annotate-genes", bg=True,
         desc="list genes inside the archaic segments and compare with the published tracts",
         what="List the genes inside the user's archaic segments, flag genes named in the paper, and compare ghost segments with the published tracts.",
         time="This skill finishes in a few minutes.",
         outputs=["results/15-annotate-genes.json (`metrics.paper_genes_in_user_segments`)",
                  "work/annotation/segment_genes.tsv"],
         fixes=["GENCODE download failed: run again; if it keeps failing ask the user to check GENCODE_URL in repo/config.env."]),
    dict(name="16-report",
         desc="write the final report from all skill results",
         what="Collect the results of all skills into one readable report.",
         time="This skill finishes in seconds.",
         outputs=["results/report.md, also returned in full as `report` in the tool result", "results/16-report.json"],
         fixes=["13-label-segments has not run: run the skills in order up to 13 first."],
         notes=["After this skill, give the user the text in `report` from the tool result. Do not add claims that are not in it."]),
]


def skill_md(s, nxt):
    n = s["name"]
    bg = s.get("bg")
    lines = ["---", f"name: {n}", f"description: {s['desc']}", "---", "",
             f"#  {n} Skill", "", f"SKILL {n[:2]} — {s['what']}", "", "Expected workflow:", ""]
    lines.append(f"1. Call `run_skill_script` with `skill_name` set to `{n}` and `file_path` set "
                 f"to `scripts/{n}.py`. Pass no other arguments. The tool result's `stdout` is a "
                 f"JSON object (the same content is saved in `results/{n}.json`).")
    states = "OK, WARN, FAIL, SKIPPED or RUNNING" if bg else "OK, WARN, FAIL or SKIPPED"
    lines.append(f"2. Read that JSON. `status` is {states}; `verdict` is the one-line finding; "
                 "`metrics` holds the numbers; `warnings` lists anything to mention in the report. "
                 "On a failed command the verdict ends with the last lines of the log.")
    if bg:
        lines.append("3. RUNNING means the work continues in the background. Wait (at least 30 "
                     "minutes), then call this skill again the same way to check progress. Never "
                     "start the next skill while this one is RUNNING.")
        lines.append("4. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On "
                     "FAIL, apply the fix below and run this skill again.")
    else:
        lines.append("3. Only continue to the next skill when `status` is OK, WARN or SKIPPED. On "
                     "FAIL, apply the fix below and run this skill again.")
    lines += ["", "General expectations:", "",
              "The script finds the repo folder (next to .agent/skills in your working "
              "directory) by itself; all paths below are relative to repo/.", "",
              s["time"] + (" The tool call itself returns within seconds." if bg else ""), ""]
    for note in s.get("notes", []):
        lines += [note, ""]
    lines += ["Outputs:", ""] + s["outputs"] + [""]
    fixes = s["fixes"] + ["cannot find the repo folder: ask the user to start the agent from the "
                          "working directory that contains .agent/skills/ and repo/."]
    if n == "00-check-env":
        fixes = s["fixes"]
    lines += ["If it fails:", ""] + [f"- {f}" for f in fixes] + [""]
    lines += [f"Next skill: {nxt}" if nxt else "This is the last skill.", ""]
    return "\n".join(lines)


NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")  # ADK skill-name rule


def main():
    for i, s in enumerate(SKILLS):
        n = s["name"]
        if not NAME_RE.match(n) or len(n) > 64:
            raise SystemExit(f"invalid ADK skill name {n!r}")
        if not 0 < len(s["desc"]) <= 1024:
            raise SystemExit(f"description of {n} must be 1-1024 characters")
        d = SKILLS_ROOT / n
        (d / "scripts").mkdir(parents=True, exist_ok=True)
        nxt = SKILLS[i + 1]["name"] if i + 1 < len(SKILLS) else None
        (d / "SKILL.md").write_text(skill_md(s, nxt))
        shutil.copy2(LIB, d / "scripts" / "pipeline_common.py")
        script = d / "scripts" / f"{n}.py"
        if not script.exists():
            raise SystemExit(f"missing script {script}")
        script.chmod(0o755)
    print(f"wrote {len(SKILLS)} skills")


if __name__ == "__main__":
    main()
