"""Fundus-image preprocessing.

Pipeline (same at training time and inside the web app):

    raw photo
      -> crop_to_retina     (data cleaning: remove the black camera border)
      -> resize to square   (data transformation)
      -> enhance            (Ben Graham local-contrast filter  OR  CLAHE)
      -> circular mask      (removes the bright ring the filter creates at the edge)
      -> [in dataset.py] standardise with ImageNet mean/std (feature scaling)

Why Ben Graham? It subtracts a heavy Gaussian blur from the image, i.e. it
removes slow illumination changes and keeps local detail – exactly where
micro-aneurysms, haemorrhages and exudates live. It was the trick used by the
winner of the 2015 Kaggle DR competition.
"""
from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from .config import CACHE_SIZE


def read_rgb(path_or_bytes) -> np.ndarray:
    """Read an image file (path or raw bytes) as an RGB uint8 array."""
    if isinstance(path_or_bytes, (str, Path)):
        bgr = cv2.imread(str(path_or_bytes), cv2.IMREAD_COLOR)
    else:
        buf = np.frombuffer(path_or_bytes, dtype=np.uint8)
        bgr = cv2.imdecode(buf, cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError("Could not decode image")
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def crop_to_retina(img: np.ndarray, tol: int = 7) -> np.ndarray:
    """Crop away the dark background around the circular retina."""
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    mask = gray > tol
    if mask.sum() < 0.01 * mask.size:      # almost black image: nothing to crop
        return img
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    return img[rows[0]: rows[-1] + 1, cols[0]: cols[-1] + 1]


def pad_to_square(img: np.ndarray) -> np.ndarray:
    """Pad with black so the aspect ratio is kept (retina stays circular)."""
    h, w = img.shape[:2]
    s = max(h, w)
    out = np.zeros((s, s, 3), dtype=img.dtype)
    y0, x0 = (s - h) // 2, (s - w) // 2
    out[y0: y0 + h, x0: x0 + w] = img
    return out


def circular_mask(img: np.ndarray, scale: float = 0.96) -> np.ndarray:
    h, w = img.shape[:2]
    mask = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(mask, (w // 2, h // 2), int(min(h, w) / 2 * scale), 1, -1)
    return img * mask[..., None]


def retina_mask(img: np.ndarray, tol: int = 7) -> np.ndarray:
    """Binary mask of real retina pixels (excludes black border / padding)."""
    m = (cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) > tol).astype(np.uint8)
    k = max(3, img.shape[0] // 100) | 1
    return cv2.erode(m, np.ones((k, k), np.uint8))


def ben_graham(img: np.ndarray, sigma_frac: float = 1 / 30, mask: np.ndarray | None = None) -> np.ndarray:
    """4*I - 4*GaussianBlur(I) + 128  (local contrast normalisation).

    The blur is *mask-normalised* (blur(I*M) / blur(M)), so black background
    pixels do not leak into the estimate near the edge – otherwise the filter
    paints a bright halo where the retina meets the border.
    """
    sigma = max(img.shape[:2]) * sigma_frac
    f = img.astype(np.float32)
    if mask is None:
        mask = retina_mask(img)
    m = mask.astype(np.float32)
    num = cv2.GaussianBlur(f * m[..., None], (0, 0), sigma)
    den = cv2.GaussianBlur(m, (0, 0), sigma)[..., None]
    blur = num / np.maximum(den, 1e-3)
    out = np.clip(4 * f - 4 * blur + 128, 0, 255).astype(np.uint8)
    return out * mask[..., None]


def clahe(img: np.ndarray, clip: float = 2.0, grid: int = 8) -> np.ndarray:
    """Contrast Limited Adaptive Histogram Equalisation on the L channel."""
    lab = cv2.cvtColor(img, cv2.COLOR_RGB2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid)).apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)


def preprocess(img: np.ndarray, size: int = CACHE_SIZE, method: str = "ben"):
    """Return (display_image, model_image), both RGB uint8 of shape size x size.

    display_image – cropped & resized original (what a health worker recognises)
    model_image   – contrast-enhanced version that the CNN is trained on
    """
    sq = pad_to_square(crop_to_retina(img))
    sq = cv2.resize(sq, (size, size), interpolation=cv2.INTER_AREA)
    mask = retina_mask(sq)
    display = circular_mask(sq * mask[..., None])
    if method == "ben":
        enhanced = ben_graham(sq, mask=mask)
    elif method == "clahe":
        enhanced = clahe(sq) * mask[..., None]
    elif method == "none":
        enhanced = sq * mask[..., None]
    else:
        raise ValueError(f"unknown method {method}")
    return display, circular_mask(enhanced)
