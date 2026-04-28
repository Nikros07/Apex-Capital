# ▲ Apex Capital Management

> Fully autonomous multi-agent AI hedge fund with simulated paper trading. Starts at €10,000.

A hierarchy of AI agents with distinct personalities that research stocks independently, debate, and autonomously execute trades. No manual confirmation needed — the fund runs itself.

---

## Live Demo

Deploy to Railway in one click (see below) and open the Bloomberg terminal dashboard in your browser.

---

## Agent Roster

| Agent | Role | Personality |
|---|---|---|
| **Elena** | Macro Economist | Calm, data-driven. Sets market regime for all other agents |
| **Kai** | Technical Analyst | Arrogant chart obsessive. "The tape never lies." |
| **Sophie** | Fundamental Analyst | Buffett/Munger devotee. Free cash flow above all |
| **Alex** | Research Analyst | Hyperactive. Finds what everyone else misses |
| **Jordan** | Social Sentiment | Reads Reddit + StockTwits. Never a perma-bull or bear |
| **Viktor** | Risk Manager | Seen every crash since 1987. Always says no first |
| **Leo** | Bull Advocate | Eternal optimist. Always finds a reason to buy |
| **Nina** | Bear Advocate | Permanent skeptic. Remembers 2008, 2001, 1987 |
| **Marcus** | CIO / Verdict | Ray Dalio energy. Final INVEST / PASS / WAIT decision |
| **Dante** | Devil's Advocate | Finds the fatal flaw after every INVEST verdict |

---

## Pipeline

```
Elena (Macro Context)
    ↓
yfinance OHLCV + Technical Indicators
    ↓
Kai + Sophie + Alex [parallel] → Jordan (Sentiment)
    ↓
Viktor (Risk: position size, SL, TP, R/R)
    ↓
Leo vs Nina → Marcus (INVEST / PASS / WAIT)
    ↓  [if INVEST]
Dante (Devil's Advocate — advisory warning)
    ↓
Auto-execute paper trade
```

---

## Tech Stack

- **Backend:** Python 3.11, FastAPI + uvicorn (fully async)
- **LLM:** OpenRouter → `meta-llama/llama-3.1-8b-instruct:free`
- **Market Data:** yfinance + pandas + ta
- **Web Search:** Tavily
- **Social Data:** PRAW (Reddit) + StockTwits REST API
- **Database:** SQLite
- **Scheduling:** APScheduler
- **Frontend:** Vanilla JS, single `index.html`, Bloomberg terminal dark UI
- **Deploy:** Railway

---

## Dashboard

| Page | Description |
|---|---|
| **Dashboard** | Portfolio value, open positions, live agent activity feed |
| **Analyze** | Enter ticker → live pipeline → full report with 8 sub-tabs |
| **Portfolio** | Trade history, equity curve, win/loss chart |
| **Reports** | Monthly reports with Marcus's narrative |
| **Watchlist** | Auto-scan tickers on signal triggers |

---

## Local Setup

```bash
git clone https://github.com/Nikros07/Apex-Capital.git
cd Apex-Capital

# Configure
cp .env.example .env
# Edit .env — fill in your API keys

# Install
pip install -r requirements.txt

# Run
python main.py
# → http://localhost:8000
```

### Required API Keys

| Key | Source |
|---|---|
| `OPENROUTER_KEY_1..5` | [openrouter.ai](https://openrouter.ai) → Keys (free tier available) |
| `TAVILY_API_KEY` | [app.tavily.com](https://app.tavily.com) |
| `REDDIT_CLIENT_ID/SECRET` | [reddit.com/prefs/apps](https://reddit.com/prefs/apps) → create script app |

---

## Deploy to Railway

### 1 — Fork & connect

1. Fork this repo on GitHub
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
3. Select `Apex-Capital`

### 2 — Add Volume (for persistent SQLite)

Railway's filesystem is ephemeral. Without a volume, `apex.db` is wiped on every restart.

1. Railway dashboard → your project → **+ New** → **Volume**
2. Mount path: `/data`
3. Set env var: `DB_PATH=/data/apex.db`

### 3 — Set environment variables

In Railway → your service → **Variables**, add all keys from `.env.example`:

```
OPENROUTER_KEY_1=sk-or-v1-...
OPENROUTER_KEY_2=sk-or-v1-...
OPENROUTER_KEY_3=sk-or-v1-...
OPENROUTER_KEY_4=sk-or-v1-...
OPENROUTER_KEY_5=sk-or-v1-...
TAVILY_API_KEY=tvly-...
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=ApexCapital/1.0
WATCHLIST=AAPL,TSLA,NVDA,MSFT,SPY
DB_PATH=/data/apex.db
```

> `PORT` is set automatically by Railway — **do not add it manually**.

### 4 — Deploy

Railway auto-builds via Nixpacks and deploys. Your public URL appears in the dashboard.

---

## Scheduled Jobs

| Job | Schedule | Action |
|---|---|---|
| Position Monitor | Every 15 min, Mon–Fri 09:00–22:00 CET | Check SL/TP, auto-sell |
| Daily Watchlist Scan | 09:15 CET weekdays | Signal scan → auto-analyze if triggered |
| Monthly Report | 1st Monday 08:00 CET | P&L report + Marcus narrative |

---

## Risk Rules

- Position size = 1% account risk ÷ (1.5 × ATR)
- Stop-loss: entry − 1.5×ATR
- Take-profit: entry + 2.5×ATR
- Monthly drawdown >5% → halve all sizes
- 3 consecutive losses → cooling-off, −50% sizes
- Meme risk flag (WSB >50 posts) → −40% size
- Contrarian flag → −15% size
- HIGH_UNCERTAINTY (Leo/Nina conviction diff >2) → −30% size
- Viktor CRITICAL → CIO veto → forced PASS

---

## Project Structure

```
apex/
├── main.py                  FastAPI app + WebSocket manager
├── agents/
│   ├── base.py              LLM calls, Tavily search, key rotation
│   ├── cio.py               Pipeline orchestrator
│   ├── macro.py             Elena
│   ├── technical.py         Kai
│   ├── fundamental.py       Sophie
│   ├── research.py          Alex
│   ├── sentiment.py         Jordan
│   ├── risk.py              Viktor
│   ├── committee.py         Leo + Nina + Marcus
│   └── devil.py             Dante
├── core/
│   ├── portfolio.py         Paper trading engine
│   ├── scheduler.py         APScheduler jobs
│   └── reporter.py          Monthly reports
├── data/
│   ├── market.py            yfinance + indicators
│   ├── reddit_client.py     PRAW wrapper
│   └── stocktwits_client.py StockTwits REST
├── utils/
│   ├── key_manager.py       Round-robin key rotation
│   └── db.py                SQLite schema + CRUD
├── static/index.html        Bloomberg terminal UI
├── .env.example             Config template
├── requirements.txt
├── nixpacks.toml            Railway build config
├── .python-version          Python 3.11
├── Procfile
└── railway.json
```

---

## Health Check

`GET /health` — returns JSON with portfolio state. Used by Railway to confirm the app is running.

---

*Built with Claude Code*
