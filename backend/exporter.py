"""Standardized Nyquest package export for SpendGuard — a portable cost report."""
import datetime
import pricing
import cost_engine


def to_package(viewer, project=None, days=30):
    bd_model = cost_engine.breakdown(viewer, "model", days=days)
    bd_provider = cost_engine.breakdown(viewer, "provider", days=days)
    bd_project = cost_engine.breakdown(viewer, "project", days=days)
    recs = cost_engine.recommendations(viewer, days=days)
    stats = cost_engine.dashboard_stats(viewer)
    return {
        "schema_version": "1.0",
        "package_type": "nyquest_cost_report",
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "source_app": "spendguard",
        "price_snapshot": pricing.PRICE_SNAPSHOT,
        "window_days": days,
        "scope": {"project_id": project.get("id") if project else None,
                  "project_name": project.get("name") if project else "all"},
        "summary": stats,
        "breakdown": {"by_model": bd_model["rows"], "by_provider": bd_provider["rows"],
                      "by_project": bd_project["rows"]},
        "recommendations": recs["recommendations"],
        "potential_savings_usd": recs["potential_savings_usd"],
        "disclaimer": "Costs computed from recorded token counts against list prices "
                      f"(snapshot {pricing.PRICE_SNAPSHOT}); may differ from provider invoices.",
    }


def to_yaml(pkg):
    def emit(v, ind=0):
        pad = "  " * ind
        if isinstance(v, dict):
            out = []
            for k, val in v.items():
                if isinstance(val, (dict, list)) and val:
                    out.append(f"{pad}{k}:")
                    out.append(emit(val, ind + 1))
                else:
                    out.append(f"{pad}{k}: {_scalar(val)}")
            return "\n".join(out)
        if isinstance(v, list):
            out = []
            for item in v:
                if isinstance(item, (dict, list)):
                    out.append(f"{pad}-")
                    out.append(emit(item, ind + 1))
                else:
                    out.append(f"{pad}- {_scalar(item)}")
            return "\n".join(out)
        return f"{pad}{_scalar(v)}"

    def _scalar(v):
        if v is None:
            return "null"
        if isinstance(v, bool):
            return "true" if v else "false"
        s = str(v)
        return f'"{s}"' if (":" in s or "#" in s) else s

    return emit(pkg) + "\n"
