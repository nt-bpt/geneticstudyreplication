# Caudate-putamen pipeline: Ubuntu 24.04 + FreeSurfer 8.2.0 (SynthSeg) + dcm2niix + Python libs
#   docker build -t striatum -f repo/docker/Dockerfile repo/docker
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    FS_VERSION=8.2.0

COPY apt-packages.txt /tmp/apt-packages.txt

# System packages
RUN apt-get update \
 && grep -vE '^\s*(#|$)' /tmp/apt-packages.txt | xargs apt-get install -y --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*

# FreeSurfer: install the official .deb with apt (unpacking it is not a valid install).
# ~8 GB download; downloaded and removed in one layer to keep the image smaller.
RUN apt-get update \
 && wget -q -O /tmp/fs.deb \
      https://surfer.nmr.mgh.harvard.edu/pub/dist/freesurfer/${FS_VERSION}/freesurfer_ubuntu24-${FS_VERSION}_amd64.deb \
 && echo "9f04a1b93ce4789ab04f3dd68e26a2fe  /tmp/fs.deb" | md5sum -c - \
 && apt-get install -y /tmp/fs.deb \
 && rm -f /tmp/fs.deb \
 && rm -rf /var/lib/apt/lists/*

# FreeSurfer environment (equivalent of sourcing SetUpFreeSurfer.sh)
ENV FREESURFER_HOME=/usr/local/freesurfer/${FS_VERSION}
ENV SUBJECTS_DIR=/tmp/fs_subjects \
    FUNCTIONALS_DIR=/tmp/fs_sessions \
    MNI_DIR=${FREESURFER_HOME}/mni \
    FSFAST_HOME=${FREESURFER_HOME}/fsfast \
    FSF_OUTPUT_FORMAT=nii.gz \
    PATH=${FREESURFER_HOME}/bin:${FREESURFER_HOME}/fsfast/bin:${FREESURFER_HOME}/tktools:${FREESURFER_HOME}/mni/bin:${PATH}

# Fail the build early if the install path differs from what's assumed above
RUN test -x ${FREESURFER_HOME}/bin/mri_synthseg && which dcm2niix && python3 -c "import nibabel, scipy, numpy"

# Licence is mounted at run time:  -v /path/license.txt:/license.txt:ro -e FS_LICENSE=/license.txt
WORKDIR /project
CMD ["bash"]
