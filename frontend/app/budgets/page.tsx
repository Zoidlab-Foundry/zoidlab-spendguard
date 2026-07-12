"use client";
import { useEffect, useState } from "react";
import { api, usd } from "../../lib/api";

export default function Budgets() {
  const [budgets, setBudgets] = useState<any[]>([]);
  const [meta, setMeta] = useState<any>(null);
  const [projects, setProjects] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [f, setF] = useState<any>({ name: "", scope: "global", scope_ref: "", period: "monthly", limit_usd: "100", alert_pct: "80" });

  const load = () => api.budgets().then(setBudgets).catch(() => {});
  useEffect(() => {
    load();
    api.meta().then(setMeta).catch(() => {});
    api.projects().then(setProjects).catch(() => {});
  }, []);

  async function create() {
    setBusy(true); setErr("");
    try {
      await api.createBudget({ name: f.name, scope: f.scope, scope_ref: f.scope_ref || null,
        period: f.period, limit_usd: parseFloat(f.limit_usd) || 0, alert_pct: parseInt(f.alert_pct) || 80 });
      setOpen(false); setF({ name: "", scope: "global", scope_ref: "", period: "monthly", limit_usd: "100", alert_pct: "80" }); load();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }
  async function remove(id: string) { await api.deleteBudget(id); load(); }

  const refOptions = f.scope === "model" ? (meta?.prices || []).map((p: any) => p.model)
    : f.scope === "project" ? projects.map((p) => p.id)
    : f.scope === "provider" ? Array.from(new Set((meta?.prices || []).map((p: any) => p.provider))) : [];

  return (
    <div className="py-8">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-[24px] font-semibold">Budgets</h1>
          <p className="mt-1 text-[13px] text-dim">Set spend caps by scope and period. Spend is summed live from the ledger for the current period.</p>
        </div>
        <button onClick={() => setOpen(true)} className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90">+ New budget</button>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {budgets.map((b) => (
          <div key={b.id} className="rounded-2xl border border-line bg-panel p-4">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[14px] font-semibold text-ink">{b.name}</div>
                <div className="mt-0.5 text-[11.5px] text-faint">{b.scope}{b.scope_ref ? ` · ${b.scope_ref}` : ""} · {b.period} · alert @ {b.alert_pct}%</div>
              </div>
              <button onClick={() => remove(b.id)} className="text-[11px] text-faint hover:text-bad">Delete</button>
            </div>
            <div className="mt-3 flex justify-between text-[12.5px]"><span className="tnum text-ink">{usd(b.spent_usd)}</span><span className="tnum text-dim">of {usd(b.limit_usd)}</span></div>
            <div className="mt-1 h-2.5 rounded bg-white/5"><div className={`h-2.5 rounded ${b.state === "over" ? "bg-bad" : b.state === "alert" ? "bg-warn" : "bg-ok"}`} style={{ width: `${Math.min(b.pct_used, 100)}%` }} /></div>
            <div className="mt-1.5 flex justify-between text-[11.5px]">
              <span className={b.state === "over" ? "text-bad" : b.state === "alert" ? "text-warn" : "text-ok"}>{b.pct_used}% used</span>
              <span className="text-faint">{usd(b.remaining_usd)} left</span>
            </div>
          </div>
        ))}
        {!budgets.length && <div className="col-span-2 rounded-2xl border border-dashed border-line py-14 text-center text-[13px] text-faint">No budgets yet.</div>}
      </div>

      {open && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/60 p-4" onClick={() => setOpen(false)}>
          <div className="w-full max-w-md rounded-2xl border border-line bg-panel p-5" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-[16px] font-semibold">New budget</h2>
            <div className="mt-4 space-y-3">
              <label className="block text-[12px] text-dim">Name<input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className="mt-1 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-[13px] text-ink" placeholder="Monthly AI budget" /></label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-[12px] text-dim">Scope
                  <select value={f.scope} onChange={(e) => setF({ ...f, scope: e.target.value, scope_ref: "" })} className="mt-1 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-[13px] text-ink">
                    {(meta?.budget_scopes || ["global", "project", "model", "provider"]).map((s: string) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </label>
                <label className="block text-[12px] text-dim">Period
                  <select value={f.period} onChange={(e) => setF({ ...f, period: e.target.value })} className="mt-1 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-[13px] text-ink">
                    {(meta?.budget_periods || ["daily", "weekly", "monthly"]).map((s: string) => <option key={s} value={s}>{s}</option>)}
                  </select>
                </label>
              </div>
              {f.scope !== "global" && (
                <label className="block text-[12px] text-dim">{f.scope} target
                  <select value={f.scope_ref} onChange={(e) => setF({ ...f, scope_ref: e.target.value })} className="mt-1 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-[13px] text-ink">
                    <option value="">— select —</option>
                    {refOptions.map((o: string) => <option key={o} value={o}>{f.scope === "project" ? (projects.find((p) => p.id === o)?.name || o) : o}</option>)}
                  </select>
                </label>
              )}
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-[12px] text-dim">Limit (USD)<input value={f.limit_usd} onChange={(e) => setF({ ...f, limit_usd: e.target.value })} className="mt-1 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-[13px] text-ink tnum" /></label>
                <label className="block text-[12px] text-dim">Alert at %<input value={f.alert_pct} onChange={(e) => setF({ ...f, alert_pct: e.target.value })} className="mt-1 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-[13px] text-ink tnum" /></label>
              </div>
            </div>
            {err && <p className="mt-2 text-[12px] text-bad">{err}</p>}
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setOpen(false)} className="rounded-lg border border-line px-4 py-2 text-[13px] text-dim hover:text-ink">Cancel</button>
              <button onClick={create} disabled={busy || !f.name} className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50">{busy ? "Creating…" : "Create"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
