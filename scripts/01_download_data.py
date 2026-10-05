"""Step 1 – Data collection through the Kaggle REST API.

Prerequisites
  1. pip install kaggle
  2. Kaggle -> Settings -> "Create New Token" -> save kaggle.json to ~/.kaggle/
  3. Accept the competition rules once at
     https://www.kaggle.com/competitions/aptos2019-blindness-detection/rules

Usage:  python scripts/01_download_data.py
(Skip this step if data/raw/aptos/train_images already exists.)
"""
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from retina.config import RAW_DIR  # noqa: E402

COMPETITION = "aptos2019-blindness-detection"


def main():
    if (RAW_DIR / "train.csv").exists() and any((RAW_DIR / "train_images").glob("*.png")):
        print(f"Dataset already present in {RAW_DIR} – nothing to do.")
        return
    from kaggle.api.kaggle_api_extended import KaggleApi

    api = KaggleApi()
    api.authenticate()                       # reads ~/.kaggle/kaggle.json
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print("Downloading APTOS 2019 (~10 GB) via the Kaggle API ...")
    api.competition_download_files(COMPETITION, path=str(RAW_DIR), quiet=False)
    zpath = RAW_DIR / f"{COMPETITION}.zip"
    with zipfile.ZipFile(zpath) as z:
        z.extractall(RAW_DIR)
    zpath.unlink()
    print("Done ->", RAW_DIR)


if __name__ == "__main__":
    main()
