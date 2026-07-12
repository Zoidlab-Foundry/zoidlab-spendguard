"use client";
import { useEffect, useState } from "react";
import { api, usd } from "../../lib/api";

export default function Simulator() {
  const [prices, setPrices] = useState<any[]>([]);
  const [models, setModels] = useState<string[]>([]);
  const [from, setFrom] = useState("gpt-4o");
  const [to, setTo] = useState("gpt-4o-mini");
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.meta().then((m) => setPrices(m.prices)).catch(() => {});
    api.breakdown({ group_by: "model" }).then((d) => setModels(d.rows.map((r: any) => r.key))).catch(() => {});
  }, []);

  async function run() {
    setBusy(true);
    try { setRes(await api.simulate({ from_model: from, to_model: to })); } finally { setBusy(false); }
  }

  const saving = res && !res.error && res.savings_usd > 0;
  const worse = res && !res.error && res.savings_usd < 0;

  return (
    <div className="py-8 max-w-[860px]">
      <h1 className="text-[24px] font-semibold">Savings Simulator</h1>
      <p className="mt-1 text-[13px] text-dim">Recompute your real historical token usage as if it had run on a different model. Exact arithmetic — not an estimate.</p>

      <div className="mt-5 rounded-2xl border border-line bg-panel p-5">
        <div className="grid gap-4 sm:grid-cols-[1fr_auto_1fr] sm:items-end">
          <label className="block text-[12px] text-dim">Currently using
            <select value={from} onChange={(e) => setFrom(e.target.value)} className="mt-1 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-[13px] text-ink">
              {(models.length ? models : prices.map((p) => p.model)).map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
          <div className="pb-2 text-center text-[18px] text-faint">→</div>
          <label className="block text-[12px] text-dim">Switch to
            <select value={to} onChange={(e) => setTo(e.target.value)} className="mt-1 w-full rounded-lg border border-line bg-panel2 px-3 py-2 text-[13px] text-ink">
              {prices.map((p) => <option key={p.model} value={p.model}>{p.model}</option>)}
            </select>
          </label>
        </div>
        <button onClick={run} disabled={busy} className="mt-4 rounded-lg bg-vi px-5 py-2 text-[13px] font-semibold text-white hover:opacity-90 disabled:opacity-50">{busy ? "Simulating…" : "Simulate"}</button>
      </div>

      {res?.error && <div className="mt-4 rounded-xl border border-bad/30 bg-bad/5 px-4 py-3 text-[13px] text-bad">{res.error}</div>}

      {res && !res.error && (
        <div className="mt-4 rounded-2xl border border-line bg-panel p-5">
          {res.events_considered === 0 ? (
            <p className="text-[13px] text-faint">No recorded events on <b className="text-dim">{res.from_model}</b> to simulate. Record some usage first.</p>
          ) : (
            <>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-xl bg-panel2 p-4"><div className="text-[11px] uppercase tracking-wider text-faint">Current</div><div className="mt-1 text-[22px] font-semibold tnum text-ink">{usd(res.current_cost_usd)}</div></div>
                <div className="rounded-xl bg-panel2 p-4"><div className="text-[11px] uppercase tracking-wider text-faint">Simulated</div><div className="mt-1 text-[22px] font-semibold tnum text-ink">{usd(res.simulated_cost_usd)}</div></div>
                <div className={`rounded-xl p-4 ${saving ? "bg-ok/10" : worse ? "bg-bad/10" : "bg-panel2"}`}><div className="text-[11px] uppercase tracking-wider text-faint">{saving ? "Savings" : worse ? "Extra cost" : "No change"}</div><div className={`mt-1 text-[22px] font-semibold tnum ${saving ? "text-ok" : worse ? "text-bad" : "text-ink"}`}>{usd(Math.abs(res.savings_usd))}</div><div className="text-[11px] text-dim">{res.savings_pct}%</div></div>
              </div>
              <p className="mt-3 text-[12px] text-faint">Based on <b className="text-dim">{res.events_considered}</b> recorded {res.from_model} calls. {res.note}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
