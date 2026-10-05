import type { ModelInfo, ScreeningResult, ScreeningRow, Stats } from "@/types";

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {}
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () =>
    fetch(`${API_URL}/api/health`, { cache: "no-store" }).then((r) =>
      json<{ status: string; model_loaded: boolean; error: string | null; device: string | null; model_version: string | null }>(r),
    ),
  screen: (form: FormData) => fetch(`${API_URL}/api/screen`, { method: "POST", body: form }).then((r) => json<ScreeningResult>(r)),
  screenings: () => fetch(`${API_URL}/api/screenings`, { cache: "no-store" }).then((r) => json<ScreeningRow[]>(r)),
  stats: () => fetch(`${API_URL}/api/stats`, { cache: "no-store" }).then((r) => json<Stats>(r)),
  setFollowup: (id: number, status: string) =>
    fetch(`${API_URL}/api/screenings/${id}/followup`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }).then((r) => json<{ ok: boolean }>(r)),
  remove: (id: number) => fetch(`${API_URL}/api/screenings/${id}`, { method: "DELETE" }).then((r) => json<{ ok: boolean }>(r)),
  model: () => fetch(`${API_URL}/api/model`, { cache: "no-store" }).then((r) => json<ModelInfo>(r)),
  reportUrl: (id: number) => `${API_URL}/api/report/${id}`,
};
