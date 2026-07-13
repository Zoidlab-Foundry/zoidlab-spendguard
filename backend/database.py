"""SQLite persistence for ZoidLab SpendGuard (Foundry Package 07 — AI Cost Optimizer).

Postgres-portable: JSON columns are JSON-encoded TEXT; all access goes through these
helpers. Ownership = Nyquest user id; seed content (owner NULL) is visible to everyone.
Costs are computed by `pricing.cost_usd` from real token counts — this module stores
usage events and budgets; it never fabricates spend.
"""
import os
import json
import uuid
import sqlite3
import datetime

import pricing

DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "spendguard.db")


def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def _j(v):
    return json.dumps(v)


def _pj(v, default=None):
    if v is None:
        return default
    try:
        return json.loads(v)
    except Exception:
        return default


def _slug(s):
    import re
    return (re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:50] or "item") + "-" + uuid.uuid4().hex[:5]


def init():
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY, email TEXT, name TEXT, role TEXT DEFAULT 'user',
                org_id TEXT, created_at TEXT, updated_at TEXT );
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, org_id TEXT, owner_user_id TEXT, name TEXT NOT NULL, slug TEXT,
                description TEXT, status TEXT DEFAULT 'active', icon TEXT, accent TEXT,
                created_at TEXT, updated_at TEXT );
            CREATE TABLE IF NOT EXISTS usage_events (
                id TEXT PRIMARY KEY, project_id TEXT, owner_user_id TEXT, app TEXT, feature TEXT,
                model TEXT, provider TEXT, prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0, cost_usd REAL DEFAULT 0, latency_ms INTEGER,
                status TEXT DEFAULT 'ok', source TEXT DEFAULT 'api', metadata TEXT, occurred_at TEXT, created_at TEXT );
            CREATE INDEX IF NOT EXISTS idx_ev_owner ON usage_events(owner_user_id, occurred_at);
            CREATE INDEX IF NOT EXISTS idx_ev_project ON usage_events(project_id, occurred_at);
            CREATE INDEX IF NOT EXISTS idx_ev_model ON usage_events(model);
            -- canonical usage-event fields (blueprint §6.3): pin cost to a pricing snapshot,
            -- carry environment + correlation id + the resource that produced the usage.
            """
        )
        ecols = [r["name"] for r in c.execute("PRAGMA table_info(usage_events)")]
        for col, ddl in [("pricing_snapshot", "TEXT"), ("environment", "TEXT"),
                         ("correlation_id", "TEXT"), ("resource_ref", "TEXT")]:
            if col not in ecols:
                c.execute(f"ALTER TABLE usage_events ADD COLUMN {col} {ddl}")
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS budgets (
                id TEXT PRIMARY KEY, project_id TEXT, owner_user_id TEXT, name TEXT NOT NULL,
                scope TEXT DEFAULT 'global', scope_ref TEXT, period TEXT DEFAULT 'monthly',
                limit_usd REAL NOT NULL, alert_pct INTEGER DEFAULT 80, status TEXT DEFAULT 'active',
                created_at TEXT, updated_at TEXT );
            CREATE INDEX IF NOT EXISTS idx_budget_owner ON budgets(owner_user_id);
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT, action TEXT, actor_user_id TEXT,
                details TEXT, created_at TEXT );
            CREATE INDEX IF NOT EXISTS idx_audit ON audit_logs(entity_type, entity_id, created_at);
            """
        )
        # budget enforcement action (§7.7): what happens when over — notify|require_approval|throttle|block
        bcols = [r["name"] for r in c.execute("PRAGMA table_info(budgets)")]
        if "action" not in bcols:
            c.execute("ALTER TABLE budgets ADD COLUMN action TEXT DEFAULT 'notify'")


def _visible(col="owner_user_id"):
    return f"({col} IS NULL OR {col}=?)"


# --- users / admin / audit --------------------------------------------
def upsert_user(uid, email=None, name=None):
    if not uid:
        return
    now = now_iso()
    with _conn() as c:
        c.execute("""INSERT INTO users (id,email,name,role,created_at,updated_at) VALUES (?,?,?,'user',?,?)
                     ON CONFLICT(id) DO UPDATE SET email=COALESCE(excluded.email,users.email),
                       name=COALESCE(excluded.name,users.name), updated_at=excluded.updated_at""",
                  (uid, email, name, now, now))


def is_admin(uid):
    if not uid:
        return False
    admins = [a.strip() for a in os.environ.get("SPENDGUARD_ADMINS", "").split(",") if a.strip()]
    return uid in admins


def audit(entity_type, entity_id, action, actor, details=None):
    with _conn() as c:
        c.execute("INSERT INTO audit_logs (id,entity_type,entity_id,action,actor_user_id,details,created_at) VALUES (?,?,?,?,?,?,?)",
                  (new_id("aud"), entity_type, entity_id, action, actor, _j(details or {}), now_iso()))


def audit_for(entity_id, limit=80):
    with _conn() as c:
        rows = c.execute("SELECT * FROM audit_logs WHERE entity_id=? ORDER BY created_at DESC LIMIT ?", (entity_id, limit)).fetchall()
    out = []
    for r in rows:
        d = dict(r); d["details"] = _pj(d.get("details"), {}); out.append(d)
    return out


# --- projects (cost scopes) -------------------------------------------
def list_projects(viewer=None):
    with _conn() as c:
        rows = c.execute(f"""SELECT p.*,
                             (SELECT COUNT(*) FROM usage_events e WHERE e.project_id=p.id) AS event_count,
                             (SELECT COALESCE(SUM(cost_usd),0) FROM usage_events e WHERE e.project_id=p.id) AS spend_usd
                             FROM projects p WHERE {_visible()} ORDER BY p.updated_at DESC""", (viewer,)).fetchall()
    return [dict(r) for r in rows]


def get_project(pid, viewer=None):
    with _conn() as c:
        r = c.execute(f"SELECT * FROM projects WHERE id=? AND {_visible()}", (pid, viewer)).fetchone()
    return dict(r) if r else None


def create_project(data, owner):
    pid = new_id("proj"); now = now_iso()
    with _conn() as c:
        c.execute("""INSERT INTO projects (id,owner_user_id,name,slug,description,status,icon,accent,created_at,updated_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?)""",
                  (pid, owner, data["name"], _slug(data["name"]), data.get("description", ""), "active",
                   data.get("icon", "$"), data.get("accent", "#34d399"), now, now))
    audit("project", pid, "created", owner)
    return get_project(pid, owner)


# --- usage events ------------------------------------------------------
def record_event(data, owner):
    """Store a usage event. cost_usd is computed here from tokens + pricing (never trusted
    from the caller) so the ledger is always internally consistent."""
    eid = new_id("ev"); now = now_iso()
    model = data.get("model") or "unknown"
    pt = int(data.get("prompt_tokens") or 0)
    ct = int(data.get("completion_tokens") or 0)
    tt = int(data.get("total_tokens") or (pt + ct))
    cost = pricing.cost_usd(model, pt, ct)
    snap = pricing.PRICE_SNAPSHOT  # cost is pinned to this pricing version at ingest (§7.7)
    rref = data.get("resource_ref")
    with _conn() as c:
        c.execute("""INSERT INTO usage_events (id,project_id,owner_user_id,app,feature,model,provider,
                     prompt_tokens,completion_tokens,total_tokens,cost_usd,latency_ms,status,source,metadata,
                     pricing_snapshot,environment,correlation_id,resource_ref,occurred_at,created_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (eid, data.get("project_id"), owner, data.get("app", ""), data.get("feature", ""),
                   model, pricing.provider_of(model), pt, ct, tt, cost, data.get("latency_ms"),
                   data.get("status", "ok"), data.get("source", "api"), _j(data.get("metadata", {})),
                   snap, data.get("environment") or "production", data.get("correlation_id"),
                   _j(rref) if rref else None, data.get("occurred_at") or now, now))
    return {"id": eid, "model": model, "prompt_tokens": pt, "completion_tokens": ct,
            "total_tokens": tt, "cost_usd": cost, "provider": pricing.provider_of(model),
            "price_known": pricing.known(model), "pricing_snapshot": snap}


def list_events(viewer=None, project_id=None, model=None, limit=200):
    q = f"SELECT * FROM usage_events WHERE {_visible()}"
    args = [viewer]
    if project_id and project_id != "all":
        q += " AND project_id=?"; args.append(project_id)
    if model and model != "all":
        q += " AND model=?"; args.append(model)
    q += " ORDER BY occurred_at DESC LIMIT ?"; args.append(limit)
    with _conn() as c:
        rows = c.execute(q, args).fetchall()
    out = []
    for r in rows:
        d = dict(r); d["metadata"] = _pj(d.get("metadata"), {})
        d["resource_ref"] = _pj(d.get("resource_ref"), None); out.append(d)
    return out


# --- budgets -----------------------------------------------------------
def create_budget(data, owner):
    bid = new_id("bud"); now = now_iso()
    action = data.get("action") or "notify"
    if action not in ("notify", "require_approval", "throttle", "block"):
        action = "notify"
    with _conn() as c:
        c.execute("""INSERT INTO budgets (id,project_id,owner_user_id,name,scope,scope_ref,period,limit_usd,alert_pct,status,action,created_at,updated_at)
                     VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (bid, data.get("project_id"), owner, data["name"], data.get("scope", "global"),
                   data.get("scope_ref"), data.get("period", "monthly"), float(data["limit_usd"]),
                   int(data.get("alert_pct", 80)), "active", action, now, now))
    audit("budget", bid, "created", owner)
    return get_budget(bid, owner)


def get_budget(bid, viewer=None):
    with _conn() as c:
        r = c.execute(f"SELECT * FROM budgets WHERE id=? AND {_visible()}", (bid, viewer)).fetchone()
    return dict(r) if r else None


def update_budget(bid, data, owner):
    b = get_budget(bid, owner)
    if not b or (b.get("owner_user_id") and b["owner_user_id"] != owner and not is_admin(owner)):
        return None
    fields, args = [], []
    for k in ("name", "scope", "scope_ref", "period", "status", "action"):
        if k in data and data[k] is not None:
            fields.append(f"{k}=?"); args.append(data[k])
    if data.get("limit_usd") is not None:
        fields.append("limit_usd=?"); args.append(float(data["limit_usd"]))
    if data.get("alert_pct") is not None:
        fields.append("alert_pct=?"); args.append(int(data["alert_pct"]))
    fields.append("updated_at=?"); args.append(now_iso()); args.append(bid)
    with _conn() as c:
        c.execute(f"UPDATE budgets SET {','.join(fields)} WHERE id=?", args)
    audit("budget", bid, "updated", owner)
    return get_budget(bid, owner)


def delete_budget(bid, owner):
    b = get_budget(bid, owner)
    if not b or (b.get("owner_user_id") and b["owner_user_id"] != owner and not is_admin(owner)):
        return False
    with _conn() as c:
        c.execute("DELETE FROM budgets WHERE id=?", (bid,))
    audit("budget", bid, "deleted", owner)
    return True


def _period_start(period):
    now = datetime.datetime.utcnow()
    if period == "daily":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "weekly":
        return (now - datetime.timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)  # monthly


def _spend_for_budget(c, b, viewer):
    """Actual spend in the current period matching the budget's scope."""
    start = _period_start(b["period"]).isoformat() + "Z"
    q = f"SELECT COALESCE(SUM(cost_usd),0) s FROM usage_events WHERE {_visible()} AND occurred_at>=?"
    args = [viewer, start]
    if b["scope"] == "project" and b.get("scope_ref"):
        q += " AND project_id=?"; args.append(b["scope_ref"])
    elif b["scope"] == "model" and b.get("scope_ref"):
        q += " AND model=?"; args.append(b["scope_ref"])
    elif b["scope"] == "provider" and b.get("scope_ref"):
        q += " AND provider=?"; args.append(b["scope_ref"])
    return c.execute(q, args).fetchone()["s"]


def list_budgets(viewer=None):
    with _conn() as c:
        rows = c.execute(f"SELECT * FROM budgets WHERE {_visible()} ORDER BY created_at DESC", (viewer,)).fetchall()
        out = []
        for r in rows:
            b = dict(r)
            spent = round(_spend_for_budget(c, b, viewer), 4)
            lim = b["limit_usd"] or 0
            pct = round((spent / lim) * 100, 1) if lim else 0
            b["spent_usd"] = spent
            b["remaining_usd"] = round(max(lim - spent, 0), 4)
            b["pct_used"] = pct
            b["state"] = "over" if pct >= 100 else ("alert" if pct >= (b["alert_pct"] or 80) else "ok")
            out.append(b)
    return out


_ACTION_RANK = {"ok": 0, "notify": 1, "throttle": 2, "require_approval": 3, "block": 4}


def budget_check(viewer=None, scope="global", scope_ref=None, projected_usd=0.0):
    """Operational budget gate (§7.7): given a proposed piece of work (its scope + a
    projected cost), return the strongest enforcement action across applicable budgets.
    action: ok | notify | throttle | require_approval | block. allowed=False only on block."""
    proj = float(projected_usd or 0)
    worst = {"allowed": True, "action": "ok", "state": "ok", "budget": None,
             "projected_pct": None, "reason": "No budget threshold reached."}
    for b in list_budgets(viewer):
        if b.get("status") != "active":
            continue
        applies = b["scope"] == "global" or (b["scope"] == scope and (b.get("scope_ref") or None) == (scope_ref or None))
        if not applies:
            continue
        lim = b["limit_usd"] or 0
        projected = b["spent_usd"] + proj
        pct = round((projected / lim) * 100, 1) if lim else 0
        if lim and projected >= lim:
            act = b.get("action") or "notify"
            reason = f"'{b['name']}' would be exceeded (${round(projected,4)} of ${lim})."
        elif pct >= (b["alert_pct"] or 80):
            act = "notify"
            reason = f"'{b['name']}' at {pct}% of its ${lim} {b['period']} limit."
        else:
            continue
        if _ACTION_RANK[act] > _ACTION_RANK[worst["action"]]:
            worst = {"allowed": act != "block", "action": act, "state": "over" if lim and projected >= lim else "alert",
                     "budget": {"id": b["id"], "name": b["name"], "scope": b["scope"], "limit_usd": lim},
                     "projected_pct": pct, "reason": reason}
    return worst
