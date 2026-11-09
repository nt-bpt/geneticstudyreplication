# trio-pipeline

Folder layout (the *process folder* is this one):

    config.env  AGENT.md  README.md
    .agent/skills/<name>/{SKILL.md,<name>.sh}    skills, executed from the process folder
    workspace/{lib,py,resources,run_all.sh}       the agent's world; outputs (data, results, logs ...) are written here too

From a shell, in the process folder:

    bash workspace/run_all.sh                       # everything
    BASELINE_CHROMS="2 4" bash workspace/run_all.sh # adds a baseline
    MANUAL_DIR=/path/to/downloads bash workspace/run_all.sh
    CHROM=3 bash .agent/skills/03_npa_scan/03_npa_scan.sh

Needs: bcftools, tabix, bgzip, curl, python3 with numpy and cyvcf2. See AGENT.md.
