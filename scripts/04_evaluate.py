"""Step 4 – Evaluate on the held-out TEST set + export embeddings.

  * Test-time augmentation (TTA): average logits of original + h-flip + v-flip.
  * Metrics before/after temperature scaling (accuracy, QWK, macro-F1, ECE,
    per-class sensitivity/specificity/precision, referable-DR ROC-AUC).
  * Figures: confusion matrix, training curves, ROC, reliability diagram,
    Grad-CAM++ gallery.
  * Saves 1280-d CNN embeddings for train/val/test (used by 05_baselines.py
    and by the K-NN out-of-distribution check in the web app).

Usage:  python scripts/04_evaluate.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from PIL import Image  # noqa: E402
from sklearn.metrics import roc_curve  # noqa: E402
from sklearn.neighbors import NearestNeighbors  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402
from tqdm import tqdm  # noqa: E402

from retina.calibration import softmax_np  # noqa: E402
from retina.config import (CHECKPOINT_PATH, CLASS_NAMES, EMBEDDINGS_PATH, FIGURES_DIR, HISTORY_PATH,  # noqa: E402
                           METRICS_PATH, MODELS_DIR, PROCESSED_DIR, REFERABLE_GRADE, get_device)
from retina.dataset import FundusDataset, eval_transforms, load_split  # noqa: E402
from retina.gradcam import GradCAM, overlay  # noqa: E402
from retina.metrics import full_report  # noqa: E402
from retina.model import load_checkpoint  # noqa: E402
from retina.utils import load_json, save_json  # noqa: E402


@torch.no_grad()
def run(model, loader, device, tta=True):
    model.eval()
    L, E, Y = [], [], []
    for x, y in tqdm(loader, leave=False):
        x = x.to(device)
        emb = model.embed(x)
        logits = model.head(emb)
        if tta:
            logits = (logits + model(torch.flip(x, dims=[3])) + model(torch.flip(x, dims=[2]))) / 3
        L.append(logits.float().cpu()); E.append(emb.float().cpu()); Y.append(y)
    return torch.cat(L).numpy(), torch.cat(E).numpy(), torch.cat(Y).numpy()


def reliability(probs, y, bins=10):
    conf, correct = probs.max(1), probs.argmax(1) == y
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        out.append({"bin": round((lo + hi) / 2, 2), "count": int(m.sum()),
                    "accuracy": round(float(correct[m].mean()), 4) if m.any() else None,
                    "confidence": round(float(conf[m].mean()), 4) if m.any() else None})
    return out


def plot_confusion(cm, path):
    cm = np.array(cm)
    norm = cm / np.maximum(cm.sum(1, keepdims=True), 1)
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
    for i in range(len(cm)):
        for j in range(len(cm)):
            ax.text(j, i, cm[i, j], ha="center", va="center", color="white" if norm[i, j] > 0.5 else "black")
    ax.set_xticks(range(5), CLASS_NAMES, rotation=30, ha="right"); ax.set_yticks(range(5), CLASS_NAMES)
    ax.set_xlabel("Predicted"); ax.set_ylabel("True"); ax.set_title("Test confusion matrix")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def plot_history(hist, path):
    h = hist["history"]
    ep = [r["epoch"] for r in h]
    fig, ax = plt.subplots(1, 2, figsize=(10, 4))
    ax[0].plot(ep, [r["train_loss"] for r in h], label="train"); ax[0].plot(ep, [r["val_loss"] for r in h], label="val")
    ax[0].set_title("Loss"); ax[0].legend(); ax[0].set_xlabel("epoch")
    ax[1].plot(ep, [r["val_acc"] for r in h], label="val accuracy"); ax[1].plot(ep, [r["val_qwk"] for r in h], label="val QWK")
    ax[1].set_title("Validation"); ax[1].legend(); ax[1].set_xlabel("epoch")
    fig.tight_layout(); fig.savefig(path, dpi=150); plt.close(fig)


def gradcam_gallery(model, device, size, test_df, path, per_class=2):
    cam = GradCAM(model, model.target_layer)
    tf = eval_transforms(size)
    rows = []
    for c in range(5):
        ids = test_df[test_df.diagnosis == c].id_code.head(per_class).tolist()
        rows += [(i, c) for i in ids]
    if not rows:
        return
    fig, axes = plt.subplots(len(rows), 2, figsize=(5, 2.5 * len(rows)))
    axes = np.atleast_2d(axes)
    for r, (id_code, c) in enumerate(rows):
        img = np.array(Image.open(PROCESSED_DIR / f"{id_code}.png").convert("RGB"))
        x = tf(Image.fromarray(img)).unsqueeze(0).to(device)
        heat, logits = cam(x)
        pred = int(logits.argmax(1))
        axes[r, 0].imshow(img); axes[r, 0].set_title(f"true: {CLASS_NAMES[c]}", fontsize=8)
        axes[r, 1].imshow(overlay(img, cv2.resize(heat, img.shape[:2][::-1])))
        axes[r, 1].set_title(f"pred: {CLASS_NAMES[pred]}", fontsize=8)
        for a in axes[r]:
            a.axis("off")
    cam.remove()
    fig.tight_layout(); fig.savefig(path, dpi=120); plt.close(fig)


def main():
    device = get_device()
    model, ckpt = load_checkpoint(CHECKPOINT_PATH, device)
    size = ckpt["config"]["image_size"]
    T = float(ckpt.get("temperature", 1.0))
    thr = float(ckpt.get("referral_threshold", 0.5))
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    splits = {s: load_split(s) for s in ("train", "val", "test")}
    lim = ckpt["config"].get("limit")
    if lim:
        splits = {"train": splits["train"].head(lim), "val": splits["val"].head(max(10, lim // 4)),
                  "test": splits["test"].head(max(10, lim // 4))}
    res = {}
    for s, df in splits.items():
        dl = DataLoader(FundusDataset(df, eval_transforms(size)), batch_size=32, num_workers=0)
        res[s] = run(model, dl, device, tta=(s == "test"))
        print(f"{s}: {len(df)} images")

    logits, emb, y = res["test"]
    raw_probs, probs = softmax_np(logits), softmax_np(logits, T)
    report = full_report(probs, y, thr)
    report_uncal = full_report(raw_probs, y, thr)
    p_ref = probs[:, REFERABLE_GRADE:].sum(1)
    yb = (y >= REFERABLE_GRADE).astype(int)
    roc = []
    if 0 < yb.sum() < len(yb):
        fpr, tpr, _ = roc_curve(yb, p_ref)
        idx = np.linspace(0, len(fpr) - 1, min(60, len(fpr))).astype(int)
        roc = [{"fpr": round(float(fpr[i]), 4), "tpr": round(float(tpr[i]), 4)} for i in idx]

    # ---- embeddings + K-NN out-of-distribution threshold ---------------------
    tr_e = res["train"][1] / np.linalg.norm(res["train"][1], axis=1, keepdims=True)
    va_e = res["val"][1] / np.linalg.norm(res["val"][1], axis=1, keepdims=True)
    nn_ = NearestNeighbors(n_neighbors=min(5, len(tr_e)), metric="cosine").fit(tr_e)
    d_val = nn_.kneighbors(va_e)[0].mean(1)
    ood_thr = float(np.percentile(d_val, 99) * 1.25)
    np.savez_compressed(EMBEDDINGS_PATH, embeddings=res["train"][1], labels=res["train"][2], ood_threshold=ood_thr)
    np.savez_compressed(MODELS_DIR / "all_embeddings.npz",
                        **{f"{s}_{k}": v for s in res for k, v in zip(("emb", "y"), res[s][1:])})

    hist = load_json(HISTORY_PATH, {"history": []})
    metrics = {
        "model": "EfficientNet-B0 (ImageNet transfer learning) + TTA + temperature scaling",
        "version": ckpt.get("version"),
        "image_size": size,
        "temperature": round(T, 4),
        "referral_threshold": round(thr, 3),
        "ood_threshold": round(ood_thr, 4),
        "test": report,
        "test_uncalibrated": {k: report_uncal[k] for k in ("accuracy", "qwk", "macro_f1", "ece")},
        "roc_referable": roc,
        "reliability": {"before": reliability(raw_probs, y), "after": reliability(probs, y)},
        "history": hist.get("history", []),
        "best_epoch": hist.get("best_epoch"),
        "params_millions": round(sum(p.numel() for p in model.parameters()) / 1e6, 2),
    }
    save_json(metrics, METRICS_PATH)

    plot_confusion(report["confusion_matrix"], FIGURES_DIR / "confusion_matrix.png")
    if hist.get("history"):
        plot_history(hist, FIGURES_DIR / "training_curves.png")
    gradcam_gallery(model, device, size, splits["test"], FIGURES_DIR / "gradcam_gallery.png")

    print(f"\nTEST  acc={report['accuracy']}  QWK={report['qwk']}  macroF1={report['macro_f1']}  "
          f"ECE {report_uncal['ece']} -> {report['ece']}")
    print("referable DR:", report["referable"])
    print("saved", METRICS_PATH)


if __name__ == "__main__":
    main()
