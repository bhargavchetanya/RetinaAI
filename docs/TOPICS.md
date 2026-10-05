# Topics used in RetinaAI – and why

The goal was **not** to use every syllabus algorithm. Each technique below solves a real problem in diabetic
retinopathy (DR) screening, so every one of them can be justified in the viva.

## A. Syllabus topics used (UML501)

| Syllabus unit | Topic | Where | Why it is needed here |
|---|---|---|---|
| Introduction | **Supervised learning** (5-class classification) | `scripts/03_train.py` | Grades are labelled by ophthalmologists |
| Introduction | **Unsupervised learning** | `scripts/05_baselines.py` | Explore the structure of the learned features without labels |
| Introduction | **Transfer learning** | `retina/model.py` | Only 3.6k images. Training a CNN from scratch would overfit, so we reuse ImageNet features |
| Data collection | **Unstructured data** (images) + **collection via API** | `scripts/01_download_data.py` | Kaggle REST API, authenticated with a token |
| Pre-processing | **Data cleaning** | `retina/preprocessing.py`, `02_prepare_data.py` | Crop the black camera border; remove unreadable and duplicate photos; drop duplicates whose labels conflict |
| Pre-processing | **Data transformation** | `preprocessing.py` | Resize, Ben Graham local-contrast enhancement (CLAHE as an alternative), circular mask |
| Pre-processing | **Data reduction** | `02_prepare_data.py`, `05_baselines.py` | Cache at 512 px (~40× smaller); PCA keeps 95 % of the variance of the 1280-d embedding |
| Pre-processing | **Feature scaling – standardisation** | `retina/dataset.py`, `05_baselines.py` | z-score with the ImageNet mean/std (the backbone expects it); StandardScaler before PCA / SVM |
| Pre-processing | **Train/test split** | `02_prepare_data.py` | **Stratified** 70/15/15, so the rare classes appear in every split |
| Classification | **Logistic Regression, SVM (RBF)** | `05_baselines.py` | Baselines on CNN embeddings: is fine-tuning worth it? |
| Classification | **Boosting: XGBoost** | `05_baselines.py` | Strongest classical model; used on hand-crafted features *and* on embeddings |
| Classification | **K-NN** | `retina/inference.py` | Distance to the 5 nearest training embeddings is used to detect out-of-distribution images |
| Classification | **Evaluation: sensitivity, specificity, precision, recall, F1, confusion matrix** | `retina/metrics.py` | Accuracy alone is misleading because 49 % of images are "No DR" |
| Regularization | **L2 (weight decay), dropout, early stopping, data augmentation** | `03_train.py`, `dataset.py` | Prevent overfitting on a small dataset |
| Clustering | **Density-based (DBSCAN)** | `05_baselines.py` | Finds dense groups and *noise points* (atypical images) |
| Clustering | **Hierarchical (Agglomerative, Ward)** | `05_baselines.py` | Compared with the true grades using the Adjusted Rand Index |
| Deep learning | **ANN / MLP layers, activation (SiLU), batch normalisation** | EfficientNet-B0 | MBConv blocks = conv + BN + SiLU + squeeze-excitation |
| Deep learning | **Optimisation** (AdamW, LR warm-up + cosine schedule, gradient clipping) | `03_train.py` | Stable fine-tuning |
| Deep learning | **Hyper-parameter tuning** | `GridSearchCV` in `05_baselines.py`; CLI flags in `03_train.py` | Systematic search (3-fold CV, scored by QWK) |
| Deep learning | **Metrics** | `metrics.py` | QWK, macro-F1, ROC-AUC, ECE |

**Deliberately not used:** linear and polynomial regression (the target is an ordered category, not a continuous
value); Naïve Bayes (its feature-independence assumption fails badly for image pixels); Apriori / association rules
(this is not a transaction dataset). Being able to say *why* a method was rejected also shows understanding.

## B. Beyond the syllabus

| Topic | Where | One-line explanation |
|---|---|---|
| **EfficientNet compound scaling** | `model.py` | Scales depth, width and resolution together; better accuracy per FLOP than ResNet |
| **Grad-CAM / Grad-CAM++ (from scratch)** | `retina/gradcam.py` | Gradients of the class score with respect to the last conv maps, used to weight those maps. ++ uses pixel-wise weights, so several small lesions all light up |
| **Quadratic Weighted Kappa (from scratch)** | `metrics.py` | The official Kaggle DR metric; confusing grade 4 with 0 costs 16× more than confusing 4 with 3 |
| **Class-imbalance handling** | `dataset.py` | Square-root inverse-frequency class weights in the cross-entropy loss |
| **Label smoothing** | `03_train.py` | Soft targets (0.96 for the true grade, 0.01 for each other); grade boundaries are fuzzy even for doctors |
| **Temperature scaling (calibration)** | `retina/calibration.py` | Fit one scalar T on the validation set so that "80 % confident" means right 80 % of the time |
| **Expected Calibration Error + reliability diagram** | `metrics.py`, Model page | Measures how honest the confidence scores are |
| **Test-time augmentation** | `inference.py`, `04_evaluate.py` | Average the predictions on the original and flipped images |
| **Clinical operating point** | `metrics.pick_referral_threshold` | Referable DR = grade ≥ 2; the threshold is chosen for ≥ 90 % sensitivity, because a missed patient costs far more than an extra referral |
| **Ben Graham preprocessing** | `preprocessing.py` | 4·I − 4·Gaussian(I) + 128, with a mask-normalised blur so no halo forms at the edge |
| **Duplicate removal (data leakage)** | `utils.fingerprint` | Vessel-pattern fingerprint + correlation. On APTOS, 147 photo pairs correlate above 0.95 while every other pair is below 0.8 (a clean gap). 43 of those pairs (~30 %) carry *different* grades, i.e. label noise. A DCT perceptual hash was tried first and rejected (too many false matches) |
| **Image-quality assessment** | `retina/quality.py` | Laplacian variance (blur), exposure, contrast, retina coverage |
| **Out-of-distribution detection** | `inference.py` | K-NN cosine distance in embedding space; a selfie or a document gets flagged |
| **t-SNE** | `05_baselines.py` | Non-linear 2-D view of the embeddings |
| **ONNX export** | `06_export_onnx.py` | Run the model without PyTorch, offline, on cheap hardware |
| **MLOps-style serving** | `backend/` | FastAPI + SQLite + PDF report; a deployable system, not just a notebook |

## C. Likely viva questions

1. **Why transfer learning?** 3.6k images are far too few to train 4 M parameters from scratch. ImageNet features
   (edges, blobs, textures) carry over to lesions.
2. **Why freeze the backbone in epoch 1?** The new head starts random. Its large gradients would wreck the
   pre-trained features, so the head is trained alone first.
3. **Why QWK and not accuracy?** The grades are ordered, so calling Proliferative "Mild" is much worse than calling
   it "Severe". QWK penalises by squared distance. Accuracy also rewards always predicting the majority class.
4. **How does Grad-CAM work?** Take the gradient of the class logit with respect to the last conv feature maps,
   average it per channel to get weights, take the weighted sum of the maps, apply ReLU, then upsample.
5. **Does temperature scaling change predictions?** No. Dividing all logits by the same T > 0 keeps the arg-max
   unchanged; only the confidence changes.
6. **What is data leakage and how did you prevent it?** The same eye appearing in both train and test sets
   inflates the scores. We remove duplicates *before* splitting.
7. **Why is the referral threshold not 0.5?** Screening must have high sensitivity, so the threshold is chosen on
   the validation set (not the test set!) to keep sensitivity ≥ 90 %.
8. **Why did the classical baselines do worse?** Hand-crafted features miss the subtle patterns. Frozen embeddings
   are generic ImageNet features; fine-tuning adapts them to retinal lesions.
9. **What do DBSCAN noise points mean?** They are images in low-density regions of feature space, i.e. atypical
   images. The same idea gives the out-of-distribution guard.
10. **Limitations?** One dataset (single hospital, one camera type); the lesion words in the explanation are
    heuristic hints, not segmentation; the model has not been clinically validated.
