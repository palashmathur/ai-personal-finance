# Personal Finance — Implementation Tickets (Backend-first)

Companion to [you-are-a-senior-glowing-piglet.md](you-are-a-senior-glowing-piglet.md).

**Strategy:** build the entire backend and verify it with Postman collections before writing a single line of frontend code. This means every API endpoint, service, and AI feature is complete and battle-tested before the UI phase starts. Frontend then connects to a rock-solid, fully-documented API.

**Testing convention:**
- `pytest` — unit/integration tests for services, pure functions, AI agent loop.
- **Postman** — manual API verification, saved as a collection in `postman/` (exported JSON committed to the repo). Each backend milestone ends with a Postman checkpoint ticket.
- Postman collections use an environment with `{{base_url}}=http://localhost:8000`.

---

## PHASE 1 — Backend

---

### Backend Group 1 — Repo + Schema + CRUD APIs
PF-1 through PF-9

#### PF-1 — Repo + dev tooling (backend only)
**Goal:** `apps/api` running locally; web scaffold deferred to Phase 2.
**AC:**
- `apps/api/pyproject.toml` declares: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic v2, anthropic, ruff, pytest, pytest-asyncio, httpx.
- `python -m uvicorn app.main:app --reload` starts the server on port 8000.
- `ruff check .` passes clean.
- Root `Makefile` with `make api` starts the backend.
- `data/` directory in `.gitignore`.

#### PF-2 — SQLAlchemy models for MVP schema
**Goal:** ORM models for all 6 MVP tables with correct types, FKs, and constraints.
**AC:**
- Models for: `accounts`, `categories`, `transactions`, `settings`, `instruments`, `investment_txns`.
- SQLAlchemy 2.0 `Mapped[...]` / `mapped_column()` syntax throughout.
- Money columns use `BigInteger` (paise; safe to totals of trillions).
- `category.parent_id` self-referential FK; `ON DELETE RESTRICT` for account/instrument FKs; `ON DELETE SET NULL` for `transactions.category_id`.
- `settings.id` has `CheckConstraint("id = 1")`.
**Deps:** PF-1.

#### PF-3 — Alembic init + migration 0001 (schema)
**Goal:** Schema versioned from day 1; round-trip upgrade/downgrade verified.
**AC:**
- `alembic upgrade head` from empty DB creates all 6 MVP tables.
- `alembic downgrade base` cleanly removes them.
- Indexes created: `transactions(occurred_on)`, `transactions(category_id)`, `transactions(account_id)`, `investment_txns(instrument_id, occurred_on)`.
- `PRAGMA journal_mode=WAL` and `PRAGMA foreign_keys=ON` set on every connect.
**Deps:** PF-2.

#### PF-4 — Alembic migration 0002 (seed data)
**Goal:** Starter categories and the single settings row seeded automatically on first run.
**AC:**
- Inserts income categories: Salary, Freelance, Bonus, Interest, Dividend, Refund, Gift, Other Income.
- Inserts expense parents + children (Food/Groceries/Dining Out/Snacks; Transport/Fuel/Cab/Transit; Housing/Rent/Maintenance; Utilities/Electricity/Internet/Mobile; Health/Doctor/Pharmacy/Insurance/Fitness; Shopping/Clothing/Electronics/Home; Lifestyle/Entertainment/Subscriptions/Personal Care; Travel/Flights/Hotels; Finance/Bank Charges/Loan EMI; Other/Misc).
- Inserts `settings(id=1, fy_start_month=4, allocation_targets='{}')`.
- Idempotent — running twice neither fails nor duplicates.
**Deps:** PF-3.

#### PF-5 — FastAPI app shell + OpenAPI
**Goal:** App skeleton with CORS, structured error responses, healthcheck.
**AC:**
- `GET /health` → `{"status": "ok", "db": "connected"}`.
- CORS allows all origins in dev (`*`); locked down in PF-39.
- Custom exception handler: all `HTTPException` and `RequestValidationError` return `{"detail": "...", "code": "..."}`.
- `/openapi.json` is reachable and valid.
- `pytest tests/test_health.py` passes.
**Deps:** PF-1.

#### PF-6 — Accounts CRUD
**Goal:** Full CRUD for bank/cash/broker accounts.
**AC:**
- `GET /api/accounts` (filter `?archived=true`), `POST`, `PATCH /{id}`, soft-delete (`PATCH /{id}` with `archived=true`).
- Hard delete rejected with 409 when any `transactions` or `investment_txns` reference the account.
- `type` validated to enum: `cash | bank | broker | wallet | credit_card`.
- `opening_balance_minor` defaults to 0, must be ≥ 0.
- pytest: happy path + FK violation + bad type.
- **Postman:** `POST` a new account; `GET` it back; `PATCH` to rename; `PATCH` to archive; verify it disappears from default list.
**Deps:** PF-2, PF-5.

#### PF-7 — Categories CRUD
**Goal:** Two-level category tree with kind enforcement and safe deletion.
**AC:**
- `GET /api/categories` → nested JSON `{...parent, children: [...]}`.
- `POST` rejects child whose `kind` differs from parent's.
- Cycle prevention: cannot set `parent_id` to a descendant of self.
- Delete sets `transactions.category_id = NULL` (ON DELETE SET NULL); returns count of affected txns in response.
- pytest: cycle detection, kind mismatch, delete with orphaned txns.
- **Postman:** create parent; create child; attempt kind mismatch (expect 422); delete parent with children.
**Deps:** PF-2, PF-5.

#### PF-8 — Transactions CRUD
**Goal:** Full ledger CRUD for income/expense/transfer with transfer pairing.
**AC:**
- `POST /api/transactions` validates: `kind ∈ {income, expense, transfer}`, `amount_minor > 0`, `category_id` required for income/expense (and must match kind), `account_id` must exist.
- Transfer creation: body has `{kind: "transfer", from_account_id, to_account_id, amount_minor, ...}`; service inserts two rows in one DB transaction, linked by a shared `note` field containing `#transfer:{uuid}`.
- `GET /api/transactions` supports: `from`, `to` (date), `account_id`, `category_id`, `kind`, `q` (partial note match), `limit` (default 50), `offset`.
- `PATCH /{id}` updates any field; for transfer rows, updates both paired rows atomically.
- `DELETE /{id}` for a transfer row deletes both halves.
- pytest: transfer pairing, FK violation, kind+category mismatch.
- **Postman:** add income; add expense; add transfer; verify paired rows; `GET` with filters; edit; delete.
**Deps:** PF-2, PF-5, PF-6, PF-7.

#### PF-9 — Postman collection: Core APIs
**Goal:** Committed, runnable Postman collection covering all Group 1 endpoints.
**AC:**
- Collection exported to `postman/01-core-apis.json`.
- Covers: health, accounts (CRUD + archive), categories (tree + CRUD + edge cases), transactions (CRUD + filters + transfer pairing).
- Uses `{{base_url}}` environment variable; requests chain IDs via Postman variables.
- Each request has a brief description.
- Collection runs top-to-bottom cleanly against a freshly-seeded DB.
**Deps:** PF-6, PF-7, PF-8.

---

### Backend Group 2 — Investments + Analytics
PF-10 through PF-18

#### PF-10 — Investment models + migration 0003
**Goal:** `instruments` and `investment_txns` tables.
**AC:**
- Models match plan §4; `investment_txns.quantity` is `Float` (MFs trade fractional units).
- Migration 0003 creates both tables with correct FKs and indexes.
- `alembic upgrade head` → `downgrade -1` → `upgrade head` round-trip passes.
**Deps:** PF-3.

#### PF-11 — Instruments find-or-create + search
**Goal:** Instrument catalog endpoints.
**AC:**
- `GET /api/instruments?q=...` — case-insensitive match on symbol or name; returns top 20.
- `POST /api/instruments` — validates `kind ∈ {mutual_fund, stock, etf, crypto, metal, other}`; rejects duplicate `(kind, symbol)` with 409.
- `PATCH /api/instruments/{id}` — update name, current_price_minor, meta.
- pytest: duplicate rejection, search ordering.
**Deps:** PF-10, PF-5.

#### PF-12 — Investment txns CRUD
**Goal:** Per-trade ledger endpoints.
**AC:**
- `POST /api/investment-txns` validates: `account.type ∈ {broker, wallet, bank, cash}` (bank/cash allowed because SIP debits come directly from a bank account; `credit_card` is the only excluded type), `quantity > 0`, `price_minor ≥ 0`, `side ∈ {buy, sell, dividend}`.
- Side effect on insert: if `instruments.current_price_minor IS NULL`, set it to `price_minor` from this trade (bootstrap, idempotent).
- `GET /api/investment-txns` supports: `from`, `to`, `instrument_id`, `account_id`, `side`.
- `PATCH /{id}` and `DELETE /{id}` supported.
- pytest: bootstrap side-effect, account-type validation.
**Deps:** PF-10, PF-11.

#### PF-13 — Holdings service + endpoint
**Goal:** Aggregated position view from the trade ledger.
**AC:**
- `GET /api/holdings` runs the GROUP BY SQL from plan §4b.
- Returns: `[{instrument, account, qty, cost_basis_minor, market_value_minor, unrealized_pnl_minor}]`.
- Excludes positions with `qty ≤ 0` (fully sold).
- Filters: `?account_id=`.
- pytest: seeds a set of buy/sell/dividend rows; asserts exact qty, cost_basis, pnl.
**Deps:** PF-12.

#### PF-14 — Dashboard endpoint
**Goal:** Single endpoint returning all four dashboard blocks.
**AC:**
- `GET /api/dashboard?from=&to=` returns `{cashflow: {income_minor, expense_minor, savings_rate}, by_category: [...], allocation: [...], networth_series: [...]}`.
- All math in `services/analytics.py` as pure functions.
- Net-worth series: monthly snapshots using `instruments.current_price_minor` for now (PF-27 upgrades to prices history).
- Allocation groups by `instrument.kind`, returns `[{kind, market_value_minor, pct}]`.
- pytest: fixture seeds 3 months of known data; snapshot-tests the full response JSON.
**Deps:** PF-8, PF-13.

#### PF-15 — Unified ledger endpoint
**Goal:** Single endpoint merging cash transactions + investment cashflows.
**AC:**
- `GET /api/ledger?from=&to=&limit=&offset=` runs the UNION ALL from plan §4b.
- Returns `[{source, source_id, kind, account_id, category_id, instrument_id, quantity, amount_minor, occurred_on, note, created_at}]`.
- `kind` values: `income | expense | transfer | inv_buy | inv_sell | inv_dividend`.
- `ORDER BY occurred_on DESC, created_at DESC`.
- pytest: asserts union row count equals `transactions` + `investment_txns` count for the period.
**Deps:** PF-8, PF-12.

#### PF-16 — Monthly cashflow summary endpoint
**Goal:** Monthly income/expense/investment breakdown with percentages.
**AC:**
- `GET /api/analytics/monthly?from=&to=` returns per-month rows from plan §4b.
- Response: `[{ym, income_minor, expense_minor, invest_minor, expense_pct, invest_pct, savings_minor, savings_pct}]`.
- `*_pct` is `null` when `income_minor == 0` (guard against division by zero).
- pytest: known 3-month fixture; exact pct values asserted.
**Deps:** PF-14, PF-15.

#### PF-17 — CSV import backend (parse + bulk insert)
**Goal:** Two-step import API: parse preview → confirm insert.
**AC:**
- `POST /api/imports/transactions/preview` accepts multipart CSV; returns parsed rows as `[{date, amount_minor, note, suggested_category_id}]` without inserting. Hardcoded HDFC Bank column mapping.
- `POST /api/imports/transactions/confirm` accepts `[{...row, account_id, category_id}]`; bulk-inserts in one DB transaction; returns `{inserted, skipped}`.
- Skip detection: `(amount_minor, occurred_on, note)` exact match in existing rows.
- pytest: happy CSV, duplicate detection, malformed CSV (422).
**Deps:** PF-8.

#### PF-18 — Postman collection: Investments + Analytics
**Goal:** Postman coverage for Group 2 endpoints.
**AC:**
- Collection exported to `postman/02-investments-analytics.json`.
- Covers: instruments (search, create, update price), investment-txns (buy, sell, dividend, list), holdings (verify numbers), dashboard (check all four blocks), ledger (check union), monthly summary, CSV import (upload + confirm).
- Chained requests: create instrument → buy → sell → verify holding → check dashboard reflects it.
**Deps:** PF-13, PF-14, PF-15, PF-16, PF-17.

---

### Backend Group 3 — AI Layer 1 + 2
PF-19 through PF-25

#### PF-19 — AI client + audit log
**Goal:** Anthropic SDK wired in; every LLM call audited.
**AC:**
- Migration 0004: `ai_calls(id, feature, model, input_tokens, output_tokens, cache_read_tokens, cache_creation_tokens, latency_ms, created_at)`.
- `app/ai/client.py::create(...)` wraps `anthropic.messages.create`, inserts an `ai_calls` row, returns the response.
- System prompt + static context blocks carry `cache_control: {type: "ephemeral"}`.
- `ANTHROPIC_API_KEY` loaded from `.env` via pydantic-settings.
- `GET /api/ai/usage?from=&to=` returns aggregated token + cost summary.
**Deps:** PF-3, PF-5.

#### PF-20 — Generic agent loop
**Goal:** `app/ai/agent.py::run_agent` — the reusable tool-use loop.
**AC:**
- Signature: `run_agent(messages, system, tools, model, max_steps=8) → AgentResult`.
- Loops until `stop_reason == 'end_turn'` or `max_steps` exceeded (raises `AgentError`).
- Collects each tool call's `(name, input, result)` in `AgentResult.steps`.
- pytest with a fake Anthropic client (no network): simulate tool_use → tool_result → end_turn; assert loop terminates correctly.
**Deps:** PF-19.

#### PF-21 — Tool registry
**Goal:** `app/ai/tools.py` — decorator + schema auto-generation.
**AC:**
- `@tool` decorator on a function with a Pydantic model input exposes `.schema` (Anthropic tool-use JSON) and `await .run(**kwargs)`.
- `TOOL_REGISTRY: dict[str, Tool]` keyed by name; used by the agent loop.
- pytest: assert a decorated function's schema matches the Anthropic spec shape.
**Deps:** PF-20.

#### PF-22 — Auto-categorize endpoint
**Goal:** Suggest a category for a txn; accept → write rule.
**AC:**
- Migration 0005: `categorization_rules(id, pattern, field, category_id, priority)`.
- `services/categorize.py::suggest(note, amount_minor)`:
  1. Try rules (regex match on note, ordered by priority DESC).
  2. On miss, call Claude Haiku with system prompt (cached) + categories list (cached) + txn fields → returns `{category_id, confidence, suggested_rule}`.
  3. Prompt caching verified: second call shows `cache_read_tokens > 0` in `ai_calls`.
- `POST /api/categorize/suggest` → `{category_id, category_name, confidence, suggested_rule}`.
- `POST /api/categorize/accept` → writes `categorization_rules` row + optionally updates txn's `category_id`.
- `GET /api/categorize/rules` → list rules. `DELETE /api/categorize/rules/{id}`.
- pytest golden set: 30 hand-labeled notes; assert ≥ 85% match (rules + LLM).
**Deps:** PF-21, PF-7.

#### PF-23 — NL input endpoint
**Goal:** Parse a natural-language expense/income string into a structured entry.
**AC:**
- Tool `create_expense(amount_minor, category_id, account_id, occurred_on, note)` registered.
- `POST /api/ai/nl-input` body: `{text: "spent 450 on uber yesterday", default_account_id}` → calls `run_agent` → returns the parsed `tool_use` payload as JSON (does **not** insert; caller confirms first).
- Edge cases: "yesterday" → ISO date; unknown category → trigger categorize; missing account → use `default_account_id`.
- pytest: 10 golden-set phrases with canned fake-client responses; assert correct field parsing.
**Deps:** PF-21, PF-22.

#### PF-24 — Deterministic insights endpoint
**Goal:** Quick insights computed in pure Python, no LLM needed yet.
**AC:**
- `GET /api/insights/quick?from=&to=` returns `[{kind, title, body}]`.
- Three kinds:
  - `savings_rate`: "Savings rate this month: 34% (−6pp vs 3-month median)."
  - `top_category_change`: "Dining Out up ₹3,200 (+47%) vs last month."
  - `allocation_drift`: "Equity at 71% — 6pp above your 65% target." (only if targets set).
- pytest: seeded fixture; assert body strings contain the correct numeric values.
**Deps:** PF-14.

#### PF-25 — Postman collection: AI Layer
**Goal:** Postman collection to verify AI endpoints manually.
**AC:**
- Exported to `postman/03-ai-layer.json`.
- Covers: `POST /ai/nl-input` (try 5 phrases); `POST /categorize/suggest` (try 5 notes); `POST /categorize/accept`; `GET /categorize/rules`; `GET /ai/usage`; `GET /insights/quick`.
- Each request has the expected response shape documented in a comment.
**Deps:** PF-22, PF-23, PF-24.

---

### Backend Group 4 — V2 Schema + Backend Polish
PF-26 through PF-31

#### PF-26 — Migration 0006: prices table + price-fetch service
**Goal:** Historical prices for accurate net-worth valuation.
**AC:**
- Migration 0006: `prices(instrument_id, on_date, close_minor, PK(instrument_id, on_date))`.
- `services/pricing.py::fetch_prices(instrument_id)`:
  - MF: AMFI daily NAV file → match by `meta.amfi_code` → upsert.
  - Stock/ETF: `yfinance` (NSE stocks: append `.NS`).
  - Crypto: CoinGecko `/simple/price?ids=...&vs_currencies=inr`.
  - Metal: skip for now (manual only).
- `POST /api/prices/refresh?instrument_id=` triggers fetch for one instrument.
- `POST /api/prices/refresh-all` triggers all active instruments.
- pytest: mock HTTP responses for each source type; assert upsert behavior.
**Deps:** PF-10, PF-5.

#### PF-27 — Net-worth series uses price history
**Goal:** Historical net-worth line is accurate (not "current price for all dates").
**AC:**
- `services/analytics.py::networth_series(start, end)` now joins `prices` table per `(instrument_id, month_end_date)`.
- Falls back to nearest-earlier price when exact date is missing; falls back to `instruments.current_price_minor` only when no price history exists at all.
- Dashboard endpoint response unchanged (same field names); numbers are now more accurate.
- pytest: fixture with known prices at month-ends; assert exact net-worth values.
**Deps:** PF-14, PF-26.

#### PF-28 — XIRR service
**Goal:** `services/analytics.py::xirr(cashflows)` pure function.
**AC:**
- Uses `scipy.optimize.brentq` with Newton fallback.
- Input: `[{date, amount_minor}]` — positive = cash in, negative = cash out.
- Output: annualized rate (float) or `None` if no solution.
- `GET /api/holdings/{id}/xirr` returns `{instrument_id, xirr_pct}` for a single holding.
- pytest: known cashflows (buy ₹10k, sell ₹12k 1 year later = ~20% XIRR) within ±0.5%.
**Deps:** PF-13.

#### PF-29 — Settings CRUD endpoint
**Goal:** Read and update the single settings row.
**AC:**
- `GET /api/settings` → `{fy_start_month, allocation_targets}`.
- `PATCH /api/settings` → partial update; validates `fy_start_month ∈ {1..12}`; validates `allocation_targets` values sum ≤ 1.0.
- pytest: invalid month, allocation > 100%.
**Deps:** PF-2, PF-5.

#### PF-30 — Backups
**Goal:** Automated nightly DB snapshot + manual export endpoint.
**AC:**
- APScheduler copies `data/finance.db` → `data/backups/finance-YYYY-MM-DD.db` nightly at 02:00. Keeps last 14 copies.
- `GET /api/export.json` streams all rows as JSON (`{accounts, categories, transactions, ...}`). Does not include prices history (re-fetchable).
- pytest: mock scheduler; assert backup file is created; assert export JSON structure.
**Deps:** PF-3.

#### PF-31 — Postman collection: V2 Schema + Polish
**Goal:** Postman coverage for Group 4 endpoints.
**AC:**
- Exported to `postman/04-v2-schema.json`.
- Covers: `POST /prices/refresh` (verify price lands in DB), `GET /api/holdings/{id}/xirr`, `GET/PATCH /api/settings`, `GET /api/export.json`.
**Deps:** PF-26, PF-27, PF-28, PF-29, PF-30.

---

### Backend Group 5 — RAG + Insights
PF-32 through PF-34

#### PF-32 — Chroma + indexer
**Goal:** Embed financial events for retrieval-augmented generation.
**AC:**
- Migration 0007: `embeddings_meta(id, source_kind, source_id, chunk_text, chroma_id, created_at)`.
- `app/ai/rag.py::index_txn(txn_id)` and `index_investment_txn(txn_id)` write chunks to Chroma + pointer to `embeddings_meta`.
- Chunk format: `"YYYY-MM-DD: ₹X,XXX expense in <Category> from <Account> — <note>"`.
- `app/ai/rag.py::retrieve(query, k=10)` returns top-K chunks.
- Service layer calls `index_txn` on create/update/delete.
- `python -m app.cli reindex-all` backfills all existing txns.
- pytest: round-trip (index → retrieve with matching query → assert chunk returned).
**Deps:** PF-19, PF-8.

#### PF-33 — Monthly insights generator
**Goal:** LLM-narrated insights backed by deterministic facts + retrieved history.
**AC:**
- Migration 0008: `insights(id, period_start, period_end, kind, title, body, data JSON, generated_at, model)`.
- `services/insights.py::generate_for_month(year, month)`:
  1. Compute facts via `analytics.py` (top category changes, drift, savings-rate trend).
  2. Retrieve top-10 historical chunks.
  3. Call Claude Sonnet; system prompt: *"Only use numbers that appear in the facts block. Do not invent values."*
  4. Upsert result in `insights` keyed by `(period_start, period_end, kind)`.
- `GET /api/insights?from=&to=` returns cached insights.
- `POST /api/insights/generate?year=&month=` triggers generation (force-regenerates if cached).
- pytest numeric guard: regex-extract all digit sequences from `body`; assert every number appears verbatim in the facts JSON.
**Deps:** PF-24, PF-32.

#### PF-34 — Postman collection: RAG + Insights
**Goal:** Postman coverage for Group 5 endpoints.
**AC:**
- Exported to `postman/05-rag-insights.json`.
- Covers: `POST /insights/generate` (run for current month), `GET /insights` (read back), `GET /ai/usage` (check Sonnet token spend).
**Deps:** PF-33.

---

### Backend Group 6 — Chat Advisor
PF-35 through PF-37

#### PF-35 — Read-only AI tools
**Goal:** Tools the chat agent can call without risking writes.
**AC:**
- Tools registered: `query_transactions(from, to, account_id, category_id, limit)`, `get_holdings(as_of)`, `get_allocation()`, `compute_xirr(instrument_id)`, `get_monthly_summary(year)`.
- Each tool's DB session uses `execution_options(isolation_level='READ UNCOMMITTED')` and raises on any write attempt (SQLAlchemy event hook).
- pytest: attempt a write inside the tool session; assert it raises. Call each tool with valid args; assert structured JSON returned.
**Deps:** PF-21, PF-13, PF-14, PF-28.

#### PF-36 — Chat backend (streaming SSE)
**Goal:** Streaming multi-turn chat endpoint with full tool-use support.
**AC:**
- Migration 0009: `chat_threads(id, title, created_at)`, `chat_messages(id, thread_id, role, content_json, created_at)`.
- `POST /api/chat` body: `{thread_id?, message_text}` — creates thread if new; streams `text/event-stream`.
- SSE event types: `token` (text delta), `tool_start`, `tool_end`, `done`.
- Messages persisted on stream completion.
- System prompt enforces analyst persona + hard-coded refusal: *"Do not advise buying or selling specific securities."*
- `GET /api/chat/threads` → list threads. `GET /api/chat/threads/{id}/messages` → message history.
- pytest: integration test with fake streaming client; assert SSE event sequence.
**Deps:** PF-35, PF-19.

#### PF-37 — Postman collection: Chat
**Goal:** Verify chat endpoint with Postman's SSE support (or curl fallback).
**AC:**
- Exported to `postman/06-chat.json`.
- Includes: start a new thread; ask "what's my savings rate this month?"; ask "should I buy HDFC Bank?" (expect refusal); list threads; fetch message history.
- Notes explain how to view SSE in Postman's response panel.
**Deps:** PF-36.

---

### Backend Group 7 — Auth + Multi-user DB
PF-38 through PF-42

#### PF-38 — Registry DB + per-user engine cache
**Goal:** Move from one shared `finance.db` to one DB per user.
**AC:**
- `data/registry.db` with `users(id, email, name, db_path, created_at)`.
- `app/db/registry.py` — engine/session for registry only.
- `app/db/user_db.py` — LRU cache `{user_id: Engine}`; opens `data/users/{user_id}.db` lazily; applies WAL + foreign_keys pragmas.
- `get_user_db(user_id)` FastAPI dependency resolves to the user's session.
- `scripts/migrate_to_per_user.py`: moves existing `data/finance.db` → `data/users/1.db`; inserts placeholder registry row.
- pytest: create two user engines; assert no data cross-contamination.
**Deps:** PF-3.

#### PF-39 — Google OAuth + session cookie
**Goal:** Sign-in works end-to-end; all endpoints require auth.
**AC:**
- `authlib` library; `GET /auth/login` → Google OAuth redirect; `GET /auth/callback` exchanges code for user profile.
- Session: signed JWT in an httpOnly `session` cookie.
- `current_user = Depends(get_current_user)` raises 401 when cookie absent or invalid.
- All existing routers gain `current_user` dependency; DB session resolves through `get_user_db(current_user.id)`.
- `GET /auth/me` → `{id, email, name}` or 401. `POST /auth/logout` clears the cookie.
- pytest: test 401 on a protected endpoint with no cookie; test `/auth/me` with a valid signed cookie.
**Deps:** PF-38.

#### PF-40 — New-user onboarding
**Goal:** OAuth callback for a first-time user auto-provisions their DB.
**AC:**
- On callback for unknown email: insert registry row; create empty `data/users/{id}.db`; run Alembic `upgrade head` programmatically against it.
- Subsequent logins reuse existing DB.
- `scripts/migrate_all_users.py`: loops registry, runs `alembic upgrade head` against each file; reports pass/fail per user.
- pytest: simulate new user flow; assert DB file is created and seeded tables exist.
**Deps:** PF-39.

#### PF-41 — Postman collection: Auth
**Goal:** Postman coverage for Group 7 endpoints.
**AC:**
- Exported to `postman/07-auth.json`.
- Covers: `GET /auth/me` without cookie (expect 401), with valid cookie (expect user JSON); `POST /auth/logout`; protected endpoint without cookie (expect 401).
- Note: Google OAuth full flow requires a browser; manual steps documented in the collection description.
**Deps:** PF-39, PF-40.

#### PF-42 — Backend complete — Postman master smoke-run
**Goal:** Confirm the entire backend works end-to-end before Phase 2 starts.
**AC:**
- All 7 Postman collections (`01–07`) imported into one Postman workspace.
- Full smoke-run against a fresh DB (delete `data/finance.db`, run `alembic upgrade head`) passes without manual intervention.
- All 200/201 responses verified; all expected 4xx error cases verified.
- This is the **gate** to start Phase 2.
**Deps:** PF-9, PF-18, PF-25, PF-31, PF-34, PF-37, PF-41.

---

## PHASE 2 — Frontend

*(Start only after PF-42 is checked off.)*

---

### Frontend Group 1 — Scaffold + Transactions
PF-F1 through PF-F4

#### PF-F1 — Vite + React scaffold
**Goal:** Frontend project running, connected to the live backend.
**AC:**
- `apps/web` with Vite + React 18 + TypeScript + Tailwind + shadcn/ui.
- `VITE_API_URL=http://localhost:8000` in `.env`.
- `npm run dev` starts on port 5173.
- `npm run typecheck` passes.
- Root `Makefile` updated: `make web` starts the frontend; `make dev` starts both.
**Deps:** PF-1.

#### PF-F2 — Auto-generated TS API client
**Goal:** Typed frontend client generated from FastAPI's OpenAPI spec.
**AC:**
- `scripts/gen-api-client.sh` calls `openapi-typescript-codegen` against `/openapi.json`; outputs to `apps/web/src/lib/api/`.
- Client committed so `npm run typecheck` passes without the backend running.
- One smoke call (`api.health.getHealth()`) verified in a test component.
**Deps:** PF-F1, PF-5.

#### PF-F3 — AppShell + Global filter store
**Goal:** Layout, sidebar navigation, global date-range/account filter.
**AC:**
- Sidebar with links: Dashboard, Transactions, Investments, Insights, Chat, Settings.
- Zustand store `useFiltersStore`: `{from, to, accountIds}` with presets: This Month, Last 3M, FY (Apr–Mar), YTD, Custom.
- Filter state passed as query keys so TanStack Query refetches when filters change.
- Dark mode toggle wired (shadcn `ThemeProvider`).
**Deps:** PF-F2.

#### PF-F4 — Transactions page
**Goal:** Full CRUD UI for income/expense/transfer.
**AC:**
- Table with columns: Date, Kind, Account, Category, Amount (₹), Note. Paginated (50/page). Sortable by date.
- "Add" button opens a dialog form; react-hook-form + zod validation; optimistic insert.
- Inline edit on row click; delete with confirm dialog.
- Transfer creation: shows From Account + To Account; backend handles the paired rows.
- Toast on success/error. Empty state with CTA.
**Deps:** PF-F3.

---

### Frontend Group 2 — Investments + Dashboard
PF-F5 through PF-F7

#### PF-F5 — Investments page
**Goal:** Add investment trades and view current holdings.
**AC:**
- Holdings table: Instrument, Kind, Qty, Avg Cost (₹), Current Price (₹), Market Value (₹), P&L (₹ + %), XIRR (%).
- "Add Trade" dialog: instrument typeahead, "Create new instrument" inline option, side, qty, price, fee, date, account.
- "Update Price" button per row → calls `PATCH /api/instruments/{id}`.
- Delete a trade via the trade list tab.
**Deps:** PF-F3.

#### PF-F6 — Dashboard (4 charts)
**Goal:** The four core data visualizations, driven by global filters.
**AC:**
- CashflowSummary cards: Income / Expenses / Savings Rate.
- CategoryBar: horizontal Recharts bar chart, top 10 expense categories.
- AllocationDonut: Recharts PieChart with center-text total net worth.
- NetWorthLine: Recharts AreaChart, monthly data points.
- All charts auto-update when a txn or investment is added/edited (TanStack Query invalidation).
**Deps:** PF-F3.

#### PF-F7 — CSV import UI
**Goal:** Upload → preview → confirm flow.
**AC:**
- "Import CSV" button → opens multi-step dialog.
- Step 1: upload file → calls `POST /api/imports/transactions/preview` → shows parsed rows table.
- Step 2: user adjusts account + category per row (or bulk-assign).
- Step 3: "Confirm Import" → calls `POST /api/imports/transactions/confirm` → shows inserted/skipped count.
**Deps:** PF-F4.

---

### Frontend Group 3 — AI Features UI
PF-F8 through PF-F9

#### PF-F8 — Auto-categorize chip
**Goal:** When a transaction has no category, suggest one inline.
**AC:**
- On transaction rows with `category_id == null`, show a chip "Suggested: Groceries (87%) ✓✗".
- Clicking ✓ calls `POST /api/categorize/accept`; ✗ dismisses.
- Confidence < 60% shows as a muted suggestion, not auto-highlighted.
**Deps:** PF-F4.

#### PF-F9 — NL input box
**Goal:** Natural language expense entry with confirm card.
**AC:**
- Input box on Dashboard (or floating command palette `Cmd-K`).
- On submit, calls `POST /api/ai/nl-input` → shows a confirm card with parsed fields (editable).
- "Save" on the confirm card calls `POST /api/transactions` with the parsed values.
- Loading state during AI call; error toast if AI fails.
**Deps:** PF-F6.

---

### Frontend Group 4 — Polish + Visualization
PF-F10 through PF-F12

#### PF-F10 — Advanced charts
**Goal:** Sankey, Heatmap, XIRR sparklines.
**AC:**
- Sankey (`@visx/sankey`): Income → Categories → Savings/Investments pool; responds to date filters.
- Category Heatmap: months × categories grid; color intensity = ₹ spend; hover tooltip.
- Sparkline + XIRR column in the holdings table (uses `GET /api/holdings/{id}/xirr`).
**Deps:** PF-F5, PF-F6.

#### PF-F11 — Settings page
**Goal:** Edit FY start month, allocation targets; drift indicator on donut.
**AC:**
- FY start month select (Jan / Apr); saves to `PATCH /api/settings`.
- Per-asset-class target percentage inputs; sum-to-100 validation in UI; saves.
- Allocation donut gains a target-vs-actual ring; drift values listed below with color coding.
**Deps:** PF-F6.

#### PF-F12 — Deterministic insights cards
**Goal:** Surface quick insights from `GET /api/insights/quick` on the dashboard.
**AC:**
- Dashboard shows 3 compact insight cards (savings rate, top category change, drift).
- Each card has a "Why?" expand link showing the calculation breakdown.
- Refreshes when global filters change.
**Deps:** PF-F6.

---

### Frontend Group 5 — Insights + Chat
PF-F13 through PF-F14

#### PF-F13 — Insights page
**Goal:** Full LLM-narrated insights history.
**AC:**
- `/insights` route: insights grouped by month, newest first.
- "Generate for [Month]" button calls `POST /api/insights/generate`.
- Each insight card shows title, body (markdown rendered), and generation timestamp.
- Dashboard pins the 3 most recent insights.
**Deps:** PF-F6.

#### PF-F14 — Chat UI
**Goal:** Streaming chat with tool-call visibility.
**AC:**
- `/chat` route: thread list on left; message pane on right.
- Messages stream via `EventSource`; text deltas render progressively.
- Tool calls render as collapsible `🔧 query_transactions(...)` rows; click to expand input/output JSON.
- New thread created automatically on first message.
- Sending while streaming is disabled.
**Deps:** PF-F3.

---

### Frontend Group 6 — Auth UI + Deploy
PF-F15 through PF-F17

#### PF-F15 — Auth UI
**Goal:** Sign-in page + redirect-on-401 behavior.
**AC:**
- `/login` page with "Sign in with Google" button → hits `GET /auth/login` (redirect).
- On any 401 from the API client, redirect to `/login`.
- `GET /auth/me` on app load to detect signed-in state.
- Header shows user avatar/email + "Sign out" button.
**Deps:** PF-39, PF-F3.

#### PF-F16 — Docker + static serving
**Goal:** Vite build served by FastAPI; one container for everything.
**AC:**
- Multi-stage Dockerfile: Stage 1 `node` → `vite build` → `dist/`. Stage 2 `python` → copies `dist/` to `app/static/`; FastAPI serves SPA fallback for all non-API routes.
- `docker compose up` runs the complete stack locally.
- Healthcheck wired in Dockerfile.
**Deps:** PF-F15, PF-40.

#### PF-F17 — Deploy
**Goal:** App live at a real URL with HTTPS + backups.
**AC:**
- Deployed to Fly.io or Railway with persistent volume mounted at `/data`.
- Litestream sidecar replicates `data/` to S3-compatible storage; restore procedure documented.
- Google OAuth redirect URIs updated to production domain.
- All 7 Postman collections re-run against the production URL; all pass.
**Deps:** PF-F16.

---

## Ticket index

| ID | Ticket | Group |
|---|---|---|
| PF-1 | Repo + dev tooling | Backend G1 |
| PF-2 | SQLAlchemy models | Backend G1 |
| PF-3 | Migration 0001 — schema | Backend G1 |
| PF-4 | Migration 0002 — seed data | Backend G1 |
| PF-5 | FastAPI app shell | Backend G1 |
| PF-6 | Accounts CRUD | Backend G1 |
| PF-7 | Categories CRUD | Backend G1 |
| PF-8 | Transactions CRUD | Backend G1 |
| PF-9 | Postman: Core APIs | Backend G1 |
| PF-10 | Investment models + migration | Backend G2 |
| PF-11 | Instruments find-or-create | Backend G2 |
| PF-12 | Investment txns CRUD | Backend G2 |
| PF-13 | Holdings service + endpoint | Backend G2 |
| PF-14 | Dashboard endpoint | Backend G2 |
| PF-15 | Unified ledger endpoint | Backend G2 |
| PF-16 | Monthly cashflow summary | Backend G2 |
| PF-17 | CSV import backend | Backend G2 |
| PF-18 | Postman: Investments + Analytics | Backend G2 |
| PF-19 | AI client + audit log | Backend G3 |
| PF-20 | Generic agent loop | Backend G3 |
| PF-21 | Tool registry | Backend G3 |
| PF-22 | Auto-categorize endpoint | Backend G3 |
| PF-23 | NL input endpoint | Backend G3 |
| PF-24 | Deterministic insights endpoint | Backend G3 |
| PF-25 | Postman: AI Layer | Backend G3 |
| PF-26 | Migration 0006 — prices + price-fetch | Backend G4 |
| PF-27 | Net-worth series uses price history | Backend G4 |
| PF-28 | XIRR service | Backend G4 |
| PF-29 | Settings CRUD endpoint | Backend G4 |
| PF-30 | Backups | Backend G4 |
| PF-31 | Postman: V2 Schema + Polish | Backend G4 |
| PF-32 | Chroma + indexer | Backend G5 |
| PF-33 | Monthly insights generator | Backend G5 |
| PF-34 | Postman: RAG + Insights | Backend G5 |
| PF-35 | Read-only AI tools | Backend G6 |
| PF-36 | Chat backend (streaming SSE) | Backend G6 |
| PF-37 | Postman: Chat | Backend G6 |
| PF-38 | Registry DB + per-user engine | Backend G7 |
| PF-39 | Google OAuth + session cookie | Backend G7 |
| PF-40 | New-user onboarding | Backend G7 |
| PF-41 | Postman: Auth | Backend G7 |
| PF-42 | Backend complete — master smoke-run | Backend gate |
| PF-F1 | Vite + React scaffold | Frontend G1 |
| PF-F2 | Auto-generated TS API client | Frontend G1 |
| PF-F3 | AppShell + Global filter store | Frontend G1 |
| PF-F4 | Transactions page | Frontend G1 |
| PF-F5 | Investments page | Frontend G2 |
| PF-F6 | Dashboard (4 charts) | Frontend G2 |
| PF-F7 | CSV import UI | Frontend G2 |
| PF-F8 | Auto-categorize chip | Frontend G3 |
| PF-F9 | NL input box | Frontend G3 |
| PF-F10 | Advanced charts | Frontend G4 |
| PF-F11 | Settings page | Frontend G4 |
| PF-F12 | Deterministic insights cards | Frontend G4 |
| PF-F13 | Insights page | Frontend G5 |
| PF-F14 | Chat UI | Frontend G5 |
| PF-F15 | Auth UI | Frontend G6 |
| PF-F16 | Docker + static serving | Frontend G6 |
| PF-F17 | Deploy | Frontend G6 |

---

## Dependency map

```
Phase 1 (Backend):
PF-1 → PF-2 → PF-3 → PF-4
PF-1 → PF-5
PF-2, PF-5 → PF-6
PF-2, PF-5 → PF-7
PF-2, PF-5, PF-6, PF-7 → PF-8
PF-6, PF-7, PF-8 → PF-9

PF-3 → PF-10 → PF-11 → PF-12 → PF-13 → PF-14 → PF-16
                                  PF-13 → PF-28
PF-8, PF-12 → PF-15 → PF-16
PF-8 → PF-17
PF-13, PF-14, PF-15, PF-16, PF-17 → PF-18

PF-3, PF-5 → PF-19 → PF-20 → PF-21 → PF-22 → PF-23
                               PF-21, PF-13, PF-14, PF-28 → PF-35 → PF-36 → PF-37
PF-14 → PF-24
PF-22, PF-23, PF-24 → PF-25

PF-10, PF-5 → PF-26 → PF-27
PF-2, PF-5 → PF-29
PF-3 → PF-30
PF-26, PF-27, PF-28, PF-29, PF-30 → PF-31

PF-19, PF-8 → PF-32 → PF-33 → PF-34

PF-3 → PF-38 → PF-39 → PF-40
PF-39, PF-40 → PF-41
PF-9, PF-18, PF-25, PF-31, PF-34, PF-37, PF-41 → PF-42

Phase 2 (Frontend, starts after PF-42):
PF-1 → PF-F1 → PF-F2 → PF-F3 → PF-F4 → PF-F7, PF-F8
                          PF-F3 → PF-F5 → PF-F10
                          PF-F3 → PF-F6 → PF-F9, PF-F10, PF-F11, PF-F12, PF-F13
                          PF-F3 → PF-F14
PF-39, PF-F3 → PF-F15 → PF-F16 → PF-F17
PF-40 → PF-F16
```

---

## Out-of-scope (not in this plan)
- CAMS/Karvy CAS PDF parser
- Bank statement parsers beyond HDFC CSV
- Tax computation (LTCG/STCG, FIFO/LIFO)
- Goals + projections
- Recurring txns / SIP automation
- Mobile PWA
- Multi-currency
- Multi-agent investment analysis (L5 AI) — re-evaluate LangGraph when we get there
