"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CheckCircle2, Eye, FileDown, ShieldAlert, Trash2, UserCheck } from "lucide-react";
import { api, openReport } from "@/lib/api";
import { RequireRole, useAuth } from "@/lib/auth";
import { axisProps, gridProps, Legend, StatTile, tooltipProps } from "@/components/charts";
import type { ScreeningRow, Stats } from "@/types";

const GRADES = ["No DR", "Mild", "Moderate", "Severe", "Proliferative"];
const FOLLOWUP: Record<string, string> = {
  pending: "Pending",
  referred: "Referred",
  seen_by_doctor: "Seen by doctor",
  not_required: "Not required",
  lost: "Lost to follow-up",
};

export default function DashboardPage() {
  return (
    <RequireRole roles={["admin", "hospital", "doctor"]}>
      <Dashboard />
    </RequireRole>
  );
}

const SCOPE_TEXT = {
  admin: "All records from every hospital (administrator view).",
  hospital: "Screenings performed at your hospital, by you or your doctors.",
  doctor: "Screenings you performed.",
  patient: "",
};

function Dashboard() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const showDoctor = user?.role !== "doctor";
  const [stats, setStats] = useState<Stats | null>(null);
  const [rows, setRows] = useState<ScreeningRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "refer" | "pending">("all");

  const load = useCallback(() => {
    Promise.all([api.stats(), api.screenings()])
      .then(([s, r]) => {
        setStats(s);
        setRows(r);
        setError(null);
      })
      .catch((e) => setError((e as Error).message));
  }, []);
  useEffect(load, [load]);

  const shown = rows.filter((r) => (filter === "refer" ? r.refer : filter === "pending" ? r.followup === "pending" : true));

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <h1 className="text-3xl font-bold">{isAdmin ? "All records" : "Screening dashboard"}</h1>
      <p className="mt-2 text-slate-400">{user ? SCOPE_TEXT[user.role] : ""} Volume, referral rate and follow-up status.</p>

      {error && <p className="mt-5 rounded-lg bg-red-500/10 p-3 text-sm text-red-300">Could not load records: {error}</p>}

      {stats && (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatTile label="Screenings" value={stats.total} />
            <StatTile label="Referred" value={stats.referred} sub={`${(stats.referral_rate * 100).toFixed(0)}% referral rate`} />
            <StatTile label="Pending follow-up" value={stats.followup.pending ?? 0} />
            <StatTile label="Poor-quality images" value={stats.poor_quality} sub="retake advised" />
          </div>

          {stats.total === 0 ? (
            <div className="card mt-6 text-center text-slate-400">
              No screenings yet.{" "}
              <Link href="/screening" className="text-cyan-400 underline">
                Screen the first patient
              </Link>
              .
            </div>
          ) : (
            <div className="mt-6 grid gap-6 lg:grid-cols-[1.6fr_1fr]">
              <div className="card">
                <div className="mb-1 font-semibold">Screenings per day</div>
                <Legend
                  items={[
                    { label: "Screenings", color: "var(--series-1)" },
                    { label: "Referrals", color: "var(--series-2)" },
                  ]}
                />
                <div className="mt-3 h-64">
                  <ResponsiveContainer>
                    <BarChart data={stats.by_day} barGap={2}>
                      <CartesianGrid {...gridProps} />
                      <XAxis dataKey="day" {...axisProps} tickFormatter={(d: string) => d.slice(5)} />
                      <YAxis {...axisProps} allowDecimals={false} width={30} />
                      <Tooltip {...tooltipProps} />
                      <Bar dataKey="screenings" name="Screenings" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={28} />
                      <Bar dataKey="referrals" name="Referrals" fill="var(--series-2)" radius={[4, 4, 0, 0]} maxBarSize={28} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
              <div className="card">
                <div className="mb-1 font-semibold">Predicted grade distribution</div>
                <div className="mt-3 h-64">
                  <ResponsiveContainer>
                    <BarChart data={stats.by_grade.map((n, g) => ({ grade: GRADES[g], n }))} layout="vertical">
                      <CartesianGrid {...gridProps} horizontal={false} vertical />
                      <XAxis type="number" {...axisProps} allowDecimals={false} />
                      <YAxis type="category" dataKey="grade" {...axisProps} width={90} />
                      <Tooltip {...tooltipProps} />
                      <Bar dataKey="n" name="Screenings" fill="var(--series-1)" radius={[0, 4, 4, 0]} maxBarSize={22} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}

          {stats.by_centre.length > 0 && (
            <div className="card mt-6 overflow-x-auto">
              <div className="mb-3 font-semibold">By health centre</div>
              <table className="tabular w-full text-sm">
                <thead className="text-left text-xs text-slate-400">
                  <tr>
                    <th className="py-2">Centre</th>
                    <th className="py-2 text-right">Screenings</th>
                    <th className="py-2 text-right">Referrals</th>
                    <th className="py-2 text-right">Referral rate</th>
                  </tr>
                </thead>
                <tbody>
                  {stats.by_centre.map((c) => (
                    <tr key={c.centre} className="border-t border-slate-800">
                      <td className="py-2">{c.centre}</td>
                      <td className="py-2 text-right">{c.screenings}</td>
                      <td className="py-2 text-right">{c.referrals}</td>
                      <td className="py-2 text-right">{((c.referrals / c.screenings) * 100).toFixed(0)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      {rows.length > 0 && (
        <div className="card mt-6 overflow-x-auto">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="font-semibold">Screening records</div>
            <div className="flex gap-1 rounded-lg border border-slate-800 p-1 text-xs">
              {(["all", "refer", "pending"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={`rounded-md px-3 py-1 ${filter === f ? "bg-slate-800 text-white" : "text-slate-400"}`}
                >
                  {f === "all" ? "All" : f === "refer" ? "Referred" : "Pending follow-up"}
                </button>
              ))}
            </div>
          </div>
          <table className="tabular w-full min-w-[960px] text-sm">
            <thead className="text-left text-xs text-slate-400">
              <tr>
                <th className="py-2">#</th>
                <th className="py-2">Date</th>
                <th className="py-2">Patient</th>
                <th className="py-2">Centre</th>
                {showDoctor && <th className="py-2">Screened by</th>}
                <th className="py-2">Grade</th>
                <th className="py-2 pr-6 text-right">Conf.</th>
                <th className="py-2">Decision</th>
                <th className="py-2">Follow-up</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id} className="border-t border-slate-800">
                  <td className="py-2 text-slate-500">{r.id}</td>
                  <td className="py-2 text-slate-300">{r.created_at.replace("T", " ").slice(0, 16)}</td>
                  <td className="py-2">
                    {r.patient_name || <span className="text-slate-500">—</span>}
                    {r.patient_age ? <span className="text-slate-500">, {r.patient_age}</span> : null}
                    {r.eye ? <span className="text-slate-500"> ({r.eye})</span> : null}
                    {r.patient_id ? (
                      <span title="Linked to a patient account – the patient can see this report">
                        <UserCheck className="ml-1 inline h-3.5 w-3.5 text-cyan-400" />
                      </span>
                    ) : null}
                  </td>
                  <td className="py-2 text-slate-300">{r.centre || "—"}</td>
                  {showDoctor && <td className="py-2 text-slate-300">{r.doctor_name || r.hospital_name || "Admin"}</td>}
                  <td className="py-2">{r.grade_name}</td>
                  <td className="py-2 pr-6 text-right">{(r.confidence * 100).toFixed(0)}%</td>
                  <td className="py-2">
                    {r.refer ? (
                      <span className="inline-flex items-center gap-1 text-red-300">
                        <ShieldAlert className="h-4 w-4" style={{ color: "var(--critical)" }} /> Refer
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-green-300">
                        <CheckCircle2 className="h-4 w-4" style={{ color: "var(--good)" }} /> Routine
                      </span>
                    )}
                  </td>
                  <td className="py-2">
                    <select
                      value={r.followup}
                      onChange={(e) => api.setFollowup(r.id, e.target.value).then(load)}
                      className="rounded-md border border-slate-700 bg-slate-950 px-2 py-1 text-xs"
                    >
                      {Object.entries(FOLLOWUP).map(([k, v]) => (
                        <option key={k} value={k}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="py-2">
                    <div className="flex justify-end gap-2">
                      <Link href={`/records/${r.id}`} title="Open" className="text-slate-300 hover:text-white">
                        <Eye className="h-4 w-4" />
                      </Link>
                      <button
                        title="PDF report"
                        className="text-cyan-400 hover:text-cyan-300"
                        onClick={() => openReport(r.id).catch((e) => alert((e as Error).message))}
                      >
                        <FileDown className="h-4 w-4" />
                      </button>
                      {isAdmin && (
                        <button
                          title="Delete (admin only)"
                          className="text-slate-500 hover:text-red-400"
                          onClick={() => confirmDelete(r.id) && api.remove(r.id).then(load)}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}

function confirmDelete(id: number) {
  return window.confirm(`Delete screening #${id}?`);
}
