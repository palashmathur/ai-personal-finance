# CLAUDE.md — AI Personal Finance App

Project-specific instructions for Claude. These override default behaviour.

---

## Project overview

A single-user, local-first personal finance dashboard. Tracks income, expenses, and investments (MF / stocks / ETFs / crypto / metals). Progressively adds AI features: auto-categorisation → NL input → RAG-backed insights → chat advisor -> Deep stock and investment research AI agents(multiple agents working together).

**Primary goal:** ship a useful tool and learn AI/GenAI hands-on using the Anthropic SDK directly.
If require suggest langgraph for AI agent workflow.

**Current phase:** Backend (Phase 1). The entire API is built and verified with Postman before any frontend code is written.

**Completed tickets:** PF-1 through PF-9, PF-11, PF-12, PF-13 (Repo + tooling, SQLAlchemy models, Alembic migrations, seed data, FastAPI shell, Accounts CRUD, Categories CRUD, Transactions CRUD, Postman Core APIs collection, Instruments find-or-create + search, Investment txns CRUD, Holdings service + endpoint). PF-10 skipped — instruments and investment_txns tables were already created in migration 0001.

---

## Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.9+, FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2 |
| Database | SQLite (single file at `data/finance.db`) |
| AI | Anthropic Claude API — raw SDK, suggest LangChain, Langgraph if you feel the need for |
| Linter | Ruff |
| Tests | pytest + pytest-asyncio + httpx (TestClient) |
| Frontend (Phase 2) | React 18 + Vite + TypeScript + Tailwind + shadcn/ui |

---

## Repo layout

```
personal-finance/
  apps/
    api/                    # FastAPI backend — the only active app right now
      app/
        routers/            # FastAPI routers — one file per resource (e.g. accounts_router.py)
        db/
          session.py        # SQLAlchemy engine, session factory, get_db()
        services/           # business logic — pure functions, no FastAPI imports
        ai/                 # Anthropic SDK wrappers (added in PF-22+)
        models.py           # SQLAlchemy ORM models (all 6 MVP tables)
        main.py             # App entry point: CORS, exception handlers, router registration
      alembic/
        versions/           # Migration files — never edit after merging to main
      tests/                # pytest test files
      pyproject.toml
      alembic.ini
  plans/                    # Design docs — read-only reference
  data/                     # gitignored — SQLite DB lives here
  Makefile
```

---

## Development commands

All commands run from the **project root** (where the Makefile lives).

```bash
make install-api    # create .venv and install all dependencies (first-time setup)
make api            # start the API server on port 8000 with hot reload
```

Running tests (from `apps/api/`):
```bash
.venv/bin/pytest -v                        # all tests
.venv/bin/pytest tests/test_health.py -v   # specific file
.venv/bin/pytest -v -k "health"            # filter by name
```

Linting (from `apps/api/`):
```bash
.venv/bin/ruff check .          # check
.venv/bin/ruff check --fix .    # auto-fix
```

Migrations (from `apps/api/`):
```bash
.venv/bin/alembic upgrade head      # apply all pending migrations
.venv/bin/alembic downgrade -1      # roll back one migration
.venv/bin/alembic downgrade base    # roll back everything
.venv/bin/alembic revision --autogenerate -m "description"   # generate new migration
```

---

## Git workflow

- **One branch per ticket:** `palash/PF-<n>/<task-kebab>` — always created from `main`.
- **Create the branch FIRST** — before writing a single file. Branch creation is always step 1 of implementation.
- **Always pull main** before branching for a new ticket.
- **Never commit without the user reviewing first** — implement, then stop. The user commits.
- **Exception:** user explicitly asks to commit — then do it.
- Commit messages: `PF-<n>: <short description>` — no Co-Authored-By lines, no Claude references.
- After implementation, push and open a PR with a short human description (2–4 sentences, no filler).
- **After every ticket:** update CLAUDE.md if any new decisions, patterns, or gotchas were discovered during implementation.

---

## Locked decisions

**Money:** Every monetary value is stored as `amount_minor` — an integer in **paise** (1 INR = 100 paise). ₹1,500 = `150000`. No floats for money anywhere. No `currency` or `fx_rate` columns.

**Auth:** Skipped in MVP. Google OAuth via Authlib + httpOnly session cookies added in PF-42.

**No `user_id` columns** in MVP tables — added in the auth migration as a one-shot backfill.

**No `user_id` columns or filters needed — ever.** The architecture is DB-per-user (decided in the design doc): each user gets their own SQLite file at `data/users/{user_id}.db`. The `get_user_db()` FastAPI dependency (PF-41) routes each request to the correct file. Because the database itself is the isolation boundary, `GET /api/accounts` (and every other list endpoint) simply returns all rows — they are already scoped to the right user by virtue of which file was opened. No `user_id` column, no WHERE filter, no risk of a forgotten filter leaking data across users.

**No LangChain.** Use the Anthropic SDK directly. The agent loop is hand-rolled in `app/ai/agent.py` (~80 lines). LangGraph is re-evaluated only for the multi-agent Layer 5 feature.

**DB-per-user** (after auth): one SQLite file per user at `data/users/{user_id}.db`. A tiny `data/registry.db` holds the `users` table. Not relevant until PF-41.

**SQLite PRAGMAs** applied on every connection (both app and migrations):
- `PRAGMA journal_mode=WAL` — allows concurrent reads during writes
- `PRAGMA foreign_keys=ON` — SQLite disables FK enforcement by default; this turns it on

---

## Code conventions

**Comments:** Write natural, conversational comments on every method, class, and non-obvious variable. Explain the *use case and why*, not just what the name already says. A comment like `# increment counter` is useless. A comment like `# WAL mode lets reads and writes overlap without locking the whole file` is useful.

**Error responses:** Every HTTP error returns `{"detail": "...", "code": "..."}`. `detail` is human-readable; `code` is a machine-readable slug (`"not_found"`, `"conflict"`, `"validation_error"`, etc.). This is wired globally in `main.py` — route handlers just `raise HTTPException(...)` normally.

**Exception handler:** Registered against `StarletteHTTPException` (not FastAPI's `HTTPException`) so it catches both routing-level 404s and explicit raises inside route handlers. FastAPI's `HTTPException` inherits from Starlette's, so one handler covers both.

**Services layer:** Business logic lives in `app/services/` as pure functions — no FastAPI imports, no `Depends`. Routers call services; services don't know about HTTP. Think of it like the service layer in Spring Boot.

**Pydantic v2:** Use `model_validator`, `field_validator`, `model_config = ConfigDict(...)`. The v1 `@validator` decorator is deprecated.

**Pydantic `model_validator` cross-field errors do not reliably produce 422s** in this FastAPI/Python 3.9 version combination — they surface as 500s instead. Always do cross-field validation in the service layer by raising `HTTPException(status_code=422, detail="...")` directly. This is reliably caught by the global exception handler.

**SQLAlchemy 2.0:** Use `Mapped[type]` + `mapped_column()` syntax. Never use the old `Column(...)` style.

**Python 3.9 compatibility:** Do not use `X | Y` union syntax for type hints (e.g. `str | None`). Use `Optional[X]` from `typing` instead. The `|` union syntax requires Python 3.10+.

**`TestClient` and server exceptions:** Use `TestClient(app, raise_server_exceptions=False)` in test files so that server-side errors (4xx, 5xx) are returned as response objects rather than re-raised as Python exceptions in the test process.

**SQLAlchemy `relationship` for nested responses:** When a response schema embeds a nested object (e.g. `InvestmentTxnResponse` embeds `InstrumentSummary`), add a SQLAlchemy `relationship(..., lazy="joined")` on the ORM model. FastAPI's response serializer reads the attribute via `from_attributes=True` — without the relationship the field is missing and a 500 is returned at serialization time.

**Investment account types:** `broker`, `wallet`, `bank`, and `cash` are all valid for investment trades. `credit_card` is the only excluded type. Bank/cash are allowed because SIP debits come directly from a bank account without a separate broker. The check lives in `_get_investment_account_or_error` in the investment_txns service.

**Bootstrap price on first trade:** When `instrument.current_price_minor IS NULL`, the first trade sets it to `price_minor`. This is done in the service before `commit()` so both the trade INSERT and the instrument UPDATE land in the same DB transaction. Subsequent trades never overwrite an existing price.

---

## Database — migration rules

- Migration files are **immutable once merged to main**. Never edit a migration that has already been applied to a real database.
- To add data on top of a seed migration: create a new migration file (e.g. `0002b_...`).
- Idempotency in data migrations:
  - For seeding a whole table: `SELECT COUNT(*)` guard at the top — skip if already populated.
  - For adding specific rows: `WHERE NOT EXISTS (SELECT 1 FROM ... WHERE name = ?)`.
  - For single-row tables with a PK: `INSERT OR IGNORE`.
- Never hardcode auto-increment IDs. Always look up parent IDs by name at migration time via `result.lastrowid` or a SELECT.
- Downgrade must be the exact inverse of upgrade — delete in reverse dependency order (children before parents).
- All migrations run with `render_as_batch=True` because SQLite doesn't support `ALTER TABLE`.

---

## Testing conventions

- **pytest** — unit and integration tests for services, pure functions, routers.
- **Postman** — manual API verification; collections exported to `postman/` and committed.
- Postman collection format: Postman Collection v2.1. Environment file `postman/env-local.json` sets `{{base_url}}=http://localhost:8000`. Collection variables (IDs) are chained automatically via Tests scripts — no manual copy-pasting needed between requests.
- Use `TestClient` from `fastapi.testclient` for synchronous route tests (no async needed).
- Test files live in `apps/api/tests/`, named `test_<resource>.py`.
- Every new router gets its own test file in the same PR.

---

## Manual testing (end of every ticket)

After every implementation, provide a short manual test block so the user can verify before committing:
- `make api` to start the server
- Exact `curl` commands or URLs to hit
- Cover the happy path and one error/edge case
- Keep it under 10 bullet points

---

## AI layer decisions (PF-22 onwards)

- **Prompt caching:** `cache_control: {"type": "ephemeral"}` on system prompts and static context (category list, account list). Without this, every Haiku categorisation call pays full token cost.
- **Structured output:** Use tool-use with `tool_choice` forced to a specific tool — not JSON mode.
- **Streaming:** `client.messages.stream(...)` piped straight to `text/event-stream` for the chat UI.
- **Audit log:** Every LLM call writes a row to `ai_calls(feature, model, input_tokens, output_tokens, cache_read_tokens, latency_ms)`. No LangSmith dependency.
- **Model selection per feature:** Haiku for auto-categorisation, Sonnet for NL input / insights / chat, Opus only for explicit "deep analysis" user triggers.
