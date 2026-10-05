"""Step 3b – (Re)fit temperature scaling + referral threshold on an existing
checkpoint. Use this if training was interrupted with Ctrl+C: the best epoch
is already saved in models/, this adds the calibration that 03_train.py
normally does at the very end.

Usage:  python scripts/03b_calibrate.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch  # noqa: E402
from torch.utils.data import DataLoader  # noqa: E402

from retina.calibration import fit_temperature, softmax_np  # noqa: E402
from retina.config import CHECKPOINT_PATH, HISTORY_PATH, get_device  # noqa: E402
from retina.dataset import FundusDataset, eval_transforms, load_split  # noqa: E402
from retina.metrics import expected_calibration_error, pick_referral_threshold  # noqa: E402
from retina.model import DRNet  # noqa: E402
from retina.utils import load_json, save_json  # noqa: E402


@torch.no_grad()
def collect_logits(model, loader, device):
    model.eval()
    out, ys = [], []
    for x, y in loader:
        out.append(model(x.to(device)).float().cpu())
        ys.append(y)
    return torch.cat(out).numpy(), torch.cat(ys).numpy()


def main():
    device = get_device()
    ckpt = torch.load(CHECKPOINT_PATH, map_location=device, weights_only=False)
    cfg = ckpt["config"]
    model = DRNet(dropout=cfg.get("dropout", 0.3), pretrained=False).to(device)
    model.load_state_dict(ckpt["state_dict"])
    val_dl = DataLoader(FundusDataset(load_split("val"), eval_transforms(cfg["image_size"])),
                        batch_size=32, num_workers=0)
    v_logits, v_y = collect_logits(model, val_dl, device)
    T = min(max(fit_temperature(v_logits, v_y), 0.5), 5.0)
    ece_raw = expected_calibration_error(softmax_np(v_logits), v_y)
    if expected_calibration_error(softmax_np(v_logits, T), v_y) > ece_raw:
        T = 1.0
    probs = softmax_np(v_logits, T)
    thr = pick_referral_threshold(probs, v_y, min_sensitivity=0.90)
    print(f"best epoch {ckpt.get('epoch')} (val QWK {ckpt.get('val_qwk')})  T={T:.3f}  "
          f"ECE before={ece_raw:.4f} after={expected_calibration_error(probs, v_y):.4f}  referral threshold={thr:.2f}")
    ckpt.update({"temperature": T, "referral_threshold": thr,
                 "version": time.strftime("effb0-%Y%m%d-%H%M")})
    torch.save(ckpt, CHECKPOINT_PATH)
    hist = load_json(HISTORY_PATH, {})
    hist.update({"best_val_qwk": ckpt.get("val_qwk"), "best_epoch": ckpt.get("epoch"),
                 "temperature": T, "referral_threshold": thr})
    save_json(hist, HISTORY_PATH)
    print("saved", CHECKPOINT_PATH)


if __name__ == "__main__":
    main()
