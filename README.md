# AI Personal Finance

A personal finance dashboard with AI-powered insights, built to track income, expenses, and investments — and to learn AI/GenAI hands-on.

---

## What this app does

- Track **income** and **expenses** with categories and subcategories
- Track **investments** — Mutual Funds, Stocks, ETFs, Crypto, Gold/Silver
- Auto-recompute **dashboards and charts** on every change
- Use **AI** to categorize, parse, analyze, and research — progressively across 5 layers

Everything is in **INR (₹)**. Built for personal use, deployable for small groups.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + Vite + TypeScript + Tailwind + shadcn/ui |
| Backend | Python 3.12 + FastAPI + Pydantic v2 |
| Database | SQLite (one file per user) + SQLAlchemy 2.0 + Alembic |
| AI | Anthropic Claude API (Haiku + Sonnet + Opus) |
| Vector Store | Chroma (local, for RAG) |
| Auth | Google OAuth via Authlib (added pre-deploy) |

---

## AI Features

### Layer 1 — Auto-Categorization
Add a transaction → AI automatically assigns the right category.
Learns your patterns over time. Near-free after rules build up.

### Layer 2 — Natural Language Input
Type: *"spent 450 on Swiggy yesterday"*
App parses it into a transaction and shows a confirm card before saving.

### Layer 3 — Smart Insights (RAG)
Monthly AI analysis of your actual spending and investment data.
AI reads your real history (not generic advice), computes facts in Python, then narrates them.
Example: *"Dining out is 47% above your 3-month average."*

### Layer 4 — Chat Advisor
Ask questions about your money in plain English.
*"What's my XIRR on Zerodha?"* → answers from your real data.
Read-only — the AI can never write to your database.

### Layer 5 — Deep Research Agent (Multi-Agent)
Say: *"Research HDFC Bank"*
Six specialist AI agents run in parallel (fundamentals, news, price, peers, risk, your position).
A synthesis agent combines them into a one-pager.
Based on live data. Research only — no buy/sell advice.

---

## Project Structure

```
ai-personal-finance/
├── apps/
│   ├── api/                  # Python FastAPI backend
│   │   ├── app/
│   │   │   ├── api/          # Route handlers (one file per resource)
│   │   │   ├── models/       # SQLAlchemy ORM models
│   │   │   ├── schemas/      # Pydantic request/response models
│   │   │   ├── services/     # Business logic (pure functions)
│   │   │   ├── ai/           # Claude API client, agent loop, tools, RAG
│   │   │   └── db/           # Session, engine, migrations
│   │   ├── alembic/          # Database migrations
│   │   ├── tests/            # pytest test suite
│   │   └── pyproject.toml
│   └── web/                  # React + Vite frontend (Phase 2)
├── postman/                  # Postman collections (one per backend milestone)
├── data/                     # SQLite files — gitignored
├── scripts/                  # Dev utilities (backup, migrate-all-users, gen-api-client)
├── CLAUDE.md                 # Instructions for Claude Code
└── Makefile                  # make api | make test | make dev
```

---

## Database Design

- **Single-currency:** all values stored as `amount_minor` (paise integers). No FX columns.
- **DB-per-user:** each user gets their own SQLite file at `data/users/{user_id}.db`.
- **6 MVP tables:** `accounts`, `categories`, `transactions`, `instruments`, `investment_txns`, `settings`.
- More tables added as features ship (prices history, categorization rules, insights, embeddings).

---

## Build Strategy

**Backend first.** The entire backend (all API endpoints + AI features) is built and verified with Postman before the frontend starts.

**Implementation tickets:** see [`plans/personal-finance-impl-tickets.md`](plans/personal-finance-impl-tickets.md)

**AI features reference:** see [`plans/personal-finance-ai-features.md`](plans/personal-finance-ai-features.md)

---

## Getting Started

### Prerequisites
- Python 3.12+
- Node 20+ (for frontend, Phase 2)
- An [Anthropic API key](https://console.anthropic.com/)

### Backend setup

```bash
cd apps/api

# Create virtual environment (like Maven local cache — isolates dependencies)
python -m venv .venv
source .venv/bin/activate      # Mac/Linux
# .venv\Scripts\activate       # Windows

# Install dependencies
pip install -e ".[dev]"

# Copy env file and add your API key
cp .env.example .env

# Run database migrations (creates SQLite file + seeds categories)
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload --port 8000
```

API runs at `http://localhost:8000`
OpenAPI docs at `http://localhost:8000/docs`

### Run tests

```bash
cd apps/api
pytest
```

### Makefile shortcuts

```bash
make api        # Start backend
make test       # Run pytest
make dev        # Start backend + frontend (Phase 2)
```

---

## Roadmap

| Phase | Milestone | Status |
|---|---|---|
| Backend | Core schema + CRUD APIs (PF-1 → PF-8) | Not started |
| Backend | Investments + Analytics (PF-13 → PF-19) | Not started |
| Backend | AI Layer 1 + 2 (PF-22 → PF-27) | Not started |
| Backend | V2 Schema + Polish (PF-29 → PF-33) | Not started |
| Backend | RAG + Insights (PF-34 → PF-35) | Not started |
| Backend | Chat Advisor (PF-37 → PF-38) | Not started |
| Backend | Auth + Multi-user DB (PF-41 → PF-44) | Not started |
| Frontend | All UI (PF-F1 → PF-F17) | Not started |

---

## Plans & Design Docs

| Document | Contents |
|---|---|
| [`plans/you-are-a-senior-glowing-piglet.md`](plans/you-are-a-senior-glowing-piglet.md) | Full architecture + schema + dashboard logic |
| [`plans/personal-finance-impl-tickets.md`](plans/personal-finance-impl-tickets.md) | All 46 implementation tickets |
| [`plans/personal-finance-ai-features.md`](plans/personal-finance-ai-features.md) | All 5 AI layers explained |

---

## License

Personal use. Not for redistribution.
