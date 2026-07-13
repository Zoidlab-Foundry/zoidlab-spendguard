"use client";
import { useEffect, useState } from "react";
import { api } from "../../lib/api";

const HOOKS = [
  { name: "ZoidLab Workflow Builder", desc: "LIVE — every Builder workflow run emits its real model usage here automatically (source: builder).", href: "https://builder.zoidlab.ai", live: true },
  { name: "ZoidLab TrustGate", desc: "Enforce a cost_limit policy using these per-model spend figures.", href: "https://trustgate.zoidlab.ai" },
  { name: "ZoidLab Foundry", desc: "Roll this cost report into the Foundry overview control plane.", href: "https://foundry.zoidlab.ai" },
];

export default function ExportPage() {
  const [projects, setProjects] = useState<any[]>([]);
  const [pid, setPid] = useState("");
  const [pkg, setPkg] = useState<any>(null);

  useEffect(() => { api.projects().then((p) => setProjects(p)).catch(() => {}); }, []);
  useEffect(() => { fetch(api.exportJsonUrl(pid || undefined), { credentials: "include" }).then((r) => r.json()).then(setPkg).catch(() => {}); }, [pid]);

  return (
    <div className="py-8">
      <h1 className="text-[22px] font-semibold">Export & Integrate</h1>
      <p className="mt-1 text-[13px] text-dim">Export the cost analysis as a portable <b>Nyquest Cost Report</b>, or wire spend tracking across the Foundry.</p>
      {projects.length > 0 && (
        <select value={pid} onChange={(e) => setPid(e.target.value)} className="mt-3 rounded-lg border border-line bg-panel2 px-3 py-2 text-[13px] text-ink">
          <option value="">All scopes</option>
          {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      )}

      <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_440px]">
        <div>
          <h2 className="mb-3 text-[15px] font-semibold">Cross-app hooks</h2>
          <div className="space-y-2">
            {HOOKS.map((h) => (
              <div key={h.name} className="flex items-center justify-between rounded-xl border border-line bg-panel p-3">
                <div><div className="text-[13px] font-medium text-ink">{h.name}</div><div className="text-[12px] text-dim">{h.desc}</div></div>
                <a href={h.href} target="_blank" rel="noopener" className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-cy hover:bg-white/5">Open ↗</a>
              </div>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-faint">The Workflow Builder integration is <b className="text-vi">live</b> — its runs emit real usage here automatically. TrustGate cost-limit enforcement and Foundry roll-up use the export contract below.</p>
          <h2 className="mb-3 mt-6 text-[15px] font-semibold">Download</h2>
          <div className="flex flex-wrap gap-2">
            <a href={api.exportJsonUrl(pid || undefined)} target="_blank" rel="noopener" className="rounded-lg bg-vi px-4 py-2 text-[13px] font-semibold text-white hover:opacity-90">Download JSON report</a>
            <a href={api.exportYamlUrl(pid || undefined)} target="_blank" rel="noopener" className="rounded-lg border border-line px-4 py-2 text-[13px] text-ink hover:bg-white/5">Download YAML</a>
          </div>
        </div>
        <div>
          <div className="mb-2 text-[11px] uppercase tracking-wider text-faint">spendguard.cost_report.json</div>
          <pre className="max-h-[580px] overflow-auto rounded-xl border border-line bg-panel2 p-3 text-[11px] leading-relaxed text-dim">{pkg ? JSON.stringify(pkg, null, 2) : "…"}</pre>
        </div>
      </div>
    </div>
  );
}
