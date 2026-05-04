from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

if TYPE_CHECKING:
    from agents.cio import MarcusCIO
    from core.portfolio import PortfolioManager

_scheduler: Optional[AsyncIOScheduler] = None
_portfolio_manager: Optional["PortfolioManager"] = None
_cio: Optional["MarcusCIO"] = None
_broadcast: Optional[Callable] = None


def setup_scheduler(portfolio_manager: "PortfolioManager",
                    cio: "MarcusCIO",
                    broadcast_func: Callable) -> AsyncIOScheduler:
    global _scheduler, _portfolio_manager, _cio, _broadcast
    _portfolio_manager = portfolio_manager
    _cio = cio
    _broadcast = broadcast_func

    _scheduler = AsyncIOScheduler(timezone="Europe/Berlin")

    # ── Position monitoring: every 15 min, Mon–Fri 08:00–23:00 CET ──────────
    _scheduler.add_job(
        _monitor_job,
        CronTrigger(minute="*/15", hour="8-23", day_of_week="mon-fri"),
        id="position_monitor", replace_existing=True, misfire_grace_time=120,
    )

    # ── European pre-open scan: 08:00 CET ────────────────────────────────────
    _scheduler.add_job(
        _scan_job, CronTrigger(hour=8, minute=0, day_of_week="mon-fri"),
        id="scan_eu_open", replace_existing=True, misfire_grace_time=300,
    )

    # ── Pre-US-open deep scan: 13:45 CET (30 min before NY 09:30) ────────────
    # Scores all tickers, always fully analyzes top 10 regardless of thresholds
    _scheduler.add_job(
        _deep_scan_job, CronTrigger(hour=13, minute=45, day_of_week="mon-fri"),
        id="scan_premarket_us", replace_existing=True, misfire_grace_time=300,
    )

    # ── US session intraday scans every ~2h ───────────────────────────────────
    _scheduler.add_job(
        _scan_job, CronTrigger(hour=15, minute=30, day_of_week="mon-fri"),
        id="scan_us_open", replace_existing=True, misfire_grace_time=300,
    )
    _scheduler.add_job(
        _intraday_job, CronTrigger(hour=17, minute=30, day_of_week="mon-fri"),
        id="scan_intraday_1", replace_existing=True, misfire_grace_time=300,
    )
    _scheduler.add_job(
        _intraday_job, CronTrigger(hour=19, minute=30, day_of_week="mon-fri"),
        id="scan_intraday_2", replace_existing=True, misfire_grace_time=300,
    )
    _scheduler.add_job(
        _scan_job, CronTrigger(hour=21, minute=0, day_of_week="mon-fri"),
        id="scan_preclose", replace_existing=True, misfire_grace_time=300,
    )

    # ── Daily minimum trade enforcer: 21:30 CET ───────────────────────────────
    # If no BUY was executed today, forces analysis of top-scored tickers
    _scheduler.add_job(
        _daily_min_trade_job, CronTrigger(hour=21, minute=30, day_of_week="mon-fri"),
        id="daily_min_trade", replace_existing=True, misfire_grace_time=300,
    )

    # ── Monthly report: first Monday of month at 08:00 CET ──────────────────
    _scheduler.add_job(
        _monthly_report_job,
        CronTrigger(hour=8, minute=0, day_of_week="mon", week="1"),
        id="monthly_report", replace_existing=True, misfire_grace_time=600,
    )

    _scheduler.start()
    print(
        "[Scheduler] Started — hedge fund mode: 6 daily scans + deep pre-market scan, "
        "15-min position monitor, 21:30 daily-min-trade enforcer."
    )
    return _scheduler


# ─── Opportunity scoring ─────────────────────────────────────────────────────

def _score_ticker(ind: dict) -> float:
    """
    Opportunity score 0–100.
    Higher = stronger multi-factor signal for trading consideration.
    """
    score = 50.0
    rsi = ind.get("rsi", 50) or 50
    score += abs(rsi - 50) * 0.5           # RSI deviation → max +25
    vol_ratio = ind.get("volume_ratio", 1.0) or 1.0
    score += min((vol_ratio - 1.0) * 10, 20)   # volume spike → max +20
    ema_cross = ind.get("ema_crossover", "NONE") or "NONE"
    if ema_cross in ("GOLDEN_CROSS", "DEATH_CROSS"):
        score += 15                          # crossover → +15
    macd_diff = abs(ind.get("macd_diff", 0) or 0)
    score += min(macd_diff * 5, 10)          # MACD momentum → max +10
    return min(score, 100.0)


# ─── Jobs ────────────────────────────────────────────────────────────────────

async def _monitor_job():
    if _portfolio_manager:
        try:
            await _portfolio_manager.monitor_positions()
        except Exception as e:
            print(f"[Scheduler] Monitor error: {e}")


async def _scan_job():
    """Standard watchlist signal scan — triggers pipeline on any signal."""
    await run_watchlist_scan(_cio, _portfolio_manager, _broadcast)


async def _deep_scan_job():
    """
    Pre-US-open deep scan: score every ticker, always fully analyze top 10.
    Ensures we're positioned before the US session opens.
    """
    await run_deep_scan(_cio, _portfolio_manager, _broadcast)


async def _intraday_job():
    """
    Intraday volatility-aware scan: lower volume threshold (1.3×) so we catch
    unusual activity developing mid-session.
    """
    await run_watchlist_scan(_cio, _portfolio_manager, _broadcast, vol_threshold=1.3)


async def _daily_min_trade_job():
    """
    Daily minimum trade enforcer: if no BUY was executed today,
    force-analyze the top-scored tickers and buy the best opportunity.
    Guarantees at least 1 trade per trading day.
    """
    from utils.db import get_trades_today
    try:
        trades_today = get_trades_today()
        buys_today = [t for t in trades_today if t["action"] == "BUY"]
        if buys_today:
            if _broadcast:
                await _broadcast({
                    "type": "watchlist_trigger",
                    "ticker": "SYSTEM",
                    "message": (
                        f"Daily min-trade check: {len(buys_today)} buy(s) already executed today"
                        f" ({', '.join(t['ticker'] for t in buys_today)}) — OK."
                    ),
                    "reason": "",
                })
            return

        # No BUY trades yet today
        if _broadcast:
            await _broadcast({
                "type": "watchlist_trigger",
                "ticker": "SYSTEM",
                "message": "Daily min-trade enforcer: no trades today — finding best opportunity...",
                "reason": "",
            })
        await run_forced_trade(_cio, _portfolio_manager, _broadcast)
    except Exception as e:
        print(f"[Scheduler] Daily min-trade error: {e}")


# ─── Public scan functions ────────────────────────────────────────────────────

async def run_watchlist_scan(cio, portfolio_manager, broadcast_fn,
                              vol_threshold: float = 1.5) -> dict:
    """
    Scan all watchlist tickers for signals; run full pipeline on hits.
    Returns summary dict. Called by scheduler jobs and /api/scan endpoint.
    """
    if not cio:
        return {"error": "CIO not initialised"}

    from data.market import fetch_indicators
    from utils.db import get_watchlist, update_watchlist_signal

    watchlist = get_watchlist()
    triggered = []
    skipped = []

    if broadcast_fn:
        await broadcast_fn({
            "type": "watchlist_trigger",
            "ticker": "ALL",
            "message": f"Scanning {len(watchlist)} tickers for signals...",
            "reason": "",
        })

    for item in watchlist:
        ticker = item["ticker"]
        try:
            ind = await fetch_indicators(ticker)
            if not ind:
                skipped.append(ticker)
                continue

            rsi = ind.get("rsi", 50) or 50
            vol_ratio = ind.get("volume_ratio", 1.0) or 1.0
            ema_cross = ind.get("ema_crossover", "NONE") or "NONE"
            macd_diff = ind.get("macd_diff", 0) or 0

            should_run = (
                rsi < 35 or rsi > 65
                or vol_ratio > vol_threshold
                or ema_cross in ("GOLDEN_CROSS", "DEATH_CROSS")
                or abs(macd_diff) > 0.5
            )

            if should_run:
                reason = (
                    f"RSI={rsi:.1f}"
                    + (f" Vol={vol_ratio:.1f}x" if vol_ratio > vol_threshold else "")
                    + (f" {ema_cross}" if ema_cross != "NONE" else "")
                    + (f" MACD_DIFF={macd_diff:.2f}" if abs(macd_diff) > 0.5 else "")
                )
                triggered.append(ticker)
                if broadcast_fn:
                    await broadcast_fn({
                        "type": "watchlist_trigger",
                        "ticker": ticker,
                        "reason": reason,
                        "message": f"Signal on {ticker} ({reason}) — running pipeline",
                    })
                try:
                    result = await cio.run_pipeline(ticker)
                    verdict = result.get("verdict", "WAIT")
                    if verdict == "INVEST":
                        risk_verdict = (
                            result.get("reports", {}).get("risk", {}).get("risk_verdict", "")
                        )
                        if risk_verdict != "CRITICAL" and portfolio_manager:
                            await portfolio_manager.execute_buy(ticker, result)
                    update_watchlist_signal(ticker, verdict)
                except Exception as pipe_err:
                    print(f"[Scheduler] Pipeline error {ticker}: {pipe_err}")
                    update_watchlist_signal(ticker, "PIPELINE_ERROR")
            else:
                update_watchlist_signal(ticker, f"NO_SIGNAL RSI={rsi:.0f}")
                skipped.append(ticker)

        except Exception as e:
            print(f"[Scheduler] Scan error {ticker}: {e}")
            skipped.append(ticker)

        # 400ms throttle — avoids Yahoo Finance 429 rate limit
        await asyncio.sleep(0.4)

    summary = {
        "scanned": len(watchlist),
        "triggered": len(triggered),
        "tickers_triggered": triggered,
        "skipped": len(skipped),
    }
    if broadcast_fn:
        await broadcast_fn({
            "type": "watchlist_trigger",
            "ticker": "ALL",
            "message": f"Scan complete — {len(triggered)}/{len(watchlist)} triggered",
            "reason": f"Triggered: {', '.join(triggered) or 'none'}",
        })
    return summary


async def run_deep_scan(cio, portfolio_manager, broadcast_fn) -> dict:
    """
    Deep scan: score all tickers, always fully analyze top 10.
    Used before US market open to pre-position.
    """
    if not cio:
        return {"error": "CIO not initialised"}

    from data.market import fetch_indicators
    from utils.db import get_watchlist, update_watchlist_signal

    watchlist = get_watchlist()
    if broadcast_fn:
        await broadcast_fn({
            "type": "watchlist_trigger",
            "ticker": "ALL",
            "message": f"Deep pre-market scan: scoring {len(watchlist)} tickers...",
            "reason": "",
        })

    scores: list[tuple[str, float]] = []
    for item in watchlist:
        ticker = item["ticker"]
        try:
            ind = await fetch_indicators(ticker)
            if ind:
                scores.append((ticker, _score_ticker(ind)))
        except Exception as e:
            print(f"[Scheduler] Deep scan score error {ticker}: {e}")
        await asyncio.sleep(0.3)

    # Sort by opportunity score, take top 10
    scores.sort(key=lambda x: x[1], reverse=True)
    top_10 = scores[:10]

    if broadcast_fn:
        top_str = ", ".join(f"{t}({s:.0f})" for t, s in top_10)
        await broadcast_fn({
            "type": "watchlist_trigger",
            "ticker": "ALL",
            "message": f"Deep scan top 10: {top_str}",
            "reason": "Running full pipeline on all top scorers",
        })

    traded: list[str] = []
    for ticker, score in top_10:
        try:
            result = await cio.run_pipeline(ticker)
            verdict = result.get("verdict", "WAIT")
            update_watchlist_signal(ticker, f"{verdict} score={score:.0f}")
            if verdict == "INVEST":
                risk_verdict = (
                    result.get("reports", {}).get("risk", {}).get("risk_verdict", "")
                )
                if risk_verdict != "CRITICAL" and portfolio_manager:
                    trade = await portfolio_manager.execute_buy(ticker, result)
                    if trade.get("success"):
                        traded.append(ticker)
        except Exception as e:
            print(f"[Scheduler] Deep scan pipeline error {ticker}: {e}")
        await asyncio.sleep(0.4)

    if broadcast_fn:
        await broadcast_fn({
            "type": "watchlist_trigger",
            "ticker": "ALL",
            "message": f"Deep scan complete — {len(traded)} trade(s) executed",
            "reason": f"Bought: {', '.join(traded) or 'none'}",
        })
    return {"scanned": len(watchlist), "analyzed": len(top_10), "traded": traded}


async def run_forced_trade(cio, portfolio_manager, broadcast_fn) -> dict:
    """
    Force-analyze the top 3 scored tickers and buy the first INVEST verdict.
    Called when no trade has been made today (daily minimum enforcer).
    """
    if not cio:
        return {"error": "CIO not initialised"}

    from data.market import fetch_indicators
    from utils.db import get_watchlist, update_watchlist_signal

    watchlist = get_watchlist()
    scores: list[tuple[str, float]] = []

    for item in watchlist:
        ticker = item["ticker"]
        try:
            ind = await fetch_indicators(ticker)
            if ind:
                scores.append((ticker, _score_ticker(ind)))
        except Exception:
            pass
        await asyncio.sleep(0.3)

    scores.sort(key=lambda x: x[1], reverse=True)
    top_3 = scores[:3]

    for ticker, score in top_3:
        try:
            if broadcast_fn:
                await broadcast_fn({
                    "type": "watchlist_trigger",
                    "ticker": ticker,
                    "message": f"Forced analysis: {ticker} (score={score:.0f})",
                    "reason": "Daily minimum trade enforcer",
                })
            result = await cio.run_pipeline(ticker)
            verdict = result.get("verdict", "WAIT")
            update_watchlist_signal(ticker, f"{verdict} FORCED")
            if verdict == "INVEST":
                risk_verdict = (
                    result.get("reports", {}).get("risk", {}).get("risk_verdict", "")
                )
                if risk_verdict != "CRITICAL" and portfolio_manager:
                    trade = await portfolio_manager.execute_buy(ticker, result)
                    if trade.get("success"):
                        if broadcast_fn:
                            await broadcast_fn({
                                "type": "watchlist_trigger",
                                "ticker": ticker,
                                "message": f"Daily min-trade fulfilled: BUY {ticker}",
                                "reason": f"Forced trade, score={score:.0f}",
                            })
                        return {"success": True, "ticker": ticker}
        except Exception as e:
            print(f"[Scheduler] Forced trade error {ticker}: {e}")

    if broadcast_fn:
        await broadcast_fn({
            "type": "watchlist_trigger",
            "ticker": "SYSTEM",
            "message": "Daily min-trade: no INVEST verdict found in top 3 candidates.",
            "reason": "",
        })
    return {"success": False, "reason": "No INVEST verdict in top 3"}


async def _monthly_report_job():
    from core.reporter import generate_monthly_report
    try:
        await generate_monthly_report(_broadcast)
    except Exception as e:
        print(f"[Scheduler] Monthly report error: {e}")


def get_scheduler() -> Optional[AsyncIOScheduler]:
    return _scheduler
