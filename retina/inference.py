"""Inference engine used by the web backend (and usable from a notebook).

predict(image_bytes) ->
    quality check -> preprocess -> CNN (+ test-time augmentation)
    -> temperature-scaled probabilities -> referral decision
    -> K-NN out-of-distribution check on the embedding
    -> Grad-CAM++ heat-map -> explanation text
"""
from __future__ import annotations

import base64
import time

import cv2
import numpy as np
import torch
from PIL import Image

from . import quality as quality_mod
from .calibration import softmax_np
from .config import CHECKPOINT_PATH, CLASS_NAMES, CLASS_NAMES_HI, EMBEDDINGS_PATH, REFERABLE_GRADE, get_device
from .dataset import eval_transforms
from .explain import explain
from .gradcam import GradCAM, overlay
from .model import load_checkpoint
from .preprocessing import preprocess, read_rgb


def to_b64_png(rgb: np.ndarray, max_side: int = 512) -> str:
    h, w = rgb.shape[:2]
    if max(h, w) > max_side:
        s = max_side / max(h, w)
        rgb = cv2.resize(rgb, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
    return "data:image/png;base64," + base64.b64encode(buf).decode()


class DRPredictor:
    def __init__(self, checkpoint=CHECKPOINT_PATH, device=None):
        self.device = device or get_device()
        self.model, ckpt = load_checkpoint(checkpoint, self.device)
        cfg = ckpt.get("config", {})
        self.image_size = cfg.get("image_size", 320)
        self.method = cfg.get("extra", {}).get("preprocess", "ben")
        self.temperature = float(ckpt.get("temperature", 1.0))
        self.threshold = float(ckpt.get("referral_threshold", 0.5))
        self.version = ckpt.get("version", "unknown")
        self.tf = eval_transforms(self.image_size)
        self.cam = GradCAM(self.model, self.model.target_layer)

        self.knn = None
        if EMBEDDINGS_PATH.exists():
            from sklearn.neighbors import NearestNeighbors
            d = np.load(EMBEDDINGS_PATH)
            emb = d["embeddings"]
            self.emb_norm = emb / np.linalg.norm(emb, axis=1, keepdims=True)
            self.knn = NearestNeighbors(n_neighbors=5, metric="cosine").fit(self.emb_norm)
            self.ood_threshold = float(d["ood_threshold"])

    def _tensor(self, rgb):
        return self.tf(Image.fromarray(rgb)).unsqueeze(0).to(self.device)

    @torch.no_grad()
    def _tta_logits(self, x):
        views = [x, torch.flip(x, dims=[3]), torch.flip(x, dims=[2])]
        return torch.stack([self.model(v) for v in views]).mean(0)

    def predict(self, image_bytes: bytes) -> dict:
        t0 = time.time()
        raw = read_rgb(image_bytes)
        display, model_img = preprocess(raw, method=self.method)
        q = quality_mod.assess(display)

        x = self._tensor(model_img)
        logits = self._tta_logits(x).cpu().numpy()
        probs = softmax_np(logits, self.temperature)[0]
        grade = int(probs.argmax())
        conf = float(probs[grade])
        p_ref = float(probs[REFERABLE_GRADE:].sum())
        refer = p_ref >= self.threshold

        ood = {"checked": False}
        if self.knn is not None:
            with torch.no_grad():
                e = self.model.embed(x).cpu().numpy()
            e = e / np.linalg.norm(e, axis=1, keepdims=True)
            dist = float(self.knn.kneighbors(e)[0].mean())
            ood = {"checked": True, "distance": round(dist, 4),
                   "threshold": round(self.ood_threshold, 4),
                   "is_fundus_like": dist <= self.ood_threshold}

        cam, _ = self.cam(x, class_idx=grade, plus_plus=True)
        heat = overlay(display, cv2.resize(cam, display.shape[:2][::-1]))
        expl = explain(cam, display, grade, conf, refer, quality_ok=q["ok"])

        warnings = []
        if not q["ok"]:
            warnings.append("quality")
        if ood.get("checked") and not ood["is_fundus_like"]:
            warnings.append("out_of_distribution")

        return {
            "grade": grade,
            "grade_name": CLASS_NAMES[grade],
            "grade_name_hi": CLASS_NAMES_HI[grade],
            "confidence": round(conf, 4),
            "probabilities": [{"grade": i, "name": CLASS_NAMES[i], "name_hi": CLASS_NAMES_HI[i],
                               "p": round(float(p), 4)} for i, p in enumerate(probs)],
            "p_referable": round(p_ref, 4),
            "referral_threshold": round(self.threshold, 3),
            "refer": bool(refer),
            "quality": q,
            "ood": ood,
            "warnings": warnings,
            "explanation": expl,
            "images": {
                "original": to_b64_png(display),
                "enhanced": to_b64_png(model_img),
                "heatmap": to_b64_png(heat),
            },
            "model_version": self.version,
            "temperature": round(self.temperature, 3),
            "inference_ms": int((time.time() - t0) * 1000),
        }
