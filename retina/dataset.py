"""PyTorch Dataset + augmentation pipelines."""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms as T

from .config import IMAGENET_MEAN, IMAGENET_STD, NUM_CLASSES, PROCESSED_DIR, SPLITS_DIR


def train_transforms(size: int):
    """Data augmentation = cheap regularisation.

    A retina has no 'up', so full rotations and flips are label-preserving.
    Mild colour jitter simulates different cameras / exposure.
    """
    return T.Compose([
        T.RandomResizedCrop(size, scale=(0.85, 1.0), ratio=(0.95, 1.05)),
        T.RandomHorizontalFlip(),
        T.RandomVerticalFlip(),
        T.RandomRotation(180),
        T.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.1),
        T.ToTensor(),
        T.Normalize(IMAGENET_MEAN, IMAGENET_STD),  # standardisation (z-score)
    ])


def eval_transforms(size: int):
    return T.Compose([
        T.Resize((size, size)),
        T.ToTensor(),
        T.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def load_split(name: str) -> pd.DataFrame:
    return pd.read_csv(SPLITS_DIR / f"{name}.csv")


class FundusDataset(Dataset):
    def __init__(self, df: pd.DataFrame, transform, image_dir=PROCESSED_DIR):
        self.ids = df["id_code"].tolist()
        self.labels = df["diagnosis"].astype(int).tolist()
        self.transform = transform
        self.image_dir = image_dir

    def __len__(self):
        return len(self.ids)

    def __getitem__(self, i):
        img = Image.open(self.image_dir / f"{self.ids[i]}.png").convert("RGB")
        return self.transform(img), self.labels[i]


def class_weights(labels, power: float = 0.5) -> torch.Tensor:
    """Inverse-frequency class weights, softened by `power` (0.5 = sqrt).

    APTOS is ~49 % 'No DR' and only ~5 % 'Severe'. Without weighting the
    network learns to over-predict the majority class.
    """
    counts = np.bincount(np.asarray(labels), minlength=NUM_CLASSES).astype(np.float64)
    w = (counts.sum() / np.maximum(counts, 1)) ** power
    w = w / w.mean()
    return torch.tensor(w, dtype=torch.float32)
