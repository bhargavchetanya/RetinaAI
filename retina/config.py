"""Central configuration: paths, class names and default hyper-parameters.

Everything (training scripts + web backend) imports from here so there is a
single source of truth.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw" / "aptos"
PROCESSED_DIR = DATA_DIR / "processed" / "aptos"
SPLITS_DIR = DATA_DIR / "splits"
MODELS_DIR = ROOT / "models"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

CHECKPOINT_PATH = MODELS_DIR / "dr_efficientnet_b0.pt"
LAST_STATE_PATH = MODELS_DIR / "last_state.pt"
ONNX_PATH = MODELS_DIR / "dr_efficientnet_b0.onnx"
EMBEDDINGS_PATH = MODELS_DIR / "train_embeddings.npz"
METRICS_PATH = REPORTS_DIR / "metrics.json"
HISTORY_PATH = REPORTS_DIR / "training_history.json"
BASELINES_PATH = REPORTS_DIR / "baselines.json"
CLUSTERING_PATH = REPORTS_DIR / "clustering.json"
DATA_SUMMARY_PATH = REPORTS_DIR / "data_summary.json"

NUM_CLASSES = 5
CLASS_NAMES = ["No DR", "Mild", "Moderate", "Severe", "Proliferative DR"]
CLASS_NAMES_HI = ["कोई DR नहीं", "हल्का", "मध्यम", "गंभीर", "प्रोलिफ़रेटिव DR"]

# Clinical convention: grade >= 2 (moderate NPDR or worse) is "referable DR".
REFERABLE_GRADE = 2

# ImageNet statistics – the backbone was pre-trained with these, so inputs are
# standardised (z-score) with the same mean / std.
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

# Size images are cached at after preprocessing (crop + enhance).
CACHE_SIZE = 512


def get_device():
    """Apple-Silicon GPU (MPS) > CUDA > CPU."""
    import torch

    if os.environ.get("RETINA_DEVICE"):
        return torch.device(os.environ["RETINA_DEVICE"])
    if torch.backends.mps.is_available():
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


@dataclass
class TrainConfig:
    image_size: int = 320
    batch_size: int = 16
    epochs: int = 15
    lr: float = 3e-4               # peak learning rate (AdamW)
    weight_decay: float = 1e-4     # L2-style regularisation
    dropout: float = 0.3
    label_smoothing: float = 0.05
    warmup_epochs: int = 1
    freeze_epochs: int = 1         # train only the head first (transfer learning)
    patience: int = 5              # early stopping on validation QWK
    num_workers: int = 2
    seed: int = 42
    pretrained: bool = True
    limit: int | None = None       # use only N images (smoke tests)
    resume: bool = False           # continue from models/last_state.pt
    watchdog_minutes: int = 15     # abort (exit code 3) if no progress for this long
    extra: dict = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)
