import json
from datetime import datetime
from typing import Callable, Optional

from agents.base import BaseAgent
from utils.db import (
    get_portfolio, get_trades_this_month, get_conn, save_monthly_report,
)

MARCUS_PERSONALITY = (
    "You are Marcus, Chief Investment Officer of Apex Capital. You speak like Ray Dalio — "
    "calm, systemic, unemotional. You think in probabilities and second-order effects. "
    "You end every statement with a one-line investment principle."
)


async def generate_monthly_report(broadcast: Optional[Callable] = None) -> dict:
    now = datetime.utcnow()
    month = now.strftime("%Y-%m")

    portfolio = get_portfolio()
    trades = get_trades_this_month()

    portfolio_value = float(portfolio.get("total_value", 10000))
    monthly_start = float(portfolio.get("monthly_start_value", 10000))
    total_pnl = float(portfolio.get("total_pnl_eur", 0))
    total_pnl_pct = float(portfolio.get("total_pnl_pct", 0))
    max_drawdown = float(portfolio.get("max_drawdown_pct", 0))

    sell_trades = [t for t in trades if t.get("action") == "SELL"]
    wins = [t for t in sell_trades if float(t.get("pnl_eur") or 0) > 0]
    losses = [t for t in sell_trades if float(t.get("pnl_eur") or 0) <= 0]
    win_rate = len(wins) / len(sell_trades) * 100 if sell_trades else 0

    best = max(sell_trades, key=lambda x: float(x.get("pnl_eur") or 0), default=None)
    worst = min(sell_trades, key=lambda x: float(x.get("pnl_eur") or 0), default=None)

    report_data = {
        "month": month,
        "portfolio_start_eur": monthly_start,
        "portfolio_end_eur": portfolio_value,
        "total_pnl_eur": round(total_pnl, 2),
        "total_pnl_pct": round(total_pnl_pct, 2),
        "monthly_pnl_eur": round(portfolio_value - monthly_start, 2),
        "monthly_pnl_pct": round(
            (portfolio_value - monthly_start) / monthly_start * 100
            if monthly_start > 0 else 0, 2
        ),
        "max_drawdown_pct": round(max_drawdown, 2),
        "total_trades": len(trades),
        "winning_trades": len(wins),
        "losing_trades": len(losses),
        "win_rate_pct": round(win_rate, 1),
        "best_trade": {
            "ticker": best["ticker"],
            "pnl_eur": round(float(best.get("pnl_eur") or 0), 2),
        } if best else None,
        "worst_trade": {
            "ticker": worst["ticker"],
            "pnl_eur": round(float(worst.get("pnl_eur") or 0), 2),
        } if worst else None,
        "agent_scorecard": _agent_scorecard(sell_trades),
        "dante_scorecard": _dante_scorecard(sell_trades),
    }

    marcus = BaseAgent("MarcusReporter", MARCUS_PERSONALITY)
    system_prompt = (
        "Write a 1-page monthly investment narrative (300-400 words) covering: "
        "1) What worked and why. 2) What didn't work and lessons learned. "
        "3) How macro conditions affected performance. 4) Strategic adjustments for next month. "
        "5) One key principle for the team. Write as Marcus in Dalio's style."
    )
    narrative = await marcus.call_llm(
        system_prompt,
        f"Monthly Data:\n{json.dumps(report_data, indent=2)}\n\nWrite the narrative."
    )

    save_monthly_report(month, report_data, narrative)

    # Reset monthly_start_value
    with get_conn() as conn:
        conn.execute("UPDATE portfolio SET monthly_start_value=? WHERE id=1", (portfolio_value,))

    if broadcast:
        try:
            await broadcast({
                "type": "monthly_report_ready",
                "month": month,
                "report": report_data,
                "message": f"Monthly report for {month} generated",
            })
        except Exception:
            pass

    return {"report": report_data, "narrative": narrative}


def _agent_scorecard(sell_trades: list) -> dict:
    agents = {k: {"signals": 0, "wins": 0, "win_rate": 0}
              for k in ("Kai", "Sophie", "Alex", "Jordan")}
    keys = {"Kai": "technical", "Sophie": "fundamental",
            "Alex": "research", "Jordan": "sentiment"}

    for trade in sell_trades:
        try:
            signals = json.loads(trade.get("all_agent_signals") or "{}")
            pnl = float(trade.get("pnl_eur") or 0)
            for name, key in keys.items():
                if key in signals:
                    agents[name]["signals"] += 1
                    if pnl > 0:
                        agents[name]["wins"] += 1
        except Exception:
            pass

    for a in agents.values():
        if a["signals"] > 0:
            a["win_rate"] = round(a["wins"] / a["signals"] * 100, 1)
    return agents


def _dante_scorecard(sell_trades: list) -> dict:
    total = correct = 0
    for trade in sell_trades:
        try:
            signals = json.loads(trade.get("all_agent_signals") or "{}")
            if signals.get("dante"):
                total += 1
                if float(trade.get("pnl_eur") or 0) < 0:
                    correct += 1
        except Exception:
            pass
    return {
        "warnings_issued": total,
        "warnings_correct": correct,
        "accuracy_pct": round(correct / total * 100, 1) if total > 0 else 0,
    }
