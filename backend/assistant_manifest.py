"""SpendGuard assistant manifest — what the in-app assistant knows and may do.

This file is the assistant's security boundary: only the capabilities declared here exist
for it, and they execute through this app's own session-authed API (require_pro + RLS apply).
Delete-class operations are intentionally not declared.
"""
from foundry_common.assistant import cap, page

MANIFEST = {
    "app": "SpendGuard",
    "description": (
        "SpendGuard is the Foundry AI cost optimizer: a real usage ledger fed by every "
        "Foundry app, with cost computed server-side from token counts against a published "
        "price table — nothing fabricated. It breaks spend down by model/app/feature, "
        "enforces budgets with alert thresholds, recomputes real historical tokens on other "
        "models in the savings simulator, and surfaces concrete recommendations to cut cost."
    ),
    "base_url": "http://127.0.0.1:8701",
    "pages": [
        page("/", "Dashboard", "Overview: total spend, daily series, top models, budget states."),
        page("/usage", "Usage", "The raw usage-event ledger: every recorded call with tokens and cost."),
        page("/breakdown", "Breakdown", "Spend grouped by model, provider, project, app, or feature."),
        page("/budgets", "Budgets", "Spend caps by scope and period with alert thresholds.",
             assists={"new-budget": "the New budget button"}),
        page("/simulator", "Savings Simulator",
             "Recompute real historical tokens as if they had run on a different model.",
             assists={"run-simulator": "the Simulate button"}),
        page("/recommendations", "Recommendations", "Concrete savings opportunities computed from real usage."),
        page("/export", "Export", "Signed Foundry cost-report export (JSON/YAML)."),
    ],
    "capabilities": [
        cap("stats", "GET", "/api/stats", risk="read",
            desc="Dashboard stats: total/period spend, event counts, top models, budget health."),
        cap("meta", "GET", "/api/meta", risk="read",
            desc="Price table + snapshot date, valid group_by keys, budget scopes and periods."),
        cap("list_projects", "GET", "/api/projects", risk="read",
            desc="The user's cost-scope projects."),
        cap("list_events", "GET", "/api/events", risk="read",
            desc="Usage events (newest first), optionally filtered.",
            params={"project_id": "filter to one project", "model": "filter to one model"}),
        cap("breakdown", "GET", "/api/breakdown", risk="read",
            desc="Spend broken down by a grouping key with tokens, calls, and cost per row.",
            params={"group_by": "one of model|provider|project|app|feature (default model)",
                    "days": "restrict to the last N days", "project_id": "filter to one project"}),
        cap("daily_series", "GET", "/api/series", risk="read",
            desc="Daily spend time series for charts/trends.",
            params={"days": "window size in days (default 30)", "project_id": "filter to one project"}),
        cap("list_budgets", "GET", "/api/budgets", risk="read",
            desc="All budgets with live spend, percent used, and ok/alert/over state."),
        cap("recommendations", "GET", "/api/recommendations", risk="read",
            desc="Computed savings recommendations (model swaps, anomalies) from real usage.",
            params={"days": "analysis window in days (default 30)"}),
        cap("simulate_savings", "POST", "/api/simulate", risk="write",
            desc="What-if computation ONLY — recomputes the user's real historical tokens on "
                 "another model's list price. Changes no data; the summary should say it is a "
                 "cost simulation, e.g. 'Simulate moving gpt-4o traffic to gpt-4o-mini'.",
            params={"from_model": "model currently used", "to_model": "candidate model",
                    "days": "restrict to the last N days (optional)",
                    "project_id": "restrict to one project (optional)"}),
        cap("create_budget", "POST", "/api/budgets", risk="write",
            desc="Create a spend budget. scope is one of global|project|model|provider "
                 "(scope_ref names the project id/model/provider when scope is not global); "
                 "period is daily|weekly|monthly.",
            params={"name": "budget name", "scope": "global|project|model|provider",
                    "scope_ref": "target for non-global scopes", "period": "daily|weekly|monthly",
                    "limit_usd": "spend cap in USD", "alert_pct": "alert threshold percent (default 80)",
                    "action": "on breach: notify|throttle|require_approval|block",
                    "project_id": "owning project (optional)"}),
        cap("update_budget", "PUT", "/api/budgets/{bid}", risk="write",
            desc="Update an existing budget's name, scope, period, limit, alert threshold, "
                 "status, or breach action. Only send the fields being changed.",
            params={"bid": "budget id", "name": "new name", "scope": "global|project|model|provider",
                    "scope_ref": "target for non-global scopes", "period": "daily|weekly|monthly",
                    "limit_usd": "new spend cap in USD", "alert_pct": "alert threshold percent",
                    "status": "active|paused", "action": "notify|throttle|require_approval|block"}),
    ],
}
