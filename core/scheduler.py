from __future__ import annotations

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

    # Position monitoring every 15 min on weekdays 09:00–22:00 CET
    _scheduler.add_job(
        _monitor_job, CronTrigger(minute="*/15", hour="9-22", day_of_week="mon-fri"),
        id="position_monitor", replace_existing=True, misfire_grace_time=120,
    )

    # Daily watchlist scan — 09:15 CET weekdays
    _scheduler.add_job(
        _daily_scan_job, CronTrigger(hour=9, minute=15, day_of_week="mon-fri"),
        id="daily_scan", replace_existing=True, misfire_grace_time=300,
    )

    # Monthly report — first Monday of each month at 08:00 CET
    _scheduler.add_job(
        _monthly_report_job, CronTrigger(hour=8, minute=0, day_of_week="mon", week="1"),
        id="monthly_report", replace_existing=True, misfire_grace_time=600,
    )

    _scheduler.start()
    print("[Scheduler] Started — position monitor, daily scan, monthly report.")
    return _scheduler


async def _monitor_job():
    if _portfolio_manager:
        try:
            await _portfolio_manager.monitor_positions()
        except Exception as e:
            print(f"[Scheduler] Monitor error: {e}")


async def _daily_scan_job():
    if not _cio:
        return
    from data.market import fetch_indicators
    from utils.db import get_watchlist, update_watchlist_signal

    watchlist = get_watchlist()
    for item in watchlist:
        ticker = item["ticker"]
        try:
            ind = await fetch_indicators(ticker)
            rsi = ind.get("rsi", 50)
            vol_ratio = ind.get("volume_ratio", 1.0)
            ema_cross = ind.get("ema_crossover", "NONE")

            should_run = (
                rsi < 30 or rsi > 70
                or vol_ratio > 2.0
                or ema_cross in ("GOLDEN_CROSS", "DEATH_CROSS")
            )

            if should_run:
                if _broadcast:
                    await _broadcast({
                        "type": "watchlist_trigger",
                        "ticker": ticker,
                        "reason": f"RSI={rsi:.1f} Vol={vol_ratio:.1f}x EMA={ema_cross}",
                        "message": f"Signal triggered — auto-analyzing {ticker}",
                    })
                result = await _cio.run_pipeline(ticker)
                if result.get("verdict") == "INVEST":
                    from core.portfolio import PortfolioManager
                    pm = PortfolioManager(_broadcast)
                    await pm.execute_buy(ticker, result)
                update_watchlist_signal(ticker, result.get("verdict", "WAIT"))
            else:
                update_watchlist_signal(ticker, f"NEUTRAL_RSI{rsi:.0f}")
        except Exception as e:
            print(f"[Scheduler] Scan error {ticker}: {e}")


async def _monthly_report_job():
    from core.reporter import generate_monthly_report
    try:
        await generate_monthly_report(_broadcast)
    except Exception as e:
        print(f"[Scheduler] Monthly report error: {e}")


def get_scheduler() -> Optional[AsyncIOScheduler]:
    return _scheduler
