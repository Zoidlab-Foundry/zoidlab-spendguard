"""ZoidLab SpendGuard API — Foundry Package 07, AI Cost Optimizer.

Answers "where is our AI spend going, and how do we cut it?" from a real usage ledger.
Costs are computed from token counts against a published price table (pricing.py) — no
fabricated numbers. Every data endpoint requires Nyquest Pro (backend-enforced, fail-closed).
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, List

import db_pg as db
import pricing
import cost_engine
import exporter
import envelope
import seed_usage
from auth import session, require_pro, entitlement


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init()
    n = seed_usage.run()
    if n:
        print(f"[spendguard] seeded sample cost scope + {n} usage events")
    yield


app = FastAPI(title="ZoidLab SpendGuard API", lifespan=lifespan)


def require_owner(request: Request):
    o = require_pro(request)
    s = session(request)
    db.upsert_user(o, s.get("email") if s else None, s.get("name") if s else None)
    return o


# ---- auth / meta --------------------------------------------------------
@app.get("/api/health")
def health():
    return {"ok": True, "service": "spendguard"}


@app.get("/api/auth/me")
def auth_me(request: Request):
    s = session(request)
    if not s:
        return {"authenticated": False}
    return {"authenticated": True, "user_id": s.get("sub"), "email": s.get("email"),
            "name": s.get("name"), "tier": s.get("tier")}


@app.get("/api/auth/entitlements")
def auth_entitlements(request: Request):
    return entitlement(request)


@app.get("/api/meta")
def meta():
    return {"price_snapshot": pricing.PRICE_SNAPSHOT,
            "prices": pricing.table(),
            "group_by": ["model", "provider", "project", "app", "feature"],
            "budget_scopes": ["global", "project", "model", "provider"],
            "budget_periods": ["daily", "weekly", "monthly"]}


@app.get("/api/stats")
def stats(request: Request, owner: str = Depends(require_owner)):
    return cost_engine.dashboard_stats(owner)


# ---- projects (cost scopes) --------------------------------------------
class ProjectBody(BaseModel):
    name: str
    description: Optional[str] = ""


@app.get("/api/projects")
def projects(request: Request, owner: str = Depends(require_owner)):
    return {"projects": db.list_projects(owner)}


@app.post("/api/projects")
def create_project(body: ProjectBody, owner: str = Depends(require_owner)):
    return {"ok": True, "project": db.create_project(body.model_dump(), owner)}


# ---- usage events -------------------------------------------------------
class EventBody(BaseModel):
    project_id: Optional[str] = None
    app: Optional[str] = ""
    feature: Optional[str] = ""
    model: str
    prompt_tokens: Optional[int] = 0
    completion_tokens: Optional[int] = 0
    total_tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    status: Optional[str] = "ok"
    source: Optional[str] = "api"
    occurred_at: Optional[str] = None
    metadata: Optional[dict] = {}
    # canonical usage-event fields (blueprint §6.3)
    environment: Optional[str] = None            # development | testing | production
    correlation_id: Optional[str] = None         # ties usage to a run/trace
    resource_ref: Optional[dict] = None          # {package_id, resource_id, version_id?}


@app.post("/api/events")
def ingest_event(body: EventBody, owner: str = Depends(require_owner)):
    """Record a usage event. cost_usd is computed server-side from tokens + list price."""
    rec = db.record_event(body.model_dump(), owner)
    return {"ok": True, "event": rec}


class BulkEvents(BaseModel):
    events: List[EventBody]


@app.post("/api/events/bulk")
def ingest_bulk(body: BulkEvents, owner: str = Depends(require_owner)):
    recs = [db.record_event(e.model_dump(), owner) for e in body.events]
    return {"ok": True, "recorded": len(recs), "total_cost_usd": round(sum(r["cost_usd"] for r in recs), 4)}


@app.get("/api/events")
def list_events(request: Request, project_id: Optional[str] = None, model: Optional[str] = None,
                owner: str = Depends(require_owner)):
    return {"events": db.list_events(owner, project_id=project_id, model=model)}


# ---- cost analytics -----------------------------------------------------
@app.get("/api/breakdown")
def breakdown(request: Request, group_by: str = "model", days: Optional[int] = None,
              project_id: Optional[str] = None, owner: str = Depends(require_owner)):
    return cost_engine.breakdown(owner, group_by=group_by, days=days, project_id=project_id)


@app.get("/api/series")
def series(request: Request, days: int = 30, project_id: Optional[str] = None,
           owner: str = Depends(require_owner)):
    return cost_engine.daily_series(owner, days=days, project_id=project_id)


class SimulateBody(BaseModel):
    from_model: str
    to_model: str
    days: Optional[int] = None
    project_id: Optional[str] = None


@app.post("/api/simulate")
def simulate(body: SimulateBody, owner: str = Depends(require_owner)):
    return cost_engine.simulate(owner, body.from_model, body.to_model,
                                days=body.days, project_id=body.project_id)


@app.get("/api/recommendations")
def recommendations(request: Request, days: int = 30, owner: str = Depends(require_owner)):
    return cost_engine.recommendations(owner, days=days)


# ---- budgets ------------------------------------------------------------
class BudgetBody(BaseModel):
    project_id: Optional[str] = None
    name: str
    scope: Optional[str] = "global"
    scope_ref: Optional[str] = None
    period: Optional[str] = "monthly"
    limit_usd: float
    alert_pct: Optional[int] = 80
    action: Optional[str] = "notify"   # notify | throttle | require_approval | block (§7.7)


@app.get("/api/budgets")
def budgets(request: Request, owner: str = Depends(require_owner)):
    return {"budgets": db.list_budgets(owner)}


@app.post("/api/budgets")
def create_budget(body: BudgetBody, owner: str = Depends(require_owner)):
    return {"ok": True, "budget": db.create_budget(body.model_dump(), owner)}


class BudgetUpdate(BaseModel):
    name: Optional[str] = None
    scope: Optional[str] = None
    scope_ref: Optional[str] = None
    period: Optional[str] = None
    limit_usd: Optional[float] = None
    alert_pct: Optional[int] = None
    status: Optional[str] = None
    action: Optional[str] = None


class BudgetCheckBody(BaseModel):
    scope: Optional[str] = "global"
    scope_ref: Optional[str] = None
    projected_usd: Optional[float] = 0.0


@app.post("/api/budget-check")
def budget_check(body: BudgetCheckBody, owner: str = Depends(require_owner)):
    """Operational budget gate (§7.7): apps call this before starting priced work to get
    allow/notify/throttle/require_approval/block for the caller's budgets."""
    return db.budget_check(owner, scope=body.scope, scope_ref=body.scope_ref,
                           projected_usd=body.projected_usd)


@app.put("/api/budgets/{bid}")
def update_budget(bid: str, body: BudgetUpdate, owner: str = Depends(require_owner)):
    b = db.update_budget(bid, body.model_dump(exclude_none=True), owner)
    if not b:
        raise HTTPException(404, "not_found_or_forbidden")
    return {"ok": True, "budget": b}


@app.delete("/api/budgets/{bid}")
def delete_budget(bid: str, owner: str = Depends(require_owner)):
    if not db.delete_budget(bid, owner):
        raise HTTPException(404, "not_found_or_forbidden")
    return {"ok": True}


# ---- audit / export -----------------------------------------------------
@app.get("/api/projects/{pid}/audit")
def project_audit(pid: str, request: Request, owner: str = Depends(require_owner)):
    if not db.get_project(pid, owner):
        raise HTTPException(404, "not_found")
    return {"audit": db.audit_for(pid)}


def _wrapped(owner, proj, days):
    payload = exporter.to_package(owner, proj, days=days)
    return envelope.wrap("spendguard", "cost_report", (proj or {}).get("id") or "all",
                         "1.0.0", payload, nyquest_user_id=owner)


@app.get("/api/export/json")
def export_json(request: Request, project_id: Optional[str] = None, days: int = 30,
                owner: str = Depends(require_owner)):
    proj = db.get_project(project_id, owner) if project_id else None
    return _wrapped(owner, proj, days)


@app.get("/api/export/yaml")
def export_yaml(request: Request, project_id: Optional[str] = None, days: int = 30,
                owner: str = Depends(require_owner)):
    proj = db.get_project(project_id, owner) if project_id else None
    return PlainTextResponse(exporter.to_yaml(_wrapped(owner, proj, days)))
