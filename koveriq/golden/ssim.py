"""Structural similarity (SSIM) of two frames, for the goldens (spec §13.5).

Wang et al. (2004) on 8-bit luma with an 8x8 uniform window moved 4 px at a
time, C1 = (0.01*255)^2 and C2 = (0.03*255)^2; the score is the mean of the
local SSIM map. numpy and Pillow only (both in requirements.txt), no
scikit-image.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

WINDOW = 8
STRIDE = 4
C1 = (0.01 * 255) ** 2
C2 = (0.03 * 255) ** 2


def luma(path: Path, scale: float = 1.0) -> np.ndarray:
    """The frame's luma as float64, optionally resized (Lanczos) by ``scale``."""
    with Image.open(path) as image:
        gray = image.convert("L")
        if scale != 1.0:
            size = (max(1, round(gray.width * scale)), max(1, round(gray.height * scale)))
            gray = gray.resize(size, Image.Resampling.LANCZOS)
        return np.asarray(gray, dtype=np.float64)


def ssim(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        raise ValueError(f"frames differ in size: {a.shape} vs {b.shape}")
    if min(a.shape) < WINDOW:
        raise ValueError(f"frames must be at least {WINDOW} px on each side")
    view_a = np.lib.stride_tricks.sliding_window_view(a, (WINDOW, WINDOW))[::STRIDE, ::STRIDE]
    view_b = np.lib.stride_tricks.sliding_window_view(b, (WINDOW, WINDOW))[::STRIDE, ::STRIDE]
    mean_a = view_a.mean(axis=(-2, -1))
    mean_b = view_b.mean(axis=(-2, -1))
    var_a = view_a.var(axis=(-2, -1))
    var_b = view_b.var(axis=(-2, -1))
    cov = (view_a * view_b).mean(axis=(-2, -1)) - mean_a * mean_b
    numerator = (2 * mean_a * mean_b + C1) * (2 * cov + C2)
    denominator = (mean_a**2 + mean_b**2 + C1) * (var_a + var_b + C2)
    return float((numerator / denominator).mean())
