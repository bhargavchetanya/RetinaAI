"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useLang } from "@/lib/i18n";

export default function Navbar() {
  const path = usePathname();
  const { t } = useLang();
  const links = [
    { href: "/", label: t("nav_home") },
    { href: "/screening", label: t("nav_screen") },
    { href: "/dashboard", label: t("nav_dashboard") },
    { href: "/model", label: t("nav_model") },
  ];
  return (
    <header className="sticky top-0 z-30 border-b border-slate-800 bg-slate-950/85 backdrop-blur">
      <nav className="mx-auto flex max-w-7xl items-center gap-2 px-4 py-3 sm:gap-6 sm:px-6">
        <Link href="/" className="flex items-center gap-2 font-semibold text-white">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/icon.svg" alt="" className="h-7 w-7" />
          <span>
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
      </nav>
    </header>
  );
}
