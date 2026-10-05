from __future__ import annotations

import json
import random

import cv2
import numpy as np


def seed_everything(seed: int = 42):
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)


def save_json(obj, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


def load_json(path, default=None):
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fingerprint(enhanced_rgb: np.ndarray) -> np.ndarray:
    """Image fingerprint for duplicate detection.

    Green channel of the contrast-enhanced image (vessel pattern = unique to
    each eye, like a fingerprint) -> 128x128 -> keep the inner 80x80 (the
    circular rim is identical for every photo and would fool the comparison)
    -> z-score. The dot product / N of two fingerprints is their Pearson
    correlation: ~1.0 for the same photo, < 0.4 for different eyes.

    (A classic DCT perceptual hash was tried first, but all fundus photos look
    alike at low frequencies, so it produced many false duplicates.)
    """
    g = cv2.resize(enhanced_rgb[..., 1], (128, 128), interpolation=cv2.INTER_AREA).astype(np.float32)
    g = g[24:104, 24:104].ravel()
    return ((g - g.mean()) / (g.std() + 1e-6)).astype(np.float16)
