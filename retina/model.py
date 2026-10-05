"""EfficientNet-B0 classifier (transfer learning).

Why EfficientNet-B0?
  * ~4 M parameters (5.3 M with the 1000-class ImageNet head) – trains on a laptop GPU (Apple MPS) in under an hour
    and runs on a CPU at a rural health centre in well under a second.
  * Compound scaling (depth/width/resolution balanced) gives better accuracy
    per FLOP than ResNet-50 (25 M params) on ImageNet and on fundus images.
  * Built from MBConv blocks: depthwise-separable convolutions + Batch
    Normalisation + SiLU (Swish) activation + Squeeze-and-Excitation.

Transfer learning: the ImageNet-pre-trained feature extractor is reused and
only the classification head is replaced (1280 -> 5 DR grades). For the first
epoch the backbone is frozen so the random head does not destroy the
pre-trained features; afterwards the whole network is fine-tuned.
"""
from __future__ import annotations

import torch
import torch.nn as nn
from torchvision.models import EfficientNet_B0_Weights, efficientnet_b0

from .config import NUM_CLASSES


class DRNet(nn.Module):
    def __init__(self, num_classes: int = NUM_CLASSES, dropout: float = 0.3, pretrained: bool = True):
        super().__init__()
        weights = EfficientNet_B0_Weights.IMAGENET1K_V1 if pretrained else None
        net = efficientnet_b0(weights=weights)
        self.features = net.features          # conv stem + 16 MBConv blocks + 1x1 conv head
        self.pool = nn.AdaptiveAvgPool2d(1)
        in_f = net.classifier[1].in_features  # 1280
        self.head = nn.Sequential(nn.Dropout(dropout), nn.Linear(in_f, num_classes))

    # Last convolutional block – the layer Grad-CAM explains.
    @property
    def target_layer(self) -> nn.Module:
        return self.features[-1]

    def embed(self, x: torch.Tensor) -> torch.Tensor:
        """1280-d image embedding (used by the classical ML baselines, PCA,
        DBSCAN and the K-NN out-of-distribution check)."""
        return torch.flatten(self.pool(self.features(x)), 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self.embed(x))

    def set_backbone_trainable(self, trainable: bool):
        for p in self.features.parameters():
            p.requires_grad = trainable


def load_checkpoint(path, device="cpu"):
    ckpt = torch.load(path, map_location=device, weights_only=False)
    cfg = ckpt.get("config", {})
    model = DRNet(dropout=cfg.get("dropout", 0.3), pretrained=False)
    model.load_state_dict(ckpt["state_dict"])
    model.to(device).eval()
    return model, ckpt
