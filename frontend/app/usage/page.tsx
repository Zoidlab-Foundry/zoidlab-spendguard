"use client";
import { useEffect, useState } from "react";
import { api, usd4, num } from "../../lib/api";

export default function Usage() {
  const [events, setEvents] = useState<any[]>([]);
  const [prices, setPrices] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [form, setForm] = useState({ model: "gpt-4o", app: "", feature: "", prompt_tokens: "1200", completion_tokens: "400" });

  const load = () => api.events({}).then(setEvents).catch(() => {});
  useEffect(() => { load(); api.meta().then((m) => setPrices(m.prices)).catch(() => {}); }, []);

  async function submit() {
    setBusy(true); setErr("");
    try {
      await api.ingest({ model: form.model, app: form.app, feature: form.feature,
        prompt_tokens: parseInt(form.prompt_tokens) || 0, completion_tokens: parseInt(form.completion_tokens) || 0, source: "manual" });
      setOpen(false); load();
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  }

  return (
    <div className="py-8">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-[24px] font-semibold">Usage Ledger</h1>
          <p className="mt-1 text-[13px] text-dim">Every recorded AI call. Cost is computed server-side from tokens × list price.</p>
        </div>
        <button onClick={() => setOpen(true)} className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90">+ Record event</button>
      </div>

      <div className="mt-5 overflow-x-auto rounded-2xl border border-line bg-panel">
        <table className="w-full text-[12.5px]">
          <thead><tr className="border-b border-line text-left text-[11px] uppercase tracking-wider text-faint">
            <th className="px-4 py-3 font-medium">When</th><th className="px-4 py-3 font-medium">Model</th>
            <th className="px-4 py-3 font-medium">App / Feature</th><th className="px-4 py-3 font-medium">Prompt</th>
            <th className="px-4 py-3 font-medium">Completion</th><th className="px-4 py-3 font-medium">Cost</th>
            <th className="px-4 py-3 font-medium">Source</th>
          </tr></thead>
          <tbody>
            {events.slice(0, 150).map((e) => (
              <tr key={e.id} className="border-b border-line/60 last:border-0">
                <td className="px-4 py-2 text-dim">{(e.occurred_at || "").slice(0, 16).replace("T", " ")}</td>
                <td className="px-4 py-2 text-ink">{e.model}{e.cost_usd === 0 && <span className="ml-1 rounded bg-warn/10 px-1 text-[10px] text-warn">unpriced</span>}</td>
                <td className="px-4 py-2 text-dim">{e.app}{e.feature ? ` · ${e.feature}` : ""}</td>
                <td className="px-4 py-2 tnum text-dim">{num(e.prompt_tokens)}</td>
                <td className="px-4 py-2 tnum text-dim">{num(e.completion_tokens)}</td>
                <td className="px-4 py-2 tnum text-ink">{usd4(e.cost_usd)}</td>
                <td className="px-4 py-2"><span className={`rounded-full px-2 py-0.5 text-[10.5px] ${e.source === "sample" ? "bg-warn/10 text-warn" : "bg-white/5 text-dim"}`}>{e.source}</span></td>
              </tr>
            ))}
            {!events.length && <tr><td colSpan={7} className="px-4 py-10 text-center text-[13px] text-faint">No events yet.</td></tr>}
          </tbody>
        </table>
      </div>

      {open && (
        <div className="fixed inset-0 z-40 grid place-items-center bg-black/60 p-4" onClick={() => setOpen(false)}>
          <div className="w-full max-w-md rounded-2xl border border-line bg-panel p-5" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-[16px] font-semibold">Record a usage event</h2>
            <div className="mt-4 space-y-3">
              <label className="block text-[12px] text-dim">Model
                <select value={form.model} onChange={(e) => setForm({ ...form, model: e.target.value })} className="mt-1 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-[13px] text-ink">
                  {prices.map((p) => <option key={p.model} value={p.model}>{p.model} (${p.input_per_m}/${p.output_per_m} per 1M)</option>)}
                </select>
              </label>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-[12px] text-dim">App<input value={form.app} onChange={(e) => setForm({ ...form, app: e.target.value })} className="mt-1 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-[13px] text-ink" placeholder="support-bot" /></label>
                <label className="block text-[12px] text-dim">Feature<input value={form.feature} onChange={(e) => setForm({ ...form, feature: e.target.value })} className="mt-1 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-[13px] text-ink" placeholder="summarize" /></label>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="block text-[12px] text-dim">Prompt tokens<input value={form.prompt_tokens} onChange={(e) => setForm({ ...form, prompt_tokens: e.target.value })} className="mt-1 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-[13px] text-ink tnum" /></label>
                <label className="block text-[12px] text-dim">Completion tokens<input value={form.completion_tokens} onChange={(e) => setForm({ ...form, completion_tokens: e.target.value })} className="mt-1 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-[13px] text-ink tnum" /></label>
              </div>
            </div>
            {err && <p className="mt-2 text-[12px] text-bad">{err}</p>}
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setOpen(false)} className="rounded-lg border border-line px-4 py-2 text-[13px] text-dim hover:text-ink">Cancel</button>
              <button onClick={submit} disabled={busy} className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50">{busy ? "Recording…" : "Record"}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
