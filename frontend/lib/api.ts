import type { ModelInfo, ScreeningResult, ScreeningRow, Stats, User } from "@/types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "retina-token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(t: string | null) {
  try {
    if (t) localStorage.setItem(TOKEN_KEY, t);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {}
}

/** fetch wrapper: adds the login token and turns API errors into readable messages. */
async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
  const res = await fetch(`${API_URL}${path}`, { ...init, headers, cache: "no-store" });
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") msg = body.detail;
      else if (Array.isArray(body?.detail)) msg = body.detail.map((d: { msg: string }) => d.msg).join("; ");
    } catch {}
    if (res.status === 401 && typeof window !== "undefined") window.dispatchEvent(new Event("retina-unauthorized"));
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

const post = (body: unknown) => ({ method: "POST", body: JSON.stringify(body) });

export interface ChatReply {
  answer: string;
  suggestions?: string[];
  score?: number;
}

export const api = {
  health: () =>
    call<{ status: string; model_loaded: boolean; error: string | null; device: string | null; model_version: string | null }>(
      "/api/health",
    ),
  // auth
  login: (username: string, password: string) => call<{ token: string; user: User }>("/api/auth/login", post({ username, password })),
  register: (b: { username: string; password: string; full_name: string; age?: number | null; sex?: string | null }) =>
    call<{ token: string; user: User }>("/api/auth/register", post(b)),
  me: () => call<User>("/api/auth/me"),
  logout: () => call<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),
  // users
  users: (role?: string) => call<User[]>(`/api/users${role ? `?role=${role}` : ""}`),
  createUser: (b: Record<string, unknown>) => call<User>("/api/users", post(b)),
  deleteUser: (id: number) => call<{ ok: boolean }>(`/api/users/${id}`, { method: "DELETE" }),
  patients: () => call<Pick<User, "id" | "username" | "full_name" | "age" | "sex">[]>("/api/patients"),
  // screenings
  screen: (form: FormData) => call<ScreeningResult>("/api/screen", { method: "POST", body: form }),
  screenings: () => call<ScreeningRow[]>("/api/screenings"),
  screening: (id: number) => call<ScreeningRow & { result: ScreeningResult }>(`/api/screenings/${id}`),
  stats: () => call<Stats>("/api/stats"),
  setFollowup: (id: number, status: string) =>
    call<{ ok: boolean }>(`/api/screenings/${id}/followup`, { method: "PATCH", body: JSON.stringify({ status }) }),
  remove: (id: number) => call<{ ok: boolean }>(`/api/screenings/${id}`, { method: "DELETE" }),
  model: () => call<ModelInfo>("/api/model"),
  chat: (message: string) => call<ChatReply>("/api/chat", post({ message })),
};

/** The PDF endpoint needs the login token, so fetch it and save the blob as a file. */
export async function openReport(id: number) {
  const res = await fetch(`${API_URL}/api/report/${id}`, { headers: { Authorization: `Bearer ${getToken() ?? ""}` } });
  if (!res.ok) throw new Error("Could not load the report");
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = `retinaai_report_${id}.pdf`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
