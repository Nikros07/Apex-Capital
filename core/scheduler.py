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

    # ── Watchlist scans: 4× per day ──────────────────────────────────────────
    # 08:30 — Pre-market European open
    _scheduler.add_job(
        _scan_job, CronTrigger(hour=8, minute=30, day_of_week="mon-fri"),
        id="scan_morning", replace_existing=True, misfire_grace_time=300,
    )
    # 11:00 — Mid-morning
    _scheduler.add_job(
        _scan_job, CronTrigger(hour=11, minute=0, day_of_week="mon-fri"),
        id="scan_midmorning", replace_existing=True, misfire_grace_time=300,
    )
    # 15:30 — US market open (New York 09:30)
    _scheduler.add_job(
        _scan_job, CronTrigger(hour=15, minute=30, day_of_week="mon-fri"),
        id="scan_us_open", replace_existing=True, misfire_grace_time=300,
    )
    # 20:00 — US afternoon, pre-close
    _scheduler.add_job(
        _scan_job, CronTrigger(hour=20, minute=0, day_of_week="mon-fri"),
        id="scan_afternoon", replace_existing=True, misfire_grace_time=300,
    )

    # ── Monthly report: first Monday of month at 08:00 CET ──────────────────
    _scheduler.add_job(
        _monthly_report_job,
        CronTrigger(hour=8, minute=0, day_of_week="mon", week="1"),
        id="monthly_report", replace_existing=True, misfire_grace_time=600,
    )

    _scheduler.start()
    print("[Scheduler] Started — 4 daily scans, position monitor every 15 min, monthly report.")
    return _scheduler


# ─── Jobs ────────────────────────────────────────────────────────────────────

async def _monitor_job():
    if _portfolio_manager:
        try:
            await _portfolio_manager.monitor_positions()
        except Exception as e:
            print(f"[Scheduler] Monitor error: {e}")


async def _scan_job():
    """Watchlist signal scan — triggers full pipeline on any signal."""
    await run_watchlist_scan(_cio, _portfolio_manager, _broadcast)


async def run_watchlist_scan(cio, portfolio_manager, broadcast_fn) -> dict:
    """
    Public: scan all watchlist tickers for signals, run full pipeline on hits.
    Returns summary dict. Can be called from API endpoint or scheduler.
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

            rsi = ind.get("rsi", 50)
            vol_ratio = ind.get("volume_ratio", 1.0)
            ema_cross = ind.get("ema_crossover", "NONE")
            macd_diff = ind.get("macd_diff", 0) or 0

            # Lowered thresholds: RSI 35/65 (was 30/70), volume 1.5x (was 2.0)
            # Added MACD crossover as extra signal
            should_run = (
                rsi < 35 or rsi > 65
                or vol_ratio > 1.5
                or ema_cross in ("GOLDEN_CROSS", "DEATH_CROSS")
                or abs(macd_diff) > 0.5
            )

            if should_run:
                reason = (
                    f"RSI={rsi:.1f}"
                    + (f" Vol={vol_ratio:.1f}x" if vol_ratio > 1.5 else "")
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
                result = await cio.run_pipeline(ticker)
                verdict = result.get("verdict", "WAIT")
                if verdict == "INVEST":
                    risk_verdict = result.get("reports", {}).get("risk", {}).get("risk_verdict", "")
                    if risk_verdict != "CRITICAL" and portfolio_manager:
                        await portfolio_manager.execute_buy(ticker, result)
                update_watchlist_signal(ticker, verdict)
            else:
                update_watchlist_signal(ticker, f"NO_SIGNAL RSI={rsi:.0f}")
                skipped.append(ticker)

        except Exception as e:
            print(f"[Scheduler] Scan error {ticker}: {e}")
            skipped.append(ticker)

        # Throttle: 400ms between each ticker to avoid Yahoo Finance rate limits
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


async def _monthly_report_job():
    from core.reporter import generate_monthly_report
    try:
        await generate_monthly_report(_broadcast)
    except Exception as e:
        print(f"[Scheduler] Monthly report error: {e}")


def get_scheduler() -> Optional[AsyncIOScheduler]:
    return _scheduler
