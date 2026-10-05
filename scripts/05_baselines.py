"""Step 5 – Classical ML baselines + unsupervised analysis.

A) "Why deep learning?"  – Hand-crafted features (colour statistics, lesion
   morphology counts, sharpness) + XGBoost. No neural network at all.

B) "Transfer learning as a feature extractor" – the 1280-d EfficientNet
   embeddings -> StandardScaler -> PCA (95 % variance) -> {Logistic Regression,
   SVM (RBF), XGBoost}, each tuned with GridSearchCV (stratified 3-fold,
   scored by QWK).

C) Unsupervised – PCA / t-SNE 2-D projection, DBSCAN (density-based) and
   Agglomerative (hierarchical, Ward) clustering of the embeddings, compared
   with the true grades using the Adjusted Rand Index.

Results go to reports/baselines.json + reports/clustering.json (shown on the
website's "Model" page).

Usage:  python scripts/05_baselines.py   (run after 04_evaluate.py)
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2  # noqa: E402
import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402
from sklearn.cluster import DBSCAN, AgglomerativeClustering  # noqa: E402
from sklearn.decomposition import PCA  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.manifold import TSNE  # noqa: E402
from sklearn.metrics import adjusted_rand_score, make_scorer  # noqa: E402
from sklearn.model_selection import GridSearchCV, StratifiedKFold  # noqa: E402
from sklearn.neighbors import NearestNeighbors  # noqa: E402
from sklearn.pipeline import Pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402
from sklearn.svm import SVC  # noqa: E402
from tqdm import tqdm  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

from retina.config import BASELINES_PATH, CLUSTERING_PATH, METRICS_PATH, MODELS_DIR, PROCESSED_DIR  # noqa: E402
from retina.dataset import load_split  # noqa: E402
from retina.metrics import quadratic_weighted_kappa  # noqa: E402
from retina.utils import load_json, save_json  # noqa: E402

qwk_scorer = make_scorer(quadratic_weighted_kappa)


def handcrafted(id_code):
    rgb = np.array(Image.open(PROCESSED_DIR / f"{id_code}.png").convert("RGB").resize((256, 256)))
    mask = rgb.max(2) > 10
    feats = []
    for ch in range(3):
        v = rgb[..., ch][mask].astype(np.float32)
        feats += [v.mean(), v.std(), np.percentile(v, 5), np.percentile(v, 95)]
    g = rgb[..., 1]
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))
    th, bh = cv2.morphologyEx(g, cv2.MORPH_TOPHAT, k), cv2.morphologyEx(g, cv2.MORPH_BLACKHAT, k)
    for t in (15, 30, 45):
        feats += [(th > t)[mask].mean(), (bh > t)[mask].mean()]
        n, *_ = cv2.connectedComponentsWithStats(((bh > t) & mask).astype(np.uint8))
        feats.append(n)
    feats.append(cv2.Laplacian(g, cv2.CV_32F)[mask].var())
    edges = cv2.Canny(g, 50, 150)
    feats.append((edges > 0)[mask].mean())
    return np.array(feats, dtype=np.float32)


def evaluate(model, Xte, yte):
    pred = model.predict(Xte)
    return {"test_accuracy": round(float((pred == yte).mean()), 4),
            "test_qwk": round(quadratic_weighted_kappa(yte, pred), 4)}


def main():
    d = np.load(MODELS_DIR / "all_embeddings.npz")
    Xtr = np.concatenate([d["train_emb"], d["val_emb"]]); ytr = np.concatenate([d["train_y"], d["val_y"]])
    Xte, yte = d["test_emb"], d["test_y"]
    cv = StratifiedKFold(3, shuffle=True, random_state=42)
    results = []

    # ---- A) hand-crafted features + XGBoost ---------------------------------
    print("A) hand-crafted features ...")
    splits = {s: load_split(s) for s in ("train", "val", "test")}
    n_tr, n_va, n_te = len(d["train_y"]), len(d["val_y"]), len(d["test_y"])
    ids_tr = splits["train"].id_code.head(n_tr).tolist() + splits["val"].id_code.head(n_va).tolist()
    ids_te = splits["test"].id_code.head(n_te).tolist()
    Htr = np.stack([handcrafted(i) for i in tqdm(ids_tr, leave=False)])
    Hte = np.stack([handcrafted(i) for i in tqdm(ids_te, leave=False)])
    t0 = time.time()
    g = GridSearchCV(XGBClassifier(objective="multi:softprob", tree_method="hist", n_jobs=-1, verbosity=0),
                     {"n_estimators": [200, 400], "max_depth": [3, 5], "learning_rate": [0.05, 0.1]},
                     scoring=qwk_scorer, cv=cv, n_jobs=1)
    g.fit(Htr, ytr)
    results.append({"name": "Hand-crafted features + XGBoost", "family": "Classical (no deep learning)",
                    "features": f"{Htr.shape[1]} colour / lesion-morphology features",
                    "best_params": g.best_params_, "cv_qwk": round(g.best_score_, 4),
                    **evaluate(g.best_estimator_, Hte, yte), "fit_seconds": round(time.time() - t0, 1)})
    print(results[-1])

    # ---- B) CNN embeddings + classical classifiers ---------------------------
    pre = [("scale", StandardScaler()), ("pca", PCA(n_components=0.95, random_state=42))]
    candidates = {
        "Logistic Regression": (LogisticRegression(max_iter=3000, class_weight="balanced"),
                                {"clf__C": [0.01, 0.1, 1.0]}),
        "SVM (RBF kernel)": (SVC(kernel="rbf", class_weight="balanced"),
                             {"clf__C": [1, 10], "clf__gamma": ["scale", 0.001]}),
        "XGBoost": (XGBClassifier(objective="multi:softprob", tree_method="hist", n_jobs=-1, verbosity=0),
                    {"clf__n_estimators": [300], "clf__max_depth": [3, 5], "clf__learning_rate": [0.05, 0.1]}),
    }
    for name, (clf, grid) in candidates.items():
        print("B)", name, "...")
        t0 = time.time()
        gs = GridSearchCV(Pipeline(pre + [("clf", clf)]), grid, scoring=qwk_scorer, cv=cv, n_jobs=1)
        gs.fit(Xtr, ytr)
        n_pc = gs.best_estimator_.named_steps["pca"].n_components_
        results.append({"name": f"CNN embeddings + {name}", "family": "Transfer learning (feature extractor)",
                        "features": f"1280-d embedding -> PCA {n_pc} comps (95% var)",
                        "best_params": {k.replace("clf__", ""): v for k, v in gs.best_params_.items()},
                        "cv_qwk": round(gs.best_score_, 4), **evaluate(gs.best_estimator_, Xte, yte),
                        "fit_seconds": round(time.time() - t0, 1)})
        print(results[-1])

    m = load_json(METRICS_PATH, {})
    if m:
        results.append({"name": "Fine-tuned EfficientNet-B0 (ours)", "family": "Deep learning (end-to-end)",
                        "features": "raw pixels", "best_params": {}, "cv_qwk": None,
                        "test_accuracy": m["test"]["accuracy"], "test_qwk": m["test"]["qwk"],
                        "fit_seconds": None})
    save_json({"results": results}, BASELINES_PATH)

    # ---- C) unsupervised analysis ------------------------------------------
    print("C) clustering ...")
    X = np.concatenate([Xtr, Xte]); y = np.concatenate([ytr, yte])
    Z = PCA(n_components=min(50, len(X) - 1), random_state=42).fit_transform(StandardScaler().fit_transform(X))
    # DBSCAN eps from the k-distance curve (90th percentile of 5-NN distance)
    kd = NearestNeighbors(n_neighbors=5).fit(Z).kneighbors(Z)[0][:, -1]
    eps = float(np.percentile(kd, 90))
    db = DBSCAN(eps=eps, min_samples=5).fit_predict(Z)
    ag = AgglomerativeClustering(n_clusters=5, linkage="ward").fit_predict(Z)
    rng = np.random.default_rng(0)
    idx = rng.choice(len(Z), size=min(900, len(Z)), replace=False)
    p2 = PCA(n_components=2, random_state=42).fit(Z)
    pca2 = p2.transform(Z[idx])
    ts = TSNE(n_components=2, perplexity=min(30, max(5, len(idx) // 4)), random_state=42, init="pca").fit_transform(Z[idx])

    def purity(lbl):
        out = []
        for c in sorted(set(lbl)):
            if c == -1:
                continue
            m_ = lbl == c
            counts = np.bincount(y[m_], minlength=5)
            out.append({"cluster": int(c), "size": int(m_.sum()), "majority_grade": int(counts.argmax()),
                        "grade_counts": counts.tolist()})
        return out

    clustering = {
        "pca2_explained_variance": [round(float(v), 4) for v in p2.explained_variance_ratio_],
        "dbscan": {"eps": round(eps, 3), "min_samples": 5, "n_clusters": int(len(set(db)) - (1 if -1 in db else 0)),
                   "noise_points": int((db == -1).sum()), "ari_vs_grade": round(float(adjusted_rand_score(y, db)), 4),
                   "clusters": purity(db)},
        "agglomerative": {"linkage": "ward", "n_clusters": 5,
                          "ari_vs_grade": round(float(adjusted_rand_score(y, ag)), 4), "clusters": purity(ag)},
        "points": [{"pca": [round(float(a), 3) for a in pca2[i]], "tsne": [round(float(a), 3) for a in ts[i]],
                    "grade": int(y[j]), "dbscan": int(db[j])} for i, j in enumerate(idx)],
    }
    save_json(clustering, CLUSTERING_PATH)
    print("saved", BASELINES_PATH, "and", CLUSTERING_PATH)


if __name__ == "__main__":
    main()
