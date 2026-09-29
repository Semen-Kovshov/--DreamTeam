import type {
  ActionPayload, AdminScenarioRow, Brief, Debrief, GenerationForm, Health,
  Hint, HistoryRecord, Mode, ScenarioCard, StartPayload, TurnPayload,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body.detail) detail = String(body.detail);
    } catch {
      // тело не JSON — оставляем код
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<Health>("/api/health"),
  scenarios: () => request<ScenarioCard[]>("/api/scenarios"),
  scenarioBrief: (id: string) => request<Brief & { setting: string }>(
    `/api/scenarios/${id}/brief`),
  history: () => request<HistoryRecord[]>("/api/history"),
  start: (scenario_id: string, mode: Mode, use_llm: boolean) =>
    request<StartPayload>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ scenario_id, mode, use_llm }),
    }),
  turn: (sessionId: string, text: string) =>
    request<TurnPayload>(`/api/sessions/${sessionId}/turns`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  action: (sessionId: string, action_id: string) =>
    request<ActionPayload>(`/api/sessions/${sessionId}/actions`, {
      method: "POST",
      body: JSON.stringify({ action_id }),
    }),
  hints: (sessionId: string) =>
    request<{ hints: Hint[] }>(`/api/sessions/${sessionId}/hints`),
  finish: (sessionId: string, action: "accept" | "leave") =>
    request<{ status: string }>(`/api/sessions/${sessionId}/finish`, {
      method: "POST",
      body: JSON.stringify({ action }),
    }),
  debrief: (sessionId: string) =>
    request<Debrief>(`/api/sessions/${sessionId}/debrief`),

  adminScenarios: () => request<AdminScenarioRow[]>("/api/admin/scenarios"),
  adminGenerate: (form: GenerationForm) =>
    request<{ draft: Record<string, unknown>; warnings: string[] }>(
      "/api/admin/scenarios/generate",
      { method: "POST", body: JSON.stringify(form) }),
  adminValidate: (scenario: unknown) =>
    request<{ ok: boolean; errors: string[]; card?: ScenarioCard }>(
      "/api/admin/scenarios/validate",
      { method: "POST", body: JSON.stringify({ scenario }) }),
  adminSave: (scenario: unknown, overwrite: boolean) =>
    request<{ ok: boolean; id: string }>(
      "/api/admin/scenarios",
      { method: "POST", body: JSON.stringify({ scenario, overwrite }) }),
  adminDelete: (id: string) =>
    request<{ ok: boolean }>(`/api/admin/scenarios/${id}`, { method: "DELETE" }),
};
