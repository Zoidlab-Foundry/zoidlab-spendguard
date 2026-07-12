async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { ...init, credentials: "include", headers: { "Content-Type": "application/json", ...(init?.headers || {}) } });
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try { detail = (await r.json()).detail || detail; } catch {}
    const e = new Error(detail) as Error & { status?: number }; e.status = r.status; throw e;
  }
  return r.json();
}
const qs = (q: Record<string, string>) => { const s = new URLSearchParams(Object.entries(q).filter(([, v]) => v)).toString(); return s ? "?" + s : ""; };

export const api = {
  entitlements: () => req<any>("/api/auth/entitlements"),
  stats: () => req<any>("/api/stats"),
  meta: () => req<{ price_snapshot: string; prices: any[]; group_by: string[]; budget_scopes: string[]; budget_periods: string[] }>("/api/meta"),

  projects: () => req<{ projects: any[] }>("/api/projects").then((d) => d.projects),
  createProject: (b: any) => req<any>("/api/projects", { method: "POST", body: JSON.stringify(b) }),

  events: (q: Record<string, string> = {}) => req<{ events: any[] }>(`/api/events${qs(q)}`).then((d) => d.events),
  ingest: (b: any) => req<any>("/api/events", { method: "POST", body: JSON.stringify(b) }),

  breakdown: (q: Record<string, string> = {}) => req<any>(`/api/breakdown${qs(q)}`),
  series: (q: Record<string, string> = {}) => req<any>(`/api/series${qs(q)}`),
  simulate: (b: any) => req<any>("/api/simulate", { method: "POST", body: JSON.stringify(b) }),
  recommendations: (q: Record<string, string> = {}) => req<any>(`/api/recommendations${qs(q)}`),

  budgets: () => req<{ budgets: any[] }>("/api/budgets").then((d) => d.budgets),
  createBudget: (b: any) => req<any>("/api/budgets", { method: "POST", body: JSON.stringify(b) }),
  updateBudget: (id: string, b: any) => req<any>(`/api/budgets/${id}`, { method: "PUT", body: JSON.stringify(b) }),
  deleteBudget: (id: string) => req<any>(`/api/budgets/${id}`, { method: "DELETE" }),

  exportJsonUrl: (projectId?: string) => `/api/export/json${projectId ? "?project_id=" + projectId : ""}`,
  exportYamlUrl: (projectId?: string) => `/api/export/yaml${projectId ? "?project_id=" + projectId : ""}`,
};

export const usd = (n: number) => "$" + (n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const usd4 = (n: number) => "$" + (n ?? 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
export const num = (n: number) => (n ?? 0).toLocaleString();
