"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { api, usd, num } from "../lib/api";

function Stat({ label, value, sub, accent }: { label: string; value: string; sub?: string; accent?: boolean }) {
  return (
    <div className="rounded-2xl border border-line bg-panel p-4">
      <div className="text-[11px] uppercase tracking-wider text-faint">{label}</div>
      <div className={`mt-1.5 text-[26px] font-semibold tnum ${accent ? "text-vi" : "text-ink"}`}>{value}</div>
      {sub && <div className="mt-0.5 text-[12px] text-dim">{sub}</div>}
    </div>
  );
}

function Spark({ series }: { series: { date: string; cost_usd: number }[] }) {
  if (!series.length) return <div className="flex h-[120px] items-center justify-center text-[12px] text-faint">No spend in window.</div>;
  const max = Math.max(...series.map((s) => s.cost_usd), 0.0001);
  return (
    <div className="mt-1">
      <div className="flex h-[120px] items-end gap-[3px]">
        {series.map((s) => (
          <div key={s.date} className="group relative flex-1" title={`${s.date}: ${usd(s.cost_usd)}`}>
            <div className="w-full rounded-t bg-vi/70 transition group-hover:bg-vi" style={{ height: `${Math.max((s.cost_usd / max) * 116, 2)}px` }} />
          </div>
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-faint"><span>{series[0]?.date}</span><span>{series[series.length - 1]?.date}</span></div>
    </div>
  );
}

export default function Dashboard() {
  const [s, setS] = useState<any>(null);
  const [series, setSeries] = useState<any[]>([]);
  const [models, setModels] = useState<any[]>([]);
  const [budgets, setBudgets] = useState<any[]>([]);
  const [recs, setRecs] = useState<any>(null);
  const [snapshot, setSnapshot] = useState("");
  const [sample, setSample] = useState(false);

  useEffect(() => {
    api.stats().then(setS).catch(() => {});
    api.series({ days: "30" }).then((d) => setSeries(d.series)).catch(() => {});
    api.breakdown({ group_by: "model" }).then((d) => setModels(d.rows.slice(0, 6))).catch(() => {});
    api.budgets().then(setBudgets).catch(() => {});
    api.recommendations().then(setRecs).catch(() => {});
    api.meta().then((m) => setSnapshot(m.price_snapshot)).catch(() => {});
    api.events({}).then((ev) => setSample(ev.some((e: any) => e.source === "sample"))).catch(() => {});
  }, []);

  const maxModel = Math.max(...models.map((m) => m.cost_usd), 0.0001);

  return (
    <div className="py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-[24px] font-semibold">AI Spend Overview</h1>
          <p className="mt-1 text-[13px] text-dim">Costs computed from recorded token counts against list prices{snapshot ? ` (snapshot ${snapshot})` : ""}.</p>
        </div>
        <Link href="/simulator" className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90">Run savings simulator →</Link>
      </div>

      {sample && (
        <div className="mt-4 rounded-xl border border-warn/30 bg-warn/5 px-4 py-2.5 text-[12.5px] text-warn">
          Showing <b>sample</b> usage data. Numbers are computed from synthetic token counts — POST real events to <code className="text-ink">/api/events</code> to replace it.
        </div>
      )}

      <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Total spend" value={usd(s?.total_spend_usd ?? 0)} sub={`${num(s?.events ?? 0)} calls · ${num(s?.total_tokens ?? 0)} tokens`} accent />
        <Stat label="Month to date" value={usd(s?.month_to_date_usd ?? 0)} sub="current calendar month" />
        <Stat label="Projected month" value={usd(s?.projected_month_usd ?? 0)} sub="linear run-rate" />
        <Stat label="Avg cost / call" value={"$" + (s?.avg_cost_per_call ?? 0).toFixed(4)} sub={`${num(s?.models_used ?? 0)} models used`} />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-[1.4fr_1fr]">
        <div className="rounded-2xl border border-line bg-panel p-5">
          <h2 className="text-[14px] font-semibold">Daily spend · last 30 days</h2>
          <Spark series={series} />
        </div>
        <div className="rounded-2xl border border-line bg-panel p-5">
          <div className="flex items-center justify-between"><h2 className="text-[14px] font-semibold">Spend by model</h2><Link href="/breakdown" className="text-[12px] text-cy hover:underline">All →</Link></div>
          <div className="mt-3 space-y-2.5">
            {models.map((m) => (
              <div key={m.key}>
                <div className="flex justify-between text-[12px]"><span className="text-dim">{m.key}</span><span className="tnum text-ink">{usd(m.cost_usd)} · {m.pct}%</span></div>
                <div className="mt-1 h-2 rounded bg-white/5"><div className="h-2 rounded bg-vi" style={{ width: `${(m.cost_usd / maxModel) * 100}%` }} /></div>
              </div>
            ))}
            {!models.length && <p className="text-[12px] text-faint">No usage yet.</p>}
          </div>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-line bg-panel p-5">
          <div className="flex items-center justify-between"><h2 className="text-[14px] font-semibold">Budgets</h2><Link href="/budgets" className="text-[12px] text-cy hover:underline">Manage →</Link></div>
          <div className="mt-3 space-y-3">
            {budgets.map((b) => (
              <div key={b.id}>
                <div className="flex justify-between text-[12.5px]"><span className="text-ink">{b.name}</span><span className="tnum text-dim">{usd(b.spent_usd)} / {usd(b.limit_usd)}</span></div>
                <div className="mt-1 h-2 rounded bg-white/5"><div className={`h-2 rounded ${b.state === "over" ? "bg-bad" : b.state === "alert" ? "bg-warn" : "bg-ok"}`} style={{ width: `${Math.min(b.pct_used, 100)}%` }} /></div>
              </div>
            ))}
            {!budgets.length && <p className="text-[12px] text-faint">No budgets set. <Link href="/budgets" className="text-cy hover:underline">Create one</Link>.</p>}
          </div>
        </div>
        <div className="rounded-2xl border border-line bg-panel p-5">
          <div className="flex items-center justify-between"><h2 className="text-[14px] font-semibold">Top recommendations</h2><Link href="/recommendations" className="text-[12px] text-cy hover:underline">All →</Link></div>
          {recs && <div className="mt-1 text-[12px] text-dim">Potential savings identified: <span className="font-semibold text-vi">{usd(recs.potential_savings_usd)}</span></div>}
          <div className="mt-3 space-y-2">
            {(recs?.recommendations || []).slice(0, 3).map((r: any, i: number) => (
              <div key={i} className="rounded-lg border border-line bg-panel2 p-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div className="text-[12.5px] font-medium text-ink">{r.title}</div>
                  {r.est_savings_usd > 0 && <span className="shrink-0 rounded-full bg-ok/10 px-2 py-0.5 text-[11px] text-ok tnum">save {usd(r.est_savings_usd)}</span>}
                </div>
              </div>
            ))}
            {!(recs?.recommendations || []).length && <p className="text-[12px] text-faint">No recommendations yet.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
