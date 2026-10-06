export interface Probability {
  grade: number;
  name: string;
  name_hi: string;
  p: number;
}

export interface Quality {
  ok: boolean;
  issues: string[];
  sharpness: number;
  brightness: number;
  contrast: number;
  coverage: number;
}

export interface ScreeningResult {
  id?: number;
  grade: number;
  grade_name: string;
  grade_name_hi: string;
  confidence: number;
  probabilities: Probability[];
  p_referable: number;
  referral_threshold: number;
  refer: boolean;
  quality: Quality;
  ood: { checked: boolean; distance?: number; threshold?: number; is_fundus_like?: boolean };
  warnings: string[];
  explanation: {
    en: string;
    hi: string;
    focus_region: string;
    attention_pattern: string;
    lesion_cues: string[];
  };
  images: { original: string; enhanced: string; heatmap: string };
  model_version: string;
  temperature: number;
  inference_ms: number;
}

export interface ScreeningRow {
  id: number;
  created_at: string;
  patient_name: string | null;
  patient_age: number | null;
  patient_sex: string | null;
  diabetes_years: number | null;
  eye: string | null;
  centre: string | null;
  grade: number;
  grade_name: string;
  confidence: number;
  p_referable: number;
  refer: boolean;
  quality_ok: boolean;
  followup: string;
  patient_id?: number | null;
  doctor_id?: number | null;
  hospital_id?: number | null;
  doctor_name?: string | null;
  hospital_name?: string | null;
}

export interface Stats {
  total: number;
  referred: number;
  poor_quality: number;
  referral_rate: number;
  by_grade: number[];
  by_day: { day: string; screenings: number; referrals: number }[];
  by_centre: { centre: string; screenings: number; referrals: number }[];
  followup: Record<string, number>;
}

export interface PerClass {
  class: string;
  support: number;
  sensitivity: number;
  specificity: number;
  precision: number;
  f1: number;
}

export interface Report {
  n: number;
  accuracy: number;
  qwk: number;
  macro_f1: number;
  ece: number;
  per_class: PerClass[];
  confusion_matrix: number[][];
  referable: {
    threshold: number;
    sensitivity: number;
    specificity: number;
    precision: number;
    roc_auc: number;
  };
}

export interface HistoryRow {
  epoch: number;
  train_loss: number;
  train_acc: number;
  val_loss: number;
  val_acc: number;
  val_qwk: number;
  lr: number;
}

export interface ReliabilityBin {
  bin: number;
  count: number;
  accuracy: number | null;
  confidence: number | null;
}

export interface Metrics {
  model: string;
  version: string;
  image_size: number;
  temperature: number;
  referral_threshold: number;
  test: Report;
  test_uncalibrated: { accuracy: number; qwk: number; macro_f1: number; ece: number };
  roc_referable: { fpr: number; tpr: number }[];
  reliability: { before: ReliabilityBin[]; after: ReliabilityBin[] };
  history: HistoryRow[];
  best_epoch: number;
  params_millions: number;
}

export interface Baseline {
  name: string;
  family: string;
  features: string;
  best_params: Record<string, unknown>;
  cv_qwk: number | null;
  test_accuracy: number;
  test_qwk: number;
}

export interface Clustering {
  pca2_explained_variance: number[];
  dbscan: { eps: number; n_clusters: number; noise_points: number; ari_vs_grade: number };
  agglomerative: { n_clusters: number; ari_vs_grade: number };
  points: { pca: [number, number]; tsne: [number, number]; grade: number; dbscan: number }[];
}

export interface DataSummary {
  raw_rows: number;
  unreadable: number;
  duplicate_groups: number;
  conflicting_duplicate_groups: number;
  removed_duplicates: number;
  clean_images: number;
  poor_quality_flagged: number;
  preprocess_method: string;
  original_resolution: { median_w: number; median_h: number };
  class_counts: Record<string, number>;
  splits: Record<string, Record<string, number>>;
}

export interface ModelInfo {
  metrics: Metrics | null;
  baselines: { results: Baseline[] } | null;
  clustering: Clustering | null;
  data: DataSummary | null;
}

export type Role = "admin" | "hospital" | "doctor" | "patient";

export interface User {
  id: number;
  username: string;
  role: Role;
  full_name: string;
  hospital_id: number | null;
  hospital_name?: string | null;
  age: number | null;
  sex: string | null;
  created_at: string;
}
