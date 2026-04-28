import json
from typing import Callable, Optional

from agents.base import BaseAgent
from utils.db import get_portfolio, get_trades_this_month

PERSONALITY = (
    "You are Viktor, risk manager at Apex Capital. You are stern and you have seen every "
    "crash since 1987. You always say no first, then maybe. You hate losses more than you "
    "love gains. You triple-check every number. You end every assessment with your motto: "
    "'Capital preservation is not a strategy — it is a religion.'"
)


class ViktorAgent(BaseAgent):
    def __init__(self, broadcast: Optional[Callable] = None):
        super().__init__("Viktor", PERSONALITY, broadcast)

    async def assess(self, ticker: str, all_reports: dict,
                     current_price: float, atr: float) -> dict:
        await self._broadcast("agent_status", {
            "status": "working",
            "ticker": ticker,
            "message": f"Running risk assessment for {ticker}...",
        })

        portfolio = get_portfolio()
        trades_this_month = get_trades_this_month()

        portfolio_value = portfolio.get("total_value", 10000)
        positions = portfolio.get("positions", {})
        monthly_start = portfolio.get("monthly_start_value", 10000)
        cash_eur = portfolio.get("cash_eur", 10000)

        monthly_drawdown = max(0, (monthly_start - portfolio_value) / monthly_start * 100
                               if monthly_start > 0 else 0)

        recent = sorted(trades_this_month, key=lambda x: x.get("timestamp", ""), reverse=True)[:10]
        consecutive_losses = 0
        for t in recent:
            if t.get("pnl_eur", 0) < 0:
                consecutive_losses += 1
            else:
                break

        already_positioned = ticker in positions

        stop_distance = max(1.5 * atr, current_price * 0.03) if atr > 0 else current_price * 0.05
        risk_amount = portfolio_value * 0.01
        shares = risk_amount / stop_distance if stop_distance > 0 else 0
        position_size_eur = shares * current_price

        size_multiplier = 1.0
        if monthly_drawdown > 5:
            size_multiplier *= 0.5
        if consecutive_losses >= 3:
            size_multiplier *= 0.5

        meme_risk = all_reports.get("sentiment", {}).get("meme_risk", False)
        contrarian_flag = all_reports.get("sentiment", {}).get("contrarian_flag", False)
        if meme_risk:
            size_multiplier *= 0.6
        if contrarian_flag:
            size_multiplier *= 0.85

        position_size_eur *= size_multiplier
        if position_size_eur > cash_eur:
            position_size_eur = cash_eur * 0.95
        shares_adj = position_size_eur / current_price if current_price > 0 else 0

        stop_loss = current_price - stop_distance
        take_profit = current_price + (2.5 * atr) if atr > 0 else current_price * 1.1
        rr_ratio = (
            (take_profit - current_price) / (current_price - stop_loss)
            if (current_price - stop_loss) > 0 else 0
        )

        context = {
            "ticker": ticker,
            "current_price": current_price,
            "portfolio_value": portfolio_value,
            "available_cash": cash_eur,
            "position_size_eur": round(position_size_eur, 2),
            "shares": round(shares_adj, 4),
            "stop_loss": round(stop_loss, 4),
            "take_profit": round(take_profit, 4),
            "rr_ratio": round(rr_ratio, 2),
            "atr": round(atr, 4),
            "monthly_drawdown_pct": round(monthly_drawdown, 2),
            "consecutive_losses": consecutive_losses,
            "already_positioned": already_positioned,
            "meme_risk": meme_risk,
            "contrarian_flag": contrarian_flag,
            "size_multiplier": round(size_multiplier, 2),
        }

        system_prompt = (
            "Review risk metrics and provide assessment. Output ONLY valid JSON:\n"
            '{"risk_verdict":"ACCEPTABLE|ELEVATED|CRITICAL",'
            '"risk_notes":["3-5 specific risk observations"],'
            '"position_approved":true,'
            '"risk_summary":"2-3 sentence assessment ending with your motto"}'
        )

        user_msg = (
            f"Risk Assessment for {ticker}:\n{json.dumps(context, indent=2)}\n\n"
            f"Technical: {all_reports.get('technical',{}).get('signal','UNKNOWN')}\n"
            f"Fundamental: {all_reports.get('fundamental',{}).get('signal','UNKNOWN')}\n"
            f"Crowd: {all_reports.get('sentiment',{}).get('crowd_sentiment','UNKNOWN')}\n\n"
            "Is this trade acceptable?"
        )

        response = await self.call_llm(system_prompt, user_msg)
        llm_default = {
            "risk_verdict": "ELEVATED",
            "risk_notes": ["Proceed with standard caution"],
            "position_approved": True,
            "risk_summary": "Capital preservation is not a strategy — it is a religion.",
        }
        llm = self._parse_json(response, llm_default)

        if already_positioned:
            llm["risk_verdict"] = "CRITICAL"
            notes = llm.get("risk_notes", [])
            notes.append(f"ALREADY_POSITIONED: {ticker} is in current portfolio")
            llm["risk_notes"] = notes

        result = {
            "ticker": ticker,
            "position_size_eur": round(position_size_eur, 2),
            "shares": round(shares_adj, 4),
            "stop_loss": round(stop_loss, 4),
            "take_profit": round(take_profit, 4),
            "rr_ratio": round(rr_ratio, 2),
            "risk_verdict": llm.get("risk_verdict", "ELEVATED"),
            "risk_notes": llm.get("risk_notes", []),
            "risk_summary": llm.get("risk_summary", ""),
            "monthly_drawdown": round(monthly_drawdown, 2),
            "size_multiplier": round(size_multiplier, 2),
            "consecutive_losses": consecutive_losses,
        }

        await self._broadcast("agent_done", {
            "status": "done",
            "ticker": ticker,
            "risk_verdict": result["risk_verdict"],
            "report": result,
        })
        return result
