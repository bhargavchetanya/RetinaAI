"""Step 3 – Fine-tune EfficientNet-B0 on the fundus images (transfer learning).

Key training choices (each one is a regularisation / optimisation concept):
  * Class-weighted cross-entropy + label smoothing  -> class imbalance, over-confidence
  * AdamW (Adam + decoupled weight decay)            -> optimiser + L2 regularisation
  * Linear warm-up then cosine-annealed LR           -> stable fine-tuning
  * Frozen backbone for the first epoch              -> protect pre-trained features
  * Dropout before the classifier, data augmentation -> regularisation
  * Gradient clipping                                -> stable updates
  * Early stopping on validation QWK                 -> stop before over-fitting
After training: temperature scaling + referral threshold are fitted on the
validation set and stored inside the checkpoint.

Usage:
  python scripts/03_train.py                       # defaults (≈15 epochs, 320 px)
  python scripts/03_train.py --epochs 20 --image-size 384 --lr 2e-4
"""
import argparse
import math
import os
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn as nn  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402
from tqdm import tqdm  # noqa: E402

from retina.calibration import fit_temperature, softmax_np  # noqa: E402
from retina.config import CHECKPOINT_PATH, DATA_SUMMARY_PATH, HISTORY_PATH, LAST_STATE_PATH, TrainConfig, get_device  # noqa: E402
from retina.dataset import FundusDataset, class_weights, eval_transforms, load_split, train_transforms  # noqa: E402
from retina.metrics import expected_calibration_error, pick_referral_threshold, quadratic_weighted_kappa  # noqa: E402
from retina.model import DRNet  # noqa: E402
from retina.utils import load_json, save_json, seed_everything  # noqa: E402


def parse_args() -> TrainConfig:
    c = TrainConfig()
    ap = argparse.ArgumentParser()
    for k, v in c.to_dict().items():
        if k == "extra":
            continue
        flag = "--" + k.replace("_", "-")
        if isinstance(v, bool):
            ap.add_argument(flag, type=lambda s: s.lower() in ("1", "true", "yes"), default=v)
        else:
            ap.add_argument(flag, type=type(v) if v is not None else int, default=v)
    a = ap.parse_args()
    return TrainConfig(**{k: getattr(a, k) for k in c.to_dict() if k != "extra"})


@torch.no_grad()
def collect_logits(model, loader, device):
    model.eval()
    out, ys = [], []
    for x, y in loader:
        out.append(model(x.to(device)).float().cpu())
        ys.append(y)
    return torch.cat(out).numpy(), torch.cat(ys).numpy()


class Watchdog:
    """Kills the process (exit code 3) if training makes no progress for
    `minutes` – e.g. a stuck DataLoader worker. The overnight script then
    restarts training with --resume from the last finished epoch."""

    def __init__(self, minutes):
        self.limit, self.last = minutes * 60, time.time()
        threading.Thread(target=self._run, daemon=True).start()

    def beat(self):
        self.last = time.time()

    def _run(self):
        while True:
            time.sleep(30)
            if time.time() - self.last > self.limit:
                print(f"\nWATCHDOG: no progress for {self.limit // 60} min -> exiting so it can be resumed", flush=True)
                os._exit(3)


def main():
    cfg = parse_args()
    dog = Watchdog(cfg.watchdog_minutes)
    seed_everything(cfg.seed)
    device = get_device()
    summary = load_json(DATA_SUMMARY_PATH, {})
    cfg.extra["preprocess"] = summary.get("preprocess_method", "ben")
    print(f"device={device}  config={cfg.to_dict()}")

    tr_df, va_df = load_split("train"), load_split("val")
    if cfg.limit:
        tr_df, va_df = tr_df.head(cfg.limit), va_df.head(max(10, cfg.limit // 4))
    train_ds = FundusDataset(tr_df, train_transforms(cfg.image_size))
    val_ds = FundusDataset(va_df, eval_transforms(cfg.image_size))
    kw = dict(num_workers=cfg.num_workers, persistent_workers=cfg.num_workers > 0)
    train_dl = DataLoader(train_ds, cfg.batch_size, shuffle=True, drop_last=True, **kw)
    val_dl = DataLoader(val_ds, cfg.batch_size * 2, shuffle=False, num_workers=0)  # no workers: avoids macOS hangs

    model = DRNet(dropout=cfg.dropout, pretrained=cfg.pretrained).to(device)
    w = class_weights(tr_df.diagnosis).to(device)
    print("class weights:", [round(float(v), 2) for v in w])
    criterion = nn.CrossEntropyLoss(weight=w, label_smoothing=cfg.label_smoothing)
    optim = torch.optim.AdamW(model.parameters(), lr=cfg.lr, weight_decay=cfg.weight_decay)

    steps_per_epoch = len(train_dl)
    total = cfg.epochs * steps_per_epoch
    warm = cfg.warmup_epochs * steps_per_epoch

    def lr_lambda(step):
        if step < warm:
            return (step + 1) / warm
        prog = (step - warm) / max(1, total - warm)
        return 0.02 + 0.98 * 0.5 * (1 + math.cos(math.pi * prog))

    sched = torch.optim.lr_scheduler.LambdaLR(optim, lr_lambda)

    history, best_qwk, bad_epochs, start = [], -1.0, 0, 1
    CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
    if cfg.resume and LAST_STATE_PATH.exists():
        st = torch.load(LAST_STATE_PATH, map_location=device, weights_only=False)
        model.load_state_dict(st["model"]); optim.load_state_dict(st["optim"]); sched.load_state_dict(st["sched"])
        history, best_qwk, bad_epochs, start = st["history"], st["best_qwk"], st["bad_epochs"], st["epoch"] + 1
        print(f"RESUMED after epoch {st['epoch']} (best val QWK so far {best_qwk})", flush=True)
    stop = False
    for epoch in range(start, cfg.epochs + 1):
        model.set_backbone_trainable(epoch > cfg.freeze_epochs)
        model.train()
        t0, run_loss, correct, seen = time.time(), 0.0, 0, 0
        for x, y in tqdm(train_dl, desc=f"epoch {epoch}/{cfg.epochs}", leave=False):
            x, y = x.to(device), y.to(device)
            logits = model(x)
            loss = criterion(logits, y)
            optim.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 2.0)
            optim.step()
            sched.step()
            run_loss += loss.item() * len(y)
            correct += (logits.argmax(1) == y).sum().item()
            seen += len(y)
            dog.beat()

        v_logits, v_y = collect_logits(model, val_dl, device)
        v_pred = v_logits.argmax(1)
        v_loss = float(nn.functional.cross_entropy(torch.tensor(v_logits), torch.tensor(v_y)))
        rec = {
            "epoch": epoch,
            "train_loss": round(run_loss / max(seen, 1), 4),
            "train_acc": round(correct / max(seen, 1), 4),
            "val_loss": round(v_loss, 4),
            "val_acc": round(float((v_pred == v_y).mean()), 4),
            "val_qwk": round(quadratic_weighted_kappa(v_y, v_pred), 4),
            "lr": round(optim.param_groups[0]["lr"], 7),
            "seconds": round(time.time() - t0, 1),
        }
        history.append(rec)
        print(rec, flush=True)
        dog.beat()

        if rec["val_qwk"] > best_qwk:
            best_qwk, bad_epochs = rec["val_qwk"], 0
            torch.save({"state_dict": model.state_dict(), "config": cfg.to_dict(),
                        "epoch": epoch, "val_qwk": best_qwk}, CHECKPOINT_PATH)
        else:
            bad_epochs += 1
            if bad_epochs >= cfg.patience:
                print(f"early stopping (no QWK improvement for {cfg.patience} epochs)")
                stop = True
        save_json({"config": cfg.to_dict(), "history": history}, HISTORY_PATH)
        torch.save({"model": model.state_dict(), "optim": optim.state_dict(), "sched": sched.state_dict(),
                    "epoch": epoch, "history": history, "best_qwk": best_qwk, "bad_epochs": bad_epochs},
                   LAST_STATE_PATH)
        if stop:
            break

    # ---- calibration on the validation set ---------------------------------
    dog.beat()
    ckpt = torch.load(CHECKPOINT_PATH, map_location=device, weights_only=False)
    model.load_state_dict(ckpt["state_dict"])
    v_logits, v_y = collect_logits(model, val_dl, device)
    T = fit_temperature(v_logits, v_y)
    T = min(max(T, 0.5), 5.0)                    # keep T in a sensible range
    ece_raw = expected_calibration_error(softmax_np(v_logits), v_y)
    if expected_calibration_error(softmax_np(v_logits, T), v_y) > ece_raw:
        T = 1.0                                  # scaling did not help -> keep raw probabilities
    probs = softmax_np(v_logits, T)
    thr = pick_referral_threshold(probs, v_y, min_sensitivity=0.90)
    print(f"temperature T={T:.3f}  ECE before={expected_calibration_error(softmax_np(v_logits), v_y):.4f} "
          f"after={expected_calibration_error(probs, v_y):.4f}  referral threshold={thr:.2f}")
    ckpt.update({"temperature": T, "referral_threshold": thr,
                 "version": time.strftime("effb0-%Y%m%d-%H%M")})
    torch.save(ckpt, CHECKPOINT_PATH)
    save_json({"config": cfg.to_dict(), "history": history, "best_val_qwk": best_qwk,
               "best_epoch": ckpt["epoch"], "temperature": T, "referral_threshold": thr}, HISTORY_PATH)
    print("saved", CHECKPOINT_PATH)


if __name__ == "__main__":
    main()
