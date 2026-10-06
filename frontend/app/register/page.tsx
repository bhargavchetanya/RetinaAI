"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Loader2, UserPlus } from "lucide-react";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [f, setF] = useState({ full_name: "", username: "", password: "", confirm: "", age: "", sex: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (f.password !== f.confirm) return setError("Passwords do not match");
    setBusy(true);
    setError(null);
    try {
      await register({
        full_name: f.full_name,
        username: f.username,
        password: f.password,
        age: f.age ? Number(f.age) : null,
        sex: f.sex || null,
      });
      router.replace("/reports");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto flex max-w-md flex-col px-4 py-12 sm:px-6">
      <h1 className="text-3xl font-bold">Create a patient account</h1>
      <p className="mt-2 text-slate-400">
        Your doctor links your eye screenings to this account, and you can see your reports anytime.
      </p>
      <form onSubmit={submit} className="card mt-6 space-y-4">
        <Field label="Full name">
          <input className="input" value={f.full_name} onChange={set("full_name")} required minLength={2} />
        </Field>
        <Field label="Username (letters, numbers, . _ -)">
          <input className="input" value={f.username} onChange={set("username")} required minLength={3} pattern="[A-Za-z0-9_.\-]+" />
        </Field>
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
        <Field label="Password (min 6 characters)">
          <input className="input" type="password" value={f.password} onChange={set("password")} required minLength={6} />
        </Field>
        <Field label="Confirm password">
          <input className="input" type="password" value={f.confirm} onChange={set("confirm")} required />
        </Field>
        {error && <p className="rounded-lg bg-red-500/10 p-3 text-sm text-red-300">{error}</p>}
        <button
          disabled={busy}
          className="flex w-full items-center justify-center gap-2 rounded-xl bg-cyan-500 px-6 py-3 font-semibold text-slate-950 hover:bg-cyan-400 disabled:opacity-50"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />} Create account
        </button>
        <p className="text-center text-sm text-slate-400">
          Already registered?{" "}
          <Link href="/login" className="text-cyan-400 hover:underline">
            Sign in
          </Link>
        </p>
      </form>
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
