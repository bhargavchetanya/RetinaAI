"use client";

import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { api } from "@/lib/api";
import { axisProps, gridProps, Legend, StatTile, tooltipProps } from "@/components/charts";
import ConfusionMatrix from "@/components/ConfusionMatrix";
import type { ModelInfo } from "@/types";

const pct = (v: number | null | undefined, d = 1) => (v == null || Number.isNaN(v) ? "–" : `${(v * 100).toFixed(d)}%`);

export default function ModelPage() {
  const [info, setInfo] = useState<ModelInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [proj, setProj] = useState<"tsne" | "pca">("tsne");

  useEffect(() => {
    api.model().then(setInfo).catch((e) => setError((e as Error).message));
  }, []);

  if (error) return <Shell><p className="mt-5 rounded-lg bg-red-500/10 p-3 text-sm text-red-300">Backend unreachable: {error}</p></Shell>;
  if (!info) return <Shell><p className="mt-6 text-slate-400">Loading…</p></Shell>;
  const m = info.metrics;
  if (!m)
    return (
      <Shell>
        <p className="card mt-6 text-slate-300">
          No evaluation results yet. Run <code>python scripts/04_evaluate.py</code> after training.
        </p>
      </Shell>
    );

  const t = m.test;
  const hist = m.history;
  const baselines = info.baselines?.results ?? [];
  const cl = info.clustering;
  const d = info.data;
  const rel = m.reliability.before.map((b, i) => ({
    bin: b.bin,
    before: b.accuracy,
    after: m.reliability.after[i]?.accuracy ?? null,
  }));
  const pts = cl?.points ?? [];
  const nonRef = pts.filter((p) => p.grade < 2).map((p) => ({ x: p[proj][0], y: p[proj][1], g: p.grade }));
  const ref = pts.filter((p) => p.grade >= 2).map((p) => ({ x: p[proj][0], y: p[proj][1], g: p.grade }));

  return (
    <Shell>
      <p className="mt-1 text-sm text-slate-500">
        {m.model} · {m.params_millions} M params · {m.image_size}px · version {m.version} · held-out test set n = {t.n}
      </p>

      {/* headline numbers */}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatTile label="Quadratic weighted κ" value={t.qwk.toFixed(3)} sub="official DR metric (1 = perfect)" />
        <StatTile label="Accuracy (5-class)" value={pct(t.accuracy)} sub={`macro-F1 ${t.macro_f1.toFixed(3)}`} />
        <StatTile label="Referable DR sensitivity" value={pct(t.referable.sensitivity)} sub={`specificity ${pct(t.referable.specificity)}`} />
        <StatTile label="Referable DR ROC-AUC" value={t.referable.roc_auc.toFixed(3)} sub={`threshold ${t.referable.threshold}`} />
        <StatTile label="Calibration error (ECE)" value={pct(t.ece)} sub={`was ${pct(m.test_uncalibrated.ece)} before T = ${m.temperature.toFixed(2)}`} />
      </div>

      {/* training curves – two charts, never a dual axis */}
      {hist.length > 0 && (
        <div className="mt-6 grid gap-6 lg:grid-cols-2">
          <ChartCard title="Loss per epoch" legend={[{ label: "Train", color: "var(--series-1)" }, { label: "Validation", color: "var(--series-2)" }]}>
            <LineChart data={hist}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="epoch" {...axisProps} />
              <YAxis {...axisProps} width={40} domain={["auto", "auto"]} />
              <Tooltip {...tooltipProps} />
              <ReferenceLine x={m.best_epoch} stroke="var(--axis)" strokeDasharray="4 4" label={{ value: "best", fill: "var(--text-muted)", fontSize: 10, position: "insideTopRight" }} />
              <Line dataKey="train_loss" name="Train" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 3 }} />
              <Line dataKey="val_loss" name="Validation" stroke="var(--series-2)" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ChartCard>
          <ChartCard title="Validation performance" legend={[{ label: "QWK", color: "var(--series-1)" }, { label: "Accuracy", color: "var(--series-2)" }]}>
            <LineChart data={hist}>
              <CartesianGrid {...gridProps} />
              <XAxis dataKey="epoch" {...axisProps} />
              <YAxis {...axisProps} width={40} domain={[0, 1]} />
              <Tooltip {...tooltipProps} />
              <ReferenceLine x={m.best_epoch} stroke="var(--axis)" strokeDasharray="4 4" />
              <Line dataKey="val_qwk" name="QWK" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 3 }} />
              <Line dataKey="val_acc" name="Accuracy" stroke="var(--series-2)" strokeWidth={2} dot={{ r: 3 }} />
            </LineChart>
          </ChartCard>
        </div>
      )}

      {/* confusion matrix + per class */}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="card">
          <div className="mb-3 font-semibold">Confusion matrix (test)</div>
          <ConfusionMatrix cm={t.confusion_matrix} />
          <p className="mt-3 text-xs text-slate-500">Colour = share of the true class; most errors are between neighbouring grades, which QWK penalises lightly.</p>
        </div>
        <div className="card overflow-x-auto">
          <div className="mb-3 font-semibold">Per-class metrics (one-vs-rest)</div>
          <table className="tabular w-full text-sm">
            <thead className="text-left text-xs text-slate-400">
              <tr>
                <th className="py-2">Grade</th>
                <th className="py-2 text-right">n</th>
                <th className="py-2 text-right">Sensitivity</th>
                <th className="py-2 text-right">Specificity</th>
                <th className="py-2 text-right">Precision</th>
                <th className="py-2 text-right">F1</th>
              </tr>
            </thead>
            <tbody>
              {t.per_class.map((r) => (
                <tr key={r.class} className="border-t border-slate-800">
                  <td className="py-2">{r.class}</td>
                  <td className="py-2 text-right text-slate-400">{r.support}</td>
                  <td className="py-2 text-right">{pct(r.sensitivity)}</td>
                  <td className="py-2 text-right">{pct(r.specificity)}</td>
                  <td className="py-2 text-right">{pct(r.precision)}</td>
                  <td className="py-2 text-right">{r.f1.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* model comparison */}
      {baselines.length > 0 && (
        <div className="mt-6 grid gap-6 lg:grid-cols-[1.2fr_1fr]">
          <div className="card">
            <div className="font-semibold">Model comparison – test QWK</div>
            <p className="mt-1 text-xs text-slate-500">Same split for every model. Classical models tuned with GridSearchCV (3-fold, QWK).</p>
            <div className="mt-3" style={{ height: 48 * baselines.length + 30 }}>
              <ResponsiveContainer>
                <BarChart data={baselines.map((b) => ({ name: b.name.replace("CNN embeddings + ", "Embeddings + "), qwk: b.test_qwk, ours: b.name.includes("ours") }))} layout="vertical" margin={{ left: 10, right: 40 }}>
                  <CartesianGrid {...gridProps} horizontal={false} vertical />
                  <XAxis type="number" domain={[(lo: number) => Math.min(0, Math.floor(lo * 10) / 10), 1]} {...axisProps} tickFormatter={(v) => Number(v).toFixed(1)} />
                  <YAxis type="category" dataKey="name" {...axisProps} width={190} />
                  <Tooltip {...tooltipProps} formatter={(v) => Number(v).toFixed(3)} />
                  <Bar dataKey="qwk" name="Test QWK" radius={[0, 4, 4, 0]} maxBarSize={22} label={{ position: "right", fill: "var(--text-secondary)", fontSize: 11, formatter: (v: unknown) => Number(v).toFixed(3) }}>
                    {baselines.map((b) => (
                      <Cell key={b.name} fill={b.name.includes("ours") ? "var(--series-1)" : "#475569"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="card overflow-x-auto">
            <div className="mb-3 font-semibold">Baseline details</div>
            <table className="w-full text-xs">
              <tbody>
                {baselines.map((b) => (
                  <tr key={b.name} className="border-t border-slate-800 align-top">
                    <td className="py-2 pr-3">
                      <div className="font-medium text-slate-200">{b.name}</div>
                      <div className="text-slate-500">{b.family} · {b.features}</div>
                      {Object.keys(b.best_params).length > 0 && (
                        <div className="text-slate-500">best: {Object.entries(b.best_params).map(([k, v]) => `${k}=${v}`).join(", ")}</div>
                      )}
                    </td>
                    <td className="tabular py-2 text-right">
                      <div>acc {pct(b.test_accuracy)}</div>
                      {b.cv_qwk != null && <div className="text-slate-500">cv κ {b.cv_qwk.toFixed(3)}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* calibration + ROC */}
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <ChartCard
          title="Reliability diagram"
          note="Accuracy within each confidence bin. On the dashed diagonal, 'X % confident' means right X % of the time."
          legend={[{ label: "Before temperature scaling", color: "var(--series-2)" }, { label: "After", color: "var(--series-1)" }, { label: "Perfect calibration", color: "var(--axis)", dashed: true }]}
        >
          <LineChart data={rel}>
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="bin" type="number" domain={[0, 1]} {...axisProps} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
            <YAxis domain={[0, 1]} {...axisProps} width={40} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
            <Tooltip {...tooltipProps} formatter={(v) => pct(Number(v))} labelFormatter={(v) => `confidence ≈ ${Math.round(Number(v) * 100)}%`} />
            <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="var(--axis)" strokeDasharray="4 4" />
            <Line dataKey="before" name="Before" stroke="var(--series-2)" strokeWidth={2} dot={{ r: 4 }} connectNulls />
            <Line dataKey="after" name="After" stroke="var(--series-1)" strokeWidth={2} dot={{ r: 4 }} connectNulls />
          </LineChart>
        </ChartCard>
        <ChartCard title="ROC – referable DR (grade ≥ 2)" note={`AUC = ${t.referable.roc_auc.toFixed(3)}. The operating threshold was chosen on the validation set for ≥ 90 % sensitivity.`}>
          <LineChart data={m.roc_referable}>
            <CartesianGrid {...gridProps} />
            <XAxis dataKey="fpr" type="number" domain={[0, 1]} {...axisProps} label={{ value: "1 − specificity", fill: "var(--text-muted)", fontSize: 11, position: "insideBottom", offset: -2 }} />
            <YAxis domain={[0, 1]} {...axisProps} width={40} />
            <Tooltip {...tooltipProps} formatter={(v) => Number(v).toFixed(3)} labelFormatter={(v) => `FPR ${Number(v).toFixed(3)}`} />
            <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke="var(--axis)" strokeDasharray="4 4" />
            <Line dataKey="tpr" name="Sensitivity" stroke="var(--series-1)" strokeWidth={2} dot={false} />
          </LineChart>
        </ChartCard>
      </div>

      {/* unsupervised */}
      {cl && (
        <div className="mt-6 grid gap-6 lg:grid-cols-[1.4fr_1fr]">
          <div className="card">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="font-semibold">CNN embedding space ({proj === "tsne" ? "t-SNE" : "PCA"})</div>
              <div className="flex gap-1 rounded-lg border border-slate-800 p-1 text-xs">
                {(["tsne", "pca"] as const).map((p) => (
                  <button key={p} onClick={() => setProj(p)} className={`rounded-md px-3 py-1 ${proj === p ? "bg-slate-800 text-white" : "text-slate-400"}`}>
                    {p === "tsne" ? "t-SNE" : "PCA"}
                  </button>
                ))}
              </div>
            </div>
            <div className="mt-2">
              <Legend items={[{ label: `Non-referable (grade 0–1, n=${nonRef.length})`, color: "var(--series-1)" }, { label: `Referable (grade 2–4, n=${ref.length})`, color: "var(--series-2)" }]} />
            </div>
            <div className="mt-3 h-80">
              <ResponsiveContainer>
                <ScatterChart>
                  <CartesianGrid {...gridProps} vertical />
                  <XAxis dataKey="x" type="number" {...axisProps} tick={false} name="dim 1" />
                  <YAxis dataKey="y" type="number" {...axisProps} tick={false} width={10} name="dim 2" />
                  <ZAxis range={[28, 28]} />
                  <Tooltip {...tooltipProps} formatter={(v, n) => (n === "g" ? `grade ${v}` : Number(v).toFixed(2))} />
                  <Scatter name="Non-referable" data={nonRef} fill="var(--series-1)" fillOpacity={0.75} stroke="#0f172a" strokeWidth={1} />
                  <Scatter name="Referable" data={ref} fill="var(--series-2)" fillOpacity={0.75} stroke="#0f172a" strokeWidth={1} />
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              Each dot is an image&apos;s 1280-d EfficientNet embedding projected to 2-D. Labels were not used to make this map – the separation shows the network learned disease-related features.
            </p>
          </div>
          <div className="card text-sm">
            <div className="mb-3 font-semibold">Clustering the embeddings</div>
            <dl className="space-y-4">
              <div>
                <dt className="text-slate-400">DBSCAN (density-based)</dt>
                <dd className="tabular mt-1 text-slate-200">
                  eps {cl.dbscan.eps} · {cl.dbscan.n_clusters} clusters · {cl.dbscan.noise_points} noise points · ARI vs grade {cl.dbscan.ari_vs_grade}
                </dd>
                <dd className="mt-1 text-xs text-slate-500">Noise points are atypical images – the same idea powers the K-NN out-of-distribution guard in the app.</dd>
              </div>
              <div>
                <dt className="text-slate-400">Agglomerative (hierarchical, Ward)</dt>
                <dd className="tabular mt-1 text-slate-200">
                  {cl.agglomerative.n_clusters} clusters · ARI vs grade {cl.agglomerative.ari_vs_grade}
                </dd>
              </div>
              <div>
                <dt className="text-slate-400">PCA</dt>
                <dd className="tabular mt-1 text-slate-200">first 2 components explain {pct(cl.pca2_explained_variance[0] + cl.pca2_explained_variance[1])} of variance</dd>
              </div>
            </dl>
          </div>
        </div>
      )}

      {/* data pipeline */}
      {d && (
        <div className="card mt-6">
          <div className="mb-3 font-semibold">Data pipeline (APTOS 2019)</div>
          <div className="grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4">
            <Fact k="Raw labelled images" v={d.raw_rows} />
            <Fact k="Duplicate photos removed" v={d.removed_duplicates} s={`${d.duplicate_groups} groups, ${d.conflicting_duplicate_groups} with conflicting labels`} />
            <Fact k="Clean images" v={d.clean_images} s={`median ${d.original_resolution.median_w}×${d.original_resolution.median_h}px → 512px`} />
            <Fact k="Flagged poor quality" v={d.poor_quality_flagged} s={`enhancement: ${d.preprocess_method === "ben" ? "Ben Graham" : d.preprocess_method}`} />
          </div>
          <div className="mt-5 overflow-x-auto">
            <table className="tabular w-full text-sm">
              <thead className="text-left text-xs text-slate-400">
                <tr>
                  <th className="py-2">Split</th>
                  {Object.keys(d.class_counts).map((c) => (
                    <th key={c} className="py-2 text-right">{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(d.splits).map(([s, counts]) => (
                  <tr key={s} className="border-t border-slate-800">
                    <td className="py-2 capitalize">{s}</td>
                    {Object.keys(d.class_counts).map((c) => (
                      <td key={c} className="py-2 text-right">{counts[c]}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <h1 className="text-3xl font-bold">Model performance</h1>
      {children}
    </main>
  );
}

function ChartCard({
  title,
  note,
  legend,
  children,
}: {
  title: string;
  note?: string;
  legend?: { label: string; color: string; dashed?: boolean }[];
  children: React.ReactElement;
}) {
  return (
    <div className="card">
      <div className="mb-1 font-semibold">{title}</div>
      {legend && <Legend items={legend} />}
      <div className="mt-3 h-64">
        <ResponsiveContainer>{children}</ResponsiveContainer>
      </div>
      {note && <p className="mt-2 text-xs text-slate-500">{note}</p>}
    </div>
  );
}

function Fact({ k, v, s }: { k: string; v: number | string; s?: string }) {
  return (
    <div>
      <div className="text-slate-400">{k}</div>
      <div className="mt-1 text-2xl font-bold">{v}</div>
      {s && <div className="text-xs text-slate-500">{s}</div>}
    </div>
  );
}
