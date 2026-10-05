"""Grad-CAM and Grad-CAM++ implemented from scratch with PyTorch hooks.

Grad-CAM (Selvaraju et al., 2017)
    A^k   = feature maps of the last conv layer  (K maps of size h x w)
    y^c   = score (logit) of class c
    w_k   = mean over (i,j) of  dy^c / dA^k_ij          (global-average gradient)
    L^c   = ReLU( sum_k w_k A^k )                       (class activation map)

Grad-CAM++ (Chattopadhay et al., 2018) replaces the plain mean with
pixel-wise weights alpha so that *several* small lesions of the same class all
light up (plain Grad-CAM tends to highlight only the strongest one – a real
issue for scattered micro-aneurysms):
    alpha^kc_ij = g^2 / (2 g^2 + sum_ab A^k_ab * g^3)
    w_k         = sum_ij alpha^kc_ij * ReLU(g_ij)
where g = dy^c/dA (using the exponential-score trick, higher derivatives
reduce to powers of g).
"""
from __future__ import annotations

import cv2
import numpy as np
import torch
import torch.nn.functional as F


class GradCAM:
    def __init__(self, model: torch.nn.Module, target_layer: torch.nn.Module):
        self.model = model
        self.activations = None
        self.gradients = None
        self._h = target_layer.register_forward_hook(self._forward_hook)

    def _forward_hook(self, module, inp, out):
        self.activations = out
        if out.requires_grad:
            out.register_hook(self._save_grad)

    def _save_grad(self, grad):
        self.gradients = grad

    def remove(self):
        self._h.remove()

    def __call__(self, x: torch.Tensor, class_idx: int | None = None, plus_plus: bool = True):
        """x: (1,3,H,W) tensor. Returns (cam HxW float in [0,1], logits)."""
        self.model.zero_grad(set_to_none=True)
        with torch.enable_grad():
            x = x.clone().requires_grad_(True)
            logits = self.model(x)
            if class_idx is None:
                class_idx = int(logits.argmax(1))
            logits[0, class_idx].backward()

        A = self.activations.detach()[0]   # K x h x w
        g = self.gradients.detach()[0]     # K x h x w

        if plus_plus:
            g2, g3 = g.pow(2), g.pow(3)
            denom = 2 * g2 + A.sum(dim=(1, 2), keepdim=True) * g3
            alpha = g2 / torch.where(denom != 0, denom, torch.ones_like(denom))
            weights = (alpha * F.relu(g)).sum(dim=(1, 2))
        else:
            weights = g.mean(dim=(1, 2))

        cam = F.relu((weights[:, None, None] * A).sum(0))
        cam = F.interpolate(cam[None, None], size=x.shape[-2:], mode="bilinear", align_corners=False)[0, 0]
        cam = cam.cpu().numpy()
        cam -= cam.min()
        if cam.max() > 0:
            cam /= cam.max()
        return cam, logits.detach()


def overlay(rgb: np.ndarray, cam: np.ndarray, alpha: float = 0.45) -> np.ndarray:
    """Blend a [0,1] heat-map (resized to rgb) onto an RGB uint8 image."""
    cam = cv2.resize(cam, (rgb.shape[1], rgb.shape[0]))
    heat = cv2.applyColorMap(np.uint8(255 * cam), cv2.COLORMAP_JET)
    heat = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB)
    retina = (rgb.max(axis=2) > 10)[..., None]
    out = (rgb * (1 - alpha) + heat * alpha).astype(np.uint8)
    return np.where(retina, out, rgb)
