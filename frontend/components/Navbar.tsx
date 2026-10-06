"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LogIn, LogOut } from "lucide-react";
import { ROLE_LABEL, useAuth } from "@/lib/auth";
import type { Role } from "@/types";

const LINKS: { href: string; label: string; roles: (Role | "public")[] }[] = [
  { href: "/", label: "Home", roles: ["public", "admin", "hospital", "doctor", "patient"] },
  { href: "/screening", label: "Screening", roles: ["doctor"] },
  { href: "/dashboard", label: "Dashboard", roles: ["admin", "hospital", "doctor"] },
  { href: "/reports", label: "My Reports", roles: ["patient"] },
  { href: "/users", label: "Users", roles: ["admin", "hospital"] },
  { href: "/model", label: "Model", roles: ["public", "admin", "hospital", "doctor", "patient"] },
];

export default function Navbar() {
  const path = usePathname();
  const router = useRouter();
  const { user, ready, logout } = useAuth();
  const role: Role | "public" = user?.role ?? "public";
  const links = LINKS.filter((l) => l.roles.includes(role));

  return (
    <header className="sticky top-0 z-30 border-b border-slate-800 bg-slate-950/85 backdrop-blur">
      <nav className="mx-auto flex max-w-7xl items-center gap-2 px-4 py-3 sm:gap-6 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold text-white">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/icon.svg" alt="" className="h-7 w-7" />
          <span className="hidden sm:inline">
            Retina<span className="text-cyan-400">AI</span>
          </span>
        </Link>
        <div className="flex flex-1 items-center gap-1 overflow-x-auto text-sm">
          {links.map((l) => {
            const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`whitespace-nowrap rounded-lg px-3 py-1.5 ${active ? "bg-slate-800 text-white" : "text-slate-400 hover:text-white"}`}
              >
                {l.label}
              </Link>
            );
          })}
        </div>
        {ready &&
          (user ? (
            <div className="flex items-center gap-3">
              <div className="hidden text-right leading-tight md:block">
                <div className="text-sm text-slate-100">{user.full_name}</div>
                <div className="text-xs text-cyan-400">{ROLE_LABEL[user.role]}</div>
              </div>
              <button
                onClick={async () => {
                  await logout();
                  router.replace("/login");
                }}
                className="flex items-center gap-1.5 rounded-lg border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:text-white"
                title="Log out"
              >
                <LogOut className="h-4 w-4" />
                <span className="hidden sm:inline">Log out</span>
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="flex items-center gap-1.5 rounded-lg bg-cyan-500 px-3 py-1.5 text-sm font-semibold text-slate-950 hover:bg-cyan-400"
            >
              <LogIn className="h-4 w-4" /> Log in
            </Link>
          ))}
      </nav>
    </header>
  );
}
