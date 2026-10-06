"use client";

import { Suspense, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Building2, Loader2, LogIn, ShieldCheck, Stethoscope, User as UserIcon } from "lucide-react";
import { HOME_FOR, ROLE_LABEL, useAuth } from "@/lib/auth";
import type { Role } from "@/types";

const ROLES: { role: Role; icon: React.ElementType; text: string; demo: [string, string] }[] = [
  { role: "patient", icon: UserIcon, text: "See your own eye-screening reports", demo: ["patient1", "patient123"] },
  { role: "doctor", icon: Stethoscope, text: "Screen patients and review your cases", demo: ["doctor1", "doctor123"] },
  { role: "hospital", icon: Building2, text: "All screenings at your centre, manage doctors", demo: ["hospital1", "hospital123"] },
  { role: "admin", icon: ShieldCheck, text: "All records and all user accounts", demo: ["admin", "admin123"] },
];

function LoginForm() {
  const { login } = useAuth();
  const router = useRouter();
  const next = useSearchParams().get("next");
  const [role, setRole] = useState<Role>("patient");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const active = ROLES.find((r) => r.role === role)!;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await login(username, password);
      if (u.role !== role) {
        // logged in fine, but with a different kind of account than the selected tab
        setRole(u.role);
      }
      router.replace(next && next !== "/login" ? next : HOME_FOR[u.role]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-5xl flex-col items-center px-4 py-12 sm:px-6">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src="/icon.svg" alt="" className="h-14 w-14" />
      <h1 className="mt-4 text-3xl font-bold">Sign in to RetinaAI</h1>
      <p className="mt-2 text-slate-400">Choose who you are</p>

      <div className="mt-8 grid w-full gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {ROLES.map(({ role: r, icon: Icon, text }) => (
          <button
            key={r}
            type="button"
            onClick={() => {
              setRole(r);
              setError(null);
            }}
            className={`rounded-2xl border p-4 text-left transition ${
              role === r ? "border-cyan-400 bg-cyan-500/10" : "border-slate-800 bg-slate-900/70 hover:border-slate-600"
            }`}
          >
            <Icon className={`h-6 w-6 ${role === r ? "text-cyan-400" : "text-slate-400"}`} />
            <div className="mt-2 font-semibold">{ROLE_LABEL[r]}</div>
            <div className="mt-1 text-xs text-slate-400">{text}</div>
          </button>
        ))}
      </div>

      <form onSubmit={submit} className="card mt-6 w-full max-w-md space-y-4">
        <div className="label">{ROLE_LABEL[role]} login</div>
        <label className="block">
          <span className="mb-1 block text-xs text-slate-400">Username</span>
          <input className="input" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-slate-400">Password</span>
          <input
            className="input"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && <p className="rounded-lg bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
        <button
          disabled={busy}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-500 px-6 py-3 font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />} Sign in
        </button>

        <button
          type="button"
          onClick={() => {
            setUsername(active.demo[0]);
            setPassword(active.demo[1]);
          }}
          className="w-full rounded-lg border border-dashed border-slate-700 px-3 py-2 text-xs text-slate-400 hover:text-white"
        >
          Use demo {ROLE_LABEL[role].toLowerCase()} account ({active.demo[0]} / {active.demo[1]})
        </button>

        {role === "patient" && (
          <p className="text-center text-sm text-slate-400">
            New patient?{" "}
            <Link href="/register" className="text-cyan-400 hover:underline">
              Create an account
            </Link>
          </p>
        )}
        {role !== "patient" && (
          <p className="text-center text-xs text-slate-500">
            {role === "admin" ? "Admin accounts are created by an existing admin." : "Staff accounts are created by the hospital or the administrator."}
          </p>
        )}
      </form>
    </main>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
