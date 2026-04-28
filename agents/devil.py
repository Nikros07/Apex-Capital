from typing import Callable, Optional

from agents.base import BaseAgent

PERSONALITY = (
    "You are Dante, the devil's advocate at Apex Capital. Your only job is to find the "
    "fatal flaw in whatever the committee just decided. You are not trying to be right — "
    "you are trying to make sure the fund is not wrong. You always start with: "
    "'With respect, here is what everyone is missing.'"
)


class DanteAgent(BaseAgent):
    def __init__(self, broadcast: Optional[Callable] = None):
        super().__init__("Dante", PERSONALITY, broadcast)

    async def challenge(self, ticker: str, verdict: dict, all_reports: dict) -> dict:
        await self._broadcast("agent_status", {
            "status": "working",
            "ticker": ticker,
            "message": "Finding the fatal flaw...",
        })

        risk_notes = all_reports.get("risk", {}).get("risk_notes", [])
        summary = (
            f"Committee Decision:\n"
            f"- Verdict: {verdict.get('verdict','INVEST')}\n"
            f"- Position: {verdict.get('position_size_eur',0)} EUR\n"
            f"- Entry: {verdict.get('entry',0)}\n"
            f"- Stop: {verdict.get('stop_loss',0)}\n"
            f"- Take Profit: {verdict.get('take_profit',0)}\n"
            f"- Conviction: {verdict.get('conviction',0)}/10\n\n"
            f"Leo's Bull: {verdict.get('leo',{}).get('argument','')}\n"
            f"Nina's Bear: {verdict.get('nina',{}).get('argument','')}\n"
            f"Marcus: {verdict.get('reasoning','')}\n\n"
            f"Risk Notes: {risk_notes}"
        )

        system_prompt = (
            "Find the one fatal flaw the committee missed. Output ONLY valid JSON:\n"
            '{"fatal_flaw":"Starting with: With respect, here is what everyone is missing:",'
            '"severity":"HIGH|MEDIUM|LOW",'
            '"invalidating_scenario":"specific scenario where this trade blows up",'
            '"probability_estimate":"e.g. 15-20%",'
            '"mitigation":"one protective action"}'
        )

        response = await self.call_llm(
            system_prompt,
            f"Ticker: {ticker}\n\n{summary}\n\nFind the fatal flaw."
        )

        default = {
            "fatal_flaw": (
                f"With respect, here is what everyone is missing: the liquidity risk "
                f"in {ticker} has not been adequately priced into the position sizing."
            ),
            "severity": "MEDIUM",
            "invalidating_scenario": (
                "A sudden liquidity crunch forces stop-loss execution at materially "
                "worse prices than modeled, resulting in a larger-than-expected drawdown."
            ),
            "probability_estimate": "10-15%",
            "mitigation": "Reduce position size 20% and widen stop to account for gap risk.",
        }
        result = self._parse_json(response, default)
        result["ticker"] = ticker
        result["advisory"] = True

        await self._broadcast("agent_done", {
            "status": "done",
            "ticker": ticker,
            "severity": result.get("severity", "MEDIUM"),
            "report": result,
            "message": "Devil's advocate analysis complete",
        })
        return result
