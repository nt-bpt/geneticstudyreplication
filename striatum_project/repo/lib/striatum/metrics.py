"""Caudate / putamen metrics computed from a SynthSeg (FreeSurfer-label) segmentation.

Nolan's caudate-putamen observation has never been published with a method,
so the "bridge zone" metrics below are an *operationalization* of the idea
(grey-matter-like tissue between the caudate head and putamen, i.e. across the
anterior limb of the internal capsule), not a reproduction of his analysis.
"""
from __future__ import annotations

import numpy as np
import nibabel as nib
from scipy import ndimage

# FreeSurfer / SynthSeg label IDs
LABELS = {
    "left_wm": 2, "right_wm": 41,
    "left_caudate": 11, "right_caudate": 50,
    "left_putamen": 12, "right_putamen": 51,
}
HEMIS = {
    "left": (LABELS["left_caudate"], LABELS["left_putamen"], LABELS["left_wm"]),
    "right": (LABELS["right_caudate"], LABELS["right_putamen"], LABELS["right_wm"]),
}


def _dist_mm(mask: np.ndarray, zooms) -> np.ndarray:
    """Euclidean distance (mm) from every voxel to the nearest voxel of mask."""
    return ndimage.distance_transform_edt(~mask, sampling=zooms)


def compute_metrics(seg_path: str, image_path: str, icv_mm3: float | None,
                    bridge_mm: float = 4.0) -> dict:
    """Return a flat dict of metrics.

    seg_path   : SynthSeg label volume
    image_path : the input image resampled to the segmentation grid
                 (SynthSeg --resample output), used for intensity metrics
    icv_mm3    : total intracranial volume, for normalisation (None to skip)
    bridge_mm  : a WM voxel belongs to the bridge zone if it lies within this
                 distance of BOTH the caudate and the putamen
    """
    seg_img = nib.load(seg_path)
    seg = np.asarray(seg_img.dataobj).astype(np.int32)
    img = np.asarray(nib.load(image_path).dataobj).astype(np.float32)
    if img.shape != seg.shape:
        raise ValueError(f"image {img.shape} and segmentation {seg.shape} grids differ; "
                         "pass the SynthSeg --resample output as the image")
    zooms = seg_img.header.get_zooms()[:3]
    vox_mm3 = float(np.prod(zooms))

    out: dict = {"voxel_mm3": vox_mm3, "bridge_mm": bridge_mm}
    if icv_mm3:
        out["icv_mm3"] = icv_mm3

    for hemi, (cau_l, put_l, wm_l) in HEMIS.items():
        cau, put, wm = seg == cau_l, seg == put_l, seg == wm_l
        for name, m in (("caudate", cau), ("putamen", put)):
            v = m.sum() * vox_mm3
            out[f"{hemi}_{name}_mm3"] = v
            if icv_mm3:
                out[f"{hemi}_{name}_icv_pct"] = 100.0 * v / icv_mm3

        bridge = wm & (_dist_mm(cau, zooms) <= bridge_mm) & (_dist_mm(put, zooms) <= bridge_mm)
        out[f"{hemi}_bridge_mm3"] = bridge.sum() * vox_mm3

        # Intensity: where does bridge tissue sit between pure WM and striatum?
        # 0 = looks like white matter, 1 = looks like caudate/putamen grey matter.
        # Uses deep WM (eroded) as the reference so partial volume doesn't bias it.
        deep_wm = ndimage.binary_erosion(wm, iterations=2) & ~bridge
        striatum = ndimage.binary_erosion(cau | put, iterations=1)
        if bridge.sum() >= 10 and deep_wm.sum() >= 100 and striatum.sum() >= 50:
            wm_med = float(np.median(img[deep_wm]))
            st_med = float(np.median(img[striatum]))
            br_med = float(np.median(img[bridge]))
            contrast = wm_med - st_med
            out[f"{hemi}_bridge_gm_index"] = (wm_med - br_med) / contrast if abs(contrast) > 1e-6 else np.nan
            out[f"{hemi}_wm_striatum_contrast"] = contrast / (abs(wm_med) + 1e-6)
        else:
            out[f"{hemi}_bridge_gm_index"] = np.nan
            out[f"{hemi}_wm_striatum_contrast"] = np.nan

    # asymmetry index, (L-R)/mean, in percent
    for name in ("caudate", "putamen", "bridge"):
        l, r = out[f"left_{name}_mm3"], out[f"right_{name}_mm3"]
        out[f"{name}_asymmetry_pct"] = 100.0 * (l - r) / ((l + r) / 2) if (l + r) else np.nan
    return out
