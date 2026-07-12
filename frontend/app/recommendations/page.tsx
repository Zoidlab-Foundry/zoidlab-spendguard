"use client";
import { useEffect, useState } from "react";
import { api, usd } from "../../lib/api";

const SEV: Record<string, string> = { high: "bg-bad/10 text-bad border-bad/30", medium: "bg-warn/10 text-warn border-warn/30", low: "bg-white/5 text-dim border-line" };

export default function Recommendations() {
  const [data, setData] = useState<any>(null);
  useEffect(() => { api.recommendations({ days: "30" }).then(setData).catch(() => {}); }, []);

  return (
    <div className="py-8 max-w-[900px]">
      <h1 className="text-[24px] font-semibold">Recommendations</h1>
      <p className="mt-1 text-[13px] text-dim">Rule-based, explainable suggestions over your real spend. Each shows exactly why and the estimated saving.</p>

      {data && (
        <div className="mt-4 flex gap-4">
          <div className="rounded-2xl border border-line bg-panel px-5 py-3"><span className="text-[12px] text-faint">30-day spend</span><div className="text-[18px] font-semibold tnum text-ink">{usd(data.total_spend_usd)}</div></div>
          <div className="rounded-2xl border border-vi/30 bg-vi/5 px-5 py-3"><span className="text-[12px] text-faint">Potential savings</span><div className="text-[18px] font-semibold tnum text-vi">{usd(data.potential_savings_usd)}</div></div>
        </div>
      )}

      <div className="mt-5 space-y-3">
        {(data?.recommendations || []).map((r: any, i: number) => (
          <div key={i} className="rounded-2xl border border-line bg-panel p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`rounded-full border px-2 py-0.5 text-[10.5px] uppercase tracking-wide ${SEV[r.severity] || SEV.low}`}>{r.severity}</span>
                  <span className="text-[10.5px] uppercase tracking-wide text-faint">{r.type.replace(/_/g, " ")}</span>
                </div>
                <h3 className="mt-1.5 text-[14.5px] font-semibold text-ink">{r.title}</h3>
                <p className="mt-1 text-[12.5px] leading-relaxed text-dim">{r.detail}</p>
              </div>
              {r.est_savings_usd > 0 && <div className="shrink-0 text-right"><div className="text-[11px] text-faint">est. save</div><div className="text-[17px] font-semibold tnum text-ok">{usd(r.est_savings_usd)}</div></div>}
            </div>
          </div>
        ))}
        {data && !data.recommendations.length && <div className="rounded-2xl border border-dashed border-line py-14 text-center text-[13px] text-faint">Nothing to suggest right now.</div>}
      </div>
    </div>
  );
}
