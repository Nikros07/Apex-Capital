import asyncio
from datetime import datetime
from typing import Callable, Optional

from data.market import fetch_current_price
from utils.db import (
    get_portfolio, get_recent_trades, insert_trade, update_portfolio,
)


class PortfolioManager:
    INITIAL_VALUE = 10_000.0

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
            return {"success": False, "reason": f"Verdict is {analysis_result.get('verdict')}, not INVEST"}

        reports = analysis_result.get("reports", {})
        committee = reports.get("committee", {})
        risk = reports.get("risk", {})

        position_size_eur = float(committee.get("position_size_eur") or risk.get("position_size_eur") or 0)
        current_price = float(analysis_result.get("current_price") or 0)
        stop_loss = float(committee.get("stop_loss") or risk.get("stop_loss") or 0)
        take_profit = float(committee.get("take_profit") or risk.get("take_profit") or 0)
        rr_ratio = float(risk.get("rr_ratio") or 0)
        conviction = int(float(committee.get("conviction") or 5))

        if current_price <= 0 or position_size_eur <= 0:
            return {"success": False, "reason": "Invalid price or position size"}

        portfolio = get_portfolio()
        cash_eur = float(portfolio.get("cash_eur", 0))
        positions = dict(portfolio.get("positions", {}))

        if ticker in positions:
            return {"success": False, "reason": f"Already holding {ticker}"}

        if position_size_eur > cash_eur:
            position_size_eur = cash_eur * 0.95

        shares = position_size_eur / current_price

        new_cash = cash_eur - position_size_eur
        positions[ticker] = {
            "shares": round(shares, 6),
            "entry_price": current_price,
            "current_price": current_price,
            "stop_loss": stop_loss,
            "take_profit": take_profit,
            "position_value": round(position_size_eur, 2),
            "pnl_eur": 0.0,
            "pnl_pct": 0.0,
            "entry_time": datetime.utcnow().isoformat(),
        }

        total_value, peak, max_dd = self._recalc(new_cash, positions, portfolio)
        total_pnl = total_value - self.INITIAL_VALUE
        total_pnl_pct = total_pnl / self.INITIAL_VALUE * 100

        update_portfolio(new_cash, positions, total_value, total_pnl, total_pnl_pct, peak, max_dd)

        insert_trade({
            "timestamp": datetime.utcnow().isoformat(),
            "ticker": ticker, "action": "BUY",
            "shares": round(shares, 6), "price_eur": current_price,
            "total_eur": round(position_size_eur, 2),
            "stop_loss": stop_loss, "take_profit": take_profit,
            "rr_ratio": rr_ratio, "conviction": conviction,
            "close_reason": None, "pnl_eur": 0.0,
            "all_agent_signals": reports,
        })

        await self._broadcast("trade_executed", {
            "action": "BUY", "ticker": ticker,
            "shares": round(shares, 4), "price": current_price,
            "total": round(position_size_eur, 2),
            "stop_loss": stop_loss, "take_profit": take_profit,
            "message": f"BUY {shares:.4f} {ticker} @ {current_price:.4f} EUR",
        })
        return {"success": True, "ticker": ticker, "shares": shares,
                "price": current_price, "total": position_size_eur}

    # ─── SELL ────────────────────────────────────────────────────────────────

    async def execute_sell(self, ticker: str, current_price: float,
                           reason: str = "MANUAL") -> dict:
        portfolio = get_portfolio()
        positions = dict(portfolio.get("positions", {}))

        if ticker not in positions:
            return {"success": False, "reason": f"{ticker} not in portfolio"}

        pos = positions[ticker]
        shares = float(pos["shares"])
        entry_price = float(pos["entry_price"])

        sale_value = shares * current_price
        pnl_eur = (current_price - entry_price) * shares
        pnl_pct = (current_price - entry_price) / entry_price * 100 if entry_price > 0 else 0.0

        new_cash = float(portfolio.get("cash_eur", 0)) + sale_value
        del positions[ticker]

        total_value, peak, max_dd = self._recalc(new_cash, positions, portfolio)
        total_pnl = total_value - self.INITIAL_VALUE
        total_pnl_pct = total_pnl / self.INITIAL_VALUE * 100

        update_portfolio(new_cash, positions, total_value, total_pnl, total_pnl_pct, peak, max_dd)

        insert_trade({
            "timestamp": datetime.utcnow().isoformat(),
            "ticker": ticker, "action": "SELL",
            "shares": shares, "price_eur": current_price,
            "total_eur": round(sale_value, 2),
            "stop_loss": pos.get("stop_loss"), "take_profit": pos.get("take_profit"),
            "rr_ratio": 0, "conviction": 0,
            "close_reason": reason, "pnl_eur": round(pnl_eur, 2),
            "all_agent_signals": {},
        })

        await self._broadcast("trade_executed", {
            "action": "SELL", "ticker": ticker,
            "shares": shares, "price": current_price,
            "total": round(sale_value, 2),
            "pnl_eur": round(pnl_eur, 2), "pnl_pct": round(pnl_pct, 2),
            "reason": reason,
            "message": f"SELL {shares:.4f} {ticker} @ {current_price:.4f} EUR  PnL: {pnl_eur:+.2f} EUR",
        })
        return {"success": True, "ticker": ticker,
                "pnl_eur": round(pnl_eur, 2), "reason": reason}

    # ─── MONITOR ─────────────────────────────────────────────────────────────

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

                pos = positions[ticker]
                sl = float(pos.get("stop_loss") or 0)
                tp = float(pos.get("take_profit") or 0)

                if sl and price <= sl:
                    await self.execute_sell(ticker, price, "STOP_LOSS")
                elif tp and price >= tp:
                    await self.execute_sell(ticker, price, "TAKE_PROFIT")
                else:
                    # Update position P&L in-place
                    portfolio = get_portfolio()
                    positions2 = dict(portfolio.get("positions", {}))
                    if ticker in positions2:
                        entry = float(positions2[ticker]["entry_price"])
                        sh = float(positions2[ticker]["shares"])
                        positions2[ticker]["current_price"] = price
                        positions2[ticker]["pnl_eur"] = round((price - entry) * sh, 2)
                        positions2[ticker]["pnl_pct"] = round((price - entry) / entry * 100, 2)
                        positions2[ticker]["position_value"] = round(price * sh, 2)

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
                print(f"Monitor error {ticker}: {e}")

        await self._broadcast("portfolio_update", {"portfolio": get_portfolio()})

    # ─── HELPERS ─────────────────────────────────────────────────────────────

    def _recalc(self, cash: float, positions: dict, portfolio: dict):
        pos_value = sum(
            float(p.get("shares", 0)) * float(p.get("current_price", p.get("entry_price", 0)))
            for p in positions.values()
        )
        total_value = cash + pos_value
        peak = max(float(portfolio.get("peak_value", self.INITIAL_VALUE)), total_value)
        max_dd = (peak - total_value) / peak * 100 if peak > 0 else 0
        return total_value, peak, max_dd

    def get_state(self) -> dict:
        return get_portfolio()
