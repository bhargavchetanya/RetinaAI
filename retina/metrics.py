"""Evaluation metrics.

Accuracy alone is misleading on APTOS: predicting "No DR" for everything is
already ~49 % accurate. So we report:

  * Quadratic Weighted Kappa (QWK) – the official DR-grading metric. It is an
    agreement score that punishes errors by the *square* of the grade
    distance, so calling Proliferative "No DR" costs 16x more than calling it
    Severe. 1 = perfect, 0 = chance.
  * Per-class sensitivity (recall), specificity, precision, F1 (one-vs-rest).
  * Confusion matrix.
  * Referable-DR (grade >= 2) binary sensitivity / specificity / ROC-AUC –
    the decision that actually matters for the referral.
  * Expected Calibration Error (ECE) – does "90 % confident" mean right 90 %
    of the time?
"""
from __future__ import annotations

import numpy as np
from sklearn.metrics import confusion_matrix, roc_auc_score

from .config import CLASS_NAMES, NUM_CLASSES, REFERABLE_GRADE


def quadratic_weighted_kappa(y_true, y_pred, n: int = NUM_CLASSES) -> float:
    """Cohen's kappa with quadratic weights, from scratch.

    kappa = 1 - sum(W * O) / sum(W * E)
      O = observed confusion matrix
      E = expected matrix if predictions were independent of truth
          (outer product of the two marginal histograms, scaled to N)
      W_ij = (i - j)^2 / (n - 1)^2
    """
    y_true, y_pred = np.asarray(y_true, int), np.asarray(y_pred, int)
    O = confusion_matrix(y_true, y_pred, labels=range(n)).astype(np.float64)
    i, j = np.meshgrid(range(n), range(n), indexing="ij")
    W = (i - j) ** 2 / (n - 1) ** 2
    E = np.outer(O.sum(1), O.sum(0)) / max(O.sum(), 1)
    denom = (W * E).sum()
    return float(1 - (W * O).sum() / denom) if denom > 0 else 0.0


def per_class_report(y_true, y_pred, n: int = NUM_CLASSES):
    cm = confusion_matrix(y_true, y_pred, labels=range(n))
    rows = []
    total = cm.sum()
    for c in range(n):
        tp = cm[c, c]
        fn = cm[c].sum() - tp
        fp = cm[:, c].sum() - tp
        tn = total - tp - fn - fp
        sens = tp / (tp + fn) if tp + fn else 0.0
        spec = tn / (tn + fp) if tn + fp else 0.0
        prec = tp / (tp + fp) if tp + fp else 0.0
        f1 = 2 * prec * sens / (prec + sens) if prec + sens else 0.0
        rows.append({
            "class": CLASS_NAMES[c], "support": int(cm[c].sum()),
            "sensitivity": round(float(sens), 4), "specificity": round(float(spec), 4),
            "precision": round(float(prec), 4), "f1": round(float(f1), 4),
        })
    return rows, cm


def expected_calibration_error(probs: np.ndarray, y_true, bins: int = 10) -> float:
    conf = probs.max(1)
    correct = probs.argmax(1) == np.asarray(y_true)
    edges = np.linspace(0, 1, bins + 1)
    ece = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi)
        if m.any():
            ece += m.mean() * abs(correct[m].mean() - conf[m].mean())
    return float(ece)


def referable_metrics(probs: np.ndarray, y_true, threshold: float = 0.5):
    """Binary 'refer to ophthalmologist' metrics. P(referable) = sum P(grade>=2)."""
    y = (np.asarray(y_true) >= REFERABLE_GRADE).astype(int)
    p = probs[:, REFERABLE_GRADE:].sum(1)
    pred = (p >= threshold).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum()); tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum()); fn = int(((pred == 0) & (y == 1)).sum())
    auc = float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else float("nan")
    return {
        "threshold": round(float(threshold), 3),
        "sensitivity": round(tp / (tp + fn), 4) if tp + fn else 0.0,
        "specificity": round(tn / (tn + fp), 4) if tn + fp else 0.0,
        "precision": round(tp / (tp + fp), 4) if tp + fp else 0.0,
        "roc_auc": round(auc, 4),
        "tp": tp, "tn": tn, "fp": fp, "fn": fn,
    }


def pick_referral_threshold(probs, y_true, min_sensitivity: float = 0.90) -> float:
    """Largest threshold that still keeps sensitivity >= target (screening
    tools must not miss sick patients; a false referral is cheaper)."""
    y = (np.asarray(y_true) >= REFERABLE_GRADE)
    p = probs[:, REFERABLE_GRADE:].sum(1)
    best = 0.5 if y.sum() == 0 else 0.05
    for t in np.linspace(0.05, 0.95, 91):
        sens = ((p >= t) & y).sum() / max(y.sum(), 1)
        if sens >= min_sensitivity:
            best = t
    return float(best)


def full_report(probs: np.ndarray, y_true, referral_threshold: float = 0.5) -> dict:
    y_true = np.asarray(y_true, int)
    y_pred = probs.argmax(1)
    rows, cm = per_class_report(y_true, y_pred)
    return {
        "n": int(len(y_true)),
        "accuracy": round(float((y_pred == y_true).mean()), 4),
        "qwk": round(quadratic_weighted_kappa(y_true, y_pred), 4),
        "macro_f1": round(float(np.mean([r["f1"] for r in rows])), 4),
        "ece": round(expected_calibration_error(probs, y_true), 4),
        "per_class": rows,
        "confusion_matrix": cm.tolist(),
        "referable": referable_metrics(probs, y_true, referral_threshold),
    }
