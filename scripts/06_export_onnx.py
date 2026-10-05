"""Step 6 – Export the trained model to ONNX for offline / edge deployment.

ONNX models run with onnxruntime on a cheap CPU (or be converted for Android)
without PyTorch – suitable for a rural health centre with no internet.
The script also checks that ONNX and PyTorch give the same output and reports
CPU latency.

Usage:  python scripts/06_export_onnx.py
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from retina.config import CHECKPOINT_PATH, ONNX_PATH  # noqa: E402
from retina.model import load_checkpoint  # noqa: E402


def main():
    model, ckpt = load_checkpoint(CHECKPOINT_PATH, "cpu")
    size = ckpt["config"]["image_size"]
    x = torch.randn(1, 3, size, size)
    torch.onnx.export(model, x, str(ONNX_PATH), input_names=["image"], output_names=["logits"],
                      dynamic_axes={"image": {0: "batch"}, "logits": {0: "batch"}}, opset_version=17,
                      dynamo=False)
    import onnxruntime as ort

    sess = ort.InferenceSession(str(ONNX_PATH), providers=["CPUExecutionProvider"])
    ref = model(x).detach().numpy()
    out = sess.run(None, {"image": x.numpy()})[0]
    t0 = time.time()
    for _ in range(10):
        sess.run(None, {"image": x.numpy()})
    print(f"saved {ONNX_PATH} ({ONNX_PATH.stat().st_size / 1e6:.1f} MB)  "
          f"max|diff|={np.abs(ref - out).max():.2e}  CPU latency={(time.time() - t0) * 100:.0f} ms/image")


if __name__ == "__main__":
    main()
