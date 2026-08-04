# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Apex Capital is an autonomous paper-trading "hedge fund": a hierarchy of 10 LLM-driven agent
personas independently research a ticker, debate it, and a FastAPI backend auto-executes trades
against a simulated €10,000 portfolio — no manual confirmation. Real market data (yfinance), fake
money. Trading is paper-only; there is no live brokerage integration anywhere in this codebase.

## Commands

```bash
cp .env.example .env        # fill in API keys — see .env.example for what each does
pip install -r requirements.txt
python main.py               # runs uvicorn on :8000 (or $PORT)
```

There is no lint config, formatter config, or test suite in this repo (`.gitignore` excludes a
local-only `test_local.py` that isn't tracked) — don't invent commands for these. Verify changes
by running the app and exercising the relevant endpoint/WebSocket, or by reasoning through the
async control flow directly.

Docker: `docker compose up -d --build` (mounts `./sqlite-data:/data`, sets `DB_PATH=/data/apex.db`).

Debug endpoint: `GET /api/test-keys` — pings every configured OpenRouter key against every free
model and reports per-key/per-model status. Use this first when diagnosing "agents doing nothing"
or LLM-fallback-default output — it's almost always an exhausted/dead key or a retired free model.

## Architecture

### Request flow: one ticker through the pipeline

`MarcusCIO.run_pipeline(ticker)` (`agents/cio.py`) is the single entry point every code path uses —
manual `/api/analyze`, scheduled scans, and forced trades all call it. It is a fixed sequential/
parallel pipeline, not a dynamic agent graph:

1. **Elena** (macro) sets market regime — runs first, its output is fed to everyone downstream.
2. Market data fetched once (`data/market.py`: 6mo OHLCV + `ta`-computed indicators).
3. **Kai** (technical), **Sophie** (fundamental), **Alex** (research) run **in parallel** via
   `asyncio.gather`, each conditioned on Elena's macro report.
4. **Jordan** (sentiment) runs after, conditioned on Kai's technical signal.
5. **Viktor** (risk) computes position sizing / stop-loss / take-profit in pure Python (not the
   LLM — see below), then asks the LLM only for a verdict label and narrative.
6. **Committee** (`agents/committee.py`): **Leo** argues bull, **Nina** argues bear, **Marcus**
   (CIO persona) hands down `INVEST | PASS | WAIT` plus size/entry/SL/TP. Marcus is a Python
   *veto* layer over the LLM output, not just a passthrough — see "Verdict is not purely LLM below.
7. If verdict is `INVEST`, **Dante** (devil's advocate) challenges it *after* the verdict — his
   output is informational only, he cannot reverse the trade.
8. `main.py._run_analysis` executes the buy immediately if `verdict == INVEST` and
   `risk_verdict != CRITICAL`.

Every agent extends `BaseAgent` (`agents/base.py`), which provides `call_llm`, `search`, and
`_parse_json` — read this file first when touching any agent, since the LLM-call machinery lives
here, not per-agent.

### Verdict is not purely LLM-driven

Several correctness-critical values are computed/overridden in plain Python around the LLM calls,
by design — don't "fix" these into pure LLM output:

- **Position sizing, stop-loss, take-profit, R/R** are all formula-derived in `agents/risk.py`
  (1% account risk ÷ 1.5×ATR stop distance), *before* the LLM is asked anything. The LLM only
  narrates a risk verdict; Viktor's numbers are what actually get used.
- `agents/risk.py` **hard-overrides** `risk_verdict` to `CRITICAL` regardless of what the LLM
  said, for: already holding the ticker, earnings within 2 days, or VIX > 40.
- `agents/committee.py` forces `verdict = "INVEST"` if the LLM's JSON is unparseable/missing a
  verdict (Apex is designed to be capital-deployed, not to sit in cash on LLM hiccups), applies an
  0.85× size haircut when Leo/Nina convictions diverge by >3, and **vetoes to `PASS`** whenever
  Viktor's `risk_verdict == CRITICAL` — this veto always wins regardless of Marcus's own verdict.
- `_parse_json` (`agents/base.py`) falls back to a caller-supplied Python default dict whenever
  the LLM output isn't valid JSON — every agent has a hand-written default report matching its
  schema. When adding a new agent, always author a sensible default; the pipeline must never hard
  crash just because a free model returned prose instead of JSON.

### Guaranteed-trade fallback (core/scheduler.py)

Apex is designed to never sit fully idle: every scan path has a fallback chain if no trade
results from normal signal-triggered analysis.

- `run_watchlist_scan` — RSI/volume/EMA-crossover/MACD threshold scan of the whole watchlist,
  runs the full pipeline only on tickers that trip a threshold.
- `run_deep_scan` — scores *every* watchlist ticker with `_score_ticker` (0–100, RSI deviation +
  volume spike + crossover + MACD momentum) and always fully analyzes the top 10, independent of
  thresholds. Used for the pre-US-open scan and the 90s-after-boot startup scan.
- `run_forced_trade` — two-stage last resort, called by both scan functions when nothing traded,
  and by the 21:30 daily-minimum-trade job:
  - **Stage 1**: run the full LLM pipeline on the top 5 scored tickers, take the first `INVEST`.
  - **Stage 2 (hard bypass)**: if stage 1 produces nothing, buy the top-scored eligible ticker
    directly with a Python-only ATR-based size/SL/TP — **no LLM call at all**. This is the reason
    a trade can appear with no corresponding agent commentary.

Keep this in mind before assuming every trade in `trades` reflects genuine multi-agent agreement —
per the README, not every trade came from agents agreeing.

### Scheduling (core/scheduler.py, `AsyncIOScheduler`, Europe/Berlin tz)

Fixed cron jobs, not configurable via env: 1-min position monitor (08:00–23:00 CET Mon–Fri),
08:00 EU-open scan, 08:01 morning briefing, 13:45 deep pre-market scan, 15:30 US-open scan, 17:30/
19:30 intraday scans, 21:00 pre-close scan, 21:30 daily-min-trade enforcer, first-Monday-08:00
monthly report. `setup_scheduler` is called once from `main.py`'s lifespan startup; scan/report
functions are also invoked directly by REST endpoints (`/api/scan`, `/api/reports/generate`) for
manual triggering, sharing the exact same code paths as the cron jobs.

### Portfolio & risk mechanics (core/portfolio.py)

`PortfolioManager` is the only writer to portfolio state (`utils/db.py`'s `portfolio` table, one
row, `positions` stored as a JSON blob). Key rules baked into the code, not configurable:

- Max 15 concurrent positions, min 7% cash reserve (`MIN_CASH_RESERVE`).
- Buy blocked by cash reserve → `_free_capital_for_new_position` auto-sells the weakest open
  position (lowest `pnl_pct`) and retries once before failing.
- Trailing stop only ever moves up (`monitor_positions`, called every minute).
- Partial take-profit: at TP, sell 60%, move stop-loss to breakeven, extend TP by 2×ATR on the
  remainder (`execute_partial_sell`).
- Dead-money exit: position held ≥48h with <1.5% gain is force-closed, freeing capital.
- Every sell schedules `_trigger_reinvest` (5s delay, then `run_forced_trade`) — freed capital is
  redeployed automatically rather than sitting as cash.

### LLM plumbing (agents/base.py, utils/key_manager.py)

- **No paid LLM usage anywhere** — OpenRouter's free-tier models only (`FREE_MODELS` in
  `agents/base.py`), with Gemini free tier as the last-resort fallback after every OpenRouter
  model/key combination is exhausted. There is no paid-model code path to wire up.
- `call_llm` rotates through `FREE_MODELS` and rotates the OpenRouter key on 429s, trying up to
  `len(FREE_MODELS)` combinations before falling through to Gemini.
- `KeyManager` (singleton) assigns each agent a fixed OpenRouter key round-robin at startup
  (`OPENROUTER_KEY_1..5`) so agents run against different keys in parallel without contending for
  the same rate limit; `rotate_key` advances an agent past a rate-limited key.
- **The free-model catalogs go stale** — both `FREE_MODELS` and `GEMINI_MODELS` in
  `agents/base.py` carry dated comments noting that OpenRouter's/Google's free-tier lineup has
  fully turned over before and 404'd entirely. If `/api/test-keys` shows all-model failure, refetch
  the live catalog (`https://openrouter.ai/api/v1/models`, filter `:free` suffix; or
  `https://ai.google.dev/gemini-api/docs/models`) rather than guessing model IDs.
- Web search (`BaseAgent.search`): Tavily first if `TAVILY_API_KEY` is set, falls through to
  DuckDuckGo (`ddgs`, no key) on any non-200 or missing key.

### Database (utils/db.py)

Dual backend chosen automatically by env, not by explicit config flag: if `TURSO_DATABASE_URL` is
set, uses remote Turso (libSQL) via a single reused module-level connection (network round-trip
per fresh connection is too costly for the 1-min monitor loop); otherwise local SQLite in WAL mode.
`_TursoConn`/`_TursoConnHandle` wrap libsql's API to match sqlite3's `execute`/`fetchone`/
`fetchall`/dict-row surface so every query function in this file is backend-agnostic — never call
the raw sqlite3/libsql APIs directly from outside `utils/db.py`.

### WebSocket broadcasting

`main.py`'s `ConnectionManager` fans out a single `broadcast(dict)` coroutine to every connected
`/ws` client, JSON-encoded (`default=str` handles datetimes). Almost everything in `agents/` and
`core/` accepts an optional `broadcast: Callable` and pushes typed progress events
(`agent_status`, `agent_done`, `pipeline_step`, `trade_executed`, `watchlist_trigger`, etc.) —
that's how `static/index.html` and `static/dashboard-clean.html` render live pipeline progress.
When adding a new agent or pipeline step, broadcast status the same way so the dashboards stay in
sync; don't silently skip it.

### Frontend

`static/index.html` (`/`, Bloomberg-terminal dark theme) and `static/dashboard-clean.html`
(`/clean`, minimal light-blue theme) are two independent, vanilla-JS, no-build-step UIs served as
static files against the same REST API and `/ws` feed. There is no shared component layer between
them — a UI change usually needs to be made in both files if it should appear on both dashboards.

### Deployment

Dockerfile-based; deploy target is auto-detected by env rather than by separate build configs:
Railway (persistent disk → local SQLite, mount a Volume at `/data`) or Render (no persistent disk
on free tier → must set `TURSO_DATABASE_URL`/`TURSO_AUTH_TOKEN`, plus an external pinger hitting
`/health` to prevent free-tier sleep). `APP_VERSION` in `main.py` auto-suffixes with the Railway
git commit SHA (`RAILWAY_GIT_COMMIT_SHA`) so the version shown in the UI always identifies the
exact deployed commit.
