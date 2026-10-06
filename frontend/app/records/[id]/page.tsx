"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, CheckCircle2, FileDown, ShieldAlert } from "lucide-react";
import HeatmapViewer from "@/components/HeatmapViewer";
import ConfidenceChart from "@/components/ConfidenceChart";
import { api, openReport } from "@/lib/api";
import { RequireRole, useAuth } from "@/lib/auth";
import type { ScreeningResult, ScreeningRow } from "@/types";

type Rec = ScreeningRow & { result: ScreeningResult };

const FOLLOWUP: Record<string, string> = {
  pending: "Pending",
  referred: "Referred to ophthalmologist",
  seen_by_doctor: "Seen by doctor",
  not_required: "Not required",
  lost: "Lost to follow-up",
};

export default function RecordPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <RequireRole roles={["admin", "hospital", "doctor", "patient"]}>
      <RecordView id={Number(id)} />
    </RequireRole>
  );
}

function RecordView({ id }: { id: number }) {
  const { user } = useAuth();
  const [rec, setRec] = useState<Rec | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.screening(id).then(setRec).catch((e) => setError((e as Error).message));
  }, [id]);

  const back = user?.role === "patient" ? "/reports" : "/dashboard";

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <Link href={back} className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-white">
        <ArrowLeft className="h-4 w-4" /> Back
      </Link>
      {error && <p className="mt-5 rounded-lg bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
      {!rec && !error && <p className="mt-6 text-slate-400">Loading…</p>}
      {rec && <Detail rec={rec} />}
    </main>
  );
}

function Detail({ rec }: { rec: Rec }) {
  const r = rec.result;
  const refer = rec.refer;
  return (
    <>
      <h1 className="mt-3 text-3xl font-bold">Screening #{rec.id}</h1>
      <p className="mt-1 text-slate-400">
        {rec.created_at.replace("T", " ").slice(0, 16)} · {rec.patient_name || "Unnamed patient"}
        {rec.patient_age ? `, ${rec.patient_age}` : ""}
        {rec.eye ? ` · ${rec.eye === "L" ? "left" : "right"} eye` : ""}
        {rec.centre ? ` · ${rec.centre}` : ""}
        {rec.doctor_name ? ` · ${rec.doctor_name}` : ""}
      </p>

      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <div className="card">
          {r.images?.original ? <HeatmapViewer images={r.images} /> : <p className="text-slate-500">Images not available.</p>}
        </div>
        <div className="flex flex-col gap-5">
          <div className={`rounded-2xl border p-5 ${refer ? "border-red-500/40 bg-red-500/10" : "border-green-500/40 bg-green-500/10"}`}>
            <div className="flex items-center gap-3">
              {refer ? (
                <ShieldAlert className="h-8 w-8 shrink-0" style={{ color: "var(--critical)" }} />
              ) : (
                <CheckCircle2 className="h-8 w-8 shrink-0" style={{ color: "var(--good)" }} />
              )}
              <div>
                <div className="text-xl font-bold">{refer ? "Refer to ophthalmologist" : "No referral needed"}</div>
                <div className="text-sm text-slate-300">
                  Probability of referable DR: <span className="tabular font-semibold">{(rec.p_referable * 100).toFixed(0)}%</span>
                  {" · "}Follow-up: {FOLLOWUP[rec.followup] ?? rec.followup}
                </div>
              </div>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="card">
              <div className="label">DR grade</div>
              <div className="mt-2 text-2xl font-bold">{rec.grade_name}</div>
              <div className="text-sm text-slate-500">grade {rec.grade} / 4</div>
            </div>
            <div className="card">
              <div className="label">Confidence</div>
              <div className="mt-2 text-2xl font-bold">{(rec.confidence * 100).toFixed(0)}%</div>
              <div className="text-sm text-slate-500">image quality {rec.quality_ok ? "adequate" : "poor"}</div>
            </div>
          </div>
          <div className="card">
            <div className="label mb-2">Why the model decided this</div>
            <p className="leading-7 text-slate-200">{r.explanation?.en}</p>
          </div>
          {r.probabilities && (
            <div className="card">
              <div className="label mb-3">Grade probabilities</div>
              <ConfidenceChart probs={r.probabilities} predicted={rec.grade} />
            </div>
          )}
          <button
            onClick={() => openReport(rec.id).catch((e) => alert((e as Error).message))}
            className="flex items-center justify-center gap-2 rounded-xl bg-cyan-500 px-5 py-3 font-semibold text-slate-950 hover:bg-cyan-400"
          >
            <FileDown className="h-4 w-4" /> Download PDF report
          </button>
        </div>
      </div>
    </>
  );
}
