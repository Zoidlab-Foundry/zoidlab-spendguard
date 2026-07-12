"""Seed a demo cost scope with a SAMPLE usage ledger.

Every seeded event carries source="sample" and is labeled in the UI as sample data, not
real billing. Token counts follow a fixed deterministic pattern so costs are reproducible;
cost_usd is computed by the same pricing path as real events, so the demo is internally
honest (real arithmetic over synthetic tokens).
"""
import datetime
import database as db

# Deterministic synthetic traffic: (model, app, feature, prompt_toks, completion_toks, calls_over_window)
_PATTERN = [
    ("gpt-4o",            "support-bot",   "answer",        1800, 550, 42),
    ("gpt-4o",            "support-bot",   "summarize",     3200, 300, 18),
    ("gpt-4o-mini",       "support-bot",   "classify",       420,  40, 260),
    ("claude-sonnet-4.5", "research-agent","deep-analysis",  6400, 1200, 22),
    ("claude-3.5-haiku",  "research-agent","extract",        900,  180, 140),
    ("gemini-2.5-flash",  "ingest-worker", "ocr-caption",    1100,  90, 310),
    ("gemini-2.5-pro",    "ingest-worker", "reconcile",      2800, 400, 12),
    ("deepseek-reasoner", "quant-lab",     "chain-of-thought",5200, 2100, 16),
    ("deepseek-chat",     "quant-lab",     "score",          800,  120, 90),
]


def run():
    with db._conn() as c:
        existing = c.execute("SELECT COUNT(*) n FROM usage_events").fetchone()["n"]
    if existing:
        return 0

    proj = db.create_project(
        {"name": "Production AI Spend", "description": "Sample cross-app AI usage ledger "
         "(synthetic demo data) — replace by POSTing real events to /api/events.",
         "icon": "$", "accent": "#34d399"}, owner=None)
    pid = proj["id"]

    now = datetime.datetime.utcnow()
    n = 0
    for (model, app, feature, pt, ct, calls) in _PATTERN:
        for i in range(calls):
            # spread calls across the last 30 days, deterministic
            day_offset = (i * 30) // max(calls, 1)
            occurred = (now - datetime.timedelta(days=day_offset,
                        hours=(i * 7) % 24, minutes=(i * 13) % 60)).isoformat() + "Z"
            # small deterministic variation in token counts
            vpt = pt + ((i * 37) % max(pt // 5, 1))
            vct = ct + ((i * 19) % max(ct // 5, 1))
            db.record_event({
                "project_id": pid, "app": app, "feature": feature, "model": model,
                "prompt_tokens": vpt, "completion_tokens": vct,
                "latency_ms": 400 + (i * 53) % 3000, "source": "sample",
                "occurred_at": occurred,
            }, owner=None)
            n += 1

    # sample budgets
    db.create_budget({"project_id": pid, "name": "Monthly AI budget", "scope": "global",
                      "period": "monthly", "limit_usd": 250.0, "alert_pct": 80}, owner=None)
    db.create_budget({"name": "Claude Sonnet cap", "scope": "model", "scope_ref": "claude-sonnet-4.5",
                      "period": "monthly", "limit_usd": 60.0, "alert_pct": 75}, owner=None)
    return n
