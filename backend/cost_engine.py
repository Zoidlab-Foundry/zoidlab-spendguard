"""Deterministic cost analytics for SpendGuard.

Everything here is arithmetic over the recorded usage_events ledger and the published
price table — no estimates presented as measurements, no fabricated savings. The savings
simulator recomputes real historical token counts against a different model's list price;
recommendations are rule-based over actual spend concentration.
"""
import datetime
import pricing
from database import _conn, _visible


def _rows(viewer, days=None, project_id=None):
    q = f"SELECT * FROM usage_events WHERE {_visible()}"
    args = [viewer]
    if days:
        start = (datetime.datetime.utcnow() - datetime.timedelta(days=days)).isoformat() + "Z"
        q += " AND occurred_at>=?"; args.append(start)
    if project_id and project_id != "all":
        q += " AND project_id=?"; args.append(project_id)
    with _conn() as c:
        return [dict(r) for r in c.execute(q, args).fetchall()]


def dashboard_stats(viewer=None):
    rows = _rows(viewer)
    total = sum(r["cost_usd"] for r in rows)
    tokens = sum(r["total_tokens"] for r in rows)
    # month-to-date + previous full month for trend
    now = datetime.datetime.utcnow()
    mstart = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    mtd = sum(r["cost_usd"] for r in rows if r["occurred_at"] >= mstart.isoformat() + "Z")
    days_elapsed = max((now - mstart).days + 1, 1)
    days_in_month = (mstart.replace(month=mstart.month % 12 + 1, day=1) - datetime.timedelta(days=1)).day if mstart.month != 12 else 31
    projected = round(mtd / days_elapsed * days_in_month, 2) if mtd else 0
    models = len({r["model"] for r in rows})
    unknown = sum(1 for r in rows if not pricing.known(r["model"]))
    return {
        "total_spend_usd": round(total, 4),
        "month_to_date_usd": round(mtd, 4),
        "projected_month_usd": projected,
        "total_tokens": tokens,
        "events": len(rows),
        "models_used": models,
        "unpriced_events": unknown,  # events on models absent from the price table (cost=0)
        "avg_cost_per_call": round(total / len(rows), 6) if rows else 0,
    }


def breakdown(viewer=None, group_by="model", days=None, project_id=None):
    rows = _rows(viewer, days=days, project_id=project_id)
    key = {"model": "model", "provider": "provider", "project": "project_id",
           "app": "app", "feature": "feature"}.get(group_by, "model")
    agg = {}
    for r in rows:
        k = r.get(key) or "(none)"
        a = agg.setdefault(k, {"key": k, "cost_usd": 0.0, "tokens": 0, "events": 0})
        a["cost_usd"] += r["cost_usd"]; a["tokens"] += r["total_tokens"]; a["events"] += 1
    out = sorted(agg.values(), key=lambda x: x["cost_usd"], reverse=True)
    for a in out:
        a["cost_usd"] = round(a["cost_usd"], 4)
    total = round(sum(a["cost_usd"] for a in out), 4) or 0
    for a in out:
        a["pct"] = round((a["cost_usd"] / total) * 100, 1) if total else 0
    return {"group_by": group_by, "total_usd": total, "rows": out}


def daily_series(viewer=None, days=30, project_id=None):
    rows = _rows(viewer, days=days, project_id=project_id)
    buckets = {}
    for r in rows:
        day = (r["occurred_at"] or "")[:10]
        buckets[day] = round(buckets.get(day, 0) + r["cost_usd"], 4)
    series = [{"date": d, "cost_usd": buckets[d]} for d in sorted(buckets)]
    return {"days": days, "series": series}


def simulate(viewer, from_model, to_model, days=None, project_id=None):
    """Recompute the real historical token usage on `from_model` as if it had run on
    `to_model`. Exact arithmetic over recorded tokens — honest what-if, not a guess."""
    rows = [r for r in _rows(viewer, days=days, project_id=project_id) if r["model"] == from_model]
    if not pricing.known(to_model):
        return {"error": f"'{to_model}' is not in the price table", "known_models": list(pricing.PRICES)}
    cur = sum(r["cost_usd"] for r in rows)
    alt = sum(pricing.cost_usd(to_model, r["prompt_tokens"], r["completion_tokens"]) for r in rows)
    saved = cur - alt
    return {
        "from_model": from_model, "to_model": to_model,
        "events_considered": len(rows),
        "current_cost_usd": round(cur, 4),
        "simulated_cost_usd": round(alt, 4),
        "savings_usd": round(saved, 4),
        "savings_pct": round((saved / cur) * 100, 1) if cur else 0,
        "note": "Recomputed from actual recorded token counts against list prices; "
                "does not account for quality/latency differences between models.",
    }


def recommendations(viewer=None, days=30):
    """Rule-based, explainable recommendations over real spend concentration."""
    rows = _rows(viewer, days=days)
    recs = []
    by_model = {}
    for r in rows:
        m = r["model"]
        a = by_model.setdefault(m, {"cost": 0.0, "pt": 0, "ct": 0, "events": 0})
        a["cost"] += r["cost_usd"]; a["pt"] += r["prompt_tokens"]; a["ct"] += r["completion_tokens"]; a["events"] += 1
    total = sum(a["cost"] for a in by_model.values()) or 0

    for m, a in sorted(by_model.items(), key=lambda kv: kv[1]["cost"], reverse=True):
        alt = pricing.CHEAPER_ALT.get(m)
        if alt and a["cost"] > 0:
            alt_cost = pricing.cost_usd(alt, a["pt"], a["ct"])
            saved = a["cost"] - alt_cost
            if saved > 0.005:  # meaningful
                recs.append({
                    "type": "model_swap", "severity": "high" if saved / (total or 1) > 0.2 else "medium",
                    "model": m, "suggest": alt,
                    "title": f"Consider {alt} for some {m} traffic",
                    "detail": f"{m} accounts for ${round(a['cost'],2)} ({round(a['cost']/(total or 1)*100)}%) "
                              f"of spend across {a['events']} calls. The same token volume on {alt} "
                              f"would cost ${round(alt_cost,2)} — up to ${round(saved,2)} lower. "
                              f"Validate quality on your workload before switching.",
                    "est_savings_usd": round(saved, 2),
                })
    # concentration warning
    if by_model:
        top_model, top = max(by_model.items(), key=lambda kv: kv[1]["cost"])
        if total and top["cost"] / total > 0.7:
            recs.append({
                "type": "concentration", "severity": "low", "model": top_model, "suggest": None,
                "title": f"{round(top['cost']/total*100)}% of spend is on {top_model}",
                "detail": "Spend is concentrated on a single model. A routing policy that sends "
                          "simpler requests to a cheaper tier can cut cost with little quality loss.",
                "est_savings_usd": 0,
            })
    if not rows:
        recs.append({"type": "no_data", "severity": "low", "title": "No usage recorded yet",
                     "detail": "Send usage events to /api/events (or load the sample ledger) to get "
                               "cost breakdowns and savings recommendations.", "est_savings_usd": 0,
                     "model": None, "suggest": None})
    return {"days": days, "total_spend_usd": round(total, 4),
            "potential_savings_usd": round(sum(r["est_savings_usd"] for r in recs), 2),
            "recommendations": recs}
