"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Trash2, UserPlus } from "lucide-react";
import { api } from "@/lib/api";
import { RequireRole, ROLE_LABEL, useAuth } from "@/lib/auth";
import type { Role, User } from "@/types";

export default function UsersPage() {
  return (
    <RequireRole roles={["admin", "hospital"]}>
      <Users />
    </RequireRole>
  );
}

const EMPTY = { role: "doctor" as Role, full_name: "", username: "", password: "", hospital_id: "", age: "", sex: "" };

function Users() {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const [users, setUsers] = useState<User[]>([]);
  const [hospitals, setHospitals] = useState<User[]>([]);
  const [f, setF] = useState(EMPTY);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [roleFilter, setRoleFilter] = useState<Role | "all">("all");

  const load = useCallback(() => {
    api.users().then(setUsers).catch((e) => setMsg({ ok: false, text: (e as Error).message }));
    if (isAdmin) api.users("hospital").then(setHospitals).catch(() => {});
  }, [isAdmin]);
  useEffect(load, [load]);

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setMsg(null);
    try {
      const role: Role = isAdmin ? f.role : "doctor";
      const u = await api.createUser({
        role,
        full_name: f.full_name,
        username: f.username,
        password: f.password,
        hospital_id: role === "doctor" && isAdmin ? Number(f.hospital_id) || null : null,
        age: f.age ? Number(f.age) : null,
        sex: f.sex || null,
      });
      setMsg({ ok: true, text: `Created ${ROLE_LABEL[u.role].toLowerCase()} account @${u.username}` });
      setF({ ...EMPTY, role: f.role, hospital_id: f.hospital_id });
      load();
    } catch (err) {
      setMsg({ ok: false, text: (err as Error).message });
    } finally {
      setBusy(false);
    }
  }

  async function remove(u: User) {
    if (!window.confirm(`Delete ${u.full_name} (@${u.username})? Their past screenings are kept.`)) return;
    try {
      await api.deleteUser(u.id);
      load();
    } catch (err) {
      setMsg({ ok: false, text: (err as Error).message });
    }
  }

  const shown = users.filter((u) => roleFilter === "all" || u.role === roleFilter);
  const newRole: Role = isAdmin ? f.role : "doctor";

  return (
    <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
      <h1 className="text-3xl font-bold">{isAdmin ? "Users" : "Doctors at your hospital"}</h1>
      <p className="mt-2 text-slate-400">
        {isAdmin
          ? "Create and remove accounts. Patients can also register themselves."
          : "Add the doctors who work at your hospital. Their screenings appear in your dashboard."}
      </p>

      <div className="mt-6 grid gap-6 lg:grid-cols-[1fr_1.6fr]">
        <form onSubmit={create} className="card space-y-4 self-start">
          <div className="label">Add account</div>
          {isAdmin && (
            <Field label="Role">
              <select className="input" value={f.role} onChange={set("role")}>
                <option value="doctor">Doctor</option>
                <option value="hospital">Hospital</option>
                <option value="patient">Patient</option>
                <option value="admin">Admin</option>
              </select>
            </Field>
          )}
          {isAdmin && newRole === "doctor" && (
            <Field label="Hospital">
              <select className="input" value={f.hospital_id} onChange={set("hospital_id")} required>
                <option value="">Choose a hospital…</option>
                {hospitals.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.full_name}
                  </option>
                ))}
              </select>
            </Field>
          )}
          <Field label={newRole === "hospital" ? "Hospital / centre name" : "Full name"}>
            <input
              className="input"
              value={f.full_name}
              onChange={set("full_name")}
              required
              minLength={2}
              placeholder={newRole === "hospital" ? "e.g. PHC Rampur" : newRole === "doctor" ? "e.g. Dr. Anjali Sharma" : ""}
            />
          </Field>
          <Field label="Username">
            <input className="input" value={f.username} onChange={set("username")} required minLength={3} pattern="[A-Za-z0-9_.\-]+" />
          </Field>
          <Field label="Password (min 6 characters)">
            <input className="input" type="password" value={f.password} onChange={set("password")} required minLength={6} />
          </Field>
          {newRole === "patient" && (
            <div className="grid grid-cols-2 gap-4">
              <Field label="Age">
                <input className="input" type="number" min={0} max={120} value={f.age} onChange={set("age")} />
              </Field>
              <Field label="Sex">
                <select className="input" value={f.sex} onChange={set("sex")}>
                  <option value="">—</option>
                  <option value="M">Male</option>
                  <option value="F">Female</option>
                  <option value="O">Other</option>
                </select>
              </Field>
            </div>
          )}
          {msg && (
            <p className={`rounded-lg p-3 text-sm ${msg.ok ? "bg-green-500/10 text-green-300" : "bg-red-500/10 text-red-300"}`}>{msg.text}</p>
          )}
          <button
            disabled={busy}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-500 px-6 py-3 font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-50"
          >
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />} Create {ROLE_LABEL[newRole].toLowerCase()}
          </button>
        </form>

        <div className="card overflow-x-auto">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
            <div className="font-semibold">{shown.length} account{shown.length === 1 ? "" : "s"}</div>
            {isAdmin && (
              <div className="flex gap-1 rounded-lg border border-slate-800 p-1 text-xs">
                {(["all", "admin", "hospital", "doctor", "patient"] as const).map((r) => (
                  <button
                    key={r}
                    onClick={() => setRoleFilter(r)}
                    className={`rounded-md px-3 py-1 ${roleFilter === r ? "bg-slate-800 text-white" : "text-slate-400"}`}
                  >
                    {r === "all" ? "All" : ROLE_LABEL[r]}
                  </button>
                ))}
              </div>
            )}
          </div>
          <table className="w-full min-w-[560px] text-sm">
            <thead className="text-left text-xs text-slate-400">
              <tr>
                <th className="py-2">Name</th>
                <th className="py-2">Username</th>
                <th className="py-2">Role</th>
                <th className="py-2">Hospital</th>
                <th className="py-2">Created</th>
                <th className="py-2" />
              </tr>
            </thead>
            <tbody>
              {shown.map((u) => (
                <tr key={u.id} className="border-t border-slate-800">
                  <td className="py-2">{u.full_name}</td>
                  <td className="py-2 text-slate-400">@{u.username}</td>
                  <td className="py-2">
                    <span className="rounded-full border border-slate-700 px-2 py-0.5 text-xs">{ROLE_LABEL[u.role]}</span>
                  </td>
                  <td className="py-2 text-slate-400">{u.hospital_name || "—"}</td>
                  <td className="py-2 text-slate-500">{u.created_at.slice(0, 10)}</td>
                  <td className="py-2 text-right">
                    {u.id !== user?.id && (
                      <button title="Delete account" onClick={() => remove(u)} className="text-slate-500 hover:text-red-400">
                        <Trash2 className="h-4 w-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs text-slate-400">{label}</span>
      {children}
    </label>
  );
}
