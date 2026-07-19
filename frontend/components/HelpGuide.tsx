"use client";
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/* In-app guide: what SpendGuard is and how to go from raw usage to real savings.
   Auto-opens once per browser (localStorage) and lives behind the Guide nav button. */

const STORAGE_KEY = "sg_guide_v1";

const STEPS: { title: string; body: string }[] = [
  {
    title: "Watch spend flow in",
    body: "The Dashboard shows your AI spend as it happens — total, month-to-date, and projected run-rate. Usage arrives from other Foundry apps automatically (Workflow Builder runs emit real model and token splits), or POST your own events to /api/events.",
  },
  {
    title: "Inspect the usage ledger",
    body: "Usage lists every recorded AI call: model, app and feature, prompt and completion tokens. Cost is computed server-side from tokens × list price — nothing estimated. You can also record events by hand for quick what-ifs.",
  },
  {
    title: "Break down the cost",
    body: "Breakdown groups spend by model, provider, project, app, or feature over 7/30/90-day windows — so you can see exactly which feature or model is burning the budget.",
  },
  {
    title: "Set budgets with alerts",
    body: "On Budgets, cap spend by scope (global, project, model, or provider) and period (daily, weekly, monthly), with an alert threshold. Spend is summed live from the ledger — bars go green, amber, then red as you approach the cap.",
  },
  {
    title: "Simulate the switch",
    body: "The Savings Simulator recomputes your real historical token usage as if it had run on a different model — exact arithmetic on recorded calls, so 'what if I switched gpt-4o → gpt-4o-mini' gets a hard dollar answer.",
  },
  {
    title: "Act on it, then export",
    body: "Recommendations are rule-based and explainable — each shows exactly why plus the estimated saving. When you're done, export the whole analysis as a portable Nyquest Cost Report (JSON/YAML) for TrustGate cost limits or the Foundry roll-up.",
  },
];

export default function HelpGuide() {
  const [open, setOpen] = useState(false);

  useEffect(() => {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setOpen(true);
    } catch {}
  }, []);

  const dismiss = () => {
    try { localStorage.setItem(STORAGE_KEY, "1"); } catch {}
    setOpen(false);
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") dismiss(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="rounded-lg border border-line px-3 py-1.5 text-[12px] text-dim transition hover:text-ink hover:bg-white/5"
        aria-label="Open the SpendGuard guide"
      >
        Guide
      </button>
      {open && createPortal(
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={dismiss} role="dialog" aria-modal="true" aria-label="SpendGuard guide">
          <div className="max-h-[85vh] w-full max-w-lg overflow-y-auto rounded-xl border border-line bg-panel p-6 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-1 flex items-center gap-2">
              <span className="grid h-6 w-6 place-items-center rounded-md bg-vi/15 text-[13px] font-bold text-vi">$</span>
              <h2 className="text-[16px] font-semibold">How SpendGuard works</h2>
            </div>
            <p className="mb-5 text-[13px] text-dim">
              See exactly what your AI spend costs, cap it, and cut it — computed from real token counts, not estimates. Six steps:
            </p>
            <ol className="space-y-4">
              {STEPS.map((s, i) => (
                <li key={i} className="flex gap-3">
                  <span className="mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-vi/15 text-[12px] font-semibold text-vi">{i + 1}</span>
                  <div>
                    <div className="text-[13.5px] font-medium">{s.title}</div>
                    <div className="text-[12.5px] leading-relaxed text-dim">{s.body}</div>
                  </div>
                </li>
              ))}
            </ol>
            <div className="mt-6 flex items-center justify-between border-t border-line pt-4">
              <a href="https://foundry.zoidlab.ai" className="text-[12px] text-dim hover:text-ink">◈ All Foundry apps</a>
              <button onClick={dismiss} className="rounded-lg bg-vi px-4 py-1.5 text-[12.5px] font-semibold text-white hover:opacity-90">
                Got it
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
