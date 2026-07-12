"use client";
import { useEffect, useState } from "react";
import { api, usd, num } from "../../lib/api";

const GROUPS = [
  { k: "model", label: "Model" }, { k: "provider", label: "Provider" },
  { k: "project", label: "Project" }, { k: "app", label: "App" }, { k: "feature", label: "Feature" },
];
const WINDOWS = [{ k: "", label: "All time" }, { k: "7", label: "7d" }, { k: "30", label: "30d" }, { k: "90", label: "90d" }];

export default function Breakdown() {
  const [group, setGroup] = useState("model");
  const [win, setWin] = useState("30");
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    api.breakdown({ group_by: group, ...(win ? { days: win } : {}) }).then(setData).catch(() => {});
  }, [group, win]);

  const max = Math.max(...(data?.rows || []).map((r: any) => r.cost_usd), 0.0001);

  return (
    <div className="py-8">
      <h1 className="text-[24px] font-semibold">Cost Breakdown</h1>
      <p className="mt-1 text-[13px] text-dim">Where the money goes, grouped and windowed. Every figure is summed from the usage ledger.</p>

      <div className="mt-4 flex flex-wrap items-center gap-2">
        <div className="flex rounded-lg border border-line bg-panel2 p-0.5">
          {GROUPS.map((g) => <button key={g.k} onClick={() => setGroup(g.k)} className={`rounded-md px-3 py-1.5 text-[12.5px] ${group === g.k ? "bg-vi text-white" : "text-dim hover:text-ink"}`}>{g.label}</button>)}
        </div>
        <div className="flex rounded-lg border border-line bg-panel2 p-0.5">
          {WINDOWS.map((w) => <button key={w.k} onClick={() => setWin(w.k)} className={`rounded-md px-3 py-1.5 text-[12.5px] ${win === w.k ? "bg-white/10 text-ink" : "text-dim hover:text-ink"}`}>{w.label}</button>)}
        </div>
        <div className="ml-auto text-[13px] text-dim">Total: <span className="font-semibold text-ink tnum">{usd(data?.total_usd ?? 0)}</span></div>
      </div>

      <div className="mt-4 overflow-x-auto rounded-2xl border border-line bg-panel">
        <table className="w-full text-[13px]">
          <thead><tr className="border-b border-line text-left text-[11px] uppercase tracking-wider text-faint">
            <th className="px-4 py-3 font-medium">{GROUPS.find((g) => g.k === group)?.label}</th>
            <th className="px-4 py-3 font-medium">Cost</th>
            <th className="px-4 py-3 font-medium">Share</th>
            <th className="px-4 py-3 font-medium">Tokens</th>
            <th className="px-4 py-3 font-medium">Calls</th>
          </tr></thead>
          <tbody>
            {(data?.rows || []).map((r: any) => (
              <tr key={r.key} className="border-b border-line/60 last:border-0">
                <td className="px-4 py-2.5 text-ink">{r.key}</td>
                <td className="px-4 py-2.5 tnum text-ink">{usd(r.cost_usd)}</td>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-24 rounded bg-white/5"><div className="h-2 rounded bg-vi" style={{ width: `${(r.cost_usd / max) * 100}%` }} /></div>
                    <span className="tnum text-dim">{r.pct}%</span>
                  </div>
                </td>
                <td className="px-4 py-2.5 tnum text-dim">{num(r.tokens)}</td>
                <td className="px-4 py-2.5 tnum text-dim">{num(r.events)}</td>
              </tr>
            ))}
            {!(data?.rows || []).length && <tr><td colSpan={5} className="px-4 py-10 text-center text-[13px] text-faint">No usage in this window.</td></tr>}
          </tbody>
        </table>
      </div>
    </div>
  );
}
