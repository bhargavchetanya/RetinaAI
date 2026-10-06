"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CheckCircle2, ChevronRight, FileDown, ShieldAlert } from "lucide-react";
import { api, openReport } from "@/lib/api";
import { RequireRole, useAuth } from "@/lib/auth";
import type { ScreeningRow } from "@/types";

export default function ReportsPage() {
  return (
    <RequireRole roles={["patient"]}>
      <MyReports />
    </RequireRole>
  );
}

function MyReports() {
  const { user } = useAuth();
  const [rows, setRows] = useState<ScreeningRow[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.screenings().then(setRows).catch((e) => setError((e as Error).message));
  }, []);

  const latest = rows?.[0];

  return (
    <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6">
      <h1 className="text-3xl font-bold">My reports</h1>
      <p className="mt-2 text-slate-400">
        Hello {user?.full_name}. These are your eye screenings. Only you, the doctor who screened you and your hospital can see them.
      </p>
      {error && <p className="mt-5 rounded-lg bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
      {rows && rows.length === 0 && (
        <div className="card mt-6 text-slate-300">
          You have no screenings yet. When a doctor screens you, they choose your account (<b>@{user?.username}</b>) and the
          report appears here.
        </div>
      )}

      {latest && (
        <div className={`mt-6 rounded-2xl border p-5 ${latest.refer ? "border-red-500/40 bg-red-500/10" : "border-green-500/40 bg-green-500/10"}`}>
          <div className="label">Latest result · {latest.created_at.slice(0, 10)}</div>
          <div className="mt-2 flex items-center gap-3">
            {latest.refer ? (
              <ShieldAlert className="h-8 w-8" style={{ color: "var(--critical)" }} />
            ) : (
              <CheckCircle2 className="h-8 w-8" style={{ color: "var(--good)" }} />
            )}
            <div>
              <div className="text-xl font-bold">{latest.grade_name}</div>
              <div className="text-sm text-slate-300">
                {latest.refer
                  ? "Please visit an eye specialist (ophthalmologist) for a detailed examination."
                  : "No referral needed now. Keep your blood sugar controlled and get screened again in 12 months."}
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="mt-6 space-y-3">
        {rows?.map((r) => (
          <div key={r.id} className="card flex items-center gap-4">
            <Link href={`/records/${r.id}`} className="flex flex-1 items-center gap-4">
              {r.refer ? (
                <ShieldAlert className="h-5 w-5 shrink-0" style={{ color: "var(--critical)" }} />
              ) : (
                <CheckCircle2 className="h-5 w-5 shrink-0" style={{ color: "var(--good)" }} />
              )}
              <div className="flex-1">
                <div className="font-semibold">
                  {r.grade_name} <span className="font-normal text-slate-400">· {(r.confidence * 100).toFixed(0)}% confidence</span>
                </div>
                <div className="text-sm text-slate-500">
                  {r.created_at.replace("T", " ").slice(0, 16)} · {r.centre || "—"}
                  {r.doctor_name ? ` · ${r.doctor_name}` : ""}
                  {r.eye ? ` · ${r.eye === "L" ? "left" : "right"} eye` : ""}
                </div>
              </div>
              <ChevronRight className="h-5 w-5 text-slate-500" />
            </Link>
            <button
              onClick={() => openReport(r.id).catch((e) => alert((e as Error).message))}
              className="text-cyan-400 hover:text-cyan-300"
              title="Download PDF"
            >
              <FileDown className="h-5 w-5" />
            </button>
          </div>
        ))}
      </div>
    </main>
  );
}
