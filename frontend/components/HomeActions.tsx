"use client";

import Link from "next/link";
import { ROLE_LABEL, useAuth } from "@/lib/auth";
import type { Role } from "@/types";

type Action = { href: string; label: string };

/** Buttons under the hero text – different for each kind of account. */
const ACTIONS: Record<Role | "guest", Action[]> = {
  guest: [
    { href: "/login", label: "Log in" },
    { href: "/register", label: "Register as patient" },
    { href: "/model", label: "How the model performs" },
  ],
  doctor: [
    { href: "/screening", label: "Start screening" },
    { href: "/dashboard", label: "My screenings" },
    { href: "/model", label: "Model performance" },
  ],
  hospital: [
    { href: "/dashboard", label: "Hospital dashboard" },
    { href: "/users", label: "Manage doctors" },
    { href: "/model", label: "Model performance" },
  ],
  admin: [
    { href: "/dashboard", label: "All records" },
    { href: "/users", label: "Manage users" },
    { href: "/model", label: "Model performance" },
  ],
  patient: [
    { href: "/reports", label: "View my reports" },
    { href: "/model", label: "How the model works" },
  ],
};

const primary = "rounded-xl bg-cyan-500 px-6 py-3 text-center font-semibold text-slate-950 transition hover:bg-cyan-400";
const secondary =
  "rounded-xl border border-slate-700 px-6 py-3 text-center font-semibold text-slate-100 transition hover:border-slate-500 hover:bg-slate-900";

export default function HomeActions() {
  const { user, ready } = useAuth();
  // keep the space reserved while we check the login, so the page doesn't jump
  if (!ready) return <div className="mt-10 h-12" />;
  const actions = ACTIONS[user?.role ?? "guest"];

  return (
    <div className="mt-10">
      {user && (
        <p className="mb-4 text-sm text-slate-400">
          Signed in as <span className="text-slate-200">{user.full_name}</span>{" "}
          <span className="rounded-full border border-cyan-500/40 px-2 py-0.5 text-xs text-cyan-400">{ROLE_LABEL[user.role]}</span>
        </p>
      )}
      <div className="flex flex-col gap-4 sm:flex-row">
        {actions.map((a, i) => (
          <Link key={a.href} href={a.href} className={i === 0 ? primary : secondary}>
            {a.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
