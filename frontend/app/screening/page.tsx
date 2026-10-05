"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, FileDown, Loader2, RotateCcw, ShieldAlert, Stethoscope } from "lucide-react";
import ImageUploader from "@/components/ImageUploader";
import HeatmapViewer from "@/components/HeatmapViewer";
import ConfidenceChart from "@/components/ConfidenceChart";
import { api, API_URL } from "@/lib/api";
import { useLang } from "@/lib/i18n";
import type { ScreeningResult } from "@/types";

const QUALITY_TEXT: Record<string, string> = {
  blurred: "blurred",
  too_dark: "too dark",
  over_exposed: "over-exposed",
  low_contrast: "low contrast",
  retina_not_centered: "retina not centred / too small",
};

export default function ScreeningPage() {
  const { t, lang } = useLang();
  const [file, setFile] = useState<File | null>(null);
  const [meta, setMeta] = useState({ patient_name: "", patient_age: "", patient_sex: "", diabetes_years: "", eye: "", centre: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ScreeningResult | null>(null);
  const [health, setHealth] = useState<{ ok: boolean; msg?: string } | null>(null);

  useEffect(() => {
    api
      .health()
      .then((h) => setHealth(h.model_loaded ? { ok: true } : { ok: false, msg: h.error ?? t("model_missing") }))
      .catch(() => setHealth({ ok: false, msg: `${t("backend_down")} ${API_URL}` }));
    try {
      const c = localStorage.getItem("retina-centre");
      if (c) setMeta((m) => ({ ...m, centre: c }));
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function analyse() {
    if (!file) return;
    setLoading(true);
    setError(null);
    const fd = new FormData();
    fd.append("file", file);
    Object.entries(meta).forEach(([k, v]) => v !== "" && fd.append(k, v));
    try {
      localStorage.setItem("retina-centre", meta.centre);
    } catch {}
    try {
      setResult(await api.screen(fd));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function reset() {
    setResult(null);
    setFile(null);
    setError(null);
    setMeta((m) => ({ ...m, patient_name: "", patient_age: "", patient_sex: "", diabetes_years: "", eye: "" }));
  }

  const set = (k: keyof typeof meta) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setMeta({ ...meta, [k]: e.target.value });

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <h1 className="text-3xl font-bold">{t("screen_title")}</h1>
      <p className="mt-2 max-w-3xl text-slate-400">{t("screen_sub")}</p>

      {health && !health.ok && (
        <div className="mt-5 flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-300">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{health.msg}</span>
        </div>
      )}

      {!result ? (
        <div className="mt-8 grid gap-6 lg:grid-cols-[1.1fr_1fr]">
          <div className="card">
            <ImageUploader file={file} onFile={setFile} />
          </div>
          <div className="card flex flex-col">
            <div className="label mb-4">{t("patient")}</div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label={t("name")} className="sm:col-span-2">
                <input className="input" value={meta.patient_name} onChange={set("patient_name")} />
              </Field>
              <Field label={t("age")}>
                <input className="input" type="number" min={0} max={120} value={meta.patient_age} onChange={set("patient_age")} />
              </Field>
              <Field label={t("sex")}>
                <select className="input" value={meta.patient_sex} onChange={set("patient_sex")}>
                  <option value="">—</option>
                  <option value="M">{t("male")}</option>
                  <option value="F">{t("female")}</option>
                  <option value="O">{t("other")}</option>
                </select>
              </Field>
              <Field label={t("eye")}>
                <select className="input" value={meta.eye} onChange={set("eye")}>
                  <option value="">—</option>
                  <option value="L">{t("left")}</option>
                  <option value="R">{t("right")}</option>
                </select>
              </Field>
              <Field label={t("dm_years")}>
                <input className="input" type="number" min={0} step={0.5} value={meta.diabetes_years} onChange={set("diabetes_years")} />
              </Field>
              <Field label={t("centre")} className="sm:col-span-2">
                <input className="input" value={meta.centre} onChange={set("centre")} placeholder="e.g. PHC Rampur" />
              </Field>
            </div>
            <div className="mt-auto pt-6">
              {error && <p className="mb-3 rounded-lg bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
              <button
                disabled={!file || loading || (health !== null && !health.ok)}
                onClick={analyse}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-500 px-6 py-3 font-semibold text-slate-950 hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-40"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Stethoscope className="h-4 w-4" />}
                {loading ? t("analysing") : t("analyse")}
              </button>
            </div>
          </div>
        </div>
      ) : (
        <Result result={result} lang={lang} t={t} onReset={reset} />
      )}
    </main>
  );
}

function Field({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <label className={`block ${className}`}>
      <span className="mb-1 block text-xs text-slate-400">{label}</span>
      {children}
    </label>
  );
}

function Result({
  result: r,
  lang,
  t,
  onReset,
}: {
  result: ScreeningResult;
  lang: "en" | "hi";
  t: ReturnType<typeof useLang>["t"];
  onReset: () => void;
}) {
  const refer = r.refer;
  const ood = r.ood.checked && r.ood.is_fundus_like === false;
  return (
    <div className="mt-8 grid gap-6 lg:grid-cols-[1fr_1fr]">
      <div className="card">
        <HeatmapViewer images={r.images} />
      </div>

      <div className="flex flex-col gap-5">
        {/* Referral decision – status colour always paired with icon + label */}
        <div
          className={`rounded-2xl border p-5 ${refer ? "border-red-500/40 bg-red-500/10" : "border-green-500/40 bg-green-500/10"}`}
        >
          <div className="flex items-center gap-3">
            {refer ? (
              <ShieldAlert className="h-8 w-8 shrink-0" style={{ color: "var(--critical)" }} />
            ) : (
              <CheckCircle2 className="h-8 w-8 shrink-0" style={{ color: "var(--good)" }} />
            )}
            <div>
              <div className="text-xl font-bold">{refer ? t("refer") : t("no_refer")}</div>
              <div className="text-sm text-slate-300">
                {t("p_ref")}: <span className="tabular font-semibold">{(r.p_referable * 100).toFixed(0)}%</span>{" "}
                <span className="text-slate-500">(threshold {(r.referral_threshold * 100).toFixed(0)}%)</span>
              </div>
            </div>
          </div>
          <ThresholdMeter p={r.p_referable} thr={r.referral_threshold} />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="card">
            <div className="label">{t("grade")}</div>
            <div className="mt-2 text-2xl font-bold">{lang === "hi" ? r.grade_name_hi : r.grade_name}</div>
            <div className="text-sm text-slate-500">grade {r.grade} / 4</div>
          </div>
          <div className="card">
            <div className="label">{t("confidence")}</div>
            <div className="mt-2 text-2xl font-bold">{(r.confidence * 100).toFixed(0)}%</div>
            <div className="text-sm text-slate-500">calibrated (T = {r.temperature.toFixed(2)})</div>
          </div>
        </div>

        {(ood || !r.quality.ok) && (
          <div className="flex items-start gap-3 rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-sm text-amber-200">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" style={{ color: "var(--warning)" }} />
            <div className="space-y-1">
              {!r.quality.ok && (
                <p>
                  {t("quality")}: {t("quality_bad")} ({r.quality.issues.map((i) => QUALITY_TEXT[i] ?? i).join(", ")})
                </p>
              )}
              {ood && <p>{t("ood_warn")}</p>}
            </div>
          </div>
        )}

        <div className="card">
          <div className="label mb-2">{t("explanation")}</div>
          <p className="leading-7 text-slate-200">{lang === "hi" ? r.explanation.hi : r.explanation.en}</p>
        </div>

        <div className="card">
          <div className="label mb-3">{t("probabilities")}</div>
          <ConfidenceChart probs={r.probabilities} predicted={r.grade} />
        </div>

        <div className="card text-xs text-slate-400">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4">
            <span>sharpness {r.quality.sharpness}</span>
            <span>brightness {r.quality.brightness}</span>
            <span>contrast {r.quality.contrast}</span>
            <span>
              OOD dist {r.ood.distance ?? "–"}/{r.ood.threshold ?? "–"}
            </span>
          </div>
          <div className="mt-2">
            {r.model_version} · {r.inference_ms} ms
          </div>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          {r.id !== undefined && (
            <a
              href={api.reportUrl(r.id)}
              target="_blank"
              rel="noreferrer"
              className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-cyan-500 px-5 py-3 font-semibold text-slate-950 hover:bg-cyan-400"
            >
              <FileDown className="h-4 w-4" /> {t("report")}
            </a>
          )}
          <button
            onClick={onReset}
            className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-slate-700 px-5 py-3 font-semibold hover:bg-slate-900"
          >
            <RotateCcw className="h-4 w-4" /> {t("new_scan")}
          </button>
        </div>
      </div>
    </div>
  );
}

function ThresholdMeter({ p, thr }: { p: number; thr: number }) {
  return (
    <div className="relative mt-4 h-2 rounded bg-slate-800" aria-hidden>
      <div className="h-2 rounded" style={{ width: `${p * 100}%`, background: "var(--series-1)" }} />
      <div className="absolute -top-1 h-4 w-0.5 bg-slate-200" style={{ left: `${thr * 100}%` }} />
    </div>
  );
}
