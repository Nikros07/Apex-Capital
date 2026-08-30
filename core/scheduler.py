from __future__ import annotations

import asyncio
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

    # ── Position monitoring — split by market state to cut wasted compute ────
    # Every position here is a US-listed ticker (NYSE/NASDAQ) — the regular
    # session runs ~15:30-22:00 CET. Polling every minute outside that window
    # burns CPU/RAM for prices that cannot move (market's shut), which is
    # exactly what was driving Railway usage up. Two tiers:
    #   - 15:00-21:59 CET: every 1 min — real trading hours, live feel intact
    #   - 08:00-14:59 & 22:00-22:59 CET: every 15 min — pre-market/after-hours
    #     safety net only, at 1/15th the call volume
    # Nothing at all outside 08:00-23:00 or on weekends (day_of_week already
    # excludes Sat/Sun on every job in this file).
    _scheduler.add_job(
        _monitor_job,
        CronTrigger(minute="*", hour="15-21", day_of_week="mon-fri"),
        id="position_monitor_active", replace_existing=True, misfire_grace_time=30,
    )
    _scheduler.add_job(
        _monitor_job,
        CronTrigger(minute="*/15", hour="8-14,22", day_of_week="mon-fri"),
        id="position_monitor_offhours", replace_existing=True, misfire_grace_time=60,
    )

    # ── Morning position briefing: 08:01 CET ──────────────────────────────────
    _scheduler.add_job(
        _morning_briefing_job,
        CronTrigger(hour=8, minute=1, day_of_week="mon-fri"),
        id="morning_briefing", replace_existing=True, misfire_grace_time=300,
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
        "1-min monitor during US hours (15-22 CET) / 15-min off-hours, "
        "08:01 morning briefing, 21:30 daily-min-trade enforcer."
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
                              vol_threshold: float = 1.2) -> dict:
    """
    Scan all watchlist tickers for signals; run full pipeline on hits.
    Returns summary dict. Called by scheduler jobs and /api/scan endpoint.
    Guarantees at least 1 trade per call via run_forced_trade fallback.
    """
    if not cio:
        return {"error": "CIO not initialised"}

    from data.market import fetch_indicators
    from utils.db import get_watchlist, update_watchlist_signal

    watchlist = get_watchlist()
    triggered = []
    skipped = []
    traded = []

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

            # Relaxed thresholds — cast wider net
            should_run = (
                rsi < 40 or rsi > 60
                or vol_ratio > vol_threshold
                or ema_cross in ("GOLDEN_CROSS", "DEATH_CROSS")
                or abs(macd_diff) > 0.3
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
                            trade = await portfolio_manager.execute_buy(ticker, result)
                            if trade.get("success"):
                                traded.append(ticker)
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
        "traded": traded,
        "skipped": len(skipped),
    }
    if broadcast_fn:
        await broadcast_fn({
            "type": "watchlist_trigger",
            "ticker": "ALL",
            "message": f"Scan complete — {len(triggered)}/{len(watchlist)} triggered, {len(traded)} trade(s)",
            "reason": f"Triggered: {', '.join(triggered) or 'none'}",
        })

    # Guarantee at least 1 trade per scan — if nothing traded, force top scorer
    if not traded:
        if broadcast_fn:
            await broadcast_fn({
                "type": "watchlist_trigger",
                "ticker": "SYSTEM",
                "message": "No trades from signal scan — running forced analysis on top scorer...",
                "reason": "",
            })
        forced = await run_forced_trade(cio, portfolio_manager, broadcast_fn)
        summary["forced_trade"] = forced

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

    # Guarantee at least 1 trade — if top 10 all came back WAIT/PASS, force the best
    if not traded:
        if broadcast_fn:
            await broadcast_fn({
                "type": "watchlist_trigger",
                "ticker": "SYSTEM",
                "message": "Deep scan: no INVEST verdict in top 10 — forcing best opportunity...",
                "reason": "",
            })
        forced = await run_forced_trade(cio, portfolio_manager, broadcast_fn)
        return {"scanned": len(watchlist), "analyzed": len(top_10), "traded": traded,
                "forced_trade": forced}

    return {"scanned": len(watchlist), "analyzed": len(top_10), "traded": traded}


async def run_forced_trade(cio, portfolio_manager, broadcast_fn) -> dict:
    """
    Two-stage forced trade:
      Stage 1 — try full LLM pipeline on top 5 scored tickers, buy first INVEST.
      Stage 2 — if LLM produces no INVEST (bad day, no key, etc.), bypass the LLM
                 entirely and directly BUY the highest-scored ticker that passes
                 basic risk checks (not held, not at max positions, enough cash).
    Guaranteed to execute a trade as long as there is any cash and a free slot.
    """
    if not portfolio_manager:
        return {"error": "Portfolio manager not initialised"}

    from data.market import fetch_indicators, fetch_current_price, fetch_ohlcv, compute_indicators
    from utils.db import get_watchlist, get_portfolio, update_watchlist_signal

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
    top_5 = scores[:5]

    # ── Stage 1: Try full LLM pipeline ──────────────────────────────────────
    if cio:
        for ticker, score in top_5:
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
                    if risk_verdict != "CRITICAL":
                        trade = await portfolio_manager.execute_buy(ticker, result)
                        if trade.get("success"):
                            if broadcast_fn:
                                await broadcast_fn({
                                    "type": "watchlist_trigger",
                                    "ticker": ticker,
                                    "message": f"Daily min-trade fulfilled: BUY {ticker}",
                                    "reason": f"LLM pipeline, score={score:.0f}",
                                })
                            return {"success": True, "ticker": ticker, "stage": "llm"}
            except Exception as e:
                print(f"[Scheduler] Forced trade stage-1 error {ticker}: {e}")

    # ── Stage 2: Hard bypass — buy top-scored ticker directly without LLM ───
    # Runs when LLM is unavailable, slow, or consistently returning WAIT/PASS.
    if broadcast_fn:
        await broadcast_fn({
            "type": "watchlist_trigger",
            "ticker": "SYSTEM",
            "message": "Stage-1 produced no trade — executing hard-forced buy on top scorer...",
            "reason": "",
        })

    for ticker, score in scores[:10]:  # try top 10 in case some are already held
        try:
            portfolio = get_portfolio()
            positions = dict(portfolio.get("positions", {}))
            total_value = float(portfolio.get("total_value", 10000))

            # Skip if already held or portfolio full
            if ticker in positions:
                continue
            if len(positions) >= 15:
                if broadcast_fn:
                    await broadcast_fn({
                        "type": "watchlist_trigger",
                        "ticker": "SYSTEM",
                        "message": "Hard-forced buy skipped: max positions (15) reached.",
                        "reason": "",
                    })
                break

            price = await fetch_current_price(ticker)
            if price <= 0:
                continue

            # Calculate position size using ATR (Viktor's formula, no LLM).
            # Cash-reserve checking (including freeing capital from the
            # weakest position if needed) is handled inside execute_buy() —
            # no need to pre-check/cap against `available` here.
            df = await fetch_ohlcv(ticker, period="1mo")
            ind = compute_indicators(df) if (df is not None and not df.empty) else {}
            atr = ind.get("atr") or price * 0.02
            stop_distance = max(1.5 * atr, price * 0.03)
            raw_size = (total_value * 0.01) / stop_distance * price  # 1% risk
            position_size_eur = min(raw_size, total_value * 0.08)

            if position_size_eur < 5:
                continue

            fake_result = {
                "verdict": "INVEST",
                "current_price": price,
                "reports": {
                    "committee": {
                        "position_size_eur": round(position_size_eur, 2),
                        "conviction": 6,
                    },
                    "risk": {
                        "position_size_eur": round(position_size_eur, 2),
                        "stop_loss": round(price - stop_distance, 4),
                        "take_profit": round(price + 2.5 * atr, 4),
                        "rr_ratio": round(2.5 * atr / stop_distance, 2),
                        "atr": round(atr, 4),
                        "risk_verdict": "ACCEPTABLE",
                    },
                },
            }
            trade = await portfolio_manager.execute_buy(ticker, fake_result)
            if trade.get("success"):
                update_watchlist_signal(ticker, "FORCED_BUY")
                if broadcast_fn:
                    await broadcast_fn({
                        "type": "watchlist_trigger",
                        "ticker": ticker,
                        "message": (
                            f"Hard-forced BUY {ticker} @ {price:.2f} "
                            f"(size={position_size_eur:.0f} EUR, score={score:.0f})"
                        ),
                        "reason": "Stage-2 bypass — no LLM INVEST verdict",
                    })
                return {"success": True, "ticker": ticker, "stage": "hard_bypass"}
        except Exception as e:
            print(f"[Scheduler] Forced trade stage-2 error {ticker}: {e}")

    if broadcast_fn:
        await broadcast_fn({
            "type": "watchlist_trigger",
            "ticker": "SYSTEM",
            "message": "Forced trade failed: no eligible tickers (max positions or no cash).",
            "reason": "",
        })
    return {"success": False, "reason": "No eligible tickers or insufficient cash"}


async def _morning_briefing_job():
    """
    08:01 CET — broadcast a morning briefing with all open positions,
    overnight P&L, key levels, and today's plan.
    """
    try:
        from utils.db import get_portfolio
        portfolio = get_portfolio()
        positions = portfolio.get("positions", {})
        cash = float(portfolio.get("cash_eur", 0))
        total = float(portfolio.get("total_value", 10000))
        pnl = float(portfolio.get("total_pnl_eur", 0))
        pnl_pct = float(portfolio.get("total_pnl_pct", 0))

        lines = [
            "🌅 MORNING BRIEFING — Apex Capital Management",
            f"Portfolio: €{total:,.2f}  |  Cash: €{cash:,.2f}  |  PnL: {pnl:+.2f} EUR ({pnl_pct:+.2f}%)",
            f"Open positions: {len(positions)}",
        ]

        for ticker, pos in positions.items():
            entry = float(pos.get("entry_price", 0))
            cur   = float(pos.get("current_price", entry))
            sl    = float(pos.get("trailing_stop") or pos.get("stop_loss") or 0)
            tp    = float(pos.get("take_profit") or 0)
            pnl_p = float(pos.get("pnl_pct", 0))
            lines.append(
                f"  • {ticker}: entry={entry:.2f}  now={cur:.2f}  "
                f"trail_SL={sl:.2f}  TP={tp:.2f}  PnL={pnl_p:+.2f}%"
            )

        if not positions:
            lines.append("  — No open positions. Full scan launching at 08:00 EU open.")

        message = "\n".join(lines)

        if _broadcast:
            await _broadcast({
                "type": "morning_briefing",
                "message": message,
                "portfolio": portfolio,
            })
        print(f"[Scheduler] {message}")
    except Exception as e:
        print(f"[Scheduler] Morning briefing error: {e}")


async def _monthly_report_job():
    from core.reporter import generate_monthly_report
    try:
        await generate_monthly_report(_broadcast)
    except Exception as e:
        print(f"[Scheduler] Monthly report error: {e}")


def get_scheduler() -> Optional[AsyncIOScheduler]:
    return _scheduler
