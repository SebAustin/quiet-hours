import type { State } from "./types";

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/${path}`, { ...init, headers: { "content-type": "application/json", ...(init?.headers || {}) }, cache: "no-store" });
  const data = await res.json();
  if (!res.ok) throw new Error(data?.error || `Request failed (${res.status})`);
  return data as T;
}

export const api = {
  state: () => call<State>("state"),
  decide: (id: string, choice: "approve" | "deny" | "trust") => call<{ ok: boolean; error?: string }>(`decisions/${id}`, { method: "POST", body: JSON.stringify({ choice }) }),
  sweep: () => call<{ ok: boolean; digest?: { narrative: string } }>("sweep", { method: "POST" }),
  simulate: (action: "advance" | "reset" | "status") => call<{ ok: boolean; day: number; arrived?: string[] }>("simulate", { method: "POST", body: JSON.stringify({ action }) }),
  chat: (prompt: string) => call<{ ok: boolean; response?: string; error?: string }>("chat", { method: "POST", body: JSON.stringify({ prompt }) }),
};
