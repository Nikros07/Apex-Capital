import asyncio
from datetime import datetime
from typing import Callable, Optional

from data.market import fetch_current_price
from utils.db import get_portfolio, insert_trade, update_portfolio


def _safe_conviction(value, default: int = 5) -> int:
    """Coerce an LLM-supplied conviction value to a safe int, never raising."""
    try:
        return int(float(value or default))
    except (TypeError, ValueError):
        return default


class PortfolioManager:
    INITIAL_VALUE    = 10_000.0
    MAX_POSITIONS    = 15          # up to 15 open positions simultaneously
    MIN_CASH_RESERVE = 0.07        # always keep 7% cash (lowered to fit 15 slots)

    def __init__(self, broadcast: Optional[Callable] = None):
        self._broadcast_fn = broadcast

    async def _broadcast(self, event_type: str, data: dict):
        if not self._broadcast_fn:
            return
        msg = {"type": event_type, **data}
        try:
            if asyncio.iscoroutinefunction(self._broadcast_fn):
                await self._broadcast_fn(msg)
            else:
                self._broadcast_fn(msg)
        except Exception:
            pass

    # ─── BUY ─────────────────────────────────────────────────────────────────

    async def execute_buy(self, ticker: str, analysis_result: dict) -> dict:
        if analysis_result.get("verdict") != "INVEST":
            return {"success": False, "reason": f"Verdict is {analysis_result.get('verdict')}"}

        reports       = analysis_result.get("reports", {})
        committee     = reports.get("committee", {})
        risk          = reports.get("risk", {})

        position_size_eur = float(committee.get("position_size_eur") or risk.get("position_size_eur") or 0)
        current_price     = float(analysis_result.get("current_price") or 0)
        stop_loss         = float(committee.get("stop_loss") or risk.get("stop_loss") or 0)
        take_profit       = float(committee.get("take_profit") or risk.get("take_profit") or 0)
        rr_ratio          = float(risk.get("rr_ratio") or 0)
        conviction        = _safe_conviction(committee.get("conviction"))
        atr               = float(risk.get("atr") or current_price * 0.02)

        if current_price <= 0 or position_size_eur <= 0:
            return {"success": False, "reason": "Invalid price or position size"}

        # ── Dynamic sizing by conviction ──────────────────────────────────────
        conv_mult = 1.25 if conviction >= 8 else (1.0 if conviction >= 6 else 0.80)
        position_size_eur *= conv_mult

        portfolio   = get_portfolio()
        cash_eur    = float(portfolio.get("cash_eur", 0))
        total_value = float(portfolio.get("total_value", self.INITIAL_VALUE))
        positions   = dict(portfolio.get("positions", {}))

        if ticker in positions:
            return {"success": False, "reason": f"Already holding {ticker}"}

        if len(positions) >= self.MAX_POSITIONS:
            return {"success": False, "reason": f"Max {self.MAX_POSITIONS} positions reached"}

        min_cash      = total_value * self.MIN_CASH_RESERVE
        available     = cash_eur - min_cash
        if available < 10:
            return {"success": False, "reason": "Cash below minimum reserve"}

        if position_size_eur > available:
            position_size_eur = available * 0.95

        shares         = position_size_eur / current_price
        trail_distance = max(1.5 * atr, current_price * 0.015)
        trailing_stop  = round(current_price - trail_distance, 4)

        new_cash = cash_eur - position_size_eur
        positions[ticker] = {
            "shares":          round(shares, 6),
            "entry_price":     current_price,
            "current_price":   current_price,
            "stop_loss":       stop_loss,
            "take_profit":     take_profit,
            "trailing_stop":   trailing_stop,
            "atr":             round(atr, 4),
            "position_value":  round(position_size_eur, 2),
            "pnl_eur":         0.0,
            "pnl_pct":         0.0,
            "partial_tp_done": False,
            "entry_time":      datetime.utcnow().isoformat(),
            "entry_signals":   reports,
        }

        total_value, peak, max_dd = self._recalc(new_cash, positions, portfolio)
        total_pnl     = total_value - self.INITIAL_VALUE
        total_pnl_pct = total_pnl / self.INITIAL_VALUE * 100
        update_portfolio(new_cash, positions, total_value, total_pnl, total_pnl_pct, peak, max_dd)

        insert_trade({
            "timestamp":        datetime.utcnow().isoformat(),
            "ticker":           ticker, "action": "BUY",
            "shares":           round(shares, 6), "price_eur": current_price,
            "total_eur":        round(position_size_eur, 2),
            "stop_loss":        stop_loss, "take_profit": take_profit,
            "rr_ratio":         rr_ratio, "conviction": conviction,
            "close_reason":     None, "pnl_eur": 0.0,
            "all_agent_signals": reports,
        })

        await self._broadcast("trade_executed", {
            "action": "BUY", "ticker": ticker,
            "shares": round(shares, 4), "price": current_price,
            "total": round(position_size_eur, 2),
            "stop_loss": stop_loss, "take_profit": take_profit,
            "trailing_stop": trailing_stop,
            "message": f"BUY {shares:.4f} {ticker} @ {current_price:.4f}  trail_SL={trailing_stop:.4f}",
        })
        return {"success": True, "ticker": ticker, "shares": shares,
                "price": current_price, "total": position_size_eur}

    # ─── SELL ────────────────────────────────────────────────────────────────

    async def execute_sell(self, ticker: str, current_price: float,
                           reason: str = "MANUAL") -> dict:
        portfolio  = get_portfolio()
        positions  = dict(portfolio.get("positions", {}))

        if ticker not in positions:
            return {"success": False, "reason": f"{ticker} not in portfolio"}

        pos        = positions[ticker]
        shares     = float(pos["shares"])
        entry_price = float(pos["entry_price"])
        entry_signals = pos.get("entry_signals", {})

        sale_value = shares * current_price
        pnl_eur    = (current_price - entry_price) * shares
        pnl_pct    = (current_price - entry_price) / entry_price * 100 if entry_price > 0 else 0.0

        new_cash = float(portfolio.get("cash_eur", 0)) + sale_value
        del positions[ticker]

        total_value, peak, max_dd = self._recalc(new_cash, positions, portfolio)
        total_pnl     = total_value - self.INITIAL_VALUE
        total_pnl_pct = total_pnl / self.INITIAL_VALUE * 100
        update_portfolio(new_cash, positions, total_value, total_pnl, total_pnl_pct, peak, max_dd)

        insert_trade({
            "timestamp":        datetime.utcnow().isoformat(),
            "ticker":           ticker, "action": "SELL",
            "shares":           shares, "price_eur": current_price,
            "total_eur":        round(sale_value, 2),
            "stop_loss":        pos.get("stop_loss"), "take_profit": pos.get("take_profit"),
            "rr_ratio":         0, "conviction": 0,
            "close_reason":     reason, "pnl_eur": round(pnl_eur, 2),
            "all_agent_signals": entry_signals,
        })

        await self._broadcast("trade_executed", {
            "action": "SELL", "ticker": ticker,
            "shares": shares, "price": current_price,
            "total": round(sale_value, 2),
            "pnl_eur": round(pnl_eur, 2), "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
            "message": f"SELL {shares:.4f} {ticker} @ {current_price:.4f}  PnL: {pnl_eur:+.2f} EUR  [{reason}]",
        })

        # Deploy freed capital immediately
        asyncio.create_task(_trigger_reinvest())

        return {"success": True, "ticker": ticker,
                "pnl_eur": round(pnl_eur, 2), "reason": reason}

    # ─── PARTIAL SELL ────────────────────────────────────────────────────────

    async def execute_partial_sell(self, ticker: str, price: float) -> dict:
        """
        Sell 60% at take-profit, keep 40% with stop-loss moved to breakeven.
        Locks in gains while letting the remainder run for free.
        """
        portfolio = get_portfolio()
        positions = dict(portfolio.get("positions", {}))

        if ticker not in positions:
            return {"success": False}

        pos           = positions[ticker]
        total_shares  = float(pos["shares"])
        shares_sell   = round(total_shares * 0.60, 6)
        shares_keep   = round(total_shares - shares_sell, 6)
        entry_signals = pos.get("entry_signals", {})

        if shares_keep <= 0:
            return await self.execute_sell(ticker, price, "TAKE_PROFIT")

        entry_price = float(pos["entry_price"])
        sale_value  = shares_sell * price
        pnl_eur     = (price - entry_price) * shares_sell
        pnl_pct     = (price - entry_price) / entry_price * 100 if entry_price > 0 else 0.0

        new_cash = float(portfolio.get("cash_eur", 0)) + sale_value

        # Remaining position: SL → breakeven, new TP further up
        atr    = float(pos.get("atr") or price * 0.02)
        new_tp = round(price + 2.0 * atr, 4)
        positions[ticker].update({
            "shares":          shares_keep,
            "partial_tp_done": True,
            "stop_loss":       entry_price,
            "trailing_stop":   entry_price,
            "take_profit":     new_tp,
            "position_value":  round(shares_keep * price, 2),
            "current_price":   price,
            "pnl_eur":         round((price - entry_price) * shares_keep, 2),
            "pnl_pct":         round(pnl_pct, 2),
        })

        total_value, peak, max_dd = self._recalc(new_cash, positions, portfolio)
        total_pnl     = total_value - self.INITIAL_VALUE
        total_pnl_pct = total_pnl / self.INITIAL_VALUE * 100
        update_portfolio(new_cash, positions, total_value, total_pnl, total_pnl_pct, peak, max_dd)

        insert_trade({
            "timestamp":        datetime.utcnow().isoformat(),
            "ticker":           ticker, "action": "PARTIAL_SELL",
            "shares":           shares_sell, "price_eur": price,
            "total_eur":        round(sale_value, 2),
            "stop_loss":        entry_price, "take_profit": new_tp,
            "rr_ratio":         0, "conviction": 0,
            "close_reason":     "PARTIAL_TAKE_PROFIT",
            "pnl_eur":          round(pnl_eur, 2),
            "all_agent_signals": entry_signals,
        })

        await self._broadcast("trade_executed", {
            "action": "PARTIAL_SELL", "ticker": ticker,
            "shares": shares_sell, "price": price,
            "total": round(sale_value, 2),
            "pnl_eur": round(pnl_eur, 2),
            "shares_remaining": shares_keep,
            "new_sl": entry_price, "new_tp": new_tp,
            "message": (
                f"PARTIAL SELL 60% {ticker} @ {price:.4f}  "
                f"PnL locked: {pnl_eur:+.2f} EUR  "
                f"Remaining {shares_keep:.4f} @ breakeven SL"
            ),
        })
        return {"success": True, "shares_sold": shares_sell, "shares_remaining": shares_keep}

    # ─── MONITOR (every 5 min) ────────────────────────────────────────────────

    async def monitor_positions(self):
        portfolio = get_portfolio()
        positions = dict(portfolio.get("positions", {}))
        if not positions:
            return

        for ticker in list(positions.keys()):
            try:
                price = await fetch_current_price(ticker)
                if price <= 0:
                    continue

                pos         = positions[ticker]
                entry_price = float(pos.get("entry_price", 0))
                atr         = float(pos.get("atr") or price * 0.02)
                tp          = float(pos.get("take_profit") or 0)
                partial_done = pos.get("partial_tp_done", False)

                # ── Update trailing stop (only moves UP) ──────────────────────
                trail_dist     = max(1.5 * atr, price * 0.015)
                new_trail      = price - trail_dist
                current_trail  = float(pos.get("trailing_stop") or pos.get("stop_loss") or 0)
                if new_trail > current_trail:
                    pos["trailing_stop"] = round(new_trail, 4)
                effective_sl = float(pos.get("trailing_stop") or pos.get("stop_loss") or 0)

                # ── Dead-money exit: >7 days, <1.5% gain ─────────────────────
                entry_time_str = pos.get("entry_time", "")
                if entry_time_str:
                    try:
                        days_held = (datetime.utcnow() - datetime.fromisoformat(entry_time_str)).days
                        pnl_pct   = (price - entry_price) / entry_price * 100 if entry_price > 0 else 0
                        if days_held >= 7 and pnl_pct < 1.5:
                            await self.execute_sell(ticker, price, "DEAD_MONEY_7D")
                            continue
                    except Exception:
                        pass

                # ── Trailing / hard stop-loss hit ─────────────────────────────
                if effective_sl and price <= effective_sl:
                    reason = "TRAILING_STOP" if pos.get("trailing_stop") else "STOP_LOSS"
                    await self.execute_sell(ticker, price, reason)
                    continue

                # ── Partial take-profit at TP ─────────────────────────────────
                if tp and price >= tp and not partial_done:
                    await self.execute_partial_sell(ticker, price)
                    continue

                # ── Normal P&L + trailing stop update ─────────────────────────
                portfolio  = get_portfolio()
                positions2 = dict(portfolio.get("positions", {}))
                if ticker in positions2:
                    entry = float(positions2[ticker]["entry_price"])
                    sh    = float(positions2[ticker]["shares"])
                    positions2[ticker].update({
                        "current_price":  price,
                        "pnl_eur":        round((price - entry) * sh, 2),
                        "pnl_pct":        round((price - entry) / entry * 100, 2),
                        "position_value": round(price * sh, 2),
                        "trailing_stop":  pos["trailing_stop"],
                    })
                    total_value, peak, max_dd = self._recalc(
                        float(portfolio.get("cash_eur", 0)), positions2, portfolio
                    )
                    update_portfolio(
                        float(portfolio.get("cash_eur", 0)), positions2, total_value,
                        total_value - self.INITIAL_VALUE,
                        (total_value - self.INITIAL_VALUE) / self.INITIAL_VALUE * 100,
                        peak, max_dd,
                    )

            except Exception as e:
                print(f"[Monitor] {ticker}: {e}")

        await self._broadcast("portfolio_update", {"portfolio": get_portfolio()})

    # ─── HELPERS ─────────────────────────────────────────────────────────────

    def _recalc(self, cash: float, positions: dict, portfolio: dict):
        pos_value = sum(
            float(p.get("shares", 0)) * float(p.get("current_price", p.get("entry_price", 0)))
            for p in positions.values()
        )
        total_value = cash + pos_value
        peak   = max(float(portfolio.get("peak_value", self.INITIAL_VALUE)), total_value)
        max_dd = (peak - total_value) / peak * 100 if peak > 0 else 0
        return total_value, peak, max_dd

    def get_state(self) -> dict:
        return get_portfolio()


# ─── Reinvest trigger (called after sells) ───────────────────────────────────

async def _trigger_reinvest():
    """Deploy freed capital: 5s grace period then run forced trade scan."""
    await asyncio.sleep(5)
    try:
        from core.scheduler import run_forced_trade, _cio, _portfolio_manager, _broadcast
        if _cio and _portfolio_manager:
            await run_forced_trade(_cio, _portfolio_manager, _broadcast)
    except Exception as e:
        print(f"[Reinvest] {e}")
