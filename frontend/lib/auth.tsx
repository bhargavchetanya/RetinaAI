"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, getToken, setToken } from "@/lib/api";
import type { Role, User } from "@/types";

interface AuthState {
  user: User | null;
  ready: boolean; // true once we know whether someone is logged in
  login: (username: string, password: string) => Promise<User>;
  register: (b: { username: string; password: string; full_name: string; age?: number | null; sex?: string | null }) => Promise<User>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export const ROLE_LABEL: Record<Role, string> = {
  admin: "Admin",
  hospital: "Hospital",
  doctor: "Doctor",
  patient: "Patient",
};

/** Where each role lands after logging in. */
export const HOME_FOR: Record<Role, string> = {
  admin: "/dashboard",
  hospital: "/dashboard",
  doctor: "/screening",
  patient: "/reports",
};

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      setReady(true);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setReady(true));
    const onUnauthorized = () => {
      setToken(null);
      setUser(null);
    };
    window.addEventListener("retina-unauthorized", onUnauthorized);
    return () => window.removeEventListener("retina-unauthorized", onUnauthorized);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const r = await api.login(username, password);
    setToken(r.token);
    setUser(r.user);
    return r.user;
  }, []);

  const register = useCallback(async (b: Parameters<AuthState["register"]>[0]) => {
    const r = await api.register(b);
    setToken(r.token);
    setUser(r.user);
    return r.user;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch {}
    setToken(null);
    setUser(null);
  }, []);

  return <Ctx.Provider value={{ user, ready, login, register, logout }}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth outside AuthProvider");
  return c;
}

/** Page guard: shows a spinner while checking, sends logged-out users to /login and
 *  users with the wrong role to their own home page. */
export function RequireRole({ roles, children }: { roles: Role[]; children: React.ReactNode }) {
  const { user, ready } = useAuth();
  const router = useRouter();
  const allowed = !!user && roles.includes(user.role);

  useEffect(() => {
    if (!ready) return;
    if (!user) router.replace(`/login?next=${encodeURIComponent(window.location.pathname)}`);
    else if (!roles.includes(user.role)) router.replace(HOME_FOR[user.role]);
  }, [ready, user, roles, router]);

  if (!ready || !allowed) {
    return <main className="mx-auto max-w-7xl px-4 py-16 text-center text-slate-500 sm:px-6">Checking access…</main>;
  }
  return <>{children}</>;
}
