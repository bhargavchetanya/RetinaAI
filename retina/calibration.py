"""Temperature scaling (Guo et al., 2017).

Modern deep networks are over-confident: they say "99 %" even when wrong.
Temperature scaling learns ONE scalar T on the validation set and divides the
logits by it:   p = softmax(z / T).
T > 1 softens the probabilities. It never changes the predicted class (argmax
is unchanged), only makes the confidence score honest – important when a
health worker decides whether to trust the screen.
"""
from __future__ import annotations

import numpy as np
import torch
import torch.nn.functional as F


def fit_temperature(logits: np.ndarray, labels: np.ndarray, iters: int = 200) -> float:
    z = torch.tensor(logits, dtype=torch.float32)
    y = torch.tensor(labels, dtype=torch.long)
    log_t = torch.zeros(1, requires_grad=True)       # optimise log T so T stays > 0
    opt = torch.optim.LBFGS([log_t], lr=0.05, max_iter=iters)

    def closure():
        opt.zero_grad()
        loss = F.cross_entropy(z / log_t.exp(), y)
        loss.backward()
        return loss

    opt.step(closure)
    return float(log_t.detach().exp().clamp(0.05, 20.0))


def softmax_np(logits: np.ndarray, T: float = 1.0) -> np.ndarray:
    z = logits / T
    z = z - z.max(1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(1, keepdims=True)
