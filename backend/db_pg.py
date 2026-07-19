"""Postgres data layer for ZoidLab SpendGuard with per-tenant Row-Level Security (§3.2).

Tenant isolation is enforced by the database, not just the app: projects, usage_events
and budgets carry owner_user_id, have FORCE ROW LEVEL SECURITY, and a policy exposing only
rows whose owner matches `app.current_owner` (set per transaction) or is NULL (shared
sample data). `users` and `audit_logs` have no owner column and stay open. Costs are
computed by `pricing.cost_usd` from real token counts — this module stores usage events
and budgets; it never fabricates spend. Public API mirrors the former sqlite database.py
exactly.
"""
import os
import json
import uuid
import datetime

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

import pricing

# App connections use the RLS-enforced role (app_rls); DDL + cross-tenant admin use the
# superuser (foundry), which bypasses RLS by design.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://app_rls@127.0.0.1:5433/spendguard")
DATABASE_URL_ADMIN = os.environ.get("DATABASE_URL_ADMIN", "postgresql://foundry@127.0.0.1:5433/spendguard")
_pool = ConnectionPool(DATABASE_URL, min_size=1, max_size=10, open=True, kwargs={"autocommit": False})


def admin_conn():
    return psycopg.connect(DATABASE_URL_ADMIN, row_factory=dict_row)


def now_iso():
    return datetime.datetime.utcnow().isoformat() + "Z"


def new_id(prefix):
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


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


class _tx:
    """Transaction scoped to a tenant: sets app.current_owner so RLS applies."""
    def __init__(self, owner):
        self.owner = owner or ""

    def __enter__(self):
        self.conn = _pool.getconn()
        self.cur = self.conn.cursor(row_factory=dict_row)
        self.cur.execute("SELECT set_config('app.current_owner', %s, true)", (self.owner,))
        return self.cur

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
        finally:
            self.cur.close()
            _pool.putconn(self.conn)


_TENANT_TABLES = ["projects", "usage_events", "budgets"]


def init():
    with admin_conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT, name TEXT, role TEXT DEFAULT 'user',
            org_id TEXT, created_at TEXT, updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY, org_id TEXT, owner_user_id TEXT, name TEXT NOT NULL, slug TEXT,
            description TEXT, status TEXT DEFAULT 'active', icon TEXT, accent TEXT,
            created_at TEXT, updated_at TEXT)""")
        # canonical usage-event fields (blueprint §6.3) are part of the base schema here:
        # pricing_snapshot pins cost to a pricing version; environment + correlation_id +
        # resource_ref carry provenance.
        c.execute("""CREATE TABLE IF NOT EXISTS usage_events (
            id TEXT PRIMARY KEY, project_id TEXT, owner_user_id TEXT, app TEXT, feature TEXT,
            model TEXT, provider TEXT, prompt_tokens INTEGER DEFAULT 0, completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0, cost_usd DOUBLE PRECISION DEFAULT 0, latency_ms INTEGER,
            status TEXT DEFAULT 'ok', source TEXT DEFAULT 'api', metadata TEXT,
            pricing_snapshot TEXT, environment TEXT, correlation_id TEXT, resource_ref TEXT,
            occurred_at TEXT, created_at TEXT)""")
        # budget enforcement action (§7.7): what happens when over — notify|require_approval|throttle|block
        c.execute("""CREATE TABLE IF NOT EXISTS budgets (
            id TEXT PRIMARY KEY, project_id TEXT, owner_user_id TEXT, name TEXT NOT NULL,
            scope TEXT DEFAULT 'global', scope_ref TEXT, period TEXT DEFAULT 'monthly',
            limit_usd DOUBLE PRECISION NOT NULL, alert_pct INTEGER DEFAULT 80, status TEXT DEFAULT 'active',
            action TEXT DEFAULT 'notify', created_at TEXT, updated_at TEXT)""")
        c.execute("""CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT, action TEXT, actor_user_id TEXT,
            details TEXT, created_at TEXT)""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ev_owner ON usage_events(owner_user_id, occurred_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ev_project ON usage_events(project_id, occurred_at)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_ev_model ON usage_events(model)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_budget_owner ON budgets(owner_user_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_audit ON audit_logs(entity_type, entity_id, created_at)")
        for t in _TENANT_TABLES:
            c.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
            c.execute(f"ALTER TABLE {t} FORCE ROW LEVEL SECURITY")
            c.execute(f"DROP POLICY IF EXISTS {t}_isolation ON {t}")
            c.execute(f"""CREATE POLICY {t}_isolation ON {t}
                USING (owner_user_id IS NULL OR owner_user_id = current_setting('app.current_owner', true))
                WITH CHECK (owner_user_id IS NULL OR owner_user_id = current_setting('app.current_owner', true))""")
        c.execute("GRANT USAGE ON SCHEMA public TO app_rls")
        c.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO app_rls")


# --- users / admin / audit --------------------------------------------
def upsert_user(uid, email=None, name=None):
    if not uid:
        return
    now = now_iso()
    with _tx(uid) as cur:
        cur.execute("""INSERT INTO users (id,email,name,role,created_at,updated_at) VALUES (%s,%s,%s,'user',%s,%s)
                       ON CONFLICT (id) DO UPDATE SET email=COALESCE(EXCLUDED.email,users.email),
                         name=COALESCE(EXCLUDED.name,users.name), updated_at=EXCLUDED.updated_at""",
                    (uid, email, name, now, now))


def is_admin(uid):
    if not uid:
        return False
    admins = [a.strip() for a in os.environ.get("SPENDGUARD_ADMINS", "").split(",") if a.strip()]
    return uid in admins


def audit(entity_type, entity_id, action, actor, details=None):
    # audit_logs has no owner column (open table), so any tenant context can write it
    with _tx(None) as cur:
        cur.execute("INSERT INTO audit_logs (id,entity_type,entity_id,action,actor_user_id,details,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (new_id("aud"), entity_type, entity_id, action, actor, _j(details or {}), now_iso()))


def audit_for(entity_id, limit=80):
    with _tx(None) as cur:
        cur.execute("SELECT * FROM audit_logs WHERE entity_id=%s ORDER BY created_at DESC LIMIT %s", (entity_id, limit))
        rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r); d["details"] = _pj(d.get("details"), {}); out.append(d)
    return out


# --- projects (cost scopes) -------------------------------------------
def list_projects(viewer=None):
    # RLS scopes both the projects and the correlated usage_events aggregates to the viewer
    with _tx(viewer) as cur:
        cur.execute("""SELECT p.*,
                       (SELECT COUNT(*) FROM usage_events e WHERE e.project_id=p.id) AS event_count,
                       (SELECT COALESCE(SUM(e.cost_usd),0) FROM usage_events e WHERE e.project_id=p.id) AS spend_usd
                       FROM projects p ORDER BY p.updated_at DESC""")
        rows = cur.fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["event_count"] = int(d["event_count"] or 0)
        d["spend_usd"] = float(d["spend_usd"] or 0)
        out.append(d)
    return out


def get_project(pid, viewer=None):
    with _tx(viewer) as cur:
        cur.execute("SELECT * FROM projects WHERE id=%s", (pid,))
        r = cur.fetchone()
    return dict(r) if r else None


def create_project(data, owner):
    pid = new_id("proj"); now = now_iso()
    with _tx(owner) as cur:
        cur.execute("""INSERT INTO projects (id,owner_user_id,name,slug,description,status,icon,accent,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
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
    with _tx(owner) as cur:
        cur.execute("""INSERT INTO usage_events (id,project_id,owner_user_id,app,feature,model,provider,
                       prompt_tokens,completion_tokens,total_tokens,cost_usd,latency_ms,status,source,metadata,
                       pricing_snapshot,environment,correlation_id,resource_ref,occurred_at,created_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (eid, data.get("project_id"), owner, data.get("app", ""), data.get("feature", ""),
                     model, pricing.provider_of(model), pt, ct, tt, cost, data.get("latency_ms"),
                     data.get("status", "ok"), data.get("source", "api"), _j(data.get("metadata", {})),
                     snap, data.get("environment") or "production", data.get("correlation_id"),
                     _j(rref) if rref else None, data.get("occurred_at") or now, now))
    return {"id": eid, "model": model, "prompt_tokens": pt, "completion_tokens": ct,
            "total_tokens": tt, "cost_usd": cost, "provider": pricing.provider_of(model),
            "price_known": pricing.known(model), "pricing_snapshot": snap}


def list_events(viewer=None, project_id=None, model=None, limit=200):
    q = "SELECT * FROM usage_events WHERE TRUE"
    args = []
    if project_id and project_id != "all":
        q += " AND project_id=%s"; args.append(project_id)
    if model and model != "all":
        q += " AND model=%s"; args.append(model)
    q += " ORDER BY occurred_at DESC LIMIT %s"; args.append(limit)
    with _tx(viewer) as cur:
        cur.execute(q, args)
        rows = cur.fetchall()
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
    with _tx(owner) as cur:
        cur.execute("""INSERT INTO budgets (id,project_id,owner_user_id,name,scope,scope_ref,period,limit_usd,alert_pct,status,action,created_at,updated_at)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (bid, data.get("project_id"), owner, data["name"], data.get("scope", "global"),
                     data.get("scope_ref"), data.get("period", "monthly"), float(data["limit_usd"]),
                     int(data.get("alert_pct", 80)), "active", action, now, now))
    audit("budget", bid, "created", owner)
    return get_budget(bid, owner)


def get_budget(bid, viewer=None):
    with _tx(viewer) as cur:
        cur.execute("SELECT * FROM budgets WHERE id=%s", (bid,))
        r = cur.fetchone()
    return dict(r) if r else None


def update_budget(bid, data, owner):
    b = get_budget(bid, owner)
    if not b or (b.get("owner_user_id") and b["owner_user_id"] != owner and not is_admin(owner)):
        return None
    fields, args = [], []
    for k in ("name", "scope", "scope_ref", "period", "status", "action"):
        if k in data and data[k] is not None:
            fields.append(f"{k}=%s"); args.append(data[k])
    if data.get("limit_usd") is not None:
        fields.append("limit_usd=%s"); args.append(float(data["limit_usd"]))
    if data.get("alert_pct") is not None:
        fields.append("alert_pct=%s"); args.append(int(data["alert_pct"]))
    fields.append("updated_at=%s"); args.append(now_iso()); args.append(bid)
    with _tx(owner) as cur:
        cur.execute(f"UPDATE budgets SET {','.join(fields)} WHERE id=%s", args)
    audit("budget", bid, "updated", owner)
    return get_budget(bid, owner)


def delete_budget(bid, owner):
    b = get_budget(bid, owner)
    if not b or (b.get("owner_user_id") and b["owner_user_id"] != owner and not is_admin(owner)):
        return False
    with _tx(owner) as cur:
        cur.execute("DELETE FROM budgets WHERE id=%s", (bid,))
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
    """Actual spend in the current period matching the budget's scope.
    `c` is a cursor already inside the viewer's _tx, so RLS scopes the sum."""
    start = _period_start(b["period"]).isoformat() + "Z"
    q = "SELECT COALESCE(SUM(cost_usd),0) s FROM usage_events WHERE occurred_at>=%s"
    args = [start]
    if b["scope"] == "project" and b.get("scope_ref"):
        q += " AND project_id=%s"; args.append(b["scope_ref"])
    elif b["scope"] == "model" and b.get("scope_ref"):
        q += " AND model=%s"; args.append(b["scope_ref"])
    elif b["scope"] == "provider" and b.get("scope_ref"):
        q += " AND provider=%s"; args.append(b["scope_ref"])
    c.execute(q, args)
    return float(c.fetchone()["s"] or 0)


def list_budgets(viewer=None):
    with _tx(viewer) as cur:
        cur.execute("SELECT * FROM budgets ORDER BY created_at DESC")
        rows = cur.fetchall()
        out = []
        for r in rows:
            b = dict(r)
            spent = round(_spend_for_budget(cur, b, viewer), 4)
            lim = float(b["limit_usd"] or 0)
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
        lim = float(b["limit_usd"] or 0)
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
