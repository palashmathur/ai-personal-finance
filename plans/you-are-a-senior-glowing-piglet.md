# Personal Finance App — Design & Build Plan

## Context

You want a single-user, local-first personal finance dashboard that tracks **income, expenses, and investments (MF / stocks / ETFs / crypto / metals)**, recomputes dashboards on every change, and progressively becomes an **AI-powered financial assistant** (auto-categorization → NL input → RAG-backed insights → chat advisor). Primary motivation: ship a useful tool *and* learn AI/GenAI hands-on.

**Locked decisions (from clarifying Qs):**
- **Stack:** React (Vite) + TypeScript on the frontend, **Python FastAPI** on the backend, **SQLite** for storage.
- **AI provider:** Anthropic **Claude API** (Python SDK), with prompt caching.
- **Currency:** **INR-only.** Every monetary value is stored as an integer `amount_minor` (paise). No `currency` or `fx_rate` columns anywhere. Multi-currency can be added later by introducing those columns and a migration — for now, it's pure clutter.
- **Auth:** skip in MVP, add **Google OAuth via Authlib** (FastAPI) + httpOnly session cookies before deploy. No `user_id` columns in MVP — added in the auth migration.

---

## 1. Product Brainstorm

### How the app should *feel*
- **Dashboard-first.** Open the app → instantly see net worth, this month's cashflow, and asset allocation. No menu-diving for the basics.
- **Two-pane workflow.** Left: "what happened" (income/expense/investment ledgers). Right: "what it means" (charts that recompute live). Adding a row should make the chart twitch — that feedback loop is the whole UX.
- **One-tap entry.** Add expense in ≤3 fields (amount, category, note). Date defaults to today. Power users get a command palette (Cmd-K) and a single NL input box.
- **Quiet by default.** Neutral palette, generous whitespace, no gamification. Money apps that look like games (Mint-style "you spent $4 more on coffee!") get annoying fast for the actual owner of the money.
- **Time controls everywhere.** Every chart respects a global date range picker (This Month / Last 3M / FY / YTD / Custom). FY defaults to Apr–Mar (Indian FY) but is configurable.
- **Honest investment view.** Show **invested**, **current value**, **absolute P&L**, **XIRR**, side-by-side. Don't bury the cost basis like most retail apps do.

### Visualization ideas (worth building)
- **Net Worth line** — single most important chart, monthly snapshot, stacked by asset class.
- **Sankey: Income → Categories → Savings/Investments** — *the* "where did my money go" view for a month.
- **Asset allocation donut** with a target-vs-actual ring around it (drift indicator).
- **Category heatmap** — months × categories, color = spend intensity. Surfaces seasonal patterns instantly.
- **Cashflow waterfall** — opening balance → +income → −expenses → +investments returns → closing.
- **Per-holding sparkline + XIRR** in the holdings table.
- **Savings rate gauge** with a 6-month rolling average overlay.

### Smart insights (the AI hook)
- "Your dining-out spend is 38% above your 3-month median."
- "Equity allocation is 72% — drifted +7pp from your 65% target. ₹X needs to move to debt to rebalance."
- "Three SIPs failed this month — ₹Y short of your monthly investment plan."
- "If you keep this savings rate, you'll cross ₹10L net worth by Sep 2026."
- All insights are **deterministic-first** (computed in Python), then LLM phrases them. Never let the LLM invent a number.

---

## 2. Feature Breakdown — MUST vs NICE

### MUST-HAVE (MVP)
| Feature | Notes |
|---|---|
| Add/edit/delete income, expense, investment txn | Forms + tables; optimistic UI |
| Categories + subcategories (seeded + user-editable) | Tree, two levels |
| Accounts (cash, bank, broker, wallet) | Just a dimension on txns; no double-entry |
| Investment holdings view | Group by symbol, compute qty/avg cost/current value |
| Dashboard: net worth, cashflow, allocation, category breakdown | The four core charts |
| Global date-range filter | Drives every widget |
| FY config (calendar vs Apr–Mar) | Single setting |
| CSV import (expenses) | Mapping wizard; saves a "profile" per source |
| SQLite + Alembic migrations | Schema versioned from day 1 |
| Local backup (DB file copy + JSON export) | Single-user app, real risk is data loss |

### NICE-TO-HAVE (post-MVP)
- Bank/broker statement parsers (HDFC, ICICI, Zerodha, Schwab CSVs)
- CAMS/Karvy CAS PDF parser for Indian MFs (single best onboarding feature for India users)
- Goals (e.g., "₹50L emergency fund by 2027") with progress bars
- Recurring txns (rent, SIPs auto-create on schedule)
- Splitwise-style shared expenses (almost certainly out of scope — single user)
- Tags (orthogonal to categories)
- Receipt OCR (photo → expense draft)
- PWA / offline mode
- Crypto price feed (CoinGecko)
- Stock/ETF price feed (yfinance for US, NSE bhavcopy for India)
- MF NAV feed (AMFI daily NAV file — free, no key)
- Notifications: weekly digest, drift alerts, SIP failures
- Export: PDF monthly report
- Multi-portfolio (mine vs spouse vs HUF)

### Explicitly OUT of scope (for now)
- Tax computation (capital gains FIFO/LIFO, ITR forms) — huge rabbit hole
- Bill payment / actual money movement
- Multi-user with permissions
- Mobile native app

---

## 3. System Architecture

### High-level
```
┌─────────────────┐     HTTP/JSON      ┌──────────────────┐
│  React (Vite)   │ ─────────────────► │   FastAPI        │
│  TS + Tailwind  │ ◄───────────────── │   Python 3.12    │
│  TanStack Query │                    │                  │
└─────────────────┘                    │  ┌────────────┐  │
                                        │  │ SQLAlchemy │  │
                                        │  └─────┬──────┘  │
                                        │        ▼         │
                                        │   SQLite (file)  │
                                        │                  │
                                        │  ┌────────────┐  │
                                        │  │ Anthropic  │──┼──► api.anthropic.com
                                        │  │ SDK        │  │
                                        │  └────────────┘  │
                                        │  ┌────────────┐  │
                                        │  │ Chroma     │  │  (local vector store
                                        │  │ (local)    │  │   for RAG)
                                        │  └────────────┘  │
                                        └──────────────────┘
```

### Frontend
- **React 18 + Vite + TypeScript.**
- **Routing:** React Router (`/`, `/transactions`, `/investments`, `/insights`, `/settings`).
- **Server state:** **TanStack Query** — handles cache invalidation on mutations (this is what makes "dashboard updates live" cheap).
- **UI state:** **Zustand** (one tiny store for global filters: date range, account filter). Avoid Redux.
- **Styling:** **Tailwind + shadcn/ui** (Radix under the hood — accessible, themeable, copy-paste components).
- **Charts:** **Recharts** for standard charts; **visx** only if you need the Sankey (Recharts has none).
- **Forms:** react-hook-form + zod.
- **Component structure:**
  ```
  src/
    pages/         # Dashboard, Transactions, Investments, Insights, Settings
    components/
      charts/      # NetWorthLine, AllocationDonut, CategoryHeatmap, CashflowSankey
      forms/       # TxnForm, InvestmentForm, CategoryEditor
      tables/      # TxnTable, HoldingsTable
      shell/       # AppShell, Sidebar, GlobalFilters
    hooks/         # useTxns, useHoldings, useInsights
    lib/
      api.ts       # typed fetch client (generated from OpenAPI)
      formatters.ts# money, date, percent
    store/         # zustand global filter store
  ```

### Backend
- **Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.0 + Alembic.**
- **Layout (light hexagonal, not over-engineered):**
  ```
  app/
    api/            # FastAPI routers (one file per resource)
      txns.py
      categories.py
      investments.py
      dashboard.py
      insights.py
      imports.py
    models/         # SQLAlchemy ORM
    schemas/        # Pydantic request/response
    services/       # business logic — pure functions, no FastAPI imports
      analytics.py     # net worth, savings rate, allocation, XIRR
      categorize.py    # rule-based + LLM categorization
      pricing.py       # holding valuations
    ai/
      client.py        # Anthropic client + prompt cache config
      tools.py         # tool definitions for tool-use
      rag.py           # retrieval over Chroma
      prompts/         # *.md system prompts
    db/
      session.py
      migrations/      # alembic
    main.py
    config.py          # pydantic-settings, .env
  ```
- **Auto-generated TS client.** FastAPI emits OpenAPI; run `openapi-typescript-codegen` in the frontend build to get a typed client. Eliminates a whole class of bugs.
- **CORS:** locked to `localhost:5173` in dev.

### Why these choices (opinionated)
- **FastAPI over Flask/Django:** async, Pydantic-native, free OpenAPI for the frontend client. Matches the Python-for-AI motivation.
- **SQLAlchemy 2.0 + Alembic:** raw SQLite-via-sqlite3 will rot. Migrations from day 1 are non-negotiable when schema evolves weekly.
- **TanStack Query over Redux Toolkit Query:** simpler, smaller, the right primitive for "fetch + invalidate."
- **Chroma (local) over pgvector:** sticks with SQLite-only deploy story; runs in-process; swap later if it stops scaling (it won't, for one user).

### Auth (when added)
- `authlib` + Google OAuth, FastAPI dependency that reads an httpOnly `session` cookie (signed JWT or itsdangerous).
- Adds the `users` table to a small **registry DB** (see "Database management" below).
- A FastAPI dependency `get_user_db()` reads the OAuth-authenticated `user_id` from the session cookie and returns the SQLAlchemy session bound to **that user's** database file.

### Database management — DB-per-user, not shared

There are two ways a multi-user version of this app could shape its storage:

| Approach | What it is | Pros | Cons |
|---|---|---|---|
| **Shared DB, `user_id` everywhere** | Single SQLite file, every table has a `user_id` column, every query filters by `current_user.id`. | Standard SaaS pattern; cross-user analytics easy; single backup target. | One bad WHERE clause leaks data across users. For **finance data** that risk is unacceptable. Every Pydantic schema, every join, every test has to remember the filter. |
| **DB-per-user** ✅ | One SQLite file per user, stored at `data/users/{user_id}.db`. A tiny **registry DB** (`data/registry.db`) holds the `users` table. Each request routes to the right user DB. | **Bulletproof isolation** — impossible to leak across users by code bug. Per-user export = `cp` the file. Per-user backup, restore, delete are trivial. App-level schema stays clean (no `user_id` columns). Aligns naturally with SQLite's "DB is a file" model. | Migrations must run against every user DB (small loop). Slightly more complex bootstrap on first sign-in (create the file + run `alembic upgrade head` against it). Cross-user analytics would need a fan-out (we don't need that anyway — single-user app). |

**Decision:** **DB-per-user.** The `user_id`-everywhere pattern saves nothing for a personal-finance app and adds 50+ places where a forgotten filter is a data-leak. SQLite's per-file model is the *right* tool — use it.

**MVP behavior (Weeks 1–8, no auth):**
- A single file at `data/finance.db`. Treated as "the default user's DB." No registry yet.

**When auth lands (Week 9):**
1. Add `data/registry.db` with one table: `users(id, email, name, db_path, created_at)`.
2. Migrate existing `data/finance.db` → `data/users/{your_id}.db`. Insert your row in the registry.
3. New sign-ins: in the OAuth callback, if the email isn't in the registry, create a new row, create `data/users/{new_id}.db`, run `alembic upgrade head` against it, then issue the session cookie.
4. Every request: FastAPI dependency `get_user_db(current_user)` opens (and caches) a SQLAlchemy session for that user's file.

**Backend code shape:**
```
app/
  db/
    registry.py        # SQLAlchemy engine for registry.db (users table only)
    user_db.py         # cache of {user_id: Engine}; LRU-evicted; one engine per file
    session.py         # get_db() dependency — returns user-scoped session
    migrations/        # ONE migrations tree; applied to every user DB
```

**Migration runner (Week 9+):** a script `scripts/migrate_all_users.py` that loops over registry users and runs `alembic upgrade head` against each file. Run it as part of deploy.

**Backups:** `scripts/backup-db.sh` becomes "tar `data/users/` + `data/registry.db`." Restore is per-user file replacement.

**Operational notes:**
- Open SQLite engines are cheap; cache up to ~100 in an LRU. Beyond that you'd want a real DB engine, but you won't have 100 users.
- Use `PRAGMA journal_mode=WAL` per user DB — better concurrency under any single-user write contention.
- Per-user DB files are gitignored from day 1.

---

## 4. Database Schema

**Principle:** start with the smallest schema that supports the MVP, add tables only when the feature that needs them ships. Below is the **6-table MVP**, then a "later" section showing what gets added in V2/V3.

**Money rule (applies everywhere):** every monetary value is stored as `amount_minor` — an integer in **paise** (1 INR = 100 paise). All math is integer; format to ₹ only at the UI edge using `Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' })`. No `currency` or `fx_rate` columns anywhere in the MVP schema.

**Single-user note:** no `users` table in MVP. Auth lands in Week 9; at that point we add `users(id, email, ...)` and a one-shot migration that adds `user_id` columns and backfills them to your account. Designing `user_id` in from day 1 buys nothing for a solo local app and clutters every query.

### MVP schema (6 tables)

#### `accounts`
Where money/holdings live. Every txn must reference one. Acts as a filter dimension on the dashboard.

| Column | Type | Usage |
|---|---|---|
| `id` | INTEGER PK | Surrogate key. Referenced by `transactions.account_id`, `investment_txns.account_id`. |
| `name` | TEXT NOT NULL | Display label, e.g. "HDFC Savings", "Zerodha", "Coinbase". Shown in dropdowns and the txn table. |
| `type` | TEXT NOT NULL | Enum: `cash` \| `bank` \| `broker` \| `wallet` \| `credit_card`. Drives icon, sign rules (credit cards roll up as a liability in net worth), and which forms the account appears in (broker/wallet shown only on investment forms). |
| `opening_balance_minor` | INTEGER NOT NULL DEFAULT 0 | Starting balance in paise. Net-worth math: `balance(D) = opening_balance + Σ signed_txns ≤ D`. |
| `archived` | BOOLEAN NOT NULL DEFAULT 0 | Hide from dropdowns but keep historical txns intact. Never hard-delete an account that has txns. |
| `created_at` | TIMESTAMP NOT NULL | Audit; sort fallback. |

#### `categories`
Two-level tree (parent + child) for tagging income and expense txns. Drives the category breakdown chart and is the target of AI auto-categorization.

| Column | Type | Usage |
|---|---|---|
| `id` | INTEGER PK | Referenced by `transactions.category_id`. |
| `name` | TEXT NOT NULL | Display label, e.g. "Groceries", "Dining". Shown in chips, charts, dropdowns. |
| `parent_id` | INTEGER NULL FK→categories.id | Subcategory link. NULL = top-level. Limit depth to 2 in code (top + leaf); deeper trees aren't worth the UI cost for one user. |
| `kind` | TEXT NOT NULL | `income` \| `expense`. Filters which dropdown the category appears in, and which charts include it. A child must match its parent's `kind` (enforced in service layer). |
| `color` | TEXT NULL | Hex like `#3b82f6` for chart slices and chips. NULL = derived from a hash of `name`. |
| `icon` | TEXT NULL | Lucide icon name (e.g. `utensils-crossed`). Pure UI sugar. |
| `archived` | BOOLEAN NOT NULL DEFAULT 0 | Hide from dropdowns; old txns keep their reference. |

#### `transactions`
The main ledger — every income, expense, and transfer between accounts. The single most queried table.

| Column | Type | Usage |
|---|---|---|
| `id` | INTEGER PK | Surrogate key. |
| `account_id` | INTEGER NOT NULL FK→accounts.id | Which account this hits. For `kind='transfer'`, this is the **source** account; the destination is captured by a paired row (see `kind` below). |
| `category_id` | INTEGER NULL FK→categories.id | Required when `kind` ∈ {income, expense}; **must be NULL** when `kind='transfer'`. Enforced in the service layer. Drives the category breakdown chart. |
| `kind` | TEXT NOT NULL | `income` \| `expense` \| `transfer`. Determines sign in cashflow math and whether `category_id` is required. **Transfers are stored as a *pair* of rows (one expense-like, one income-like) sharing the same `transfer_group` note tag** — keeps math symmetric without a separate transfers table. |
| `amount_minor` | INTEGER NOT NULL | Magnitude in paise. Always positive — sign comes from `kind`. Avoids floating-point money bugs. |
| `occurred_on` | DATE NOT NULL | The economic date (when the spend happened), **not** when it was entered. All time-series math groups on this column. |
| `note` | TEXT NULL | Free text. Primary signal for the AI categorizer in V3 and for full-text search (FTS5 added in V2 if needed). |
| `source` | TEXT NOT NULL DEFAULT 'manual' | `manual` \| `csv` \| `nl`. Audit + analytics: how much of your data is hand-entered vs imported vs NL. Helps debug auto-categorization regressions. |
| `created_at` | TIMESTAMP NOT NULL | Insertion time. Used for "recently added" lists and audit. |
| `updated_at` | TIMESTAMP NOT NULL | Last edit time. Cache-busting key for derived values. |

#### `instruments`
Catalog of investable things. One row per unique security/asset, regardless of how many times you've traded it.

| Column | Type | Usage |
|---|---|---|
| `id` | INTEGER PK | Referenced by `investment_txns.instrument_id`. |
| `kind` | TEXT NOT NULL | `mutual_fund` \| `stock` \| `etf` \| `crypto` \| `metal` \| `other`. Drives the asset-allocation donut grouping and the price-fetch strategy (different APIs per kind). |
| `symbol` | TEXT NOT NULL | Ticker / scheme code, e.g. `RELIANCE`, `BTC`, `INF090I01239`. Used as a stable join key in CSV imports. |
| `name` | TEXT NOT NULL | Human-readable, e.g. "Reliance Industries Ltd", "Parag Parikh Flexi Cap Direct Growth". |
| `current_price_minor` | INTEGER NULL | Most recent known price in paise per unit. NULL until first price is recorded. Holdings valuation: `qty × current_price_minor`. Updated by manual edit (V1) or cron (V2). For non-INR-quoted instruments (e.g. US stocks, USD-priced crypto), the user enters the INR-equivalent price at the time they're updating it — keeps math single-currency without storing FX. |
| `price_updated_at` | TIMESTAMP NULL | When `current_price_minor` was last refreshed. UI shows a "stale" badge if older than N days. |
| `meta` | JSON NULL | Bag of source-specific identifiers: `{"isin": "...", "exchange": "NSE", "amfi_code": "...", "coingecko_id": "bitcoin"}`. Keeps schema flexible without a column per provider. |

#### `investment_txns`
Per-trade ledger for investments. Separate from `transactions` because of qty/price/fees and different math.

| Column | Type | Usage |
|---|---|---|
| `id` | INTEGER PK | Surrogate key. |
| `account_id` | INTEGER NOT NULL FK→accounts.id | Which broker/wallet account holds this position. Lets you split holdings by account on the dashboard. |
| `instrument_id` | INTEGER NOT NULL FK→instruments.id | What was traded. Holdings = `Σ signed_qty per (account_id, instrument_id)`. |
| `side` | TEXT NOT NULL | `buy` \| `sell` \| `dividend`. Sign rules: buy = +qty / −cash, sell = −qty / +cash, dividend = 0 qty / +cash. (Splits/bonuses deferred to V2; rare for an MVP.) |
| `quantity` | REAL NOT NULL | Units transacted. Float, not integer — MFs trade in fractional units (e.g. 12.347 units). Use `Decimal` in Python at the boundary if precision matters for tax. |
| `price_minor` | INTEGER NOT NULL | Per-unit price in paise (INR). For non-INR-native instruments, the user records the INR-equivalent price at trade time. For `side='dividend'`, store the total dividend in paise as `quantity=1, price_minor=amount` (one convention, documented in code). |
| `fee_minor` | INTEGER NOT NULL DEFAULT 0 | Brokerage + STT + GST + slippage in paise. Subtracted from cost basis for buys, added back to proceeds for sells. |
| `occurred_on` | DATE NOT NULL | Trade date. XIRR cashflow timing key. |
| `note` | TEXT NULL | Free text (e.g. "rebalance Q2", "SIP April"). |
| `source` | TEXT NOT NULL DEFAULT 'manual' | `manual` \| `csv` \| `nl`. Same usage as on `transactions`. |
| `created_at`, `updated_at` | TIMESTAMP | Audit + cache-busting. |

#### `settings`
Single-row table holding global app config. One row only (`id = 1`); enforced by a CHECK constraint or app-layer guard.

| Column | Type | Usage |
|---|---|---|
| `id` | INTEGER PK CHECK (id = 1) | Sentinel — guarantees exactly one row. |
| `fy_start_month` | INTEGER NOT NULL DEFAULT 4 | `1` = calendar year (Jan), `4` = Indian FY (Apr). Drives "FY" preset on the date filter and yearly aggregations. |
| `allocation_targets` | JSON NOT NULL DEFAULT '{}' | Map of `{asset_class: target_pct}`, e.g. `{"equity": 0.65, "debt": 0.2, "gold": 0.1, "crypto": 0.05}`. Drives the drift indicator on the allocation donut. Lives here (vs its own table) because it's a tiny single-user knob. |

**Key indexes:** `transactions(occurred_on)`, `transactions(category_id)`, `transactions(account_id)`, `investment_txns(instrument_id, occurred_on)`.

**Two design notes worth keeping:**
- **One `transactions` table for income+expense+transfer.** They share 95% of columns and every dashboard query joins across all three. Splitting into 3 tables triples the UNIONs. Investments stay separate because qty/price/fees don't fit.
- **No `prices` history table in MVP.** Holdings are valued at `instruments.current_price_minor` for all dates. The net-worth-over-time chart shows *cashflow* drift over time with holdings revalued at today's price — slightly wrong for past months, but right enough for a single user for V1, and saves a whole table + price-fetcher cron. We add a real `prices(instrument_id, on_date, close_minor)` table when historical valuation actually matters (V2).

### Why `instruments` and `investment_txns` are kept separate

This is the same architectural question as "why have `accounts` separate from `transactions`?" or "why have `categories` separate from `transactions`?" — answered honestly with the alternatives spelled out, because the question deserves a real answer.

**The general rule:** an entity that *exists independently of events* belongs in its own table. A trade is an event ("on April 12 I bought 10 units at ₹2,480"). An instrument is an identity that exists whether or not you've ever traded it ("Reliance Industries, NSE-listed stock, currently ₹2,480"). Mixing the two is the same category error as putting `customer_name` on every order row in an e-commerce DB.

There are two ways "merging" could mean something concrete. Both are worse than keeping them separated:

**Option A — merge by collapsing trades into a single "current holding" row** (one row per (account, symbol)):
```
investments(account_id, kind, symbol, name, total_qty, avg_cost, current_price, ...)
```
What you lose:
- **History gone forever.** XIRR needs every cashflow date — you can't compute it from a rolled-up row.
- **No FIFO / LIFO for capital-gains tax.** Selling 5 of 50 units? Which lot? Without trade history, you can't answer. This is non-negotiable for an Indian investor (LTCG vs STCG is per-lot).
- **Editing a past buy means recomputing avg_cost on the server.** Every edit is now an event-sourcing problem you're solving by hand. Easy to get wrong.
- **Dividends and splits don't fit.** They're cashflows or qty changes that aren't a "buy at price." You'd need a side table — at which point you've reinvented `investment_txns` poorly.
- **Can't redraw the past.** "What was my net worth in March?" needs to know what you held then. You only have "now."

**Option B — merge by inlining instrument fields onto every trade row** (no catalog table):
```
investment_txns(account_id, kind, symbol, name, current_price, side, qty, price, ...)
```
What you lose:
- **Massive duplication.** Every Reliance trade row repeats `name`, `kind`, `current_price`. 50 trades × shared fields = pure waste.
- **Updating `current_price` becomes a bulk UPDATE** across every trade row for that symbol. With 1,000 trades and a daily price refresh, you're rewriting hundreds of rows per cron tick.
- **No watchlist.** You can't represent "I want to track Bitcoin" until you've actually bought it.
- **The V2 `prices(instrument_id, on_date, close)` migration becomes painful** — you'd have to extract instrument identity out of every trade row. With the catalog separate, V2 is a one-line migration.
- **Aggregating holdings = always a `GROUP BY symbol`.** No way to ask "how many distinct instruments do I hold?" cheaply.

**What you save by merging:** one JOIN. That's it. SQLite handles a `JOIN instruments ON id` over single-user data in microseconds. There is no performance argument here.

**The pattern is universal:** look at any double-entry accounting system, any brokerage backend, any portfolio tracker — they all separate the catalog from the ledger. It's the same shape as:

| Catalog (identity) | Ledger (events) |
|---|---|
| `accounts` | `transactions` |
| `categories` | `transactions.category_id` |
| `instruments` | `investment_txns` |

If you wouldn't merge `accounts` into `transactions` (you wouldn't — every txn would carry the bank's name), don't merge `instruments` into `investment_txns`. It's the same trade-off, the same wrong answer.

**When merging *would* be the right call:** if you only ever stored "I currently own X units of Y" with no buy/sell history, no XIRR, no tax, no dividends — i.e. a glorified spreadsheet. That's not what we're building.

**Final answer:** keep them separate. The "extra" table earns its keep on day 1.

### Data lifecycle — who writes what, when

Every table mixes some combination of **seed data** (written once at install via an Alembic data migration), **user data** (written from the UI), and **system data** (written by code on the user's behalf — e.g. NL input, CSV import, price refresh). Here's the contract per table.

| Table | Seeded at install? | User can add? | User can edit? | User can delete? | Other writers |
|---|---|---|---|---|---|
| `accounts` | **No** — user creates their first account in onboarding (e.g. "HDFC Savings"). One starter account ("Cash") is optionally auto-created on first run as a convenience. | Yes (Settings → Accounts) | Yes (name, type, opening balance, archived) | Soft-delete only — `archived = 1`. Hard-delete blocked when txns reference it. | None. |
| `categories` | **Yes** — Alembic `0001_seed_categories` inserts a starter taxonomy (see list below). Lives in code, not in JSON. | Yes (Settings → Categories) | Yes (name, color, icon, parent, archived) | Soft-delete (archived). Hard-delete only when no txns reference it; otherwise the FK constraint blocks it. | AI Layer 1 in V3 *suggests* new subcategories but never writes — user must accept. |
| `transactions` | No — empty at install. | Yes (Add form, Cmd-K, NL input). | Yes (any field). | Yes (hard delete; cheap because no FKs point at it). | CSV import (`source='csv'`), NL input (`source='nl'`). |
| `instruments` | No — empty at install. | Yes (auto-created the first time you record an investment_txn for a new symbol — "find or create" pattern). Also addable from the Holdings page. | Yes (name, current_price_minor, meta). | Yes only when no `investment_txns` reference it. | V2 price-refresh cron updates `current_price_minor` + `price_updated_at`. |
| `investment_txns` | No — empty at install. | Yes (Add Investment form). | Yes (any field). | Yes (hard delete). | CSV import. |
| `settings` | **Yes** — Alembic inserts the single row with defaults: `fy_start_month=4`, `allocation_targets='{}'`. | No — single row, can only **update** it. | Yes (Settings page). | No (CHECK (id=1) prevents removing the only row). | None. |

**Seeded categories (Alembic migration content):**

```python
# alembic/versions/0001_seed_categories.py
INCOME = ["Salary", "Freelance", "Bonus", "Interest", "Dividend", "Refund", "Gift", "Other Income"]

EXPENSE = {
    "Food":      ["Groceries", "Dining Out", "Snacks & Tea"],
    "Transport": ["Fuel", "Cab/Auto", "Public Transit", "Vehicle Maintenance"],
    "Housing":   ["Rent", "Maintenance", "Repairs"],
    "Utilities": ["Electricity", "Internet", "Mobile", "Gas", "Water"],
    "Health":    ["Doctor", "Pharmacy", "Insurance Premium", "Fitness"],
    "Shopping":  ["Clothing", "Electronics", "Home Goods"],
    "Lifestyle": ["Entertainment", "Subscriptions", "Personal Care"],
    "Travel":    ["Flights", "Hotels", "Local Transport (Travel)"],
    "Finance":   ["Bank Charges", "Taxes", "Loan EMI", "Interest Paid"],
    "Other":     ["Misc"],
}
```

The migration inserts parents first, then children with `parent_id` set. Tweak this list **before** running the migration; once your data is real, edit through the UI instead of changing the migration.

**No `is_system` / "locked" flag in MVP.** Once seeded, every category is equal — you can rename, recolor, or delete any of them. Adding a flag to "protect" defaults is a feature for multi-user apps, not a single-user one.

**Referential integrity rules (enforced in service layer + DB):**
- `transactions.account_id` → `accounts.id` ON DELETE RESTRICT (block delete; force archive).
- `transactions.category_id` → `categories.id` ON DELETE SET NULL (orphaned txns show as "Uncategorized" — user can recategorize).
- `investment_txns.account_id` → `accounts.id` ON DELETE RESTRICT.
- `investment_txns.instrument_id` → `instruments.id` ON DELETE RESTRICT.

### Tables added later (only when the feature ships)

| Added in | Table | Why |
|---|---|---|
| V2 (after W4) | `prices(instrument_id, on_date, close_minor)` | Historical valuation for an honest net-worth line |
| V2 | `import_profiles` | Save CSV column mappings per source |
| V3 (W3, with AI) | `categorization_rules(pattern, field, category_id, priority)` | Rules tried before any LLM call |
| V3 (W5–6) | `insights(period_start, period_end, kind, title, body, data, generated_at)` | Cache AI-narrated insights |
| V3 (W5–6) | `embeddings_meta(source_kind, source_id, chunk_text, chroma_id)` | Pointer table; vectors live in Chroma |
| V4 (W9) | `users(id, email, name, ...)` + `user_id` backfill on every table | Multi-user before deploy |
| Future | `currency` + `fx_rate_to_base` columns on txn tables; `fx_rates` table | If/when multi-currency is needed |

This way you start with **6 tables**, not 13. Each new table arrives with the feature that uses it, via its own Alembic migration — easier to review, easier to revert.

---

## 4b. Walkthrough — two concrete flows

Two real entries, traced end-to-end: HTTP request → validation → table writes → cache invalidation → UI update. Numbers are realistic; everything else is exactly what the code does.

### Flow 1 — Manual expense: "Bought clothes for ₹1,500"

**User action:** opens *Add Expense* form, enters `amount=1500`, picks `Account = HDFC Savings`, `Category = Shopping → Clothing`, `Date = 2026-04-27`, `Note = "Zara shirt"`, hits **Save**.

**Step 1 — Frontend submits:**
```http
POST /api/transactions
{
  "kind": "expense",
  "account_id": 2,
  "category_id": 18,
  "amount_minor": 150000,           // ₹1,500.00 → 1500 × 100 paise
  "occurred_on": "2026-04-27",
  "note": "Zara shirt",
  "source": "manual"
}
```

**Step 2 — Backend (`app/api/txns.py` → `services/txns.py`):**
- Pydantic validates types and `kind ∈ {income, expense, transfer}`.
- Service asserts: `account_id=2` exists & not archived; `category_id=18` exists & `category.kind == 'expense'`; `amount_minor > 0`; `occurred_on ≤ today + grace`.

**Step 3 — Single INSERT into `transactions`:**

| id | account_id | category_id | kind | amount_minor | occurred_on | note | source | created_at | updated_at |
|---|---|---|---|---|---|---|---|---|---|
| 42 | 2 | 18 | expense | 150000 | 2026-04-27 | Zara shirt | manual | 2026-04-27 14:32:01 | 2026-04-27 14:32:01 |

That's it. **No other table is touched.** No instruments, no investment_txns, no settings.

**Step 4 — Response:** `201 Created` with the new row (so the UI can show it immediately).

**Step 5 — Cache invalidation (TanStack Query):**
- `['txns']` → table refetches → row 42 appears.
- `['dashboard']` → cashflow card, category-breakdown bar, net-worth-line all refetch.
- Backend rerun is single-digit milliseconds for one user's data.

---

### Flow 2 — Manual investment: "Bought 10 shares of HDFC Bank at ₹100, ₹20 brokerage"

**User action:** opens *Add Investment* form. Types `HDFC` in the symbol field — typeahead hits `GET /api/instruments?q=HDFC`.

**Branch A — instrument already exists:** user picks it from the dropdown; `instrument_id = 7` is captured. Skip to Step 3.

**Branch B — instrument not yet in catalog (first-ever HDFC trade):**

**Step 1 — Implicit instrument creation.** Form has a "Create new: HDFCBANK (Stock)" option. Submitting that fires:
```http
POST /api/instruments
{
  "kind": "stock",
  "symbol": "HDFCBANK",
  "name": "HDFC Bank Ltd",
  "current_price_minor": null,
  "meta": {"exchange": "NSE"}
}
```

**Step 2 — INSERT into `instruments`:**

| id | kind | symbol | name | current_price_minor | price_updated_at | meta |
|---|---|---|---|---|---|---|
| 7 | stock | HDFCBANK | HDFC Bank Ltd | NULL | NULL | {"exchange":"NSE"} |

Returns `instrument_id = 7`. (UI now flips to the trade form pre-filled with this instrument.)

**Step 3 — Submit the trade:**
```http
POST /api/investment-txns
{
  "account_id": 5,                  // Zerodha
  "instrument_id": 7,
  "side": "buy",
  "quantity": 10,
  "price_minor": 10000,             // ₹100 → 10,000 paise per unit
  "fee_minor": 2000,                // ₹20 brokerage+STT+GST rolled up
  "occurred_on": "2026-04-27",
  "note": null,
  "source": "manual"
}
```

**Step 4 — Backend (`app/api/investments.py` → `services/investments.py`):**
- Pydantic validates.
- Service asserts: `account_id=5` exists & `account.type ∈ {broker, wallet}`; `instrument_id=7` exists; `quantity > 0`; `price_minor ≥ 0`; `fee_minor ≥ 0`; `side ∈ {buy, sell, dividend}`.

**Step 5 — INSERT into `investment_txns`:**

| id | account_id | instrument_id | side | quantity | price_minor | fee_minor | occurred_on | note | source | created_at | updated_at |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 14 | 5 | 7 | buy | 10.0 | 10000 | 2000 | 2026-04-27 | NULL | manual | 2026-04-27 14:35 | 2026-04-27 14:35 |

**Step 6 — Side effect: bootstrap the instrument's price.**
The service runs:
```sql
UPDATE instruments
   SET current_price_minor = 10000,
       price_updated_at    = now()
 WHERE id = 7
   AND current_price_minor IS NULL;
```
This only fires the first time you trade an instrument — gives the holdings page a non-NULL price to render until the V2 cron starts updating it. Idempotent, harmless.

**Step 7 — Cash-side bookkeeping (V1 limitation, document this):**
The ₹1,020 (₹1,000 cost + ₹20 fee) that left your linked bank account is **not** auto-recorded. In V1 the user adds it manually as a separate `transactions` row (or doesn't, if they're tracking the broker account in isolation). In V2 the form gets a checkbox — *"Also record ₹1,020 outflow from [linked bank]"* — and the service inserts both rows in one DB transaction.

**Step 8 — Response:** `201 Created` with the trade row.

**Step 9 — Cache invalidation:**
- `['investment-txns']` → trade ledger refetches.
- `['holdings']` → triggers recomputation (see below).
- `['dashboard']` → allocation donut + net-worth line refetch.

**How holdings are computed (read-side, no extra writes):**
```sql
SELECT it.instrument_id, it.account_id,
  SUM(CASE it.side WHEN 'buy'  THEN  it.quantity
                    WHEN 'sell' THEN -it.quantity
                    ELSE 0 END)                                  AS qty,
  SUM(CASE it.side WHEN 'buy'  THEN it.quantity*it.price_minor + it.fee_minor
                    ELSE 0 END)                                  AS cost_basis_minor,
  SUM(CASE it.side WHEN 'sell' THEN it.quantity*it.price_minor - it.fee_minor
                    ELSE 0 END)                                  AS proceeds_minor,
  SUM(CASE it.side WHEN 'dividend' THEN it.price_minor ELSE 0 END) AS dividends_minor
FROM investment_txns it
GROUP BY it.instrument_id, it.account_id
HAVING qty > 0;
```
Then JOIN `instruments` to attach `name`, `kind`, `current_price_minor` → compute `market_value = qty × current_price_minor`, `unrealized_pnl = market_value − cost_basis_minor + proceeds_minor + dividends_minor`. **Zero new tables, zero denormalization.**

---

### Summary — what each flow touches

| Flow | INSERT | UPDATE | Read-side recompute |
|---|---|---|---|
| Expense (Flow 1) | `transactions` (1 row) | — | dashboard cashflow + category breakdown |
| Investment, existing instrument | `investment_txns` (1 row) | `instruments.current_price_minor` if NULL | holdings table, dashboard allocation, net-worth line |
| Investment, new instrument | `instruments` (1 row), then `investment_txns` (1 row) | — | same as above |

This is what the schema's separation buys you: **the expense flow doesn't even know investment tables exist**, and the investment flow has a clean `find-or-create instrument → record trade` shape. Merging the tables would tangle these two flows without saving any DB writes.

---

### "But then how do I see *everything* together?" — unified ledger reads

A unified list of income + expenses + investments, and monthly `expense %` / `investment %` of income — these are **read-side problems**, not schema problems. SQL's `UNION ALL` was made for exactly this case. Two clean ways:

**Option 1 — backend service that UNIONs at query time.** (Recommended.)

```python
# app/services/ledger.py
def list_ledger(start: date, end: date, account_ids: list[int] | None = None) -> list[LedgerEntry]:
    return db.execute(text("""
        SELECT
          'cash'                         AS source,
          t.id                           AS source_id,
          t.kind                         AS kind,        -- income | expense | transfer
          t.account_id,
          t.category_id,
          NULL                           AS instrument_id,
          NULL                           AS quantity,
          t.amount_minor                 AS amount_minor,
          t.occurred_on,
          t.note,
          t.created_at
        FROM transactions t
        WHERE t.occurred_on BETWEEN :start AND :end
          AND (:no_acc OR t.account_id IN :accounts)

        UNION ALL

        SELECT
          'investment'                   AS source,
          it.id                          AS source_id,
          ('inv_' || it.side)            AS kind,        -- inv_buy | inv_sell | inv_dividend
          it.account_id,
          NULL                           AS category_id,
          it.instrument_id,
          it.quantity                    AS quantity,
          CASE it.side
            WHEN 'buy'      THEN  it.quantity * it.price_minor + it.fee_minor   -- cash out
            WHEN 'sell'     THEN -(it.quantity * it.price_minor - it.fee_minor) -- cash in (negative outflow)
            WHEN 'dividend' THEN -it.price_minor                                -- cash in
          END                            AS amount_minor,
          it.occurred_on,
          it.note,
          it.created_at
        FROM investment_txns it
        WHERE it.occurred_on BETWEEN :start AND :end
          AND (:no_acc OR it.account_id IN :accounts)

        ORDER BY occurred_on DESC, created_at DESC
        LIMIT :limit OFFSET :offset
    """), {...}).all()
```

The endpoint `GET /api/ledger?from=...&to=...` returns this unified list as `LedgerEntry[]` — a single Pydantic model with optional `category_id` / `instrument_id` / `quantity`. The frontend table renders rows generically; the cell formatter switches on `kind`.

**Option 2 — a SQL VIEW so it *feels* like one table.**

```sql
CREATE VIEW v_ledger AS
  SELECT 'cash' AS source, id AS source_id, kind, account_id, category_id,
         NULL AS instrument_id, NULL AS quantity, amount_minor, occurred_on, note, created_at
    FROM transactions
  UNION ALL
  SELECT 'investment', id, 'inv_'||side, account_id, NULL, instrument_id, quantity,
         CASE side WHEN 'buy' THEN quantity*price_minor + fee_minor
                   WHEN 'sell' THEN -(quantity*price_minor - fee_minor)
                   WHEN 'dividend' THEN -price_minor END,
         occurred_on, note, created_at
    FROM investment_txns;
```

Then `SELECT * FROM v_ledger WHERE occurred_on BETWEEN ... ORDER BY occurred_on DESC` — the rest of the code treats it as one table. Pick this if you'd rather keep query logic in SQL than Python.

Either approach is **5–10 lines of code**. That's the entire cost of "two tables" for the unified-list use case.

### Monthly cashflow & ratios — the actual query

Goal: per month → `income`, `expense`, `investment_outflow`, `expense % of income`, `investment % of income`.

```sql
WITH events AS (
  SELECT strftime('%Y-%m', occurred_on) AS ym,
         kind                            AS bucket,    -- 'income' | 'expense'
         amount_minor                    AS amount_minor
    FROM transactions
   WHERE kind IN ('income', 'expense')
     AND occurred_on BETWEEN :start AND :end

  UNION ALL

  SELECT strftime('%Y-%m', occurred_on),
         'investment_outflow',
         (quantity * price_minor + fee_minor)
    FROM investment_txns
   WHERE side = 'buy'
     AND occurred_on BETWEEN :start AND :end
  -- (sells/dividends excluded from "outflow"; add a fourth bucket if you want net)
)
SELECT ym,
       SUM(CASE WHEN bucket='income'             THEN amount_minor ELSE 0 END) AS income_minor,
       SUM(CASE WHEN bucket='expense'            THEN amount_minor ELSE 0 END) AS expense_minor,
       SUM(CASE WHEN bucket='investment_outflow' THEN amount_minor ELSE 0 END) AS invest_minor
  FROM events
 GROUP BY ym
 ORDER BY ym;
```

Result in Python (`services/analytics.py::monthly_cashflow_summary`):

```python
@dataclass
class MonthRow:
    ym: str                      # "2026-04"
    income_minor: int
    expense_minor: int
    invest_minor: int
    expense_pct: float | None    # None when income == 0
    invest_pct: float | None
    savings_minor: int           # income − expense − invest
    savings_pct: float | None

def monthly_cashflow_summary(start, end) -> list[MonthRow]:
    rows = db.execute(SQL_ABOVE, {...}).all()
    out = []
    for r in rows:
        inc = r.income_minor
        out.append(MonthRow(
            ym=r.ym,
            income_minor=inc,
            expense_minor=r.expense_minor,
            invest_minor=r.invest_minor,
            expense_pct = (r.expense_minor / inc) if inc else None,
            invest_pct  = (r.invest_minor  / inc) if inc else None,
            savings_minor = inc - r.expense_minor - r.invest_minor,
            savings_pct = ((inc - r.expense_minor - r.invest_minor) / inc) if inc else None,
        ))
    return out
```

That's the whole feature. **One SQL with one UNION, one Python wrapper to compute ratios.**

**Performance:** the query scans `transactions(occurred_on)` and `investment_txns(occurred_on)` indexes — both already in our index list. A single user with a decade of data is well under 100k rows total; this returns in single-digit milliseconds on SQLite.

### Why this still doesn't argue for merging the tables

The unified read pattern shows up *exactly once* in the codebase (the ledger endpoint + the monthly summary). The catalog/ledger split shows up in **every other place** — holdings, XIRR, allocation, asset breakdown, dashboard charts, AI categorization, instrument search. Optimizing the schema for the one query that needs `UNION` would pessimize all the others.

This is a general design heuristic: **don't pick the schema for the read shape that's easiest to write.** Pick it for the writes (correctness, no duplication, no event-sourcing) and accept that one or two reads will need a UNION or a VIEW. SQL is good at that.

---

## 5. Dashboard Logic

All math lives in `app/services/analytics.py` as **pure functions** that take a date range + filters and return JSON. The dashboard endpoint is a thin orchestrator.

### Core formulas
- **Total income (period)** = `Σ amount_minor` over `kind='income'`, in range.
- **Total expenses (period)** = same, `kind='expense'`.
- **Net cashflow** = income − expenses.
- **Savings rate** = `(income − expenses) / income`. Guard `income == 0`.
- **Net worth (as of date D)** =
  `Σ accounts.balance(D) + Σ holdings.market_value(D)`
  where `balance(D) = opening_balance + Σ signed_txns ≤ D` and `market_value(D) = Σ qty(D) × price(D)`.
- **Net worth series** = compute at month-ends across the range (not per-day — too expensive, no visible benefit).
- **Asset allocation** = group holdings by `instrument.kind`, sum market value, % of total.
- **Allocation drift** = actual_pct − target_pct per class.
- **Category breakdown** = `Σ` per `category_id` over expenses, then roll subcategories under parents.
- **XIRR per holding** = scipy `optimize.brentq` over cashflows: each buy is −cashflow, each sell/dividend is +cashflow, current market value is +cashflow on "today."
- **Monthly trends** = group txns by `strftime('%Y-%m', occurred_on)`.

### Update pattern (this is the "live dashboard")
1. Frontend mutation → POST/PATCH/DELETE.
2. On 2xx, TanStack Query **invalidates** the queries the mutation touches: `['txns', filters]`, `['dashboard', filters]`, `['holdings']`.
3. Affected hooks refetch in parallel; charts re-render.
4. Backend never pushes — pull-on-invalidate is plenty for a single user.

### Caching
- Dashboard endpoint computes on demand. SQLite + indexes is fast enough for years of single-user data.
- If it stops being fast: cache `monthly_aggregates(user_id, year_month, kind, category_id, sum_amount)` materialized on write. Don't build this until you measure a real slowdown.

---

## 6. AI Integration Plan

**Core principle: numbers are computed in Python, the LLM only narrates and routes.** The LLM never adds, percentages, or invents amounts. This avoids the #1 failure mode of finance-LLM apps.

### Framework choice — raw Anthropic SDK, not LangChain or LangGraph

Honest answer: don't use LangChain. Don't reach for LangGraph yet either. Use the **Anthropic Python SDK directly** plus ~150 lines of your own agent loop. Here's the real reasoning:

**Why not LangChain.**
- It's a wrapper around the SDK that adds 5–10× more code paths than you actually need. Tracing a bug means stepping through `BaseChatModel → ChatAnthropic → _generate → _create_message_dicts → ...` instead of reading one `client.messages.create(...)` call.
- API has churned aggressively (LCEL → Runnables → "v0.3 architecture") — stuff you write today rots in 6 months.
- Hides the wire format. **Tool-use, prompt caching, streaming, citations** — the things that actually matter for cost/quality — are exactly what you need to *see* and tune. Wrapping them is a tax.
- You said the *primary reason* for this project is to learn AI. LangChain teaches you LangChain. The SDK teaches you Claude — tool-use schemas, cache breakpoints, stop reasons, message blocks. That knowledge transfers; LangChain knowledge doesn't.
- The pattern in production: many teams adopt LangChain early, hit a wall on observability/cost, and rip it out. Skip step 1.

**Why not LangGraph yet.**
- LangGraph is a real and decent thing — it's a state-machine for multi-agent workflows, more focused than LangChain. The graph abstraction is genuinely useful when you have **>2 cooperating agents with persisted state across many turns** and want checkpointing, branching, human-in-the-loop, etc.
- Your Layers 1–4 (categorize, NL input, RAG insights, chat) are **single-agent or single-call** tasks. A graph framework here is overkill — like using Kafka to deliver one log line.
- Layer 5 (multi-agent investment analysis) *could* justify LangGraph. But a hand-rolled coordinator/sub-agent pattern in plain Python is **150–300 lines** and gives you full control. Decide then, not now. If your custom orchestrator gets messy by the time you're building L5, LangGraph is a defensible upgrade — port at that point with a clear "we needed this because X" reason. Don't pre-adopt.

**What you build instead — `app/ai/` directly on the SDK:**

```
app/ai/
  client.py           # Anthropic client, model picker, prompt-cache wiring (~40 lines)
  agent.py            # generic tool-use loop: call → execute tools → loop until stop_reason='end_turn' (~80 lines)
  tools.py            # @tool decorator + registry; defines schemas for create_expense, query_txns, get_holdings, ... (~100 lines)
  rag.py              # Chroma index/retrieve helpers (~60 lines)
  prompts/            # *.md system prompts versioned in git
    categorize.md
    nl_input.md
    insights.md
    chat_advisor.md
    investment_analyst.md
  features/
    categorize.py     # business logic for L1
    nl_input.py       # L2
    insights.py       # L3
    chat.py           # L4
    investment.py     # L5 (multi-agent — implemented when we get there)
```

The whole AI layer is ~500 lines of code you actually own and understand.

**The agent loop you'll write (sketch):**

```python
# app/ai/agent.py
async def run_agent(
    messages: list[dict],
    system: str,
    tools: list[Tool],
    *,
    model: str,
    max_steps: int = 8,
) -> AgentResult:
    """
    Generic tool-use loop. Returns final assistant message + every tool call made
    + token usage (so we can audit cost per feature).
    """
    history = list(messages)
    steps = []
    for _ in range(max_steps):
        resp = await client.messages.create(
            model=model,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            tools=[t.schema for t in tools],
            messages=history,
            max_tokens=4096,
        )
        history.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            return AgentResult(final=resp, steps=steps, usage=resp.usage)

        tool_results = []
        for block in resp.content:
            if block.type == "tool_use":
                result = await tools_by_name[block.name].run(**block.input)
                steps.append((block.name, block.input, result))
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result, default=str),
                })
        history.append({"role": "user", "content": tool_results})

    raise AgentError("max_steps exceeded")
```

That's it. Every feature (L1–L4) calls `run_agent` with different tools and a different system prompt. **Reading this once tells you exactly how the system behaves. LangChain hides the equivalent loop behind 12 classes.**

**For multi-agent (L5) when we get there:** a `Coordinator` agent has tools that *invoke other agents* (`call_portfolio_analyzer`, `call_risk_assessor`, `call_news_summarizer`). Each sub-agent is its own `run_agent` call with its own narrow tools. Communication is structured JSON via tool-results. ~200 lines on top of `agent.py`. **Re-evaluate LangGraph at that point** — by then you'll know exactly what you need from a graph framework, and you'll be able to compare against your hand-rolled version with informed eyes.

**What you do *not* skimp on by going raw-SDK:**
- **Prompt caching:** wire `cache_control` on the system prompt + static context (categories list, account list, recent txn examples). 90%+ cache hit rate on categorization → ~10× cost reduction. The SDK exposes this directly.
- **Structured output:** use **tool-use** as the structuring mechanism (`force tool_choice` to a specific tool). Don't reach for `instructor`/`outlines`/JSON-mode shims; tool-use *is* the structured-output API for Claude.
- **Streaming:** use `client.messages.stream(...)` for the chat UI. SDK gives you raw SSE events; pipe them straight to the frontend over `text/event-stream`.
- **Observability:** log every (`feature`, `model`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`, `latency_ms`) row to a tiny `ai_calls` SQLite table. Without this, cost regressions hide. Don't outsource to LangSmith — 30 lines of code and you own it.

**TL;DR:**
- **MVP through L4:** Anthropic SDK + your own 500-line `app/ai/`. No frameworks.
- **L5 (multi-agent):** start hand-rolled; evaluate LangGraph if it gets messy. Don't pre-adopt.
- **Never:** LangChain, for this app.

### Layer 1 — Auto-categorization (Week 3)
1. Try `categorization_rules` (regex over note/merchant) first — instant, free, deterministic.
2. On miss, call Claude Haiku with: `{note, amount, account, recent 5 categorizations}` → returns `category_id` + confidence + suggested rule.
3. If confidence > 0.8, auto-apply; else show a "Suggested: Groceries" chip the user clicks to accept (which also writes a new rule).
4. Use **prompt caching** on the system prompt + category list (changes rarely, hits every call).

### Layer 2 — Natural language input (Week 3)
- Single text box: `"spent 450 on uber back from airport yesterday"` →
- Claude Sonnet with **tool-use**: tool `create_expense(amount_minor, category_id, account_id, occurred_on, note)`.
- Frontend shows the parsed result as a confirm card before commit (NL is high-leverage but error-prone — never silently insert).

### Layer 3 — Insights with RAG (Week 5–6)
- **Indexer (background job):** for each new txn / monthly summary / holding change, write a short text chunk like `"2026-04-12: ₹4,200 expense in Dining (Restaurant: Toit) from HDFC Credit"` and embed via Anthropic's `voyage-3` (or whichever embedder you pick — keep it abstracted). Store vectors in Chroma, pointer in `embeddings_meta`.
- **Insight generator:**
  1. Compute deterministic facts in Python (top 5 spending changes MoM, drift values, savings-rate delta).
  2. Retrieve top-K relevant historical chunks.
  3. Send to Claude Sonnet: `{facts, retrieved_context, system_prompt}` → narrated insight.
  4. Cache result in `insights` table keyed on `(user_id, period, kind)`.
- Surface in `/insights` page as cards; pin the 3 most actionable on the dashboard.

### Layer 4 — Chat advisor (Week 7+)
- `/chat` page with streaming responses.
- Tool-equipped agent with tools:
  - `query_transactions(filters)` — read-only SQL behind a safe builder
  - `get_holdings(as_of)`, `get_allocation()`, `compute_xirr(instrument_id)`
  - `propose_rebalance(target)` — returns suggested moves, does *not* execute
- System prompt: persona = "cautious analyst, only states what data shows, refuses to give regulated advice."
- Use prompt caching on the conversation prefix; thread persisted in `chat_threads` (add when this phase lands).

### Provider design
- One `app/ai/client.py` wraps the Anthropic SDK. All callers go through it. Models picked per call site:
  - Categorization → `claude-haiku-4-5` (cheap, fast).
  - NL input + insights + chat → `claude-sonnet-4-6`.
  - Reserve `claude-opus-4-7` for "deep analysis" buttons the user explicitly triggers.
- Always use `cache_control` on the system prompt + static context (categories, account list).

---

## 7. Roadmap

### Week 1 — Skeleton + read path
- Repo init: `apps/web` (Vite) + `apps/api` (FastAPI) + `packages/shared-types` (generated).
- SQLAlchemy models for `users, accounts, categories, transactions`. Alembic migration #1.
- Seed default user + base categories (Income: Salary/Freelance/Other; Expense: Groceries/Dining/Transport/Rent/Utilities/Entertainment/Health/Shopping/Travel/Other).
- FastAPI routers: GET/POST/PATCH/DELETE for txns + categories.
- Frontend shell: layout, sidebar, global filter (date range, account), Transactions page with table + add form.
- TanStack Query wired with invalidation.

**Done when:** you can add an expense in the UI and see it in the table.

### Week 2 — Investments + first dashboard
- `instruments` + `investment_txns` tables + endpoints.
- Holdings computation (qty, avg cost, current value) using `instruments.current_price_minor` (manual price entry — refresh button on holdings table).
- Dashboard endpoint returning the 4 core blocks: cashflow summary, category breakdown, allocation, net-worth-series (holdings valued at *today's* price for all dates — documented as a known V1 limitation).
- Recharts: NetWorthLine, AllocationDonut, CategoryBar, CashflowSummary cards.
- Basic CSV import (expenses) — hardcoded column mapping for one source; `import_profiles` table waits until V2 when you have a second source.

**Done when:** import a month of CSV, see four charts populated.

### Week 3 — AI Layer 1+2
- `app/ai/client.py` with Anthropic SDK + prompt caching.
- `categorization_rules` + Claude-Haiku fallback for unrecognized txns.
- NL input box on Dashboard → tool-use → confirm card → insert.
- Insights stub: deterministic only ("savings rate this month: X%, MoM delta: Y").

**Done when:** typing "spent 500 on lunch today" creates a categorized expense after one confirm click.

### Week 4 — Polish + visualization upgrade
- Sankey (visx), Category Heatmap (Recharts custom), Holdings table with sparklines + XIRR.
- **V2 schema lands here:** add `prices` table + Alembic migration; backfill prices via free APIs (AMFI for MFs, NSE bhavcopy for stocks/ETFs, CoinGecko for crypto — converted to INR at fetch time so the schema stays single-currency). Net-worth line now uses historical prices.
- Local backup: nightly DB copy + JSON export endpoint.
- Settings page (FY start month, allocation targets).

**Done when:** the app feels like *your* tool — you reach for it daily.

### Week 5–6 — RAG + Insights v1
- Chroma integration, embeddings indexer, `insights` cache table.
- Monthly insight generation job.
- `/insights` page; pin top 3 on dashboard.

### Week 7–8 — Chat advisor (AI Layer 4)
- Read-only tools + streaming chat UI.
- Conversation persistence.
- Hard-coded refusal for regulated advice ("buy/sell X?").

### Week 9 — Pre-deploy (auth + multi-user storage + hosting)
- Authlib + Google OAuth, session cookie.
- Introduce `data/registry.db` (just the `users` table) and `data/users/{user_id}.db` per-user files. Move the existing `data/finance.db` to `data/users/{your_id}.db` and register yourself.
- `get_user_db()` FastAPI dependency that resolves session → `user_id` → engine for that file (LRU-cached).
- New-user flow: OAuth callback → create registry row → create empty user DB → run `alembic upgrade head` against it.
- `scripts/migrate_all_users.py` for fan-out migrations on deploy.
- Deploy: single Docker container (FastAPI + static SPA build) on Fly.io / Railway with a persistent volume for `data/`. Daily volume snapshot. Use Litestream or restic to push deltas to S3-compatible storage as a second backup.

### Future (V4+)
- CAMS CAS PDF parser.
- Goals + projections.
- Recurring txns / SIP automation.
- Mobile PWA.

---

## Repo layout (target)

```
personal-finance/
  apps/
    api/                    # FastAPI
      app/
      pyproject.toml
      alembic.ini
      .env.example
    web/                    # Vite + React
      src/
      package.json
      vite.config.ts
  scripts/
    gen-api-client.sh       # OpenAPI → TS client
    backup-db.sh
  data/                     # gitignored
    finance.db              # MVP: single file. After Week 9 → data/users/{id}.db
    registry.db             # added in Week 9 — maps user_id → db_path
    users/                  # added in Week 9 — one .db per user
    chroma/                 # local vector store (added in Week 5–6)
  README.md
```

---

## Critical files to create first (Week 1)

- [apps/api/app/main.py](apps/api/app/main.py) — FastAPI app, CORS, router registration.
- [apps/api/app/db/session.py](apps/api/app/db/session.py) — SQLAlchemy engine + session.
- [apps/api/app/models/](apps/api/app/models/) — `user.py`, `account.py`, `category.py`, `transaction.py` to start.
- [apps/api/app/schemas/](apps/api/app/schemas/) — Pydantic mirrors.
- [apps/api/app/api/txns.py](apps/api/app/api/txns.py) — first CRUD router.
- [apps/api/app/services/analytics.py](apps/api/app/services/analytics.py) — pure functions for the dashboard.
- [apps/api/alembic/versions/0001_init.py](apps/api/alembic/versions/0001_init.py) — initial migration.
- [apps/web/src/lib/api.ts](apps/web/src/lib/api.ts) — generated client.
- [apps/web/src/store/filters.ts](apps/web/src/store/filters.ts) — Zustand global filters.
- [apps/web/src/pages/Dashboard.tsx](apps/web/src/pages/Dashboard.tsx).
- [apps/web/src/pages/Transactions.tsx](apps/web/src/pages/Transactions.tsx).

---

## Verification plan (per milestone)

**Backend correctness**
- `pytest` unit tests for every function in `services/analytics.py`. These are pure functions with deterministic outputs — easy and high-value to test.
- A fixture that seeds a known month of data and asserts dashboard JSON matches expected numbers exactly.
- Alembic `upgrade head` then `downgrade -1` then `upgrade head` round-trip in CI to catch migration breakage.

**End-to-end (manual at first, Playwright later)**
- Add expense → table updates → dashboard updates without reload.
- Import 3-month CSV → 4 charts populate → numbers match a hand-computed spreadsheet.
- Edge cases: zero-income month (savings rate guarded), empty category (UI handles cleanly), large paise values (no integer overflow on long-running totals — INTEGER in SQLite is 64-bit, plenty).
- NL input: "spent 450 on uber yesterday" → confirm card shows correct fields → accept → row appears.

**AI behavior**
- Golden-set test for categorization: 50 hand-labeled txns, assert ≥90% match (rules + LLM).
- Insight generation: snapshot test on a fixed dataset — same input must produce the same numeric facts (LLM phrasing can vary; the **numbers** in the rendered text must match the deterministic computation, enforced by extracting them with regex and asserting).
- Tool-use safety: integration test that the chat agent's tools never write — wrap them with a SQLAlchemy read-only session.

**Pre-deploy gate**
- DB backup + restore drill on a copy.
- OAuth happy path + signed-out 401s.
- Run for 7 days locally with daily use before flipping the deploy switch.
