# CLAUDE.md — AI Personal Finance App

Project-specific instructions for Claude. These override default behaviour.

---

## Project overview

A single-user, local-first personal finance dashboard. Tracks income, expenses, and investments (MF / stocks / ETFs / crypto / metals). Progressively adds AI features: auto-categorisation → NL input → RAG-backed insights → chat advisor -> Deep stock and investment research AI agents(multiple agents working together).

**Primary goal:** ship a useful tool and learn AI/GenAI hands-on using the Anthropic SDK directly.
If require suggest langgraph for AI agent workflow.

**Current phase:** Phase 2 frontend has begun. The backend API (Phase 1) is complete and verified with Postman; the **core frontend slice (PF-F1–F8)** is now built in `apps/web` against that live API.

**Completed tickets:** PF-1 through PF-9, PF-11 through PF-22, PF-22a, PF-22b, PF-22c (Repo + tooling, SQLAlchemy models, Alembic migrations, seed data, FastAPI shell, Accounts CRUD, Categories CRUD, Transactions CRUD, Postman Core APIs collection, Instruments find-or-create + search, Investment txns CRUD, Holdings service + endpoint, Dashboard endpoint, Unified ledger endpoint, Monthly cashflow summary, CSV import backend, AI client + audit log, Generic agent loop, Tool registry, Auto-categorize endpoint, Install LangChain + LLM factory, Migrate categorize to LangChain, Enable LangSmith tracing). PF-10 skipped — instruments and investment_txns tables were already created in migration 0001.

**Frontend tickets done:** PF-F1–PF-F8 + PF-F18 (Vite/React scaffold, generated TS API client, AppShell + global filter store, Transactions CRUD, Dashboard charts, Investments, CSV import, auto-categorize chip, and the **Accounts management page**). PF-F9–F17 (NL input, advanced charts, settings, insights, chat, auth, deploy) not started — most depend on backend endpoints that don't exist yet (settings, insights, chat, NL input, auth). PF-F18 was added mid-slice to fill the account add/edit/archive/delete gap (account CRUD backend PF-6 already existed).

**Carried into PF-23:** the LangChain migration is functionally done — categorize runs on `get_llm(...).with_structured_output(...)` (default provider **Groq**, switchable via `LLM_PROVIDER`), and PF-22c wired in LangSmith tracing. Still outstanding: the generic agent-loop migration and the deletion of `app/ai/client.py` / `app/ai/tools.py`, **deferred to PF-23** because `run_agent` has no real caller yet and `agent.py` still depends on `call_llm` + the `Tool`/`@tool` machinery. Both stacks coexist until then.

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
    api/                    # FastAPI backend
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
    web/                    # React frontend (Phase 2) — Vite + TS + Tailwind + shadcn/ui
      src/
        lib/
          api/              # GENERATED typed client (committed; regen via npm run gen:api)
          http.ts           # THE one HTTP wrapper: sets base URL, api facade, getApiError
          money.ts          # THE one money util: paise <-> ₹
          dateRange.ts      # global date-range presets
        store/filters.ts    # Zustand global filter store (date range + accounts)
        hooks/              # TanStack Query hooks (useAccounts, useDashboard, ...)
        components/
          ui/               # hand-authored shadcn primitives (no shadcn CLI)
          shell/            # AppShell, Sidebar, GlobalFilters
          charts/ transactions/ investments/ imports/ accounts/
        pages/              # Dashboard, Transactions, Investments, Accounts, ComingSoon
      scripts/gen-api-client.sh
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
make install-web    # npm install for apps/web (first-time setup; needs Node — brew install node)
make web            # start the Vite dev server on port 5173
make dev            # run backend + frontend together (make -j 2)
```

Frontend commands (from `apps/web/`):
```bash
npm run dev         # Vite dev server on :5173
npm run typecheck   # tsc --noEmit (must stay green; runs offline)
npm run build       # typecheck + production build
npm run gen:api     # regenerate src/lib/api from the backend's live /openapi.json (backend must be up)
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

**LangChain — adopted (decision revised in PF-22b/PF-22c).** All LLM calls now go through LangChain via the provider-agnostic `get_llm(...)` factory in `app/ai/llm.py`. Reasons we reversed the original "no frameworks" stance: (1) learn LangChain — it's standard in real codebases; (2) multi-provider routing (cheap Groq for high-volume features like categorize, Claude only where quality matters) becomes a config switch, not a rewrite; (3) LangSmith tracing for free observability. LangGraph is still **not** adopted — re-evaluated only for the multi-agent Layer 5 feature.

> _Historical:_ PF-19→PF-22 were built on the raw Anthropic SDK with a hand-rolled ~80-line agent loop in `app/ai/agent.py`. That loop and `app/ai/client.py` / `app/ai/tools.py` still exist (deletion deferred to PF-23) but are no longer the active path for categorize.

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

**SQLite Date column requires Python `date` objects:** When seeding a `Transaction` in tests, pass `occurred_on=date(2026, 6, 1)` (a `datetime.date`), not the string `"2026-06-01"`. SQLite's Date type raises `StatementError` if given a plain string.

**Mocking `call_llm` skips the audit log write:** `call_llm` in `app/ai/client.py` is what writes to `ai_calls`. When a test patches `app.services.<feature>.call_llm`, the mock replaces the whole function — so no DB row is written. Tests that verify "LLM was invoked" should assert `mock_llm.assert_called_once()`, not `_ai_calls_count() == 1`. Reserve `_ai_calls_count()` for tests that verify a rule matched and the LLM was *not* called (those don't use a mock, so the real function runs if it were called).

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

## AI layer decisions (PF-19 onwards)

- **Single entry point:** All Anthropic API calls go through `app/ai/client.py::call_llm()`. No feature imports `anthropic` directly. The Anthropic SDK types stay within `app/ai/` — routers and services only see plain Python objects returned by feature modules.
- **Prompt caching:** Pass system prompt blocks with `cache_control: {"type": "ephemeral"}` already set in the list passed to `client.create(system=[...])`. The client forwards them as-is — it does not add caching automatically. Callers are responsible for marking what to cache.
- **Cache token field names:** The Anthropic SDK usage object uses `cache_read_input_tokens` and `cache_creation_input_tokens`. The `ai_calls` DB table uses shorter names `cache_read_tokens` and `cache_creation_tokens`. Always use `getattr(usage, "cache_read_input_tokens", 0) or 0` when reading from the SDK — the fields may be absent (None) if caching was not used.
- **Provider-agnostic by default (RULE):** Feature code, services, routers, schemas, comments, and tests must **never** name a concrete LLM provider or model (no "Claude", "Haiku", "Sonnet", "Opus", "Anthropic", "Groq", "Llama", etc.). The provider/model is a config concern, swappable without touching code. The *only* places allowed to reference concrete providers/models are `app/ai/llm.py` (the factory + provider registry), `app/config.py` (the settings fields), and `.env`. Provider-specific SDK wrappers being phased out (`app/ai/client.py`, `tools.py`, `agent.py`) are the documented exception until PF-23 deletes them. Everywhere else, write "the LLM" / "the model" / "the provider".
- **`get_llm` factory + provider registry:** `app/ai/llm.py::get_llm(feature, model=None, provider=None, max_tokens=4096)` returns a LangChain `BaseChatModel`. Provider resolves from `provider` arg → `settings.llm_provider` (default `"groq"`); model resolves from `model` arg → `settings.llm_model` → `_DEFAULT_MODEL[provider]`. `_PROVIDERS` maps a provider name to a builder (`_build_groq`, `_build_anthropic`); imports are lazy inside each builder so an uninstalled provider never breaks startup. To add a provider: add a `langchain-<provider>` dep, a builder, and a `_DEFAULT_MODEL` entry — nothing else changes. The audit callback + `metadata={"feature","provider"}` are attached here for every model.
- **Structured output:** Use `get_llm(...).with_structured_output(PydanticModel)` — LangChain generates and forces the tool/JSON schema internally and `.invoke()` returns a validated model instance. (Not raw JSON mode.)
- **Categorize on the generic path (PF-22b):** `app/services/categorize.py::_suggest_with_llm` calls `get_llm(feature="categorize").with_structured_output(_SuggestCategoryOutput).invoke([SystemMessage(...), HumanMessage(...)])`. No `db` is passed to the LLM layer — the audit row is written by the `AuditCallbackHandler` attached inside `get_llm`, which opens its own session. The system message is a **plain string** (`_SYSTEM_PROMPT` + category list) — no `cache_control` blocks, because those are Anthropic-specific and the default provider is Groq. (Anthropic prompt-caching can be reintroduced inside the factory if a feature is ever routed back to Anthropic; it does not belong in feature code.) The rules-first path (`_match_rule`, `accept_rule`, etc.) is untouched and never calls the LLM.
- **Categorize test mocking (PF-22b):** patch `app.services.categorize.get_llm` and drive the chain via `get_llm.return_value.with_structured_output.return_value.invoke` (set `.return_value`/`.side_effect` to a `_SuggestCategoryOutput`; read `.call_args_list[i].args[0]` to inspect the messages). The old `@patch("app.services.categorize.call_llm")` + fake-SDK-block pattern is gone. `tests/test_imports.py` shares this via its autouse `mock_llm` fixture, which yields that same `.invoke` mock.
- **LangSmith tracing (PF-22c):** every LangChain call also ships a clickable trace to smith.langchain.com, sitting *alongside* the local `ai_calls` table (two layers: `ai_calls` = cost ledger we own; LangSmith = the full "what was said" transcript). **Zero code at the call sites** — LangChain auto-emits traces purely from the `LANGCHAIN_*` env vars, and the `feature` tag already set via `metadata={"feature": ...}` in `get_llm` (PF-22a) makes traces filterable by feature in the UI. Config lives in `app/config.py`: `langchain_api_key` / `langchain_tracing_v2` / `langchain_project`. **Gotcha:** LangChain's tracer reads `os.environ` directly, but pydantic-settings only fills the `settings` object — so `config.py::_export_langsmith_env(settings)` bridges the three values into `os.environ` at import. It's guarded on the API key (blank key → tracing fully off, no network call) and uses `setdefault` so a real shell/OS env var wins over `.env`. Add the key to `.env` to switch tracing on; leave it blank to keep it off.
- **Streaming:** `client.messages.stream(...)` piped straight to `text/event-stream` for the chat UI.
- **Audit log:** Every LLM call writes a row to `ai_calls`. No LangSmith dependency. `GET /api/ai/usage?from=&to=` aggregates by feature with cache hit rate. Test the endpoint by inserting rows directly — no Anthropic API calls needed in tests.
- **Model selection per feature:** decided by config, not code. The default provider (Groq) and model serve every feature unless a feature passes an explicit `model=`/`provider=` to `get_llm`. Rough intent: a cheap/fast model for high-volume routing (categorize), a stronger model for narration/reasoning (NL input, insights, chat), the largest only for explicit "deep analysis" triggers — but pick these via config/the factory, never by hard-coding a model id in feature code.
- **Config:** `app/config.py` (pydantic-settings) loads `LLM_PROVIDER` (default `groq`), `LLM_MODEL` (blank → factory default), and per-provider keys `GROQ_API_KEY` / `ANTHROPIC_API_KEY`. Copy `.env.example` → `.env` and fill in the key for whichever provider `LLM_PROVIDER` selects before running any AI feature.
- **Agent loop:** `app/ai/agent.py::run_agent()` is the single reusable tool-use loop. It accepts `tools: list[Tool]` — each `Tool` carries both the Anthropic schema and the handler. The old split of `tools: list[dict]` + `tool_handlers: dict` was replaced in PF-21.
- **Tool registry:** `app/ai/tools.py` has the `@tool` decorator and `TOOL_REGISTRY`. Decorate a function whose first parameter is a Pydantic `BaseModel` subclass — the schema is auto-generated via `model_json_schema()`. The decorated name becomes the key in `TOOL_REGISTRY`. Features pick tools by name: `tools=[TOOL_REGISTRY["create_expense"]]`.
- **Tool input validation:** `Tool.run(**kwargs)` validates Claude's raw dict through the Pydantic model before calling the handler. Wrong types surface as `ValidationError`, not a crash inside the handler.
- **Message list safety:** `run_agent` passes `list(current_messages)` (a copy) to each `call_llm` call so mock captures in tests see distinct snapshots rather than the mutated reference.
- **Tool result serialization:** `_to_str()` converts dicts/lists to JSON strings and everything else to `str()`. Tool handlers should return plain Python types — no Anthropic SDK types.
- **Unknown tool handling:** If Claude calls a tool name not in the `tools` list, `run_agent` records `{"error": "Unknown tool: <name>"}` as the result and lets Claude react, rather than crashing the whole request.
- **Content conversion:** `_blocks_to_dicts()` converts Anthropic SDK `ContentBlock` objects to plain dicts before appending to the message history. This keeps message history as pure Python dicts throughout — no SDK types leak into `current_messages`.
- **Agent tests:** Patch `app.ai.agent.call_llm` (not `app.ai.client.call_llm`) and use fake dataclass objects for messages — no `anthropic` import needed in test files. Create `Tool` objects directly (without `@tool`) to avoid `TOOL_REGISTRY` side effects in tests.

---

## Frontend conventions (Phase 2 — `apps/web`, PF-F1 onwards)

**Tooling / setup**
- **Node is required** and was not pre-installed — install via `brew install node` (Node 26+, npm 11+). `make install-web` then `make web`.
- Stack is **locked**: Vite 5 · React **18** (pin to 18, don't let Vite pull 19) · TypeScript · **Tailwind v3** (not v4) · shadcn/ui · TanStack Query (server state) · Zustand (global filters) · react-hook-form + zod (forms) · Recharts · react-router-dom v6 · sonner (toasts).
- **shadcn components are hand-authored** under `src/components/ui/` (no shadcn CLI was used) so they're fully in-repo and deterministic. `components.json` exists for reference.
- **Theming is a multi-palette system** (not just light/dark). `src/lib/themes.ts` is the registry: System, Light, Dark, plus soothing palettes Paper (off-white), Sand (beige), Sage (green), Dim (warm dark). Each palette is a full CSS-variable set in `index.css`; `ThemeProvider` applies the theme's class(es) to `<html>` (light palettes = a `theme-*` class; dark palettes also add `dark` so Tailwind `dark:` utilities still fire). The picker is `ModeToggle` (a swatch dropdown). To add a palette: add a `.theme-x` block in `index.css` + an entry in `THEMES`/`THEME_CLASSES` — nothing else.
- npm blocks package install scripts by default (newer npm). `esbuild` is approved in `package.json` `allowScripts`; the `fsevents` warning is a harmless optional macOS dep — ignore it.
- `tsconfig.json` sets `noUnusedLocals/Parameters: false` **on purpose** so the committed generated API client can never break `npm run typecheck`. `strict` stays on.
- `apps/web/.env` is gitignored (repo convention); `.env.example` is committed. `VITE_API_URL` must be prefixed `VITE_` to reach client code; changing `.env` needs a dev-server restart.

**THE single-source-of-truth utilities (cross-cutting rules — never bypass)**
- **One HTTP wrapper:** `src/lib/http.ts`. Sets `OpenAPI.BASE` once, exposes the `api.<resource>.<verb>` facade over the verbose generated method names, and `getApiError()` (normalizes any throw into `{detail, code}`). The future auth wiring (PF-39: `WITH_CREDENTIALS` + 401→/login) goes **here only**. Never call raw fetch/axios or the generated services directly from a page.
- **One money util:** `src/lib/money.ts`. Money is integer **paise** everywhere; `formatMoney`/`formatMoneyCompact` (paise→₹) and `rupeesToPaise`/`paiseToRupees` are the only paise↔₹ boundary. `Math.round` on rupees→paise guards float drift.
- **Generated client:** `src/lib/api/` is committed. Regenerate with `npm run gen:api` (backend must be running) when the API surface changes, then update the `api` facade in `http.ts` only if a signature changed. Generator: `openapi-typescript-codegen --useOptions` → service methods take a single named-options object.

**State / data**
- **Global filters** live in the Zustand store `src/store/filters.ts` (`from`, `to`, `accountIds`, `preset`). They're folded into TanStack Query keys, so changing the date range refetches every page; mutations invalidate `['transactions']`/`['holdings']`/`['dashboard']` so charts update live.
- **Account filter is single-id only at the backend** (`account_id`). The UI applies the filter only when **exactly one** account is selected; 0 or 2+ selected = no account filter. Documented limitation.
- **Optimistic updates** are used for transactions (create/update/delete in `useTransactionMutations.ts`); investments just invalidate-on-success (holdings are server-computed via GROUP BY, not worth re-deriving client-side).
- FY start month is hard-coded to April in `dateRange.ts` (TODO: read from `GET /api/settings` once PF-29 + PF-F11 exist).

**Gotchas discovered**
- **Transfers are NOT `kind: "transfer"` in responses.** The backend splits a transfer into two rows whose stored `kind` is `expense` (source) and `income` (destination), linked by a `#transfer:<uuid>` tag in the note. Detect transfers by the **note tag**, never by `kind` — see `isTransfer`/`displayKind` in `src/lib/transactions.ts`. The UI shows both halves as "Transfer" and strips the tag from the displayed note.
- **You cannot POST an uncategorized income/expense** — the backend requires a category. Uncategorized rows only arise from CSV import (confirm with `category_id: null`) or category deletion (`ON DELETE SET NULL`). The auto-categorize chip (PF-F8) targets exactly those rows and skips transfers. **The Add/Edit transaction form also has a "Suggest" button** (`TransactionFormDialog`) that calls the same `POST /api/categorize/suggest` to auto-fill the category dropdown from the note — single-transaction categorize. It only fills the field (no rule is written, unlike the chip's accept); it's an explicit button (not on-keystroke) to control LLM cost, and only applies the suggestion if it matches the selected income/expense kind.
- **`TransactionUpdate` has no `kind` or `account_id`** — editing can't change either; the form disables kind and account in edit mode. Transfer accounts can't be re-routed via PATCH (delete + re-create).
- **CSV confirm uses ONE account for all rows** (top-level `account_id`), category is per row — so the import dialog has a single account selector, not per-row accounts (despite the original AC wording).
- **No instrument-delete endpoint** exists, so a leftover dev test instrument (`F5TEST`) may linger in `data/finance.db`'s instruments catalog. Harmless.
- Radix `Select.Item` cannot have an empty-string `value` — use a sentinel (e.g. `"none"`) for "no selection" and map it to `null` on submit.
- **Pages NOT built** (no backend endpoint): Insights, Chat, Settings render a `ComingSoon` stub; NL input / advanced charts / XIRR column are omitted. Don't build these until their backend ships.
- **Accounts management (PF-F18)** is its own page at `/accounts` (`src/pages/Accounts.tsx` + `components/accounts/`). It uses `useAllAccounts()` (`GET /api/accounts?archived=true`, key `['accounts','all']`) to show archived accounts too; `useAccounts()` (key `['accounts']`, active only) still feeds the filters/forms. Account writes invalidate the `['accounts']` prefix (covers both) plus transactions/holdings/dashboard. Archive = `PATCH archived=true` (soft delete); hard `DELETE` returns 409 when referenced. Account-name uniqueness is on `(name, type)`, not name alone.
