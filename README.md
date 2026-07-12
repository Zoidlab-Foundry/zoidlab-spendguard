# ZoidLab SpendGuard — Foundry Package 07

**AI Cost Optimizer.** Answers *"where is our AI spend going, and how do we cut it?"*
from a real usage ledger — no fabricated numbers.

Part of the [ZoidLab Foundry](https://foundry.zoidlab.ai). Requires **Nyquest Pro**
(enforced on both the frontend gate and every backend data endpoint, fail-closed).

## What it does

- **Usage ledger** — record every AI call (model, tokens, app/feature). Cost is computed
  server-side from token counts × published list prices (`pricing.py`), never trusted from
  the caller.
- **Cost breakdown** — group spend by model / provider / project / app / feature over any window.
- **Budgets** — spend caps by scope (global/project/model/provider) and period; live spend
  is summed from the ledger for the current period, with alert + over states.
- **Savings simulator** — recompute your *real* historical token usage as if it had run on a
  different model. Exact arithmetic, honestly labelled — not an estimate.
- **Recommendations** — rule-based, explainable suggestions over real spend concentration
  (cheaper-model swaps with the exact estimated saving; concentration warnings).
- **Export** — portable **Nyquest Cost Report** (JSON/YAML) + cross-app integration hooks.

## Honesty

- Prices are a **static list-price snapshot** (`pricing.PRICE_SNAPSHOT`), labelled in the UI;
  they can differ from provider invoices. The cost arithmetic over your tokens is exact.
- The seeded demo ledger is **synthetic** and every seeded event is tagged `source="sample"`
  and flagged in the UI. Replace it by POSTing real events to `/api/events`.
- Models absent from the price table record `cost_usd = 0` and are surfaced as **unpriced**,
  never silently counted as free.

## Stack

- **Backend**: FastAPI + SQLite (Postgres-portable, JSON-as-TEXT). `pricing.py` (price table),
  `cost_engine.py` (deterministic analytics), `database.py`, `exporter.py`.
- **Frontend**: Next.js 15 + React 19 + Tailwind. Shared `zb_session` SSO + reusable
  `FoundryAccessGate` Pro gate.
- **Deploy** (zoidberg): `spendguard-api` (:8701 uvicorn) + `spendguard-web` (:3701 next) behind
  the Cloudflare tunnel at `spendguard.zoidlab.ai`.

## Dev

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn main:app --port 8701
cd ../frontend && npm install && npm run dev   # proxies /api → 127.0.0.1:8701
```
