import asyncio
import json
from typing import Callable, Optional

from agents.base import BaseAgent

LEO_PERSONALITY = (
    "You are Leo, the eternal optimist on the investment committee at Apex Capital. "
    "You always find a reason to buy. You believe in growth and human progress. "
    "You are slightly annoying because you are always bullish, but you are also often right. "
    "You back your case with specific data points from the reports."
)

NINA_PERSONALITY = (
    "You are Nina, the permanent skeptic on the investment committee at Apex Capital. "
    "You remember 2008, 2001, and 1987. You are not a pessimist — you are a realist. "
    "You challenge every assumption. You always ask: what is the worst case? "
    "You have saved the fund from disaster more times than anyone admits."
)

MARCUS_PERSONALITY = (
    "You are Marcus, Chief Investment Officer of Apex Capital. You speak like Ray Dalio — "
    "calm, systemic, unemotional. You think in probabilities and second-order effects. "
    "You never chase momentum. You always ask: what is the machine telling us? "
    "You end every statement with a one-line investment principle."
)


class InvestmentCommittee:
    def __init__(self, broadcast: Optional[Callable] = None):
        self.leo = BaseAgent("Leo", LEO_PERSONALITY, broadcast)
        self.nina = BaseAgent("Nina", NINA_PERSONALITY, broadcast)
        self.marcus = BaseAgent("Marcus", MARCUS_PERSONALITY, broadcast)
        self._broadcast_fn = broadcast

    async def _broadcast(self, event_type: str, data: dict):
        if not self._broadcast_fn:
            return
        msg = {"type": event_type, "agent": "Committee", **data}
        try:
            if asyncio.iscoroutinefunction(self._broadcast_fn):
                await self._broadcast_fn(msg)
            else:
                self._broadcast_fn(msg)
        except Exception:
            pass

    async def deliberate(self, ticker: str, all_reports: dict) -> dict:
        await self._broadcast("agent_status", {
            "status": "working",
            "ticker": ticker,
            "message": "Committee deliberation starting...",
        })

        summary = self._summarize(all_reports)

        # Leo — bull case
        leo_prompt = (
            "Make the strongest bull case in 4-5 sentences. State upside price target. "
            "Output ONLY valid JSON:\n"
            '{"argument":"bull case text","upside_target":0.0,"conviction":7,"key_points":["3 points"]}'
        )
        leo_resp = await self.leo.call_llm(leo_prompt, f"Ticker: {ticker}\n\n{summary}")
        leo = self.leo._parse_json(leo_resp, {
            "argument": f"Strong momentum and value thesis for {ticker}.",
            "upside_target": all_reports.get("fundamental", {}).get("fair_value_eur", 0),
            "conviction": 7,
            "key_points": ["Technical momentum", "Fundamental value", "Catalyst pipeline"],
        })

        # Nina — bear case
        nina_prompt = (
            "Challenge the bull thesis directly. State downside in 4-5 sentences. "
            "Output ONLY valid JSON:\n"
            '{"argument":"bear case text","downside_target":0.0,"conviction":6,"key_points":["3 points"]}'
        )
        nina_input = f"Ticker: {ticker}\n\n{summary}\n\nBull Case (Leo): {leo.get('argument','')}"
        nina_resp = await self.nina.call_llm(nina_prompt, nina_input)
        nina = self.nina._parse_json(nina_resp, {
            "argument": f"Significant unpriced risks remain for {ticker}.",
            "downside_target": (all_reports.get("technical", {}).get("indicators", {})
                                .get("current_price", 0)) * 0.85,
            "conviction": 6,
            "key_points": ["Macro headwinds", "Valuation stretched", "Execution risk"],
        })

        leo_conv = int(float(leo.get("conviction") or 5))
        nina_conv = int(float(nina.get("conviction") or 5))
        high_uncertainty = abs(leo_conv - nina_conv) > 2

        risk = all_reports.get("risk", {})
        marcus_prompt = (
            "Deliver the final investment verdict. Output ONLY valid JSON:\n"
            '{"verdict":"INVEST|PASS|WAIT","position_size_eur":0.0,"entry":0.0,'
            '"stop_loss":0.0,"take_profit":0.0,"conviction":5,'
            '"reasoning":"3-4 sentence reasoning",'
            '"investment_principle":"one-line Dalio principle"}'
        )
        marcus_input = (
            f"Ticker: {ticker}\n\n{summary}\n\n"
            f"Leo (Bull, conviction {leo_conv}): {leo.get('argument','')}\n"
            f"Nina (Bear, conviction {nina_conv}): {nina.get('argument','')}\n"
            f"High Uncertainty: {high_uncertainty}\n\n"
            f"Viktor Risk: size={risk.get('position_size_eur',0)} EUR, "
            f"SL={risk.get('stop_loss',0)}, TP={risk.get('take_profit',0)}, "
            f"verdict={risk.get('risk_verdict','UNKNOWN')}\n\nDeliver final verdict."
        )
        marcus_resp = await self.marcus.call_llm(marcus_prompt, marcus_input)
        cur_price = (all_reports.get("technical", {}).get("indicators", {})
                     .get("current_price", 0))
        marcus = self.marcus._parse_json(marcus_resp, {
            "verdict": "WAIT",
            "position_size_eur": risk.get("position_size_eur", 0),
            "entry": cur_price,
            "stop_loss": risk.get("stop_loss", 0),
            "take_profit": risk.get("take_profit", 0),
            "conviction": 5,
            "reasoning": "Insufficient consensus to commit capital at this time.",
            "investment_principle": "When in doubt, stay out.",
        })

        # Apply HIGH_UNCERTAINTY discount
        if high_uncertainty and marcus.get("verdict") == "INVEST":
            orig = float(marcus.get("position_size_eur") or 0)
            marcus["position_size_eur"] = round(orig * 0.70, 2)

        # Marcus veto on CRITICAL risk
        if risk.get("risk_verdict") == "CRITICAL":
            marcus["verdict"] = "PASS"
            marcus["override_reason"] = "Viktor flagged CRITICAL risk — CIO veto applied"

        result = {
            "ticker": ticker,
            "verdict": marcus.get("verdict", "PASS"),
            "position_size_eur": marcus.get("position_size_eur", 0),
            "entry": marcus.get("entry", cur_price),
            "stop_loss": marcus.get("stop_loss", risk.get("stop_loss", 0)),
            "take_profit": marcus.get("take_profit", risk.get("take_profit", 0)),
            "conviction": marcus.get("conviction", 5),
            "reasoning": marcus.get("reasoning", ""),
            "investment_principle": marcus.get("investment_principle", ""),
            "high_uncertainty": high_uncertainty,
            "override_reason": marcus.get("override_reason"),
            "leo": leo,
            "nina": nina,
            "marcus": marcus,
        }

        await self._broadcast("agent_done", {
            "status": "done",
            "ticker": ticker,
            "verdict": result["verdict"],
            "conviction": result["conviction"],
            "report": result,
        })
        return result

    def _summarize(self, reports: dict) -> str:
        lines = []
        if m := reports.get("macro"):
            lines.append(
                f"MACRO (Elena): {m.get('market_regime','?')} regime. "
                f"Fed: {m.get('fed_stance','?')}. {m.get('summary','')}"
            )
        if t := reports.get("technical"):
            ind = t.get("indicators", {})
            lines.append(
                f"TECHNICAL (Kai): {t.get('signal','?')} conviction={t.get('conviction',0)}/10. "
                f"RSI={ind.get('rsi','?')}, trend={ind.get('trend','?')}. {t.get('thesis','')}"
            )
        if f := reports.get("fundamental"):
            lines.append(
                f"FUNDAMENTAL (Sophie): {f.get('signal','?')} conviction={f.get('conviction',0)}/10. "
                f"Fair value={f.get('fair_value_eur','?')} EUR ({f.get('upside_pct','?')}% upside). "
                f"{f.get('thesis','')}"
            )
        if r := reports.get("research"):
            lines.append(
                f"RESEARCH (Alex): {r.get('summary','')} "
                f"Catalysts: {', '.join(r.get('catalysts',[])[:3])}"
            )
        if s := reports.get("sentiment"):
            lines.append(
                f"SENTIMENT (Jordan): {s.get('crowd_sentiment','?')} crowd "
                f"conviction={s.get('crowd_conviction',0)}/10. {s.get('narrative','')}"
            )
        if v := reports.get("risk"):
            lines.append(
                f"RISK (Viktor): {v.get('risk_verdict','?')}. "
                f"Size={v.get('position_size_eur',0)} EUR. "
                f"SL={v.get('stop_loss',0)} TP={v.get('take_profit',0)} R/R={v.get('rr_ratio',0)}"
            )
        return "\n\n".join(lines)
