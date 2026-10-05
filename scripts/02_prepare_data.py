"""Step 2 – Data cleaning, transformation, de-duplication and splitting.

  * Data cleaning   : drop missing / unreadable files, crop black borders,
                      remove duplicate photos (vessel-pattern fingerprint correlation).
  * Transformation  : resize to 512x512, Ben Graham contrast enhancement,
                      circular mask. Cached to data/processed/aptos/*.png so
                      training does not re-decode 7 MB PNGs every epoch.
  * Data reduction  : 3.6k x ~3000x2000 px  ->  3.6k x 512x512 px (~40x smaller).
  * Splitting       : stratified 70 / 15 / 15 train / validation / test.

Why de-duplicate? APTOS contains the same eye photographed/saved more than once.
If one copy lands in train and the other in test, test accuracy is inflated
(data leakage). Duplicates with *conflicting* labels are label noise and are
dropped entirely.

Usage:  python scripts/02_prepare_data.py [--method ben|clahe] [--workers 4]
"""
import argparse
import os
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.model_selection import train_test_split  # noqa: E402
from tqdm import tqdm  # noqa: E402

from retina.config import CACHE_SIZE, CLASS_NAMES, DATA_SUMMARY_PATH, PROCESSED_DIR, RAW_DIR, SPLITS_DIR  # noqa: E402
from retina.preprocessing import preprocess, read_rgb  # noqa: E402
from retina.quality import assess  # noqa: E402
from retina.utils import fingerprint, save_json  # noqa: E402


def work(args):
    id_code, method = args
    try:
        raw = read_rgb(RAW_DIR / "train_images" / f"{id_code}.png")
    except Exception:
        return id_code, None
    display, enhanced = preprocess(raw, CACHE_SIZE, method)
    out = PROCESSED_DIR / f"{id_code}.png"
    cv2.imwrite(str(out), cv2.cvtColor(enhanced, cv2.COLOR_RGB2BGR))
    q = assess(display)
    return id_code, {"h": raw.shape[0], "w": raw.shape[1], "fp": fingerprint(enhanced),
                     "sharpness": q["sharpness"], "brightness": q["brightness"],
                     "quality_ok": q["ok"]}


def find_duplicates(fps: np.ndarray, min_corr: float = 0.90):
    """Pairs whose fingerprints correlate >= min_corr are the same photo.
    Correlation matrix computed in blocks; union-find merges pairs into groups."""
    F = fps.astype(np.float32)
    n, dim = F.shape
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for s in range(0, n, 512):
        C = F[s:s + 512] @ F.T / dim
        for i, j in zip(*np.nonzero(C >= min_corr)):
            i += s
            if j > i:
                parent[find(j)] = find(i)
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return [g for g in groups.values() if len(g) > 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", default="ben", choices=["ben", "clahe", "none"])
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--limit", type=int, default=None, help="only first N images (smoke test)")
    args = ap.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    SPLITS_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(RAW_DIR / "train.csv")
    n_raw = len(df)
    df = df.drop_duplicates("id_code")
    present = {p.stem for p in (RAW_DIR / "train_images").glob("*.png")}
    df = df[df.id_code.isin(present)].reset_index(drop=True)
    if args.limit:
        df = df.groupby("diagnosis", group_keys=False).apply(
            lambda g: g.head(max(2, args.limit // 5))).reset_index(drop=True)
    print(f"{len(df)} labelled images found (of {n_raw} rows in train.csv)")

    jobs = [(i, args.method) for i in df.id_code]
    info = {}
    with ProcessPoolExecutor(args.workers) as ex:
        for id_code, r in tqdm(ex.map(work, jobs, chunksize=8), total=len(jobs), desc="preprocess"):
            if r is not None:
                info[id_code] = r
    unreadable = [i for i in df.id_code if i not in info]
    df = df[df.id_code.isin(info)].reset_index(drop=True)
    meta = pd.DataFrame([{"id_code": k, **{a: b for a, b in v.items() if a != "fp"}} for k, v in info.items()])
    df = df.merge(meta, on="id_code")
    fps = np.stack([info[i]["fp"] for i in df.id_code])

    # ---- de-duplication -------------------------------------------------
    groups = find_duplicates(fps)
    drop, conflicting = set(), 0
    for g in groups:
        labels = df.loc[g, "diagnosis"].unique()
        if len(labels) > 1:            # same photo, different grades -> label noise
            drop.update(g)
            conflicting += 1
        else:                          # keep the sharpest copy
            keep = df.loc[g, "sharpness"].idxmax()
            drop.update(set(g) - {keep})
    clean = df.drop(index=list(drop)).reset_index(drop=True)
    print(f"duplicate groups: {len(groups)}  (conflicting labels: {conflicting})  "
          f"-> removed {len(drop)} images, {len(clean)} remain")

    # ---- stratified split -----------------------------------------------
    train, temp = train_test_split(clean, test_size=0.30, stratify=clean.diagnosis, random_state=42)
    val, test = train_test_split(temp, test_size=0.50, stratify=temp.diagnosis, random_state=42)
    for name, part in [("train", train), ("val", val), ("test", test)]:
        part[["id_code", "diagnosis"]].to_csv(SPLITS_DIR / f"{name}.csv", index=False)

    def counts(d):
        c = Counter(d.diagnosis)
        return {CLASS_NAMES[k]: int(c.get(k, 0)) for k in range(5)}

    summary = {
        "raw_rows": n_raw,
        "unreadable": len(unreadable),
        "duplicate_groups": len(groups),
        "conflicting_duplicate_groups": conflicting,
        "removed_duplicates": len(drop),
        "clean_images": len(clean),
        "poor_quality_flagged": int((~clean.quality_ok).sum()),
        "preprocess_method": args.method,
        "cache_size": CACHE_SIZE,
        "original_resolution": {
            "median_w": int(clean.w.median()), "median_h": int(clean.h.median()),
            "min_w": int(clean.w.min()), "max_w": int(clean.w.max()),
        },
        "class_counts": counts(clean),
        "splits": {"train": counts(train), "val": counts(val), "test": counts(test)},
    }
    save_json(summary, DATA_SUMMARY_PATH)
    print("Saved splits to", SPLITS_DIR, "and summary to", DATA_SUMMARY_PATH)


if __name__ == "__main__":
    main()
