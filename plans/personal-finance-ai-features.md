# Personal Finance App — AI Features Reference

Five AI layers, from simplest to most complex.
Each layer builds on the previous one.

---

## Layer 1 — Auto-Categorization

### What it does
When you add a transaction, the app automatically assigns the right category.
You don't have to pick from a dropdown every time.

### Example
> You add ₹450, note: "Swiggy order"
> App tags it → **Food → Dining Out** automatically

### How it learns
- First, it tries your saved rules (e.g. "Swiggy" always = Dining Out)
- If no rule matches, it asks Claude Haiku (fastest, cheapest model)
- You confirm or correct → that correction becomes a new rule
- Over time, 90%+ of entries need zero AI calls — rules handle them

### Models used
- Claude Haiku (only when no rule matches)

### Prompt caching benefit
The category list + system prompt is cached — so every Haiku call after the first one is ~10× cheaper

---

## Layer 2 — Natural Language Input

### What it does
Type a sentence like you'd send a WhatsApp message.
The app turns it into a proper transaction — no form filling.

### Examples
> "spent 1200 on groceries at DMart yesterday"
> "got salary of 85000 today"
> "paid 15000 rent for May from HDFC"
> "bought coffee for 180 at Blue Tokai this morning"

### How it works
- Claude Sonnet reads your sentence using **tool-use**
- Tool-use means: the AI doesn't just reply in text — it fills in a structured form (`amount`, `category`, `account`, `date`, `note`)
- A **confirm card** appears before anything is saved — you see what it parsed and can edit
- You hit Save → transaction is created

### What tool-use means (Java analogy)
Think of it like the AI calling a specific method:
`createExpense(amount=120000, category="Groceries", account="HDFC", date="2026-04-28", note="DMart")`
The AI doesn't write free text — it fills in typed fields.

### Models used
- Claude Sonnet (better at parsing ambiguous language than Haiku)

---

## Layer 3 — Smart Insights (RAG)

### What it does
Every month, the app generates a short personal financial analysis — things you wouldn't notice just by looking at numbers.

**RAG = Retrieval-Augmented Generation**
Plain English: before the AI writes anything, it first reads your actual transaction history as context. It doesn't guess or use generic advice — it responds to YOUR data.

### Example insights
> "Your dining-out spend is ₹3,800 higher this month — 47% above your 3-month average."

> "Savings rate this month: 31%. Best in 6 months."

> "Equity is at 72% of your portfolio — 7pp above your 65% target. ₹18,000 needs to move to debt."

> "3 months in a row your entertainment spend has grown. It's now your 3rd largest category."

### How it works
1. Python computes the **facts** first (exact numbers, percentages, deltas)
2. The app retrieves relevant past months from your history (the "R" in RAG)
3. Claude Sonnet writes the insight using only those facts — never invents numbers
4. Results are cached so you're not billed every page load

### Key rule
The AI only narrates. Python does the math. If the insight says "₹3,800 higher" — that number came from a Python function, not the AI's guess.

### Models used
- Claude Sonnet (for insight generation)
- Embedding model (to index and retrieve past transactions)

### Storage
- Transaction chunks stored in **Chroma** (local vector database)
- Generated insights cached in the `insights` table

---

## Layer 4 — Chat Advisor

### What it does
Ask questions about your money in plain English.
The app answers using your real data — not generic financial advice.

### Example conversations

**Spending questions**
> You: "How much did I spend on travel last quarter?"
> App: "₹34,200 across 6 transactions — flights ₹22,000, hotels ₹8,500, local transport ₹3,700."

**Investment questions**
> You: "What's my XIRR on my Zerodha account?"
> App: "14.3% annualized since April 2024, across 8 instruments."

**Portfolio questions**
> You: "Which of my mutual funds is performing worst?"
> App: "Axis Bluechip has the lowest XIRR at 6.1% over 2 years, vs your portfolio average of 13.4%."

**Boundary (what it refuses)**
> You: "Should I buy more HDFC Bank?"
> App: "I can show you your current HDFC Bank position and all the numbers — but advising whether to buy or sell is a regulated decision I can't make for you."

### How it works
- Claude Sonnet with **read-only tools** — the AI can query your DB but cannot write to it
- Tools available to the AI: `query_transactions`, `get_holdings`, `get_allocation`, `compute_xirr`, `get_monthly_summary`
- Multi-turn: the chat remembers context across messages in a thread
- Streaming: response appears word by word, like ChatGPT

### Safety
The AI session uses a read-only database connection.
Physically cannot insert, update, or delete anything.

### Models used
- Claude Sonnet (streaming, tool-use)

---

## Layer 5 — Deep Research Agent (Multi-Agent)

### What it does
You say: "Research HDFC Bank"
5 minutes later you get a structured one-pager covering every angle of that stock/MF/ETF/crypto — based on the latest live data.

Replaces hours of manual research across screener.in, moneycontrol, news sites, and broker apps.

### The one-pager it produces

```
HDFC Bank — Research Brief  |  Generated: 29 Apr 2026

BUSINESS SNAPSHOT
What the company does, revenue trend, profit, key segments

FINANCIAL HEALTH
PE: 18.2x  |  ROE: 16.8%  |  Debt/Equity: 0.8  |  PAT Margin: 22%
vs sector avg: PE 21x, ROE 15%  → trading at a discount on PE

RECENT NEWS (last 30 days)
Q4 FY26 results: Net profit ₹17,622 cr (+6.7% YoY)
RBI removed restrictions on new credit card issuances (Apr 22)

PRICE & TECHNICALS
Current: ₹1,624  |  52W High: ₹1,880  |  52W Low: ₹1,363
Trend: recovering from 52W low, above 200-day MA

PEER COMPARISON
              HDFC Bank   ICICI Bank   Kotak Bank
PE ratio       18.2x        19.4x        22.1x
ROE            16.8%        18.2%        14.1%
1Y return      +11%         +24%         +6%

YOUR POSITION
10 shares @ avg cost ₹1,450  |  Current: ₹1,624  |  P&L: +₹1,740 (+12%)

RISK FLAGS
⚠ Slowing credit growth vs peers
⚠ High exposure to unsecured retail loans

RESEARCH SUMMARY
Strong fundamentals, reasonable valuation vs sector.
Recent RBI relief is a positive trigger.
Main risk: retail credit quality in a high-rate environment.
```

### The multi-agent system — simply explained

Think of it like a research team where each person is an expert in one area:

```
You: "Research HDFC Bank"
          ↓
  [Coordinator Agent]
  Understands the request, assigns tasks to specialists
          ↓ (all run in parallel)
┌──────────────────────────────────────────────┐
│ Fundamentals Agent  → PE, ROE, margins       │
│ News Agent          → last 30 days of news   │
│ Price Agent         → chart, technicals      │
│ Peer Agent          → comparison with peers  │
│ Risk Agent          → red flags, concerns    │
│ Portfolio Agent     → your own position      │
└──────────────────────────────────────────────┘
          ↓
  [Synthesis Agent]
  Reads all 6 reports, writes the final one-pager
          ↓
  Result shown to you (~30–60 seconds)
```

Each "agent" is one Claude API call with a specific job and specific tools.
Running them in parallel means you get the full report fast.

### Data sources (all live, fetched at query time)

| Data | Source | Cost |
|---|---|---|
| Stock price, financials, ratios | `yfinance` (NSE: append `.NS`) | Free |
| Mutual fund NAV + holdings | AMFI + mfapi.in | Free |
| Latest news + announcements | Tavily search API | ~₹0.08/search |
| Crypto prices | CoinGecko free API | Free |
| Peer financials | yfinance + screener.in | Free |

### Works for
- **Stocks** (NSE/BSE listed)
- **Mutual Funds** (by scheme name or AMFI code)
- **ETFs** (Nifty 50 ETF, Gold ETF, etc.)
- **Crypto** (Bitcoin, Ethereum, etc.)
- **Gold/Silver** (current price + your holding value)

### Important boundary
This feature produces **research**, not advice.
The synthesis agent is instructed: *"Summarize the facts. Do not say buy or sell."*
The decision is always yours.

### Models used
- Claude Haiku — Fundamentals, Price, Peer agents (fast, structured data extraction)
- Claude Sonnet — News agent, Risk agent (needs judgment)
- Claude Sonnet — Synthesis agent (writes the final brief)
- Claude Opus — Optional "deep dive" mode if user wants extended analysis

### When this gets built
Last in the roadmap (after Chat Advisor is working).
This is where we evaluate **LangGraph** — because parallel agent coordination
with a supervisor is exactly the use case LangGraph was built for.

---

## Summary Table

| Layer | Feature | Trigger | Output | Model |
|---|---|---|---|---|
| 1 | Auto-Categorize | Add any transaction | Category tag | Haiku |
| 2 | NL Input | Type a sentence | Parsed transaction (confirm first) | Sonnet |
| 3 | Smart Insights | Monthly / on demand | Written financial analysis of your data | Sonnet |
| 4 | Chat Advisor | Ask a question | Answer from your real data | Sonnet |
| 5 | Deep Research | "Research HDFC Bank" | One-pager on any stock/MF/ETF/crypto | Haiku + Sonnet + Opus |

## Cost per feature (rough estimate)

| Feature | Per use | Notes |
|---|---|---|
| Auto-Categorize (Haiku) | ~₹0.002 | Near-zero after rules kick in |
| NL Input (Sonnet) | ~₹0.05 | Per sentence parsed |
| Insights (Sonnet + RAG) | ~₹0.50 | Per monthly report |
| Chat (Sonnet, streaming) | ~₹0.10 | Per conversation turn |
| Deep Research (multi-agent) | ~₹2–5 | Per full research report |

Prompt caching on system prompts + category lists cuts Layers 1–2 costs by ~80%.
