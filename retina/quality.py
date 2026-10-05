"""Image-quality pre-check (runs before the CNN).

Around a quarter of field fundus photos are blurred or badly exposed. Grading
such an image is unreliable, so the app warns the health worker and asks for a
retake instead of silently producing a grade.

Simple, explainable measurements are used:
  * sharpness  – variance of the Laplacian of the green channel (low = blurred)
  * brightness – mean intensity inside the retina (too dark / over-exposed)
  * contrast   – std-dev of intensity inside the retina
  * coverage   – fraction of the frame that is retina (tiny = bad framing)
"""
from __future__ import annotations

import cv2
import numpy as np

# Thresholds chosen from the APTOS distribution (≈ bottom 2-3 % of images);
# they are deliberately lenient – this is a warning, not a hard rejection.
MIN_SHARPNESS = 6.0
MIN_BRIGHTNESS, MAX_BRIGHTNESS = 25.0, 200.0
MIN_CONTRAST = 7.0
MIN_COVERAGE = 0.30


def assess(display_img: np.ndarray) -> dict:
    """display_img: cropped, square, masked RGB image from preprocessing."""
    green = display_img[..., 1].astype(np.float32)
    gray = cv2.cvtColor(display_img, cv2.COLOR_RGB2GRAY)
    retina = gray > 10
    coverage = float(retina.mean())
    pix = gray[retina] if retina.any() else gray.ravel()

    # Laplacian variance measured on a fixed 512 px scale, inside the retina only
    g = cv2.resize(green, (512, 512))
    m = cv2.resize(retina.astype(np.uint8), (512, 512)) > 0
    m = cv2.erode(m.astype(np.uint8), np.ones((15, 15), np.uint8)) > 0
    lap = cv2.Laplacian(g, cv2.CV_32F)
    sharpness = float(lap[m].var()) if m.any() else 0.0

    brightness = float(pix.mean())
    contrast = float(pix.std())

    issues = []
    if sharpness < MIN_SHARPNESS:
        issues.append("blurred")
    if brightness < MIN_BRIGHTNESS:
        issues.append("too_dark")
    if brightness > MAX_BRIGHTNESS:
        issues.append("over_exposed")
    if contrast < MIN_CONTRAST:
        issues.append("low_contrast")
    if coverage < MIN_COVERAGE:
        issues.append("retina_not_centered")

    return {
        "ok": not issues,
        "issues": issues,
        "sharpness": round(sharpness, 2),
        "brightness": round(brightness, 2),
        "contrast": round(contrast, 2),
        "coverage": round(coverage, 3),
    }
